import type { Movie } from '@/types/movie';

export interface MediaNavigationContext {
  id?: string;
  item_type?: string;
  type?: string;
  series_id?: string;
  seriesId?: string;
  season_id?: string;
  seasonId?: string;
  episode_id?: string;
  episodeId?: string;
  segment_id?: string;
  segmentId?: string;
  scene_id?: string;
  sceneId?: string;
  episode_number?: number;
  episodeNumber?: number;
  season_number?: number;
  seasonNumber?: number;
  start_ms?: number | null;
  startMs?: number | null;
  end_ms?: number | null;
  endMs?: number | null;
  primary_media_asset_id?: string;
  primaryMediaAssetId?: string;
  media_asset_id?: string;
  mediaAssetId?: string;
  timeline?: string;
  timescale?: string;
  [key: string]: any;
}

export interface CoverageEntry {
  episode_id?: string;
  segment_id?: string | null;
  sequence?: number;
  source_in_ms?: number;
  source_out_ms?: number | null;
  episode_in_ms?: number | null;
  scope?: string;
}

export interface MinimalMediaAsset {
  id?: string;
  coverageJson?: string | null;
  [key: string]: any;
}

export function resolveFileTimestamp(
  logicalMs: number,
  asset?: MinimalMediaAsset | null,
  segmentId?: string | null,
  episodeId?: string | null
): number | null {
  if (
    typeof logicalMs !== 'number' ||
    isNaN(logicalMs) ||
    !isFinite(logicalMs) ||
    logicalMs < 0 ||
    !asset?.coverageJson
  ) {
    return null;
  }

  try {
    const coverageList: CoverageEntry[] = JSON.parse(asset.coverageJson);
    if (!Array.isArray(coverageList) || coverageList.length === 0) {
      return null;
    }

    const relevantCoverage = episodeId
      ? coverageList.filter((c) => c && c.episode_id === episodeId)
      : coverageList.filter((c) => c);

    const isUsable = (c: CoverageEntry): c is CoverageEntry & { source_in_ms: number; episode_in_ms: number } => Number.isFinite(c.source_in_ms) &&
      Number.isFinite(c.episode_in_ms) && (c.source_in_ms as number) >= 0 &&
      (c.episode_in_ms as number) >= 0 &&
      (c.source_out_ms == null || (Number.isFinite(c.source_out_ms) && c.source_out_ms > (c.source_in_ms as number)));
    const contains = (c: CoverageEntry) => logicalMs >= (c.episode_in_ms as number) &&
      (c.source_out_ms == null || logicalMs < (c.episode_in_ms as number) + c.source_out_ms - (c.source_in_ms as number));

    if (segmentId) {
      const segCov = relevantCoverage.find((c) => c.segment_id === segmentId);
      if (segCov) {
        if (!isUsable(segCov) || !contains(segCov)) return null;
        const delta = logicalMs - segCov.episode_in_ms;
        if (delta < 0) return null;
        return (segCov.source_in_ms + delta) / 1000;
      }
    }

    const matches = relevantCoverage.filter((c) => isUsable(c) && contains(c));

    if (matches.length === 1) {
      const match = matches[0];
      const delta = logicalMs - (match.episode_in_ms as number);
      return ((match.source_in_ms as number) + delta) / 1000;
    }
  } catch {
    return null;
  }
  return null;
}

export interface ResolveSeekParams {
  timeMs?: number | string | null;
  timeline?: string | null;
  isScene?: boolean;
  isSegment?: boolean;
  asset?: MinimalMediaAsset | null;
  segmentId?: string | null;
  episodeId?: string | null;
  sceneStartMs?: number | null;
  segmentStartMs?: number | null;
}

export function resolveMediaSeekSeconds(params: ResolveSeekParams): number | null {
  const {
    timeMs,
    timeline,
    isScene,
    isSegment,
    asset,
    segmentId,
    episodeId,
    sceneStartMs,
    segmentStartMs,
  } = params;

  const isFileTimeline = timeline === 'file' || (isScene && !isSegment);

  if (timeMs !== undefined && timeMs !== null && timeMs !== '') {
    const num = Number(timeMs);
    if (!isNaN(num) && isFinite(num) && num >= 0) {
      if (isFileTimeline) {
        return num / 1000;
      }
      return resolveFileTimestamp(num, asset, segmentId, episodeId);
    }
    return null;
  }

  if (isScene && sceneStartMs !== undefined && sceneStartMs !== null) {
    if (typeof sceneStartMs === 'number' && !isNaN(sceneStartMs) && isFinite(sceneStartMs) && sceneStartMs >= 0) {
      return sceneStartMs / 1000;
    }
    return null;
  }

  if (isSegment && segmentStartMs !== undefined && segmentStartMs !== null) {
    if (typeof segmentStartMs === 'number' && !isNaN(segmentStartMs) && isFinite(segmentStartMs) && segmentStartMs >= 0) {
      return resolveFileTimestamp(segmentStartMs, asset, segmentId, episodeId);
    }
    return null;
  }

  return null;
}

