package com.dippie.moviercm.service.catalog;

import com.dippie.moviercm.dto.catalog.CatalogImportResponse;
import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.catalog.CatalogEpisode;
import com.dippie.moviercm.entity.catalog.CatalogMediaAsset;
import com.dippie.moviercm.entity.catalog.CatalogSeries;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.catalog.CatalogMediaAssetRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.persistence.EntityManager;
import jakarta.persistence.EntityManagerFactory;
import org.junit.jupiter.api.Test;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.WebApplicationType;
import com.dippie.moviercm.MovieRcmApplication;
import org.springframework.web.context.WebApplicationContext;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.test.web.servlet.MockMvc;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Set;
import java.util.function.Predicate;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasItem;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers.springSecurity;

class PreviewCatalogPersistenceTest {

    private static final String PACKAGE_ID = "pkg_preview_restart";
    private static final String SERIES_ID = "ser_rehearsal_01";
    private static final String EPISODE_1_ID = "ep_rehearsal_01_01";
    private static final String EPISODE_2_ID = "ep_rehearsal_01_02";
    private static final String VIDEO_1_ID = "asset_feature_01";
    private static final String VIDEO_2_ID = "asset_feature_02";
    private static final String AUDIO_ID = "asset_preview_private_audio";
    private static final Path TEST_DIRECTORY = createTestDirectory();
    private static final String TEST_DATABASE_URL = "jdbc:h2:file:"
            + TEST_DIRECTORY.resolve("preview_db").toString().replace('\\', '/')
            + ";DB_CLOSE_ON_EXIT=FALSE;MODE=PostgreSQL;NON_KEYWORDS=YEAR,USER";

    private CatalogImportService importService;
    private CatalogMediaAssetRepository catalogMediaAssetRepository;
    private MediaAssetRepository mediaAssetRepository;
    private EntityManagerFactory entityManagerFactory;
    private ObjectMapper objectMapper;
    private MockMvc mockMvc;

