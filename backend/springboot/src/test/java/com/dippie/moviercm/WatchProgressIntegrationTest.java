package com.dippie.moviercm;

import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.Role;
import com.dippie.moviercm.entity.User;
import com.dippie.moviercm.entity.WatchProgress;
import com.dippie.moviercm.entity.catalog.CatalogEpisode;
import com.dippie.moviercm.entity.catalog.CatalogMediaAsset;
import com.dippie.moviercm.entity.catalog.CatalogSeason;
import com.dippie.moviercm.entity.catalog.CatalogSeries;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.UserRepository;
import com.dippie.moviercm.repository.WatchProgressRepository;
import com.dippie.moviercm.repository.catalog.CatalogEpisodeRepository;
import com.dippie.moviercm.repository.catalog.CatalogMediaAssetRepository;
import com.dippie.moviercm.repository.catalog.CatalogSeasonRepository;
import com.dippie.moviercm.repository.catalog.CatalogSeriesRepository;
import com.dippie.moviercm.security.UserDetailsImpl;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class WatchProgressIntegrationTest {

    private static final String SERIES_ID = "wp-series";
    private static final String SEASON_ID = "wp-season";
    private static final String EPISODE_ID = "wp-episode";
    private static final String ASSET_ID = "wp-video";

    @Autowired private MockMvc mockMvc;
    @Autowired private ObjectMapper objectMapper;
    @Autowired private WatchProgressRepository progressRepository;
    @Autowired private UserRepository userRepository;
    @Autowired private CatalogSeriesRepository seriesRepository;
    @Autowired private CatalogSeasonRepository seasonRepository;
    @Autowired private CatalogEpisodeRepository episodeRepository;
    @Autowired private CatalogMediaAssetRepository catalogAssetRepository;
    @Autowired private MediaAssetRepository playableAssetRepository;
    @Autowired private EntityManager entityManager;

    private UserDetailsImpl user;

    @BeforeEach
    void setUp() {
        progressRepository.deleteAll();
        for (MediaAsset asset : playableAssetRepository.findAll()) {
            if (asset.getId().startsWith("wp-")) playableAssetRepository.deleteById(asset.getId());
        }
        for (CatalogMediaAsset asset : catalogAssetRepository.findAll()) {
            if (asset.getId().startsWith("wp-")) catalogAssetRepository.deleteById(asset.getId());
        }
        for (CatalogEpisode episode : episodeRepository.findAll()) {
            if (episode.getId().startsWith("wp-")) episodeRepository.deleteById(episode.getId());
        }
        seasonRepository.deleteById(SEASON_ID);
        seriesRepository.deleteById(SERIES_ID);

        User account = userRepository.findByUsername("watch_progress_test_user").orElseGet(() ->
                userRepository.save(User.builder()
                        .username("watch_progress_test_user")
                        .email("watch_progress_test_user@example.test")
                        .password("unused-test-password")
                        .fullName("Watch Progress Test")
                        .role(Role.ROLE_USER)
                        .build()));
        user = principal(account);

        CatalogSeries series = new CatalogSeries();
        series.setId(SERIES_ID);
        series.setTitle("Canonical Series");
        series.setRecordJson("{\"status\":\"ready\"}");
        seriesRepository.save(series);

        CatalogSeason season = new CatalogSeason();
        season.setId(SEASON_ID);
        season.setSeriesId(SERIES_ID);
        season.setNumber(1);
        season.setTitle("Canonical Season");
        season.setRecordJson("{\"status\":\"ready\"}");
        seasonRepository.save(season);

        addEpisode(EPISODE_ID, ASSET_ID, 1_000_000L, "full_episode", "video", "feature", "public", true, true, SEASON_ID);
    }

    @Test
    void endpointsRequireAuthentication() throws Exception {
        mockMvc.perform(get("/api/users/watch-progress"))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/users/watch-progress/" + EPISODE_ID))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(put("/api/users/watch-progress/" + EPISODE_ID)
                        .contentType(MediaType.APPLICATION_JSON).content(body(ASSET_ID, 100L, -1L)))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(delete("/api/users/watch-progress/" + EPISODE_ID))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void putUsesCanonicalMetadataAndNeverAcceptsClientDuration() throws Exception {
        mockMvc.perform(put("/api/users/watch-progress/" + EPISODE_ID)
                        .with(as(user))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(bodyWithDuration(ASSET_ID, 950_000L, -1L, 1L)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.seriesTitle").value("Canonical Series"))
                .andExpect(jsonPath("$.data.seasonTitle").value("Canonical Season"))
                .andExpect(jsonPath("$.data.episodeTitle").value("Canonical Episode"))
                .andExpect(jsonPath("$.data.durationMs").value(1_000_000))
                .andExpect(jsonPath("$.data.positionMs").value(950_000))
                .andExpect(jsonPath("$.data.completed").value(true))
                .andExpect(jsonPath("$.data.version").value(0))
                .andExpect(jsonPath("$.data.userId").doesNotExist());
    }

    @Test
    void twoWritesFromTheSameVersionConflictAndCurrentVersionAllowsBackwardSeek() throws Exception {
        mockMvc.perform(put("/api/users/watch-progress/" + EPISODE_ID)
                        .with(as(user)).contentType(MediaType.APPLICATION_JSON).content(body(ASSET_ID, 800_000L, -1L)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.version").value(0));

        mockMvc.perform(put("/api/users/watch-progress/" + EPISODE_ID)
                        .with(as(user)).contentType(MediaType.APPLICATION_JSON).content(body(ASSET_ID, 500_000L, 0L)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.version").value(1));

        mockMvc.perform(put("/api/users/watch-progress/" + EPISODE_ID)
                        .with(as(user)).contentType(MediaType.APPLICATION_JSON).content(body(ASSET_ID, 900_000L, 0L)))
                .andExpect(status().isConflict());

        mockMvc.perform(put("/api/users/watch-progress/" + EPISODE_ID)
                        .with(as(user)).contentType(MediaType.APPLICATION_JSON).content(body(ASSET_ID, 100_000L, 1L)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.positionMs").value(100_000))
                .andExpect(jsonPath("$.data.version").value(2));
    }

    @Test
    void usersCannotReadOrDeleteAnotherUsersProgress() throws Exception {
        User otherAccount = userRepository.save(User.builder()
                .username("watch_progress_other_" + UUID.randomUUID().toString().substring(0, 8))
                .email("watch_progress_other_" + UUID.randomUUID().toString().substring(0, 8) + "@example.test")
                .password("unused-test-password")
                .role(Role.ROLE_USER)
                .build());
        UserDetailsImpl other = principal(otherAccount);

        mockMvc.perform(put("/api/users/watch-progress/" + EPISODE_ID)
                        .with(as(user)).contentType(MediaType.APPLICATION_JSON).content(body(ASSET_ID, 400_000L, -1L)))
                .andExpect(status().isOk());
        mockMvc.perform(get("/api/users/watch-progress/" + EPISODE_ID).with(as(other)))
                .andExpect(status().isNotFound());
        mockMvc.perform(get("/api/users/watch-progress").with(as(other)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(0)));

        mockMvc.perform(delete("/api/users/watch-progress/" + EPISODE_ID).with(as(other)))
                .andExpect(status().isOk());
        mockMvc.perform(get("/api/users/watch-progress/" + EPISODE_ID).with(as(user)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.positionMs").value(400_000));
    }

    @Test
    void rejectsWrongEpisodePrivateAudioPartDisabledAndUnavailableAssets() throws Exception {
        addEpisode("wp-other-episode", "wp-other-video", 1_000_000L, "full_episode", "video", "feature", "public", true, true, null);
        addEpisode("wp-part-episode", "wp-part-video", 1_000_000L, "part", "video", "feature", "public", true, true, null);
        addEpisode("wp-audio-episode", "wp-audio", 1_000_000L, "full_episode", "audio", "dub", "private", true, true, null);
        addEpisode("wp-private-episode", "wp-private", 1_000_000L, "full_episode", "video", "feature", "private", true, true, null);
        addEpisode("wp-disabled-episode", "wp-disabled", 1_000_000L, "full_episode", "video", "feature", "public", false, true, null);
        addEpisode("wp-unavailable-episode", "wp-unavailable", 1_000_000L, "full_episode", "video", "feature", "public", true, false, null);

        assertRejected(EPISODE_ID, "wp-other-video");
        assertRejected("wp-missing-episode", ASSET_ID);
        assertRejected("wp-part-episode", "wp-part-video");
        assertRejected("wp-audio-episode", "wp-audio");
        assertRejected("wp-private-episode", "wp-private");
        assertRejected("wp-disabled-episode", "wp-disabled");
        assertRejected("wp-unavailable-episode", "wp-unavailable");
    }

    @Test
    void rejectsInvalidAndOversizedPositionsAndUsesCanonicalDuration() throws Exception {
        for (String invalid : List.of("-1", "1000001", "86400001", "1.5", "\"NaN\"")) {
            mockMvc.perform(put("/api/users/watch-progress/" + EPISODE_ID)
                            .with(as(user)).contentType(MediaType.APPLICATION_JSON)
                            .content("{\"assetId\":\"" + ASSET_ID + "\",\"positionMs\":" + invalid + ",\"expectedVersion\":-1}"))
                    .andExpect(status().isBadRequest());
        }

        addEpisode("wp-unknown-duration", "wp-unknown-asset", null, "full_episode", "video", "feature", "public", true, true, null);
        mockMvc.perform(put("/api/users/watch-progress/wp-unknown-duration")
                        .with(as(user)).contentType(MediaType.APPLICATION_JSON).content(body("wp-unknown-asset", 20_000L, -1L)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.durationMs").doesNotExist())
                .andExpect(jsonPath("$.data.completed").value(false));
    }

    @Test
    void recentListIsBoundedAndDoesNotExposeStorageDetails() throws Exception {
        for (int i = 0; i < 31; i++) {
            String episodeId = "wp-list-episode-" + i;
            String assetId = "wp-list-asset-" + i;
            addEpisode(episodeId, assetId, 100_000L, "full_episode", "video", "feature", "public", true, true, null);
            WatchProgress progress = new WatchProgress();
            progress.setUserId(user.getId());
            progress.setEpisodeId(episodeId);
            progress.setAssetId(assetId);
            progress.setPositionMs(1_000L);
            progressRepository.saveAndFlush(progress);
        }

        String result = mockMvc.perform(get("/api/users/watch-progress").with(as(user)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(30)))
                .andReturn().getResponse().getContentAsString();
        assertFalse(result.contains("storageKey"));
        assertFalse(result.contains("relativePath"));
        assertFalse(result.contains("driveFileId"));
        assertFalse(result.contains("rawJson"));
    }

    @Test
    void savedProgressSurvivesPersistenceContextReopenAndDeleteIsUserScoped() throws Exception {
        mockMvc.perform(put("/api/users/watch-progress/" + EPISODE_ID)
                        .with(as(user)).contentType(MediaType.APPLICATION_JSON).content(body(ASSET_ID, 420_000L, -1L)))
                .andExpect(status().isOk());

        progressRepository.flush();
        entityManager.clear();
        WatchProgress stored = progressRepository.findByUserIdAndEpisodeId(user.getId(), EPISODE_ID).orElseThrow();
        assertEquals(420_000L, stored.getPositionMs());
        assertEquals(ASSET_ID, stored.getAssetId());

        mockMvc.perform(delete("/api/users/watch-progress/" + EPISODE_ID).with(as(user)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").doesNotExist());
        assertTrue(progressRepository.findByUserIdAndEpisodeId(user.getId(), EPISODE_ID).isEmpty());
    }

    private void assertRejected(String episodeId, String assetId) throws Exception {
        mockMvc.perform(put("/api/users/watch-progress/" + episodeId)
                        .with(as(user)).contentType(MediaType.APPLICATION_JSON).content(body(assetId, 100L, -1L)))
                .andExpect(status().isNotFound());
    }

    private void addEpisode(String episodeId, String assetId, Long durationMs, String scope,
                            String contentType, String role, String policy, boolean enabled,
                            boolean available, String seasonId) {
        CatalogEpisode episode = new CatalogEpisode();
        episode.setId(episodeId);
        episode.setSeriesId(SERIES_ID);
        episode.setSeasonId(seasonId);
        episode.setNumber(episodeId.equals(EPISODE_ID) ? 1 : null);
        episode.setKind("regular");
        episode.setTitle(episodeId.equals(EPISODE_ID) ? "Canonical Episode" : episodeId);
        episode.setDurationMs(durationMs);
        episode.setRecordJson("{\"status\":\"ready\"}");
        episodeRepository.save(episode);

        CatalogMediaAsset asset = new CatalogMediaAsset();
        asset.setId(assetId);
        asset.setContentType(contentType);
        asset.setRole(role);
        asset.setStorageProvider("local");
        asset.setStorageKey("local_main");
        asset.setRelativePath("media/" + assetId + ".mp4");
        asset.setDurationMs(durationMs);
        asset.setCoverageJson("[{\"episode_id\":\"" + episodeId + "\",\"scope\":\"" + scope + "\"}]");
        asset.setAccessPolicy(policy);
        asset.setEnabled(enabled);
        asset.setRecordJson("{\"status\":\"ready\"}");
        catalogAssetRepository.save(asset);

        MediaAsset legacy = new MediaAsset(assetId, episodeId, role, "local", "media/" + assetId + ".mp4",
                "v1", "audio".equals(contentType) ? "audio/mp4" : "video/mp4", 10_000L,
                durationMs == null ? null : durationMs / 1000.0, "public".equals(policy), available);
        legacy.setStorageKey("local_main");
        playableAssetRepository.save(legacy);
    }

    private String body(String assetId, long positionMs, long expectedVersion) throws Exception {
        return objectMapper.writeValueAsString(Map.of(
                "assetId", assetId,
                "positionMs", positionMs,
                "expectedVersion", expectedVersion));
    }

    private String bodyWithDuration(String assetId, long positionMs, long expectedVersion, long clientDuration) throws Exception {
        return objectMapper.writeValueAsString(Map.of(
                "assetId", assetId,
                "positionMs", positionMs,
                "expectedVersion", expectedVersion,
                "durationMs", clientDuration));
    }

    private RequestPostProcessor as(UserDetailsImpl principal) {
        return authentication(new UsernamePasswordAuthenticationToken(principal, null, principal.getAuthorities()));
    }

    private UserDetailsImpl principal(User account) {
        return new UserDetailsImpl(account.getId(), account.getUsername(), account.getEmail(), account.getFullName(),
                account.getPassword(), List.of(new SimpleGrantedAuthority(account.getRole().name())));
    }
}
