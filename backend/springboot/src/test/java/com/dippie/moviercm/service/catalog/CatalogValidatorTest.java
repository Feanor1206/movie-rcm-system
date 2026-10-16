package com.dippie.moviercm.service.catalog;

import com.dippie.moviercm.dto.catalog.CatalogValidationError;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.File;
import java.io.IOException;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class CatalogValidatorTest {

    private CatalogValidator validator;
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        validator = new CatalogValidator();
        objectMapper = new ObjectMapper();
    }

    private JsonNode loadJson(String relativePath) throws IOException {
        File file = new File(relativePath);
        return objectMapper.readTree(file);
    }

    @Test
    @DisplayName("catalog.example.json passes validation cleanly with 0 errors")
    void testExampleCatalogPasses() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.example.json");
        List<CatalogValidationError> errors = validator.validate(data);
        assertTrue(errors.isEmpty(), "Example catalog should pass validation, but got errors: " + errors);
    }

    @Test
    @DisplayName("catalog.blank.json passes validation cleanly with 0 errors")
    void testBlankCatalogPasses() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.blank.json");
        List<CatalogValidationError> errors = validator.validate(data);
        assertTrue(errors.isEmpty(), "Blank catalog should pass validation, but got errors: " + errors);
    }

    @Test
    @DisplayName("Unknown root property is rejected with UNKNOWN_FIELD")
    void testUnknownRootPropertyRejected() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.blank.json");
        ((ObjectNode) data).put("malicious_extra_field", "evil_payload");

        List<CatalogValidationError> errors = validator.validate(data);
        assertFalse(errors.isEmpty());
        assertTrue(errors.stream().anyMatch(e -> "UNKNOWN_FIELD".equals(e.getCode()) && e.getPath().contains("malicious_extra_field")));
    }

    @Test
    @DisplayName("Missing required root collection is rejected")
    void testMissingRootCollectionRejected() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.blank.json");
        ((ObjectNode) data).remove("series");

        List<CatalogValidationError> errors = validator.validate(data);
        assertFalse(errors.isEmpty());
        assertTrue(errors.stream().anyMatch(e -> "MISSING_REQUIRED_KEY".equals(e.getCode()) && e.getPath().contains("series")));
    }

    @Test
    @DisplayName("Duplicate global ID across collections is rejected")
    void testDuplicateGlobalIdRejected() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.example.json");
        // Duplicate series id into characters collection
        ArrayNode chars = (ArrayNode) data.get("characters");
        ObjectNode dup = chars.addObject();
        dup.put("id", "ser_demo"); // Same ID as series
        dup.put("name", "Duplicate Guy");

        List<CatalogValidationError> errors = validator.validate(data);
        assertFalse(errors.isEmpty());
        assertTrue(errors.stream().anyMatch(e -> "DUPLICATE_ID".equals(e.getCode())));
    }

    @Test
    @DisplayName("Broken foreign reference is rejected")
    void testBrokenReferenceRejected() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.example.json");
        // Episode references non-existent series
        ArrayNode episodes = (ArrayNode) data.get("episodes");
        ((ObjectNode) episodes.get(0)).put("series_id", "non_existent_series_999");

        List<CatalogValidationError> errors = validator.validate(data);
        assertFalse(errors.isEmpty());
        assertTrue(errors.stream().anyMatch(e -> "BROKEN_REFERENCE".equals(e.getCode()) && e.getMessage().contains("non_existent_series_999")));
    }

    @Test
    @DisplayName("Path traversal in media storage relative_path is rejected")
    void testPathTraversalRejected() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.example.json");
        ArrayNode assets = (ArrayNode) data.get("media_assets");
        ObjectNode storage = (ObjectNode) assets.get(0).get("storage");
        storage.put("relative_path", "../../etc/passwd");

        List<CatalogValidationError> errors = validator.validate(data);
        assertFalse(errors.isEmpty());
        assertTrue(errors.stream().anyMatch(e -> "PATH_TRAVERSAL".equals(e.getCode())));
    }

    @Test
    @DisplayName("Invalid interval start >= end is rejected")
    void testInvalidIntervalRejected() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.example.json");
        ArrayNode scenes = (ArrayNode) data.get("scenes");
        ObjectNode scene = (ObjectNode) scenes.get(0);
        scene.put("start_ms", 10000);
        scene.put("end_ms", 5000); // end < start

        List<CatalogValidationError> errors = validator.validate(data);
        assertFalse(errors.isEmpty());
        assertTrue(errors.stream().anyMatch(e -> "INVALID_INTERVAL".equals(e.getCode())));
    }

    @Test
    @DisplayName("Unsorted cues in text_track are rejected")
    void testUnsortedCuesRejected() throws IOException {
        JsonNode data = loadJson("../../docs/contracts/animation-catalog-v1/catalog.example.json");
        ArrayNode tracks = (ArrayNode) data.get("text_tracks");
        ArrayNode cues = (ArrayNode) tracks.get(0).get("cues");
        if (cues.size() >= 2) {
            // Invert start_ms of cue 0 and 1
            ((ObjectNode) cues.get(0)).put("start_ms", 50000);
            ((ObjectNode) cues.get(1)).put("start_ms", 10000);

            List<CatalogValidationError> errors = validator.validate(data);
            assertFalse(errors.isEmpty());
            assertTrue(errors.stream().anyMatch(e -> "UNSORTED_CUES".equals(e.getCode())));
        }
    }
}
