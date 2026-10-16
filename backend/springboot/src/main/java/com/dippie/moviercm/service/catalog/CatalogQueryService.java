package com.dippie.moviercm.service.catalog;

import com.dippie.moviercm.dto.catalog.CatalogEpisodeResponse;
import com.dippie.moviercm.dto.catalog.CatalogSearchResult;
import com.dippie.moviercm.dto.catalog.CatalogSeriesResponse;
import com.dippie.moviercm.entity.catalog.*;
import com.dippie.moviercm.exception.MediaNotFoundException;
import com.dippie.moviercm.repository.catalog.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Service providing catalog querying, search, detail retrieval, and self-contained eligible snapshots.
 * Enforces unified publication policy cascading (G4):
 * - Deny-by-default: only record status == 'ready' is considered published.
 * - Parent cascade: draft/archived series excludes child seasons, episodes, segments, scenes.
 * - Draft/archived episode excludes child segments and scenes.
 * - Private/disabled media assets exclude linked scenes and text tracks from public views and snapshots.
 */
@Service
public class CatalogQueryService {

    private final CatalogPackageRepository packageRepository;
    private final CatalogGenreRepository genreRepository;
    private final CatalogAttributeScaleRepository scaleRepository;
    private final CatalogSourceRepository sourceRepository;
    private final CatalogSeriesRepository seriesRepository;
    private final CatalogSeasonRepository seasonRepository;
    private final CatalogEpisodeRepository episodeRepository;
    private final CatalogSegmentRepository segmentRepository;
    private final CatalogCharacterRepository characterRepository;
    private final CatalogMediaAssetRepository mediaAssetRepository;
    private final CatalogTextTrackRepository textTrackRepository;
    private final CatalogSceneRepository sceneRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Autowired
    public CatalogQueryService(
            CatalogPackageRepository packageRepository,
            CatalogGenreRepository genreRepository,
            CatalogAttributeScaleRepository scaleRepository,
            CatalogSourceRepository sourceRepository,
            CatalogSeriesRepository seriesRepository,
            CatalogSeasonRepository seasonRepository,
            CatalogEpisodeRepository episodeRepository,
            CatalogSegmentRepository segmentRepository,
            CatalogCharacterRepository characterRepository,
            CatalogMediaAssetRepository mediaAssetRepository,
            CatalogTextTrackRepository textTrackRepository,
            CatalogSceneRepository sceneRepository) {
        this.packageRepository = packageRepository;
        this.genreRepository = genreRepository;
        this.scaleRepository = scaleRepository;
        this.sourceRepository = sourceRepository;
        this.seriesRepository = seriesRepository;
        this.seasonRepository = seasonRepository;
        this.episodeRepository = episodeRepository;
        this.segmentRepository = segmentRepository;
        this.characterRepository = characterRepository;
        this.mediaAssetRepository = mediaAssetRepository;
        this.textTrackRepository = textTrackRepository;
        this.sceneRepository = sceneRepository;
    }

    /**
     * Strict publication check (G4): deny-by-default.
     * Only returns true if record_json is present, parses cleanly, has 'status', and status is 'ready'.
     */
    public boolean isPublished(String recordJson) {
        if (recordJson == null || recordJson.isBlank()) return false;
        try {
            JsonNode rec = objectMapper.readTree(recordJson);
            if (rec.has("status")) {
                String status = rec.get("status").asText();
                return "ready".equalsIgnoreCase(status);
            }
        } catch (Exception ignored) {}
        return false;
    }

