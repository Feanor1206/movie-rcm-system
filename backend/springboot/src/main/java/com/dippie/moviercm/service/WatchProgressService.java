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
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.OptimisticLockingFailureException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Optional;

@Service
public class WatchProgressService {

    private static final long MAX_POSITION_MS = 24L * 60 * 60 * 1000;
    private static final long NEAR_END_MS = 60L * 1000;

    private final WatchProgressRepository progressRepository;
    private final CatalogEpisodeRepository episodeRepository;
    private final CatalogSeriesRepository seriesRepository;
    private final CatalogSeasonRepository seasonRepository;
    private final CatalogMediaAssetRepository catalogAssetRepository;
    private final MediaAssetRepository playableAssetRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public WatchProgressService(WatchProgressRepository progressRepository,
                                CatalogEpisodeRepository episodeRepository,
                                CatalogSeriesRepository seriesRepository,
                                CatalogSeasonRepository seasonRepository,
                                CatalogMediaAssetRepository catalogAssetRepository,
                                MediaAssetRepository playableAssetRepository) {
        this.progressRepository = progressRepository;
        this.episodeRepository = episodeRepository;
        this.seriesRepository = seriesRepository;
        this.seasonRepository = seasonRepository;
        this.catalogAssetRepository = catalogAssetRepository;
        this.playableAssetRepository = playableAssetRepository;
    }

    @Transactional(readOnly = true)
    public List<WatchProgressResponse> getRecent(UserDetailsImpl user) {
        long userId = requireUserId(user);
        List<WatchProgressResponse> result = new ArrayList<>();
        for (WatchProgress progress : progressRepository.findTop30ByUserIdOrderByUpdatedAtDesc(userId)) {
            try {
                EpisodeContext context = requirePlayableEpisode(progress.getEpisodeId(), progress.getAssetId(), user);
                result.add(toResponse(progress, context));
            } catch (MediaNotFoundException ignored) {
                // Catalog edits can make a saved item unplayable; do not expose stale or private metadata.
            }
        }
        return result;
    }

    @Transactional(readOnly = true)
    public WatchProgressResponse getForEpisode(UserDetailsImpl user, String episodeId) {
        long userId = requireUserId(user);
        WatchProgress progress = progressRepository.findByUserIdAndEpisodeId(userId, episodeId)
                .orElseThrow(() -> notFound(episodeId));
        EpisodeContext context = requirePlayableEpisode(episodeId, progress.getAssetId(), user);
        return toResponse(progress, context);
    }

    @Transactional
    public WatchProgressResponse save(UserDetailsImpl user, String episodeId, WatchProgressRequest request) {
        long userId = requireUserId(user);
        if (request == null || request.getExpectedVersion() == null ||
                request.getAssetId() == null || request.getAssetId().isBlank()) {
            throw new IllegalArgumentException("assetId and expectedVersion are required.");
        }
        if (request.getExpectedVersion() < -1) {
            throw new IllegalArgumentException("expectedVersion must be -1 for create or a non-negative current version.");
        }
        EpisodeContext context = requirePlayableEpisode(episodeId, request.getAssetId(), user);
        long positionMs = validatePosition(request.getPositionMs(), context.asset().getDurationMs());
        Optional<WatchProgress> current = progressRepository.findByUserIdAndEpisodeId(userId, episodeId);

        WatchProgress progress;
        if (request.getExpectedVersion() == -1) {
            if (current.isPresent()) throw staleWrite();
            progress = new WatchProgress();
            progress.setUserId(userId);
            progress.setEpisodeId(episodeId);
        } else {
            progress = current.orElseThrow(WatchProgressService::staleWrite);
            if (progress.getVersion() == null || !progress.getVersion().equals(request.getExpectedVersion())) {
                throw staleWrite();
            }
        }

        progress.setAssetId(context.asset().getId());
        progress.setPositionMs(positionMs);
        progress.setUpdatedAt(LocalDateTime.now());
        try {
            return toResponse(progressRepository.saveAndFlush(progress), context);
        } catch (OptimisticLockingFailureException | DataIntegrityViolationException ex) {
            throw staleWrite();
        }
    }

    @Transactional
    public void delete(UserDetailsImpl user, String episodeId) {
        progressRepository.deleteByUserIdAndEpisodeId(requireUserId(user), episodeId);
    }

    private EpisodeContext requirePlayableEpisode(String episodeId, String assetId, UserDetailsImpl user) {
        CatalogEpisode episode = episodeRepository.findById(episodeId).orElseThrow(() -> notFound(episodeId));
        if (!isPublished(episode.getRecordJson())) throw notFound(episodeId);

        CatalogSeries series = seriesRepository.findById(episode.getSeriesId()).orElseThrow(() -> notFound(episodeId));
        if (!isPublished(series.getRecordJson())) throw notFound(episodeId);

        CatalogSeason season = null;
        if (episode.getSeasonId() != null) {
            season = seasonRepository.findById(episode.getSeasonId()).orElseThrow(() -> notFound(episodeId));
            if (!isPublished(season.getRecordJson())) throw notFound(episodeId);
        }

        CatalogMediaAsset asset = catalogAssetRepository.findById(assetId).orElseThrow(() -> notFound(episodeId));
        if (!isPublished(asset.getRecordJson()) || !Boolean.TRUE.equals(asset.getEnabled()) ||
                !"video".equalsIgnoreCase(asset.getContentType()) || isAudioRole(asset.getRole()) ||
                !coversFullEpisode(asset.getCoverageJson(), episodeId) || !allowedByPolicy(asset, user) ||
                !isPlayableVideo(playableAssetRepository.findByIdAndIsAvailableTrue(assetId).orElse(null))) {
            throw notFound(episodeId);
        }
        return new EpisodeContext(episode, series, season, asset);
    }

