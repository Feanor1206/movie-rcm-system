package com.dippie.moviercm.service.catalog;

import com.dippie.moviercm.entity.catalog.CatalogSnapshot;
import com.dippie.moviercm.repository.catalog.CatalogSnapshotRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;

import java.net.InetSocketAddress;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Function;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.Mockito.*;

class CatalogSyncWorkerAsyncTest {
    private final ObjectMapper mapper = new ObjectMapper();
    private final AtomicInteger requests = new AtomicInteger();
    private HttpServer server;
    private CatalogSyncWorker worker;
    private CatalogSnapshot snapshot;
    private volatile Function<Map<String, Object>, Map<String, Object>> acknowledgement;
    private volatile int httpStatus;

    @TempDir
    Path directory;

    @BeforeEach
    void setUp() throws Exception {
        CatalogSnapshotRepository repository = mock(CatalogSnapshotRepository.class);
        CatalogQueryService query = mock(CatalogQueryService.class);
        snapshot = new CatalogSnapshot("snapshot-1", 7L, "initial", 0, "PENDING");
        snapshot.setRetryCount(2);
        when(repository.save(any(CatalogSnapshot.class))).thenAnswer(invocation -> invocation.getArgument(0));
        when(repository.findByStatusInOrderBySnapshotVersionAsc(anyList())).thenAnswer(invocation ->
                List.of("PENDING", "SYNC_FAILED").contains(snapshot.getStatus()) ? List.of(snapshot) : List.of());
        when(query.exportEligibleSnapshot(false, false)).thenReturn(Map.of("series", List.of()));
        httpStatus = 202;
        acknowledgement = request -> Map.of("status", "BUILDING", "generation", request.get("generation"),
                "content_hash", request.get("content_hash"), "index_ready", false);
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/api/index/sync", exchange -> {
            try {
                assertEquals("test-sync-token", exchange.getRequestHeaders().getFirst("X-Service-Token"));
                Map<String, Object> request = mapper.readValue(exchange.getRequestBody(), Map.class);
                requests.incrementAndGet();
                byte[] body = mapper.writeValueAsBytes(acknowledgement.apply(request));
                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.sendResponseHeaders(httpStatus, body.length);
                exchange.getResponseBody().write(body);
            } finally {
                exchange.close();
            }
        });
        server.start();
        worker = new CatalogSyncWorker(repository, query);
        ReflectionTestUtils.setField(worker, "syncUrl", "http://127.0.0.1:" + server.getAddress().getPort() + "/api/index/sync");
        ReflectionTestUtils.setField(worker, "syncToken", "test-sync-token");
        ReflectionTestUtils.setField(worker, "snapshotPath", directory.resolve("catalog.json").toString());
        ReflectionTestUtils.setField(worker, "syncTimeoutSeconds", 2);
    }

    @AfterEach
    void tearDown() {
        if (server != null) server.stop(0);
    }

    @Test
    void buildingPollsPreserveRetryBudgetUntilDurableAcknowledgement() throws Exception {
        for (int poll = 0; poll < 7; poll++) {
            worker.processPendingSnapshots();
            assertEquals("PENDING", snapshot.getStatus());
            assertEquals(2, snapshot.getRetryCount());
            assertNull(snapshot.getCompletedAt());
        }
        assertEquals(7, requests.get());
        assertEquals(mapper.readTree("{\"series\":[]}"), mapper.readTree(Files.readString(directory.resolve("catalog.json"))));
        httpStatus = 200;
        acknowledgement = request -> Map.of("status", "UNCHANGED", "generation", request.get("generation"),
                "content_hash", request.get("content_hash"), "index_ready", true);
        worker.processPendingSnapshots();
        assertEquals("READY", snapshot.getStatus());
        assertEquals(2, snapshot.getRetryCount());
        assertNotNull(snapshot.getCompletedAt());
        assertEquals(8, requests.get());
    }

    @Test
    void mismatchedBuildingGenerationConsumesFailureBudget() {
        acknowledgement = request -> Map.of("status", "BUILDING", "generation", 8,
                "content_hash", request.get("content_hash"), "index_ready", false);
        worker.processPendingSnapshots();
        assertEquals("SYNC_FAILED", snapshot.getStatus());
        assertEquals(3, snapshot.getRetryCount());
        assertNull(snapshot.getCompletedAt());
    }

    @Test
    void mismatchedBuildingHashConsumesFailureBudget() {
        acknowledgement = request -> Map.of("status", "BUILDING", "generation", request.get("generation"),
                "content_hash", "wrong-hash", "index_ready", false);
        worker.processPendingSnapshots();
        assertEquals("SYNC_FAILED", snapshot.getStatus());
        assertEquals(3, snapshot.getRetryCount());
        assertNull(snapshot.getCompletedAt());
    }

    @Test
    void acceptedWithoutDurableCompletionNeverBecomesReady() {
        acknowledgement = request -> Map.of("status", "success", "generation", request.get("generation"),
                "content_hash", request.get("content_hash"), "index_ready", false);
        worker.processPendingSnapshots();
        assertEquals("SYNC_FAILED", snapshot.getStatus());
        assertEquals(3, snapshot.getRetryCount());
        assertNull(snapshot.getCompletedAt());
    }

    @Test
    void malformedBuildingAcknowledgementFailsSafely() {
        acknowledgement = request -> new HashMap<>();
        worker.processPendingSnapshots();
        assertEquals("SYNC_FAILED", snapshot.getStatus());
        assertEquals(3, snapshot.getRetryCount());
        assertNull(snapshot.getCompletedAt());
    }

    @Test
    void fractionalGenerationCannotAcknowledgeIntegerSnapshot() {
        acknowledgement = request -> Map.of("status", "BUILDING", "generation", 7.5,
                "content_hash", request.get("content_hash"), "index_ready", false);
        worker.processPendingSnapshots();
        assertEquals("SYNC_FAILED", snapshot.getStatus());
        assertEquals(3, snapshot.getRetryCount());
        assertNull(snapshot.getCompletedAt());
    }

    @Test
    void successfulStatusWithoutReadyIndexDoesNotAcknowledgeCompletion() {
        httpStatus = 200;
        acknowledgement = request -> Map.of("status", "success", "generation", request.get("generation"),
                "content_hash", request.get("content_hash"), "index_ready", false);
        worker.processPendingSnapshots();
        assertEquals("SYNC_FAILED", snapshot.getStatus());
        assertEquals(3, snapshot.getRetryCount());
        assertNull(snapshot.getCompletedAt());
    }
}