    public boolean isUserAdmin() {
        org.springframework.security.core.Authentication auth =
                org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated()) return false;
        return auth.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));
    }

    public List<CatalogSeries> getAllSeries() {
        if (isUserAdmin()) {
            return seriesRepository.findAll();
        }
        return seriesRepository.findAll().stream()
                .filter(s -> isPublished(s.getRecordJson()))
                .toList();
    }

    public CatalogSeriesResponse getSeriesDetail(String seriesId) {
        CatalogSeries series = seriesRepository.findById(seriesId)
                .orElseThrow(() -> new MediaNotFoundException("Không tìm thấy bộ phim với mã: " + seriesId));

        boolean admin = isUserAdmin();
        if (!admin && !isPublished(series.getRecordJson())) {
            throw new MediaNotFoundException("Không tìm thấy bộ phim với mã: " + seriesId);
        }

        List<CatalogSeason> seasons = seasonRepository.findBySeriesIdOrderByNumberAsc(seriesId);
        if (!admin) {
            seasons = seasons.stream().filter(sea -> isPublished(sea.getRecordJson())).toList();
        }
        Set<String> eligibleSeasonIds = seasons.stream().map(CatalogSeason::getId).collect(Collectors.toSet());

        List<CatalogEpisode> episodes = episodeRepository.findBySeriesIdOrderByNumberAsc(seriesId);
        if (!admin) {
            episodes = episodes.stream()
                    .filter(ep -> isPublished(ep.getRecordJson()))
                    .filter(ep -> ep.getSeasonId() == null || eligibleSeasonIds.contains(ep.getSeasonId()))
                    .toList();
        }

        return new CatalogSeriesResponse(series, seasons, episodes);
    }

    public CatalogEpisodeResponse getEpisodeDetail(String episodeId) {
        CatalogEpisode episode = episodeRepository.findById(episodeId)
                .orElseThrow(() -> new MediaNotFoundException("Không tìm thấy tập phim với mã: " + episodeId));

        boolean admin = isUserAdmin();
        if (!admin) {
            if (!isPublished(episode.getRecordJson())) {
                throw new MediaNotFoundException("Không tìm thấy tập phim với mã: " + episodeId);
            }
            if (episode.getSeriesId() != null) {
                CatalogSeries series = seriesRepository.findById(episode.getSeriesId()).orElse(null);
                if (series == null || !isPublished(series.getRecordJson())) {
                    throw new MediaNotFoundException("Không tìm thấy tập phim với mã: " + episodeId);
                }
            }
            if (episode.getSeasonId() != null) {
                CatalogSeason season = seasonRepository.findById(episode.getSeasonId()).orElse(null);
                if (season != null && !isPublished(season.getRecordJson())) {
                    throw new MediaNotFoundException("Không tìm thấy tập phim với mã: " + episodeId);
                }
            }
        }

        List<CatalogSegment> segments = segmentRepository.findByEpisodeIdOrderByPositionAsc(episodeId);
        List<CatalogScene> scenes = sceneRepository.findByEpisodeIdOrderByStartMsAsc(episodeId);

        if (!admin) {
            segments = segments.stream().filter(seg -> isPublished(seg.getRecordJson())).toList();
            scenes = scenes.stream().filter(sc -> isPublished(sc.getRecordJson())).toList();
        }

        // Find media assets covering this episode
        List<CatalogMediaAsset> allAssets = mediaAssetRepository.findByEnabledTrue();
        List<CatalogMediaAsset> matchingAssets = new ArrayList<>();
        Set<String> privateAssetIds = new HashSet<>();
        for (CatalogMediaAsset asset : allAssets) {
            boolean isPrivate = "private".equalsIgnoreCase(asset.getAccessPolicy());
            if (isPrivate) {
                privateAssetIds.add(asset.getId());
                if (!admin) {
                    continue;
                }
            }
            if (!admin && !isPublished(asset.getRecordJson())) {
                continue;
            }
            if (asset.getCoverageJson() != null) {
                try {
                    JsonNode cov = objectMapper.readTree(asset.getCoverageJson());
                    if (cov.isArray()) {
                        for (JsonNode part : cov) {
                            if (episodeId.equals(part.path("episode_id").asText())) {
                                matchingAssets.add(asset);
                                break;
                            }
                        }
                    }
                } catch (Exception ignored) {}
            }
        }

        if (!admin) {
            scenes = scenes.stream()
                    .filter(sc -> sc.getMediaAssetId() == null || !privateAssetIds.contains(sc.getMediaAssetId()))
                    .toList();
        }

        return new CatalogEpisodeResponse(episode, segments, matchingAssets, scenes);
    }

    public List<CatalogSearchResult> searchCatalog(String query) {
        if (query == null || query.trim().isEmpty()) {
            return Collections.emptyList();
        }
        String q = query.trim();
        List<CatalogSearchResult> results = new ArrayList<>();
        boolean admin = isUserAdmin();

        // 1. Search series
        List<CatalogSeries> matchedSeries = seriesRepository.searchSeries(q);
        for (CatalogSeries s : matchedSeries) {
            if (!admin && !isPublished(s.getRecordJson())) {
                continue;
            }
            results.add(new CatalogSearchResult(
                    s.getId(),
                    "series",
                    s.getTitle(),
                    s.getOriginalTitle(),
                    s.getId(),
                    null,
                    null,
                    null,
                    null,
                    s.getSynopsis()
            ));
        }

        // 2. Search episodes
        List<CatalogEpisode> matchedEpisodes = episodeRepository.searchEpisodes(q);
        for (CatalogEpisode ep : matchedEpisodes) {
            if (!admin) {
                if (!isPublished(ep.getRecordJson())) {
                    continue;
                }
                if (ep.getSeriesId() != null) {
                    CatalogSeries s = seriesRepository.findById(ep.getSeriesId()).orElse(null);
                    if (s == null || !isPublished(s.getRecordJson())) {
                        continue;
                    }
                }
            }
            results.add(new CatalogSearchResult(
                    ep.getId(),
                    "episode",
                    ep.getTitle(),
                    ep.getSeriesId(),
                    ep.getSeriesId(),
                    ep.getId(),
                    null,
                    null,
                    null,
                    ep.getSynopsis()
            ));
        }

        // 3. Search segments
        List<CatalogSegment> matchedSegments = segmentRepository.searchSegments(q);
        for (CatalogSegment seg : matchedSegments) {
            if (!admin && !isPublished(seg.getRecordJson())) {
                continue;
            }
            String seriesId = null;
            String parentTitle = seg.getEpisodeId();
            if (seg.getEpisodeId() != null) {
                Optional<CatalogEpisode> parentEp = episodeRepository.findById(seg.getEpisodeId());
                if (parentEp.isPresent()) {
                    if (!admin && !isPublished(parentEp.get().getRecordJson())) {
                        continue;
                    }
                    seriesId = parentEp.get().getSeriesId();
                    parentTitle = parentEp.get().getTitle();
                    if (!admin && seriesId != null) {
                        CatalogSeries s = seriesRepository.findById(seriesId).orElse(null);
                        if (s == null || !isPublished(s.getRecordJson())) {
                            continue;
                        }
                    }
                } else if (!admin) {
                    continue;
                }
            }
            results.add(new CatalogSearchResult(
                    seg.getId(),
                    "segment",
                    seg.getTitle(),
                    parentTitle,
                    seriesId,
                    seg.getEpisodeId(),
                    null,
                    seg.getEpisodeStartMs(),
                    seg.getEpisodeEndMs(),
                    seg.getSynopsis()
            ));
        }

        // 4. Search scenes
        List<CatalogScene> matchedScenes = sceneRepository.searchScenes(q);
        for (CatalogScene sc : matchedScenes) {
            if (!admin && !isPublished(sc.getRecordJson())) {
                continue;
            }
            String seriesId = null;
            String parentTitle = sc.getEpisodeId();
            if (sc.getEpisodeId() != null) {
                Optional<CatalogEpisode> parentEp = episodeRepository.findById(sc.getEpisodeId());
                if (parentEp.isPresent()) {
                    if (!admin && !isPublished(parentEp.get().getRecordJson())) {
                        continue;
                    }
                    seriesId = parentEp.get().getSeriesId();
                    parentTitle = parentEp.get().getTitle();
                    if (!admin && seriesId != null) {
                        CatalogSeries s = seriesRepository.findById(seriesId).orElse(null);
                        if (s == null || !isPublished(s.getRecordJson())) {
                            continue;
                        }
                    }
                } else if (!admin) {
                    continue;
                }
            }
            if (!admin && sc.getMediaAssetId() != null) {
                Optional<CatalogMediaAsset> assetOpt = mediaAssetRepository.findById(sc.getMediaAssetId());
                if (assetOpt.isPresent()) {
                    CatalogMediaAsset ma = assetOpt.get();
                    if ("private".equalsIgnoreCase(ma.getAccessPolicy()) || (ma.getEnabled() != null && !ma.getEnabled())) {
                        continue;
                    }
                }
            }
            results.add(new CatalogSearchResult(
                    sc.getId(),
                    "scene",
                    sc.getTitle(),
                    parentTitle,
                    seriesId,
                    sc.getEpisodeId(),
                    sc.getMediaAssetId(),
                    sc.getStartMs(),
                    sc.getEndMs(),
                    sc.getSummary()
            ));
        }

        return results;
    }

    /**
     * Builds full self-contained snapshot from eligible committed database entities (G4).
     * Guarantees reference integrity: no dangling text tracks, scenes, characters, or sources.
     */
    public Map<String, Object> exportEligibleSnapshot(boolean includeDraft, boolean includePrivate) {
        Map<String, Object> export = new LinkedHashMap<>();
        export.put("schema_version", "dippie.catalog.v1");

        // Package header
        List<CatalogPackage> packages = packageRepository.findAll();
        Map<String, Object> pkgMap = new LinkedHashMap<>();
        if (!packages.isEmpty()) {
            CatalogPackage latestPkg = packages.get(packages.size() - 1);
            pkgMap.put("id", latestPkg.getId());
            pkgMap.put("description", latestPkg.getDescription() != null && !latestPkg.getDescription().isBlank()
                    ? latestPkg.getDescription() : "Canonical catalog export");
            pkgMap.put("created_at", latestPkg.getCreatedAt() != null
                    ? latestPkg.getCreatedAt().toString() + "Z" : Instant.now().toString());
            pkgMap.put("revision", latestPkg.getRevision() != null ? latestPkg.getRevision() : 1);
            pkgMap.put("default_language", latestPkg.getDefaultLanguage() != null ? latestPkg.getDefaultLanguage() : "vi");
            pkgMap.put("import_mode", latestPkg.getImportMode() != null ? latestPkg.getImportMode() : "upsert");
            pkgMap.put("reference_scope", latestPkg.getReferenceScope() != null ? latestPkg.getReferenceScope() : "self_contained");
        } else {
            pkgMap.put("id", "pkg_canonical_export");
            pkgMap.put("description", "Empty canonical catalog export");
            pkgMap.put("created_at", Instant.now().toString());
            pkgMap.put("revision", 1);
            pkgMap.put("default_language", "vi");
            pkgMap.put("import_mode", "upsert");
            pkgMap.put("reference_scope", "self_contained");
        }
        export.put("package", pkgMap);

        // 1. Series
        List<CatalogSeries> allSeries = seriesRepository.findAll();
        List<CatalogSeries> eligibleSeries = includeDraft ? allSeries
                : allSeries.stream().filter(s -> isPublished(s.getRecordJson())).toList();
        Set<String> eligibleSeriesIds = eligibleSeries.stream().map(CatalogSeries::getId).collect(Collectors.toSet());

        // 2. Seasons (cascade parent series)
        List<CatalogSeason> allSeasons = seasonRepository.findAll();
        List<CatalogSeason> eligibleSeasons = allSeasons.stream()
                .filter(sea -> eligibleSeriesIds.contains(sea.getSeriesId()))
                .filter(sea -> includeDraft || isPublished(sea.getRecordJson()))
                .toList();
        Set<String> eligibleSeasonIds = eligibleSeasons.stream().map(CatalogSeason::getId).collect(Collectors.toSet());

        // 3. Episodes (cascade parent series & season)
        List<CatalogEpisode> allEpisodes = episodeRepository.findAll();
        List<CatalogEpisode> eligibleEpisodes = allEpisodes.stream()
                .filter(ep -> eligibleSeriesIds.contains(ep.getSeriesId()))
                .filter(ep -> ep.getSeasonId() == null || eligibleSeasonIds.contains(ep.getSeasonId()))
                .filter(ep -> includeDraft || isPublished(ep.getRecordJson()))
                .toList();
        Set<String> eligibleEpisodeIds = eligibleEpisodes.stream().map(CatalogEpisode::getId).collect(Collectors.toSet());

        // 4. Segments (cascade parent episode)
        List<CatalogSegment> allSegments = segmentRepository.findAll();
        List<CatalogSegment> eligibleSegments = allSegments.stream()
                .filter(seg -> eligibleEpisodeIds.contains(seg.getEpisodeId()))
                .filter(seg -> includeDraft || isPublished(seg.getRecordJson()))
                .toList();
        Set<String> eligibleSegmentIds = eligibleSegments.stream().map(CatalogSegment::getId).collect(Collectors.toSet());

        // 5. Media Assets (cascade policy & enabled status & coverage of eligible episodes)
        List<CatalogMediaAsset> allAssets = mediaAssetRepository.findAll();
        List<CatalogMediaAsset> eligibleAssets = allAssets.stream()
                .filter(a -> includePrivate || (!"private".equalsIgnoreCase(a.getAccessPolicy()) && (a.getEnabled() == null || a.getEnabled())))
                .filter(a -> includeDraft || isPublished(a.getRecordJson()))
                .toList();
        Set<String> eligibleAssetIds = eligibleAssets.stream().map(CatalogMediaAsset::getId).collect(Collectors.toSet());

        // 6. Text Tracks (strictly self-contained: only tracks belonging to eligible assets)
        List<CatalogTextTrack> allTracks = textTrackRepository.findAll();
        List<CatalogTextTrack> eligibleTextTracks = allTracks.stream()
                .filter(tt -> eligibleAssetIds.contains(tt.getMediaAssetId()))
                .filter(tt -> includeDraft || isPublished(tt.getRecordJson()))
                .toList();

        // 7. Scenes (cascade parent episode and media asset)
        List<CatalogScene> allScenes = sceneRepository.findAll();
        List<CatalogScene> eligibleScenes = allScenes.stream()
                .filter(sc -> eligibleEpisodeIds.contains(sc.getEpisodeId()))
                .filter(sc -> sc.getSegmentId() == null || eligibleSegmentIds.contains(sc.getSegmentId()))
                .filter(sc -> sc.getMediaAssetId() == null || eligibleAssetIds.contains(sc.getMediaAssetId()))
                .filter(sc -> includeDraft || isPublished(sc.getRecordJson()))
                .toList();

        // 8. Collect referenced character IDs across eligible entities to preserve self-containment
        Set<String> referencedCharIds = new HashSet<>();
        for (CatalogSeries s : eligibleSeries) {
            extractIdsFromJson(s.getCharacterIdsJson(), referencedCharIds);
        }
        for (CatalogEpisode ep : eligibleEpisodes) {
            extractIdsFromJson(ep.getCharacterIdsJson(), referencedCharIds);
        }
        for (CatalogSegment seg : eligibleSegments) {
            extractIdsFromJson(seg.getCharacterIdsJson(), referencedCharIds);
        }
        for (CatalogScene sc : eligibleScenes) {
            extractIdsFromJson(sc.getCharacterIdsJson(), referencedCharIds);
        }

        List<CatalogCharacter> allCharacters = characterRepository.findAll();
        List<CatalogCharacter> eligibleCharacters = (referencedCharIds.isEmpty() && eligibleSeries.isEmpty())
                ? allCharacters
                : allCharacters.stream().filter(c -> referencedCharIds.contains(c.getId())).toList();

        export.put("genres", extractItems(genreRepository.findAll(), CatalogGenre::getRawJson));
        export.put("attribute_scales", extractItems(scaleRepository.findAll(), CatalogAttributeScale::getRawJson));
        export.put("sources", extractItems(sourceRepository.findAll(), CatalogSource::getRawJson));
        export.put("series", extractItems(eligibleSeries, CatalogSeries::getRawJson));
        export.put("seasons", extractItems(eligibleSeasons, CatalogSeason::getRawJson));
        export.put("episodes", extractItems(eligibleEpisodes, CatalogEpisode::getRawJson));
        export.put("segments", extractItems(eligibleSegments, CatalogSegment::getRawJson));
        export.put("characters", extractItems(eligibleCharacters, CatalogCharacter::getRawJson));
        export.put("media_assets", extractItems(eligibleAssets, CatalogMediaAsset::getRawJson));
        export.put("text_tracks", extractItems(eligibleTextTracks, CatalogTextTrack::getRawJson));
        export.put("scenes", extractItems(eligibleScenes, CatalogScene::getRawJson));

        return export;
    }

    public Map<String, Object> exportSearchableCatalog() {
        return exportEligibleSnapshot(true, true);
    }

    private void extractIdsFromJson(String jsonArrayStr, Set<String> targetSet) {
        if (jsonArrayStr == null || jsonArrayStr.isBlank()) return;
        try {
            JsonNode node = objectMapper.readTree(jsonArrayStr);
            if (node.isArray()) {
                for (JsonNode item : node) {
                    if (item.isTextual() && !item.asText().isBlank()) {
                        targetSet.add(item.asText());
                    }
                }
            }
        } catch (Exception ignored) {}
    }

    private <T> List<Object> extractItems(List<T> entities, java.util.function.Function<T, String> rawJsonExtractor) {
        List<Object> items = new ArrayList<>();
        for (T entity : entities) {
            String raw = rawJsonExtractor.apply(entity);
            if (raw != null && !raw.isBlank()) {
                try {
                    items.add(objectMapper.readTree(raw));
                    continue;
                } catch (Exception ignored) {}
            }
            items.add(entity);
        }
        return items;
    }
}
