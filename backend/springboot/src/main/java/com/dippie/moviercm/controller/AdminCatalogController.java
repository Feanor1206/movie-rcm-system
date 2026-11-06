package com.dippie.moviercm.controller;

import com.dippie.moviercm.dto.catalog.CatalogImportResponse;
import com.dippie.moviercm.dto.catalog.CatalogValidationResult;
import com.dippie.moviercm.entity.catalog.CatalogPackage;
import com.dippie.moviercm.entity.catalog.CatalogSnapshot;
import com.dippie.moviercm.repository.catalog.CatalogPackageRepository;
import com.dippie.moviercm.repository.catalog.CatalogSnapshotRepository;
import com.dippie.moviercm.service.catalog.CatalogImportService;
import com.dippie.moviercm.service.catalog.CatalogQueryService;
import com.dippie.moviercm.service.catalog.CatalogSyncWorker;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/admin/catalog")
@CrossOrigin(origins = "*", allowedHeaders = "*")
@PreAuthorize("hasRole('ADMIN')")
public class AdminCatalogController {

    private final CatalogImportService importService;
    private final CatalogPackageRepository packageRepository;
    private final CatalogSnapshotRepository snapshotRepository;
    private final CatalogQueryService queryService;
    private final CatalogSyncWorker syncWorker;

    @Autowired
    public AdminCatalogController(
            CatalogImportService importService,
            CatalogPackageRepository packageRepository,
            CatalogSnapshotRepository snapshotRepository,
            CatalogQueryService queryService,
            @Autowired(required = false) CatalogSyncWorker syncWorker) {
        this.importService = importService;
        this.packageRepository = packageRepository;
        this.snapshotRepository = snapshotRepository;
        this.queryService = queryService;
        this.syncWorker = syncWorker;
    }

    @PostMapping("/validate")
    public ResponseEntity<CatalogValidationResult> validatePackage(@RequestBody JsonNode payload) {
        CatalogValidationResult result = importService.validateAndPreview(payload);
        if (!result.isValid()) {
            return ResponseEntity.badRequest().body(result);
        }
        return ResponseEntity.ok(result);
    }

    @PostMapping("/import")
    public ResponseEntity<CatalogImportResponse> importPackage(@RequestBody JsonNode payload) {
        CatalogImportResponse response = importService.importPackage(payload);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/history")
    public ResponseEntity<List<CatalogPackage>> getImportHistory() {
        return ResponseEntity.ok(packageRepository.findAll());
    }

    @GetMapping("/snapshots")
    public ResponseEntity<List<CatalogSnapshot>> getSnapshots() {
        return ResponseEntity.ok(snapshotRepository.findAll());
    }

    @PostMapping("/snapshots/{id}/retry")
    public ResponseEntity<CatalogSnapshot> retrySnapshot(@PathVariable String id) {
        if (syncWorker != null) {
            CatalogSnapshot retried = syncWorker.retrySnapshot(id);
            return ResponseEntity.ok(retried);
        }
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).build();
    }

    @GetMapping("/export")
    public ResponseEntity<Map<String, Object>> exportCatalog() {
        return ResponseEntity.ok(queryService.exportEligibleSnapshot(true, true));
    }
}
