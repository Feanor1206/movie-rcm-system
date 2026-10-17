package com.dippie.moviercm.service.catalog;

import com.dippie.moviercm.entity.catalog.CatalogSnapshot;
import com.dippie.moviercm.repository.catalog.CatalogSnapshotRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Background outbox worker responsible for generating full committed eligible catalog snapshots,
 * writing them atomically to configured disk paths, and synchronizing with FastAPI retrieval index.
 * Handles retries, server restart recovery, disk failure propagation, and stale generation protection (G1).
 */
@Component
public class CatalogSyncWorker {

    private static final Logger logger = LoggerFactory.getLogger(CatalogSyncWorker.class);
    private static final ObjectMapper objectMapper = new ObjectMapper();

    private final CatalogSnapshotRepository snapshotRepository;
    private final CatalogQueryService queryService;

    @Value("${app.catalog.sync-url:${APP_CATALOG_SYNC_URL:http://localhost:8000/api/index/sync}}")
    private String syncUrl;

    @Value("${app.catalog.sync-token:${CATALOG_SYNC_TOKEN:${FASTAPI_SYNC_SECRET:}}}")
    private String syncToken;

    @Value("${app.catalog.snapshot-path:${APP_CATALOG_SNAPSHOT_PATH:./data/catalog/committed_catalog_snapshot.json}}")
    private String snapshotPath;

    @Value("${app.catalog.sync-timeout-seconds:${APP_CATALOG_SYNC_TIMEOUT_SECONDS:60}}")
    private int syncTimeoutSeconds = 60;

    private final AtomicBoolean isProcessing = new AtomicBoolean(false);