export function buildMediaItemHref(item: Partial<Movie> | MediaNavigationContext | null | undefined): string {
  if (!item) return '/movies';

  const rawId = typeof item.id === 'string' ? item.id.trim() : '';
  const rawType = (
    typeof item.item_type === 'string'
      ? item.item_type
      : typeof item.type === 'string'
      ? item.type
      : ''
  ).toLowerCase().trim();

  const seriesId = (
    typeof item.series_id === 'string' && item.series_id.trim()
      ? item.series_id.trim()
      : typeof item.seriesId === 'string' && item.seriesId.trim()
      ? item.seriesId.trim()
      : ''
  );

  const episodeId = (
    typeof item.episode_id === 'string' && item.episode_id.trim()
      ? item.episode_id.trim()
      : typeof item.episodeId === 'string' && item.episodeId.trim()
      ? item.episodeId.trim()
      : ''
  );

  const segmentId = (
    typeof item.segment_id === 'string' && item.segment_id.trim()
      ? item.segment_id.trim()
      : typeof item.segmentId === 'string' && item.segmentId.trim()
      ? item.segmentId.trim()
      : ''
  );

  const sceneId = (
    typeof item.scene_id === 'string' && item.scene_id.trim()
      ? item.scene_id.trim()
      : typeof item.sceneId === 'string' && item.sceneId.trim()
      ? item.sceneId.trim()
      : ''
  );

  const assetId = (
    typeof item.media_asset_id === 'string' && item.media_asset_id.trim()
      ? item.media_asset_id.trim()
      : typeof item.mediaAssetId === 'string' && item.mediaAssetId.trim()
      ? item.mediaAssetId.trim()
      : typeof item.primary_media_asset_id === 'string' && item.primary_media_asset_id.trim()
      ? item.primary_media_asset_id.trim()
      : typeof item.primaryMediaAssetId === 'string' && item.primaryMediaAssetId.trim()
      ? item.primaryMediaAssetId.trim()
      : ''
  );

  const rawStart = item.start_ms !== undefined ? item.start_ms : item.startMs;
  const isValidTimestamp = (
    typeof rawStart === 'number' &&
    !isNaN(rawStart) &&
    isFinite(rawStart) &&
    rawStart >= 0
  );

  const explicitTimeline = (
    typeof item.timeline === 'string' && item.timeline.trim()
      ? item.timeline.trim().toLowerCase()
      : typeof item.timescale === 'string' && item.timescale.trim()
      ? item.timescale.trim().toLowerCase()
      : ''
  );

  let effectiveType = rawType;
  if (!effectiveType) {
    if (segmentId) effectiveType = 'segment';
    else if (sceneId) effectiveType = 'scene';
    else if (seriesId && rawId && seriesId !== rawId) effectiveType = 'episode';
    else if (seriesId && rawId && seriesId === rawId) effectiveType = 'series';
    else effectiveType = 'movie';
  }

  if (effectiveType === 'series') {
    const targetSeriesId = seriesId || rawId;
    if (targetSeriesId) {
      return `/series/${encodeURIComponent(targetSeriesId)}`;
    }
    return rawId ? `/movies/${encodeURIComponent(rawId)}` : '/movies';
  }

  if (effectiveType === 'episode') {
    const targetEpisodeId = episodeId || rawId;
    if (seriesId && targetEpisodeId) {
      const params = new URLSearchParams();
      params.set('episode', targetEpisodeId);
      if (assetId) {
        params.set('asset', assetId);
      }
      return `/series/${encodeURIComponent(seriesId)}?${params.toString()}`;
    }
    return rawId ? `/movies/${encodeURIComponent(rawId)}` : '/movies';
  }

  if (effectiveType === 'segment' || effectiveType === 'scene') {
    const isSegment = effectiveType === 'segment';
    const subItemId = isSegment ? (segmentId || rawId) : (sceneId || rawId);
    const parentEpisodeId = episodeId || '';

    if (seriesId && parentEpisodeId) {
      const params = new URLSearchParams();
      params.set('episode', parentEpisodeId);
      if (isSegment && subItemId) {
        params.set('segment', subItemId);
      } else if (!isSegment && subItemId) {
        params.set('scene', subItemId);
      }
      if (assetId) {
        params.set('asset', assetId);
      }
      if (isValidTimestamp) {
        params.set('t', String(rawStart));
        if (explicitTimeline === 'file' || !isSegment) {
          params.set('timeline', 'file');
        }
      }
      return `/series/${encodeURIComponent(seriesId)}?${params.toString()}`;
    }
    return rawId ? `/movies/${encodeURIComponent(rawId)}` : '/movies';
  }

  if (rawId) {
    return `/movies/${encodeURIComponent(rawId)}`;
  }
  return '/movies';
}
