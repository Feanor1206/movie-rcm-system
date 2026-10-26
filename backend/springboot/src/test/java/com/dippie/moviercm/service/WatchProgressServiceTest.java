package com.dippie.moviercm.service;

import com.dippie.moviercm.dto.WatchProgressRequest;
import com.dippie.moviercm.dto.WatchProgressResponse;
import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.WatchProgress;
import com.dippie.moviercm.entity.catalog.CatalogEpisode;
import com.dippie.moviercm.entity.catalog.CatalogMediaAsset;
import com.dippie.moviercm.entity.catalog.CatalogSeason;
import com.dippie.moviercm.entity.catalog.CatalogSeries;
import com.dippie.moviercm.exception.MediaNotFoundException;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.WatchProgressRepository;
import com.dippie.moviercm.repository.catalog.CatalogEpisodeRepository;
import com.dippie.moviercm.repository.catalog.CatalogMediaAssetRepository;
import com.dippie.moviercm.repository.catalog.CatalogSeasonRepository;
import com.dippie.moviercm.repository.catalog.CatalogSeriesRepository;
import com.dippie.moviercm.security.UserDetailsImpl;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class WatchProgressServiceTest {

    private static final long USER_ID = 42L;
    private WatchProgressService service;
    private UserDetailsImpl user;
    private CatalogEpisode episode;
    private CatalogSeries series;
    private CatalogSeason season;
    private CatalogMediaAsset catalogAsset;
    private MediaAsset playableAsset;

    @Mock private WatchProgressRepository progressRepository;
    @Mock private CatalogEpisodeRepository episodeRepository;
    @Mock private CatalogSeriesRepository seriesRepository;
    @Mock private CatalogSeasonRepository seasonRepository;
    @Mock private CatalogMediaAssetRepository catalogAssetRepository;
    @Mock private MediaAssetRepository playableAssetRepository;

    @BeforeEach
    void setUp() {
        service = new WatchProgressService(progressRepository, episodeRepository, seriesRepository,
                seasonRepository, catalogAssetRepository, playableAssetRepository);
        user = user(USER_ID, "ROLE_USER");

        episode = new CatalogEpisode();
        episode.setId("ep-1");
        episode.setSeriesId("series-1");
        episode.setSeasonId("season-1");
        episode.setNumber(1);
        episode.setTitle("Canonical episode");
        episode.setDurationMs(1_000_000L);
        episode.setRecordJson("{\"status\":\"ready\"}");

        series = new CatalogSeries();
        series.setId("series-1");
        series.setTitle("Canonical series");
        series.setRecordJson("{\"status\":\"ready\"}");

        season = new CatalogSeason();
        season.setId("season-1");
        season.setNumber(1);
        season.setTitle("Season one");
        season.setRecordJson("{\"status\":\"ready\"}");

        catalogAsset = new CatalogMediaAsset();
        catalogAsset.setId("asset-1");
        catalogAsset.setContentType("video");
        catalogAsset.setRole("feature");
        catalogAsset.setEnabled(true);
        catalogAsset.setDurationMs(1_000_000L);
        catalogAsset.setAccessPolicy("public");
        catalogAsset.setCoverageJson("[{\"episode_id\":\"ep-1\",\"scope\":\"full_episode\"}]");
        catalogAsset.setRecordJson("{\"status\":\"ready\"}");

        playableAsset = new MediaAsset("asset-1", "ep-1", "feature", "local", "video.mp4", "v1",
                "video/mp4", 10_000L, 1000.0, true, true);

        lenient().when(episodeRepository.findById("ep-1")).thenReturn(Optional.of(episode));
        lenient().when(seriesRepository.findById("series-1")).thenReturn(Optional.of(series));
        lenient().when(seasonRepository.findById("season-1")).thenReturn(Optional.of(season));
        lenient().when(catalogAssetRepository.findById("asset-1")).thenReturn(Optional.of(catalogAsset));
        lenient().when(playableAssetRepository.findByIdAndIsAvailableTrue("asset-1")).thenReturn(Optional.of(playableAsset));
    }

    @Test
    void createUsesPrincipalAndCanonicalMetadataAndDerivesCompletion() {
        when(progressRepository.findByUserIdAndEpisodeId(USER_ID, "ep-1")).thenReturn(Optional.empty());
        when(progressRepository.saveAndFlush(any())).thenAnswer(invocation -> {
            WatchProgress saved = invocation.getArgument(0);
            saved.setVersion(0L);
            saved.setUpdatedAt(LocalDateTime.now());
            return saved;
        });

        WatchProgressResponse response = service.save(user, "ep-1",
                new WatchProgressRequest("asset-1", BigDecimal.valueOf(950_000), -1L));

        assertEquals("Canonical series", response.getSeriesTitle());
        assertEquals("Canonical episode", response.getEpisodeTitle());
        assertEquals(1_000_000L, response.getDurationMs());
        assertTrue(response.isCompleted());
        assertEquals(0L, response.getVersion());
        verify(progressRepository).saveAndFlush(argThat(saved -> saved.getUserId().equals(USER_ID)));
    }

    @Test
    void missingDurationDoesNotMarkProgressComplete() {
        catalogAsset.setDurationMs(null);
        when(progressRepository.findByUserIdAndEpisodeId(USER_ID, "ep-1")).thenReturn(Optional.empty());
        when(progressRepository.saveAndFlush(any())).thenAnswer(invocation -> {
            WatchProgress saved = invocation.getArgument(0);
            saved.setVersion(0L);
            saved.setUpdatedAt(LocalDateTime.now());
            return saved;
        });

        WatchProgressResponse response = service.save(user, "ep-1",
                new WatchProgressRequest("asset-1", BigDecimal.valueOf(2_000_000), -1L));

        assertNull(response.getDurationMs());
        assertFalse(response.isCompleted());
    }

    @Test
    void staleVersionConflictsWithoutSaving() {
        WatchProgress current = storedProgress(5L);
        when(progressRepository.findByUserIdAndEpisodeId(USER_ID, "ep-1")).thenReturn(Optional.of(current));

        assertThrows(IllegalStateException.class, () -> service.save(user, "ep-1",
                new WatchProgressRequest("asset-1", BigDecimal.valueOf(300_000), 4L)));
        verify(progressRepository, never()).saveAndFlush(any());
    }

    @Test
    void assetMustBeReadyFullEpisodeVideoAndAvailable() {
        catalogAsset.setCoverageJson("[{\"episode_id\":\"ep-1\",\"scope\":\"part\"}]");
        assertThrows(MediaNotFoundException.class, () -> service.save(user, "ep-1",
                new WatchProgressRequest("asset-1", BigDecimal.TEN, -1L)));

        catalogAsset.setCoverageJson("[{\"episode_id\":\"ep-1\",\"scope\":\"full_episode\"}]");
        catalogAsset.setContentType("audio");
        assertThrows(MediaNotFoundException.class, () -> service.save(user, "ep-1",
                new WatchProgressRequest("asset-1", BigDecimal.TEN, -1L)));

        catalogAsset.setContentType("video");
        catalogAsset.setEnabled(false);
        assertThrows(MediaNotFoundException.class, () -> service.save(user, "ep-1",
                new WatchProgressRequest("asset-1", BigDecimal.TEN, -1L)));

        catalogAsset.setEnabled(true);
        lenient().when(playableAssetRepository.findByIdAndIsAvailableTrue("asset-1")).thenReturn(Optional.empty());
        assertThrows(MediaNotFoundException.class, () -> service.save(user, "ep-1",
                new WatchProgressRequest("asset-1", BigDecimal.TEN, -1L)));
    }

    @Test
    void privateAssetRequiresAdmin() {
        catalogAsset.setAccessPolicy("private");
        assertThrows(MediaNotFoundException.class, () -> service.save(user, "ep-1",
                new WatchProgressRequest("asset-1", BigDecimal.TEN, -1L)));

        UserDetailsImpl admin = user(USER_ID, "ROLE_ADMIN");
        when(progressRepository.findByUserIdAndEpisodeId(USER_ID, "ep-1")).thenReturn(Optional.empty());
        when(progressRepository.saveAndFlush(any())).thenAnswer(invocation -> {
            WatchProgress saved = invocation.getArgument(0);
            saved.setVersion(0L);
            saved.setUpdatedAt(LocalDateTime.now());
            return saved;
        });
        assertEquals("ep-1", service.save(admin, "ep-1",
                new WatchProgressRequest("asset-1", BigDecimal.TEN, -1L)).getEpisodeId());
    }

    @Test
    void positionsMustBeIntegralNonNegativeBoundedAndWithinKnownDuration() {
        for (BigDecimal invalid : List.of(BigDecimal.valueOf(-1), BigDecimal.valueOf(1.5), BigDecimal.valueOf(86_400_001L))) {
            assertThrows(IllegalArgumentException.class, () -> service.save(user, "ep-1",
                    new WatchProgressRequest("asset-1", invalid, -1L)));
        }
        assertThrows(IllegalArgumentException.class, () -> service.save(user, "ep-1",
                new WatchProgressRequest("asset-1", BigDecimal.valueOf(1_000_001L), -1L)));
    }

    @Test
    void assetMustCoverTheRequestedEpisode() {
        catalogAsset.setCoverageJson("[{\"episode_id\":\"ep-other\",\"scope\":\"full_episode\"}]");
        assertThrows(MediaNotFoundException.class, () -> service.save(user, "ep-1",
                new WatchProgressRequest("asset-1", BigDecimal.TEN, -1L)));
    }

    @Test
    void readsAreScopedToAuthenticatedUser() {
        when(progressRepository.findByUserIdAndEpisodeId(USER_ID, "ep-1")).thenReturn(Optional.empty());
        assertThrows(MediaNotFoundException.class, () -> service.getForEpisode(user, "ep-1"));
        verify(progressRepository).findByUserIdAndEpisodeId(USER_ID, "ep-1");
    }

    private WatchProgress storedProgress(long version) {
        WatchProgress progress = new WatchProgress();
        progress.setUserId(USER_ID);
        progress.setEpisodeId("ep-1");
        progress.setAssetId("asset-1");
        progress.setPositionMs(100L);
        progress.setVersion(version);
        progress.setUpdatedAt(LocalDateTime.now());
        return progress;
    }

    private UserDetailsImpl user(long id, String role) {
        return new UserDetailsImpl(id, "test", "test@example.test", "Test", "secret",
                List.of(new SimpleGrantedAuthority(role)));
    }
}