    @Autowired
    public CatalogSyncWorker(CatalogSnapshotRepository snapshotRepository, CatalogQueryService queryService) {
        this.snapshotRepository = snapshotRepository;
        this.queryService = queryService;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void onStartup() {
        logger.info("[CatalogSyncWorker] Starting recovery check on application startup...");
        try {
            // Recover any crashed SYNCING snapshots back to PENDING (G1)
            List<CatalogSnapshot> abandoned = snapshotRepository.findByStatusInOrderBySnapshotVersionAsc(List.of("SYNCING"));
            for (CatalogSnapshot s : abandoned) {
                logger.info("[CatalogSyncWorker] Phục hồi snapshot bị gián đoạn sau restart: {} (gen {})", s.getId(), s.getSnapshotVersion());
                s.setStatus("PENDING");
                s.setErrorMessage("Phục hồi sau khi hệ thống khởi động lại");
                s.setUpdatedAt(LocalDateTime.now());
                snapshotRepository.save(s);
            }
        } catch (Exception e) {
            logger.warn("[CatalogSyncWorker] Lỗi phục hồi snapshot gián đoạn: {}", e.getMessage());
        }
        processPendingSnapshots();
    }

    @Scheduled(fixedDelay = 5000)
    public void scheduledPoll() {
        processPendingSnapshots();
    }

    public synchronized void processPendingSnapshots() {
        if (!isProcessing.compareAndSet(false, true)) {
            return;
        }
        try {
            List<CatalogSnapshot> pendingSnapshots = snapshotRepository.findByStatusInOrderBySnapshotVersionAsc(
                    List.of("PENDING", "SYNC_FAILED")
            );

            for (CatalogSnapshot snapshot : pendingSnapshots) {
                if (snapshot.getRetryCount() != null && snapshot.getRetryCount() >= 5) {
                    continue; // Skip exhausted retries until manual operator intervention (G1)
                }
                processSingleSnapshot(snapshot);
            }
        } catch (Exception e) {
            logger.error("[CatalogSyncWorker] Lỗi khi xử lý hàng đợi outbox snapshots: {}", e.getMessage(), e);
        } finally {
            isProcessing.set(false);
        }
    }

    public CatalogSnapshot retrySnapshot(String snapshotId) {
        CatalogSnapshot snapshot = snapshotRepository.findById(snapshotId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy snapshot với ID: " + snapshotId));
        snapshot.setStatus("PENDING");
        snapshot.setRetryCount(0);
        snapshot.setErrorMessage(null);
        snapshot.setUpdatedAt(LocalDateTime.now());
        CatalogSnapshot saved = snapshotRepository.save(snapshot);
        processPendingSnapshots();
        return saved;
    }

    private void processSingleSnapshot(CatalogSnapshot snapshot) {
        try {
            snapshot.setStatus("SYNCING");
            snapshot.setUpdatedAt(LocalDateTime.now());
            snapshotRepository.save(snapshot);

            // 1. Generate full committed eligible catalog JSON from database (self-contained)
            Map<String, Object> fullEligibleCatalog = queryService.exportEligibleSnapshot(false, false);
            String catalogJson = objectMapper.writeValueAsString(fullEligibleCatalog);
            String fullCatalogHash = CatalogImportService.computeSha256(catalogJson);

            // 2. Write full committed catalog snapshot to configured disk path atomically (G1)
            try {
                writeSnapshotToDisk(catalogJson);
            } catch (Exception diskEx) {
                logger.error("[CatalogSyncWorker] Thất bại khi ghi snapshot ra đĩa: {}", diskEx.getMessage(), diskEx);
                int retry = snapshot.getRetryCount() != null ? snapshot.getRetryCount() + 1 : 1;
                snapshot.setRetryCount(retry);
                snapshot.setStatus("SYNC_FAILED");
                snapshot.setErrorMessage("Lỗi ghi snapshot ra đĩa: " + diskEx.getMessage());
                snapshot.setUpdatedAt(LocalDateTime.now());
                snapshotRepository.save(snapshot);
                return;
            }

            // 3. Dispatch to FastAPI if sync token is configured
            if (syncToken == null || syncToken.trim().isEmpty()) {
                logger.warn("[CatalogSyncWorker] Không cấu hình syncToken ngoài Git; snapshot đã ghi ra đĩa tại {}. Đánh dấu BLOCKED (chưa có index ack).", snapshotPath);
                snapshot.setStatus("BLOCKED");
                snapshot.setContentHash(fullCatalogHash);
                snapshot.setUpdatedAt(LocalDateTime.now());
                snapshot.setErrorMessage("Chưa cấu hình syncToken (CATALOG_SYNC_TOKEN) ngoài Git; snapshot artifact đã ghi đĩa nhưng chưa đồng bộ AI index.");
                snapshotRepository.save(snapshot);
                return;
            }

            HttpClient client = HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(3))
                    .build();

            Map<String, Object> payload = Map.of(
                    "generation", snapshot.getSnapshotVersion(),
                    "content_hash", fullCatalogHash,
                    "catalog", fullEligibleCatalog
            );

            String requestBody = objectMapper.writeValueAsString(payload);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(syncUrl))
                    .header("Content-Type", "application/json")
                    .header("X-Service-Token", syncToken.trim())
                    .POST(HttpRequest.BodyPublishers.ofString(requestBody, StandardCharsets.UTF_8))
                    .timeout(Duration.ofSeconds(syncTimeoutSeconds))
                    .build();

            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            int statusCode = response.statusCode();
            String responseBody = response.body() != null ? response.body() : "";

            Map<String, Object> respMap = null;
            try {
                respMap = objectMapper.readValue(responseBody, Map.class);
            } catch (Exception ignored) {}

            String ackStatus = respMap != null ? (String) respMap.get("status") : null;
            Number ackGen = respMap != null ? (Number) respMap.get("generation") : null;
            String ackHash = respMap != null ? (String) respMap.get("content_hash") : null;

            if (statusCode == 409 || "SKIPPED".equalsIgnoreCase(ackStatus) || responseBody.contains("SKIPPED")) {
                snapshot.setStatus("STALE_SKIPPED");
                snapshot.setCompletedAt(LocalDateTime.now());
                snapshot.setErrorMessage("Generation cũ bị từ chối/bỏ qua bởi FastAPI: " + responseBody);
                snapshotRepository.save(snapshot);
                logger.warn("[CatalogSyncWorker] Snapshot generation {} bị bỏ qua do stale: {}", snapshot.getSnapshotVersion(), responseBody);
            } else if (statusCode >= 200 && statusCode < 300) {
                boolean statusOk = "success".equalsIgnoreCase(ackStatus) || "OK".equalsIgnoreCase(ackStatus)
                        || "SYNCED".equalsIgnoreCase(ackStatus) || "UNCHANGED".equalsIgnoreCase(ackStatus);
                boolean genMatches = ackGen != null && ackGen.longValue() == snapshot.getSnapshotVersion();
                boolean hashMatches = ackHash != null && ackHash.equalsIgnoreCase(fullCatalogHash);

                if (statusOk && genMatches && hashMatches) {
                    snapshot.setStatus("READY");
                    snapshot.setContentHash(fullCatalogHash);
                    snapshot.setCompletedAt(LocalDateTime.now());
                    snapshot.setErrorMessage(null);
                    snapshotRepository.save(snapshot);
                    logger.info("[CatalogSyncWorker] Đồng bộ FastAPI thành công cho snapshot generation {}", snapshot.getSnapshotVersion());
                } else {
                    int retry = snapshot.getRetryCount() != null ? snapshot.getRetryCount() + 1 : 1;
                    snapshot.setRetryCount(retry);
                    snapshot.setStatus("SYNC_FAILED");
                    snapshot.setErrorMessage(String.format("FastAPI ACK không khớp: status=%s, gen=%s (expected %s), hash=%s (expected %s)",
                            ackStatus, ackGen, snapshot.getSnapshotVersion(), ackHash, fullCatalogHash));
                    snapshotRepository.save(snapshot);
                    logger.warn("[CatalogSyncWorker] FastAPI ACK không khớp cho generation {}", snapshot.getSnapshotVersion());
                }
            } else {
                int retry = snapshot.getRetryCount() != null ? snapshot.getRetryCount() + 1 : 1;
                snapshot.setRetryCount(retry);
                snapshot.setStatus("SYNC_FAILED");
                snapshot.setErrorMessage("FastAPI HTTP " + statusCode + ": " + responseBody);
                snapshotRepository.save(snapshot);
                logger.warn("[CatalogSyncWorker] FastAPI sync thất bại (HTTP {}): {}", statusCode, responseBody);
            }
        } catch (Exception e) {
            int retry = snapshot.getRetryCount() != null ? snapshot.getRetryCount() + 1 : 1;
            snapshot.setRetryCount(retry);
            snapshot.setStatus("SYNC_FAILED");
            snapshot.setErrorMessage("Lỗi kết nối FastAPI: " + e.getMessage());
            snapshot.setUpdatedAt(LocalDateTime.now());
            snapshotRepository.save(snapshot);
            logger.warn("[CatalogSyncWorker] Không thể kết nối FastAPI cho generation {} (sẽ retry lần {}): {}",
                    snapshot.getSnapshotVersion(), retry, e.getMessage());
        }
    }

    private void writeSnapshotToDisk(String catalogJson) throws IOException {
        Path targetPath = Path.of(snapshotPath).toAbsolutePath().normalize();
        if (targetPath.getParent() != null) {
            Files.createDirectories(targetPath.getParent());
        }

        Path tempFile = Files.createTempFile(targetPath.getParent(), "snapshot-atomic-", ".tmp");
        try {
            Files.writeString(tempFile, catalogJson, StandardCharsets.UTF_8);
            try {
                Files.move(tempFile, targetPath, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
            } catch (Exception atomicEx) {
                Files.move(tempFile, targetPath, StandardCopyOption.REPLACE_EXISTING);
            }
            logger.info("[CatalogSyncWorker] Đã ghi snapshot toàn catalog cam kết ra đĩa tại: {}", targetPath);
        } finally {
            try {
                if (Files.exists(tempFile)) {
                    Files.deleteIfExists(tempFile);
                }
            } catch (Exception ignored) {}
        }
    }
}