    @Test
    void catalogAndAnonymousMediaPolicySurviveSpringContextAndH2Reopen() throws Exception {
        // Own this context explicitly so it can close before reopening the H2 file.
        try (ConfigurableApplicationContext context = new SpringApplicationBuilder(MovieRcmApplication.class)
                .web(WebApplicationType.SERVLET).profiles("test").run(
                        "--server.port=0",
                        "--spring.datasource.url=" + TEST_DATABASE_URL,
                        "--spring.jpa.hibernate.ddl-auto=update",
                        "--app.catalog.snapshot-path=" + TEST_DIRECTORY.resolve("committed_catalog_snapshot.json"),
                        "--app.catalog.sync-token=")) {
        importService = context.getBean(CatalogImportService.class);
        catalogMediaAssetRepository = context.getBean(CatalogMediaAssetRepository.class);
        mediaAssetRepository = context.getBean(MediaAssetRepository.class);
        entityManagerFactory = context.getBean(EntityManagerFactory.class);
        objectMapper = context.getBean(ObjectMapper.class);
        mockMvc = MockMvcBuilders.webAppContextSetup((WebApplicationContext) context).apply(springSecurity()).build();
            JsonNode fixture = buildFixtureFromTrackedRehearsalCatalog();

            CatalogImportResponse firstImport = importService.importPackage(fixture);
            assertTrue(firstImport.isSuccess());
            assertEquals(PACKAGE_ID, firstImport.getPackageId());
            assertEquals(3, catalogMediaAssetRepository.count());
            assertEquals(3, mediaAssetRepository.count());

            CatalogImportResponse repeatedImport = importService.importPackage(fixture);
            assertTrue(repeatedImport.isSuccess());
            assertTrue(repeatedImport.getMessage().contains("Idempotent"));
            assertEquals(3, catalogMediaAssetRepository.count());
            assertEquals(3, mediaAssetRepository.count());

            try (EntityManager reopened = entityManagerFactory.createEntityManager()) {
                CatalogSeries series = reopened.find(CatalogSeries.class, SERIES_ID);
                CatalogEpisode episode1 = reopened.find(CatalogEpisode.class, EPISODE_1_ID);
                CatalogEpisode episode2 = reopened.find(CatalogEpisode.class, EPISODE_2_ID);
                CatalogMediaAsset video1 = reopened.find(CatalogMediaAsset.class, VIDEO_1_ID);
                CatalogMediaAsset video2 = reopened.find(CatalogMediaAsset.class, VIDEO_2_ID);
                CatalogMediaAsset audio = reopened.find(CatalogMediaAsset.class, AUDIO_ID);
                MediaAsset legacyVideo1 = reopened.find(MediaAsset.class, VIDEO_1_ID);
                MediaAsset legacyVideo2 = reopened.find(MediaAsset.class, VIDEO_2_ID);
                MediaAsset legacyAudio = reopened.find(MediaAsset.class, AUDIO_ID);

                assertNotNull(series);
                assertNotNull(episode1);
                assertNotNull(episode2);
                assertNotNull(video1);
                assertNotNull(video2);
                assertNotNull(audio);
                assertNotNull(legacyVideo1);
                assertNotNull(legacyVideo2);
                assertNotNull(legacyAudio);
                assertEquals("Biên Niên Sử Thần Tốc", series.getTitle());
                assertEquals(SERIES_ID, episode1.getSeriesId());
                assertEquals("sea_rehearsal_01_01", episode2.getSeasonId());
                assertEquals("synthetic/preview-episode-1.mp4", video1.getRelativePath());
                assertEquals("public", video1.getAccessPolicy());
                assertEquals("public", video2.getAccessPolicy());
                assertEquals("private", audio.getAccessPolicy());
                assertTrue(legacyVideo1.isPublic());
                assertTrue(legacyVideo2.isPublic());
                assertFalse(legacyAudio.isPublic());
            }

            mockMvc.perform(get("/api/catalog/search").param("q", "Biên Niên"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$[*].id", hasItem(SERIES_ID)))
                    .andExpect(jsonPath("$[*].type", hasItem("series")));

            mockMvc.perform(get("/api/catalog/series/{id}", SERIES_ID))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.series.id").value(SERIES_ID))
                    .andExpect(jsonPath("$.episodes[*].id", hasItem(EPISODE_1_ID)))
                    .andExpect(jsonPath("$.episodes[*].id", hasItem(EPISODE_2_ID)));

            mockMvc.perform(get("/api/catalog/episodes/{id}", EPISODE_1_ID))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.mediaAssets[*].id", contains(VIDEO_1_ID)));
            mockMvc.perform(get("/api/catalog/episodes/{id}", EPISODE_2_ID))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.mediaAssets[*].id", contains(VIDEO_2_ID)));

            mockMvc.perform(get("/api/movies/{id}/media-descriptor", EPISODE_1_ID))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.feature.assetId").value(VIDEO_1_ID))
                    .andExpect(jsonPath("$.feature.isPublic").value(true));
            mockMvc.perform(get("/api/movies/{id}/media-descriptor", EPISODE_2_ID))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.feature.assetId").value(VIDEO_2_ID));
            mockMvc.perform(get("/api/media/stream/{id}", AUDIO_ID))
                    .andExpect(status().isNotFound());

        }
        verifyPersistedRowsAfterContextClose();
    }

    private JsonNode buildFixtureFromTrackedRehearsalCatalog() throws IOException {
        ObjectNode fixture = (ObjectNode) objectMapper.readTree(findFixturePath().toFile());
        ((ObjectNode) fixture.get("package")).put("id", PACKAGE_ID);
        ((ObjectNode) fixture.get("package")).put("description", "Small synthetic restart test fixture");

        retain(fixture, "series", row -> SERIES_ID.equals(row.path("id").asText()));
        retain(fixture, "seasons", row -> "sea_rehearsal_01_01".equals(row.path("id").asText()));
        retain(fixture, "episodes", row -> Set.of(EPISODE_1_ID, EPISODE_2_ID).contains(row.path("id").asText()));
        retain(fixture, "characters", row -> Set.of("char_rehearsal_bao", "char_rehearsal_chi").contains(row.path("id").asText()));
        fixture.set("segments", objectMapper.createArrayNode());
        fixture.set("text_tracks", objectMapper.createArrayNode());
        fixture.set("scenes", objectMapper.createArrayNode());
        retain(fixture, "media_assets", row -> Set.of(VIDEO_1_ID, VIDEO_2_ID).contains(row.path("id").asText()));

        ObjectNode video1 = asset(fixture, VIDEO_1_ID);
        makeSyntheticLocalVideo(video1, "synthetic/preview-episode-1.mp4");
        clearSegmentReferences(video1);

        ObjectNode video2 = asset(fixture, VIDEO_2_ID);
        makeSyntheticLocalVideo(video2, "synthetic/preview-episode-2.mp4");
        video2.put("access_policy", "public");
        clearSegmentReferences(video2);

        ObjectNode audio = video1.deepCopy();
        audio.put("id", AUDIO_ID);
        audio.put("content_type", "audio");
        audio.put("role", "audio_description");
        audio.put("access_policy", "private");
        audio.put("size_bytes", 256);
        ((ObjectNode) audio.get("storage")).put("relative_path", "synthetic/preview-private-audio.mp3");
        ((ArrayNode) fixture.get("media_assets")).add(audio);
        return fixture;
    }

    private static void retain(ObjectNode fixture, String collection, Predicate<JsonNode> keep) {
        ArrayNode rows = (ArrayNode) fixture.get(collection);
        for (int i = rows.size() - 1; i >= 0; i--) {
            if (!keep.test(rows.get(i))) rows.remove(i);
        }
    }

    private static ObjectNode asset(ObjectNode fixture, String id) {
        for (JsonNode row : fixture.withArray("media_assets")) {
            if (id.equals(row.path("id").asText())) return (ObjectNode) row;
        }
        throw new IllegalStateException("Missing fixture asset " + id);
    }

    private static void makeSyntheticLocalVideo(ObjectNode asset, String relativePath) {
        asset.put("size_bytes", 1024);
        asset.put("duration_ms", 120_000);
        ObjectNode storage = (ObjectNode) asset.get("storage");
        storage.put("provider", "local");
        storage.put("storage_key", "animation_local");
        storage.put("relative_path", relativePath);
        storage.putNull("drive_folder_id");
        storage.putNull("drive_file_id");
    }

    private static void clearSegmentReferences(ObjectNode asset) {
        for (JsonNode coverage : asset.withArray("coverage")) {
            ((ObjectNode) coverage).putNull("segment_id");
        }
    }

    private static Path findFixturePath() {
        for (Path candidate : new Path[]{
                Path.of("docs/fixtures/rehearsal_catalog.json"),
                Path.of("../../docs/fixtures/rehearsal_catalog.json"),
                Path.of("../docs/fixtures/rehearsal_catalog.json")}) {
            if (Files.isRegularFile(candidate)) return candidate;
        }
        throw new IllegalStateException("Tracked rehearsal catalog fixture was not found");
    }

    private void verifyPersistedRowsAfterContextClose() throws SQLException {
        String reopenedUrl = TEST_DATABASE_URL + ";IFEXISTS=TRUE";
        try (Connection connection = DriverManager.getConnection(reopenedUrl, "sa", "")) {
            assertEquals(3, count(connection, "catalog_media_assets"));
            assertEquals(3, count(connection, "media_assets"));

            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT title FROM catalog_series WHERE id = ?")) {
                statement.setString(1, SERIES_ID);
                try (ResultSet rows = statement.executeQuery()) {
                    assertTrue(rows.next());
                    assertEquals("Biên Niên Sử Thần Tốc", rows.getString(1));
                }
            }

            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT access_policy, storage_provider, relative_path FROM catalog_media_assets WHERE id = ?")) {
                statement.setString(1, VIDEO_1_ID);
                try (ResultSet rows = statement.executeQuery()) {
                    assertTrue(rows.next());
                    assertEquals("public", rows.getString("access_policy"));
                    assertEquals("local", rows.getString("storage_provider"));
                    assertEquals("synthetic/preview-episode-1.mp4", rows.getString("relative_path"));
                }
            }

            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT series_id, season_id FROM catalog_episodes WHERE id = ?")) {
                statement.setString(1, EPISODE_1_ID);
                try (ResultSet rows = statement.executeQuery()) {
                    assertTrue(rows.next());
                    assertEquals(SERIES_ID, rows.getString("series_id"));
                    assertEquals("sea_rehearsal_01_01", rows.getString("season_id"));
                }
            }

            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT coverage_json FROM catalog_media_assets WHERE id = ?")) {
                statement.setString(1, VIDEO_1_ID);
                try (ResultSet rows = statement.executeQuery()) {
                    assertTrue(rows.next());
                    assertTrue(rows.getString("coverage_json").contains(EPISODE_1_ID));
                }
            }

            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT is_public, mime_type FROM media_assets WHERE id = ?")) {
                statement.setString(1, AUDIO_ID);
                try (ResultSet rows = statement.executeQuery()) {
                    assertTrue(rows.next());
                    assertFalse(rows.getBoolean("is_public"));
                    assertEquals("audio/mp4", rows.getString("mime_type"));
                }
            }
        }
    }

    private static int count(Connection connection, String table) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement("SELECT COUNT(*) FROM " + table);
             ResultSet rows = statement.executeQuery()) {
            assertTrue(rows.next());
            return rows.getInt(1);
        }
    }

    private static Path createTestDirectory() {
        try {
            Path target = Path.of("target").toAbsolutePath();
            Files.createDirectories(target);
            return Files.createTempDirectory(target, "preview-catalog-h2-");
        } catch (IOException e) {
            throw new ExceptionInInitializerError(e);
        }
    }
}