    private boolean coversFullEpisode(String coverageJson, String episodeId) {
        if (coverageJson == null || coverageJson.isBlank()) return false;
        try {
            JsonNode coverage = objectMapper.readTree(coverageJson);
            if (!coverage.isArray()) return false;
            for (JsonNode item : coverage) {
                if (episodeId.equals(item.path("episode_id").asText()) &&
                        "full_episode".equalsIgnoreCase(item.path("scope").asText())) return true;
            }
        } catch (Exception ignored) {}
        return false;
    }

    private boolean allowedByPolicy(CatalogMediaAsset asset, UserDetailsImpl user) {
        String policy = asset.getAccessPolicy() == null ? "" : asset.getAccessPolicy().toLowerCase(Locale.ROOT);
        return "public".equals(policy) || "authenticated".equals(policy) ||
                ("private".equals(policy) && isAdmin(user));
    }

    private boolean isAdmin(UserDetailsImpl user) {
        return user.getAuthorities() != null && user.getAuthorities().stream()
                .anyMatch(authority -> "ROLE_ADMIN".equals(authority.getAuthority()));
    }

    private boolean isPlayableVideo(MediaAsset asset) {
        return asset != null && asset.getMimeType() != null &&
                asset.getMimeType().toLowerCase(Locale.ROOT).startsWith("video/");
    }

    private boolean isAudioRole(String role) {
        if (role == null) return false;
        String value = role.toLowerCase(Locale.ROOT);
        return "dub".equals(value) || "audio_description".equals(value);
    }

    private boolean isPublished(String recordJson) {
        if (recordJson == null || recordJson.isBlank()) return false;
        try {
            JsonNode record = objectMapper.readTree(recordJson);
            return "ready".equalsIgnoreCase(record.path("status").asText());
        } catch (Exception ignored) {
            return false;
        }
    }

    private long validatePosition(BigDecimal position, Long durationMs) {
        if (position == null || position.stripTrailingZeros().scale() > 0 || position.signum() < 0 ||
                position.compareTo(BigDecimal.valueOf(MAX_POSITION_MS)) > 0) {
            throw new IllegalArgumentException("positionMs must be a non-negative integer no greater than 24 hours.");
        }
        final long value;
        try { value = position.longValueExact(); } catch (ArithmeticException ex) {
            throw new IllegalArgumentException("positionMs must be a non-negative integer no greater than 24 hours.");
        }
        if (durationMs != null && durationMs > 0 && value > durationMs) {
            throw new IllegalArgumentException("positionMs cannot exceed the canonical video duration.");
        }
        return value;
    }

    private WatchProgressResponse toResponse(WatchProgress progress, EpisodeContext context) {
        Long durationMs = context.asset().getDurationMs();
        boolean completed = false;
        if (durationMs != null && durationMs > 0) {
            long fivePercent = Math.max(1L, durationMs / 20L);
            long nearEnd = Math.min(NEAR_END_MS, fivePercent);
            long threshold = Math.max(durationMs - fivePercent, durationMs - nearEnd);
            completed = progress.getPositionMs() >= threshold;
        }
        return new WatchProgressResponse(
                context.episode().getId(),
                context.series().getId(),
                context.series().getTitle(),
                context.season() == null ? null : context.season().getId(),
                context.season() == null ? null : context.season().getNumber(),
                context.season() == null ? null : context.season().getTitle(),
                context.episode().getNumber(),
                context.episode().getTitle(),
                progress.getAssetId(),
                progress.getPositionMs(),
                durationMs != null && durationMs > 0 ? durationMs : null,
                completed,
                progress.getVersion() == null ? 0L : progress.getVersion(),
                progress.getUpdatedAt());
    }

    private long requireUserId(UserDetailsImpl user) {
        if (user == null || user.getId() == null) throw new IllegalArgumentException("Authenticated user required.");
        return user.getId();
    }

    private static MediaNotFoundException notFound(String episodeId) {
        return new MediaNotFoundException("Không tìm thấy tập có thể phát: " + episodeId);
    }

    private static IllegalStateException staleWrite() {
        return new IllegalStateException("Watch progress changed since it was loaded; refresh and retry.");
    }

    private record EpisodeContext(CatalogEpisode episode, CatalogSeries series, CatalogSeason season,
                                  CatalogMediaAsset asset) {}
}
