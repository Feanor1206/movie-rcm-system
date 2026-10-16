package com.dippie.moviercm.service.catalog;

import com.dippie.moviercm.dto.catalog.CatalogImportResponse;
import com.dippie.moviercm.dto.catalog.CatalogValidationResult;
import com.dippie.moviercm.entity.catalog.CatalogEpisode;
import com.dippie.moviercm.entity.catalog.CatalogPackage;
import com.dippie.moviercm.entity.catalog.CatalogSeries;
import com.dippie.moviercm.exception.CatalogConflictException;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.repository.catalog.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import java.io.File;
import java.io.IOException;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@ActiveProfiles("test")
class CatalogImportServiceTest {

    @Autowired
    private CatalogImportService importService;

    @Autowired
    private CatalogPackageRepository packageRepository;

    @Autowired
    private CatalogSeriesRepository seriesRepository;

    @Autowired
    private CatalogEpisodeRepository episodeRepository;

    @Autowired
    private CatalogMediaAssetRepository mediaAssetRepository;

    @Autowired
    private MediaAssetRepository legacyMediaAssetRepository;

    @Autowired
    private MovieRepository legacyMovieRepository;

    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();
    }

    private JsonNode loadJson(String relativePath) throws IOException {
        File file = new File(relativePath);
        return objectMapper.readTree(file);
    }

    @Test
    @DisplayName("Dry-run preview calculates toCreate correctly without mutating DB")
    void testDryRunPreview() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.example.json");
        CatalogValidationResult preview = importService.validateAndPreview(data);

        assertTrue(preview.isValid());
        assertEquals("pkg_demo", preview.getPackageId());
        assertEquals(1, preview.getRevision());
        assertTrue(preview.getToCreate() > 0);
        assertEquals(0, preview.getConflicts());
    }

    @Test
    @Transactional
    @DisplayName("Import package commits entities and media assets atomically")
    void testImportCommitSuccess() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.example.json");
        CatalogImportResponse response = importService.importPackage(data);

        assertTrue(response.isSuccess());
        assertEquals("pkg_demo", response.getPackageId());
        assertTrue("PENDING".equals(response.getIndexStatus()) || "READY".equals(response.getIndexStatus()) || "SYNC_PENDING".equals(response.getIndexStatus()));
        assertTrue(response.getCounts().get("episodes") >= 1);

        // Verify database persistence
        Optional<CatalogPackage> pkg = packageRepository.findById("pkg_demo");
        assertTrue(pkg.isPresent());
        assertEquals("COMMITTED", pkg.get().getStatus());

        Optional<CatalogSeries> series = seriesRepository.findById("ser_demo");
        assertTrue(series.isPresent());

        Optional<CatalogEpisode> ep = episodeRepository.findById("ep_demo_001");
        assertTrue(ep.isPresent());

        // Verify legacy streaming media sync
        assertTrue(legacyMediaAssetRepository.existsById("asset_demo_001"));
        assertTrue(legacyMovieRepository.existsById("ep_demo_001") || legacyMovieRepository.existsById("ser_demo"));
    }

    @Test
    @Transactional
    @DisplayName("Idempotent re-import with identical revision and content succeeds with unchanged status")
    void testIdempotentReimport() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.example.json");
        CatalogImportResponse resp1 = importService.importPackage(data);
        assertTrue(resp1.isSuccess());

        CatalogImportResponse resp2 = importService.importPackage(data);
        assertTrue(resp2.isSuccess());
        assertTrue(resp2.getMessage().contains("Idempotent"));
    }

    @Test
    @Transactional
    @DisplayName("Lower revision is rejected with CatalogConflictException")
    void testLowerRevisionRejected() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.example.json");
        // Set higher revision 5
        ((ObjectNode) data.get("package")).put("revision", 5);
        importService.importPackage(data);

        // Now attempt to import with revision 4 (lower)
        ((ObjectNode) data.get("package")).put("revision", 4);
        assertThrows(CatalogConflictException.class, () -> importService.importPackage(data));
    }

    @Test
    @Transactional
    @DisplayName("Same revision with modified content is rejected as conflict")
    void testSameRevisionDifferentContentConflict() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.example.json");
        ((ObjectNode) data.get("package")).put("revision", 2);
        importService.importPackage(data);

        // Modify content under same revision 2
        ArrayNode seriesArr = (ArrayNode) data.get("series");
        ((ObjectNode) seriesArr.get(0)).put("synopsis", "Completely altered synopsis text causing hash mismatch");

        assertThrows(CatalogConflictException.class, () -> importService.importPackage(data));
    }

    @Test
    @Transactional
    @DisplayName("Higher revision updates package and records cleanly")
    void testHigherRevisionUpdate() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.example.json");
        ((ObjectNode) data.get("package")).put("revision", 1);
        importService.importPackage(data);

        // Bump package revision to 2 and update entity title with bumped entity revision
        ((ObjectNode) data.get("package")).put("revision", 2);
        ArrayNode seriesArr = (ArrayNode) data.get("series");
        ((ObjectNode) seriesArr.get(0)).put("title", "Shin Cậu Bé Bút Chì (Bản Cập Nhật 2026)");
        ((ObjectNode) seriesArr.get(0).get("record")).put("revision", 2);

        CatalogImportResponse updateResp = importService.importPackage(data);
        assertTrue(updateResp.isSuccess());
        assertEquals(2, updateResp.getRevision());

        CatalogSeries updatedSeries = seriesRepository.findById("ser_demo").orElseThrow();
        assertEquals("Shin Cậu Bé Bút Chì (Bản Cập Nhật 2026)", updatedSeries.getTitle());
    }
}
