'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import {
  Film,
  Play,
  Clock,
  Calendar,
  Layers,
  ChevronRight,
  Sparkles,
  ArrowLeft,
  Volume2,
  VolumeX,
  Maximize2,
  RotateCcw,
  AlertCircle,
  Tag,
  Users,
} from 'lucide-react';
import {
  getCatalogSeriesDetail,
  getCatalogEpisodeDetail,
  CatalogSeriesResponse,
  CatalogEpisodeResponse,
  CatalogEpisode,
  CatalogSegment,
  CatalogScene,
  CatalogMediaAsset,
} from '@/lib/services/catalogService';
import { resolveStreamUrl, requestPlaybackGrant, getStoredAuthToken } from '@/lib/services/mediaService';
import { resolveFileTimestamp, resolveMediaSeekSeconds } from '@/lib/services/mediaRouting';

const formatDuration = (ms?: number) => {
  if (!ms || ms <= 0) return '00:00';
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
};

export default function SeriesDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const seriesId = (params?.id as string) || '';

  // Deep linking parameters
  const targetEpisodeId = searchParams.get('episode');
  const targetSceneId = searchParams.get('scene');
  const targetSegmentId = searchParams.get('segment');
  const targetAssetId = searchParams.get('asset');
  const targetTimeMs = searchParams.get('t');

  const [seriesData, setSeriesData] = useState<CatalogSeriesResponse | null>(null);
  const [selectedEpisode, setSelectedEpisode] = useState<CatalogEpisode | null>(null);
  const [episodeDetail, setEpisodeDetail] = useState<CatalogEpisodeResponse | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<CatalogMediaAsset | null>(null);

  const [isLoadingSeries, setIsLoadingSeries] = useState<boolean>(true);
  const [isLoadingEpisode, setIsLoadingEpisode] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [playbackWarning, setPlaybackWarning] = useState<string | null>(null);

  // Player state
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(0);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [activeSceneId, setActiveSceneId] = useState<string | null>(null);
  const [activeSegmentId, setActiveSegmentId] = useState<string | null>(null);

  interface PendingSeekIdentity {
    seriesId: string;
    episodeId: string;
    assetId: string;
    sceneId?: string | null;
    segmentId?: string | null;
    targetSec: number;
    generation: number;
  }

  // Race condition & deep-link guard refs
  const episodeGenRef = useRef<number>(0);
  const seriesGenRef = useRef<number>(0);
  const playGenRef = useRef<number>(0);
  const pendingSeekRef = useRef<PendingSeekIdentity | null>(null);
  const initialDeepLinkHandledRef = useRef<boolean>(false);
  const prevUrlEpisodeIdRef = useRef<string | null>(targetEpisodeId);

  // Unmount cleanup guard
  useEffect(() => {
    return () => {
      pendingSeekRef.current = null;
    };
  }, []);

  // Reset deep-link handling when search params change
  useEffect(() => {
    initialDeepLinkHandledRef.current = false;
  }, [targetEpisodeId, targetAssetId, targetSceneId, targetSegmentId, targetTimeMs]);

  // Load series data with AbortController and generation guard
  useEffect(() => {
    if (!seriesId) return;
    setIsLoadingSeries(true);
    setError(null);

    const currentSeriesGen = ++seriesGenRef.current;
    const controller = new AbortController();

    getCatalogSeriesDetail(seriesId, undefined, controller.signal)
      .then((data) => {
        if (currentSeriesGen !== seriesGenRef.current) return;
        if (!data) {
          setError('Không tìm thấy thông tin bộ hoạt hình.');
        } else {
          setSeriesData(data);
          if (data.episodes && data.episodes.length > 0) {
            let initialEp = data.episodes[0];
            if (targetEpisodeId) {
              const matched = data.episodes.find((e) => e.id === targetEpisodeId);
              if (matched) {
                initialEp = matched;
              }
            }
            setSelectedEpisode(initialEp);
          }
        }
      })
      .catch((err) => {
        if (currentSeriesGen !== seriesGenRef.current || err?.name === 'AbortError') return;
        setError(err?.message || 'Lỗi khi tải thông tin bộ phim.');
      })
      .finally(() => {
        if (currentSeriesGen === seriesGenRef.current) {
          setIsLoadingSeries(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [seriesId]);

  // Synchronize selectedEpisode when targetEpisodeId in URL changes (deep-link or back/forward)
  useEffect(() => {
    if (!seriesData?.episodes) return;
    if (targetEpisodeId !== prevUrlEpisodeIdRef.current) {
      prevUrlEpisodeIdRef.current = targetEpisodeId;
      if (targetEpisodeId) {
        const matched = seriesData.episodes.find((e) => e.id === targetEpisodeId);
        if (matched) {
          setSelectedEpisode(matched);
        }
      } else if (seriesData.episodes.length > 0) {
        setSelectedEpisode(seriesData.episodes[0]);
      }
    }
  }, [targetEpisodeId, seriesData]);

  // Manual episode selection handler that updates state and keeps URL in sync without page reloads
  const handleSelectEpisode = (ep: CatalogEpisode) => {
    if (ep.id === selectedEpisode?.id) return;
    setSelectedEpisode(ep);

    try {
      const currentUrl = new URL(window.location.href);
      currentUrl.searchParams.set('episode', ep.id);
      currentUrl.searchParams.delete('scene');
      currentUrl.searchParams.delete('segment');
      currentUrl.searchParams.delete('t');
      currentUrl.searchParams.delete('timeline');
      currentUrl.searchParams.delete('timescale');
      currentUrl.searchParams.delete('asset');
      window.history.replaceState(null, '', currentUrl.toString());
    } catch {
      // Safe fallback in SSR or non-browser environments
    }
  };

  // Load episode detail when selectedEpisode changes (with race condition prevention & AbortSignal)
  useEffect(() => {
    pendingSeekRef.current = null;
    setPlaybackWarning(null);
    setActiveSegmentId(null);
    if (!selectedEpisode?.id) return;
    setIsLoadingEpisode(true);
    // Immediately clear active asset and scenes of old episode to eliminate race conditions
    setEpisodeDetail(null);
    setSelectedAsset(null);
    setActiveSceneId(null);

    const currentGen = ++episodeGenRef.current;
    const controller = new AbortController();

    getCatalogEpisodeDetail(selectedEpisode.id, undefined, controller.signal)
      .then((detail) => {
        if (currentGen !== episodeGenRef.current) return;
        if (detail) {
          setEpisodeDetail(detail);

          // Only apply URL targetSceneId / targetSegmentId / targetTimeMs / targetAssetId
          // if this selected episode matches the URL's targetEpisodeId!
          const isUrlEpisode = targetEpisodeId ? detail.episode.id === targetEpisodeId : false;

          // Select asset based on deep-link or default to first
          let assetToSelect: CatalogMediaAsset | null = null;
          if (isUrlEpisode && targetAssetId && detail.mediaAssets) {
            assetToSelect = detail.mediaAssets.find((a) => a.id === targetAssetId) || null;
          }
          if (!assetToSelect && isUrlEpisode && targetSceneId && detail.scenes && detail.mediaAssets) {
            const sc = detail.scenes.find((s) => s.id === targetSceneId);
            if (sc?.mediaAssetId) {
              assetToSelect = detail.mediaAssets.find((a) => a.id === sc.mediaAssetId) || null;
            }
          }
          if (!assetToSelect && detail.mediaAssets && detail.mediaAssets.length > 0) {
            assetToSelect = detail.mediaAssets[0];
          }
          setSelectedAsset(assetToSelect);

          // Handle initial deep-link seek only for the URL's target episode
          if (isUrlEpisode && !initialDeepLinkHandledRef.current && assetToSelect) {
            initialDeepLinkHandledRef.current = true;
            const sc = targetSceneId && detail.scenes ? detail.scenes.find((s) => s.id === targetSceneId) : undefined;
            const seg = targetSegmentId && detail.segments ? detail.segments.find((s) => s.id === targetSegmentId) : undefined;

            const seekSec = resolveMediaSeekSeconds({
              timeMs: targetTimeMs,
              timeline: searchParams.get('timeline') || searchParams.get('timescale'),
              isScene: !!targetSceneId,
              isSegment: !!targetSegmentId,
              asset: assetToSelect,
              segmentId: targetSegmentId || undefined,
              episodeId: detail.episode.id,
              sceneStartMs: sc?.startMs,
              segmentStartMs: seg?.episodeStartMs,
            });

            if (targetSegmentId && seg) {
              setActiveSegmentId(seg.id);
              if (seekSec === null) {
                setPlaybackWarning(`Phân đoạn [${seg.title || seg.id}] chưa xác định thời điểm bắt đầu (episode_start_ms = null).`);
              }
            }
            if (targetSceneId && sc) {
              setActiveSceneId(sc.id);
              if (seekSec === null) {
                setPlaybackWarning(`Phân cảnh [${sc.title || sc.id}] chưa xác định thời điểm bắt đầu (start_ms = null).`);
              }
            }

            if (seekSec !== null && !isNaN(seekSec) && isFinite(seekSec) && seekSec >= 0) {
              pendingSeekRef.current = {
                seriesId: String(seriesId),
                episodeId: detail.episode.id,
                assetId: assetToSelect.id,
                sceneId: targetSceneId || null,
                segmentId: targetSegmentId || null,
                targetSec: seekSec,
                generation: ++playGenRef.current,
              };
            }
          }
        }
      })
      .catch((err) => {
        if (currentGen !== episodeGenRef.current || err?.name === 'AbortError') return;
      })
      .finally(() => {
        if (currentGen === episodeGenRef.current) {
          setIsLoadingEpisode(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [selectedEpisode?.id, targetAssetId, targetSceneId, targetSegmentId, targetTimeMs, seriesId, targetEpisodeId]);

  // Video stream URL resolution with short-lived playback grant for protected media (H4)
  const [streamUrl, setStreamUrl] = useState<string>('');

  useEffect(() => {
    if (!selectedAsset?.id) {
      setStreamUrl('');
      return;
    }
    const currentAssetId = selectedAsset.id;
    const defaultUrl = resolveStreamUrl(`/api/media/stream/${currentAssetId}`);
    const token = getStoredAuthToken();
    const isProtected = selectedAsset.accessPolicy && selectedAsset.accessPolicy !== 'public';

    if (token || isProtected) {
      const ac = new AbortController();
      requestPlaybackGrant(currentAssetId, ac.signal)
        .then((grant) => {
          if (ac.signal.aborted) return;
          if (grant?.streamUrl) {
            setPlaybackWarning(null);
            setStreamUrl(grant.streamUrl);
          } else if (isProtected) {
            setStreamUrl('');
            setPlaybackWarning('Video được bảo vệ (authenticated/private). Vui lòng đăng nhập với tài khoản có quyền để xem video.');
          } else {
            setStreamUrl(defaultUrl);
          }
        })
        .catch(() => {
          if (ac.signal.aborted) return;
          if (isProtected) {
            setStreamUrl('');
            setPlaybackWarning('Không thể lấy quyền phát video bảo vệ. Vui lòng thử lại sau.');
          } else {
            setStreamUrl(defaultUrl);
          }
        });
      return () => {
        ac.abort();
      };
    } else {
      setStreamUrl(defaultUrl);
    }
  }, [selectedAsset?.id, selectedAsset?.accessPolicy]);

  // Seek video to specific scene & switch asset with strict identity guard (F6, G6, H3)
  const handleSeekScene = (scene: CatalogScene) => {
    setPlaybackWarning(null);
    const currentEpId = selectedEpisode?.id || '';
    const currentGen = ++playGenRef.current;
    const targetSec = scene.startMs / 1000; // Scene start_ms is file timeline directly (H3)

    // Check if scene requires switching media asset
    if (scene.mediaAssetId && episodeDetail?.mediaAssets && selectedAsset?.id !== scene.mediaAssetId) {
      const matchingAsset = episodeDetail.mediaAssets.find((a) => a.id === scene.mediaAssetId);
      if (matchingAsset) {
        pendingSeekRef.current = {
          seriesId: String(seriesId),
          episodeId: currentEpId,
          assetId: matchingAsset.id,
          sceneId: scene.id,
          targetSec,
          generation: currentGen,
        };
        setActiveSceneId(scene.id);
        setSelectedAsset(matchingAsset);
        return; // Do NOT manipulate currentTime on existing asset video element!
      } else {
        // Missing scene asset: DO NOT seek on an unrelated asset!
        setPlaybackWarning(
          `Phân cảnh [${scene.title || scene.id}] thuộc tệp phát [${scene.mediaAssetId}] không có trong tập này.`
        );
        return;
      }
    }

    setActiveSceneId(scene.id);

    // Same asset: apply seek directly if metadata ready, otherwise queue
    if (videoRef.current && videoRef.current.readyState >= 1) {
      const dur = videoRef.current.duration || 0;
      const clamped = dur > 0 ? Math.min(targetSec, Math.max(0, dur - 0.5)) : targetSec;
      videoRef.current.currentTime = clamped;
      videoRef.current.play().catch(() => {});
      setIsPlaying(true);
      pendingSeekRef.current = null;
    } else {
      pendingSeekRef.current = {
        seriesId: String(seriesId),
        episodeId: currentEpId,
        assetId: selectedAsset?.id || '',
        sceneId: scene.id,
        targetSec,
        generation: currentGen,
      };
    }
  };

  // Seek video to specific segment (truyện ngắn / phân đoạn) via coverage timestamp (H3)
  const handleSeekSegment = (segment: CatalogSegment) => {
    setPlaybackWarning(null);
    setActiveSegmentId(segment.id);
    if (typeof segment.episodeStartMs !== 'number' || isNaN(segment.episodeStartMs)) {
      setPlaybackWarning(`Phân đoạn [${segment.title || segment.id}] chưa xác định thời điểm bắt đầu (episode_start_ms = null).`);
      return;
    }
    const targetSec = resolveFileTimestamp(segment.episodeStartMs, selectedAsset, segment.id, selectedEpisode?.id);
    if (targetSec === null) {
      setPlaybackWarning(
        `Không thể tua: Mốc thời gian phân đoạn chưa xác định hoặc không có coverage tương ứng trên tệp video đang phát.`
      );
      return;
    }
    const currentEpId = selectedEpisode?.id || '';
    const currentGen = ++playGenRef.current;

    if (videoRef.current && videoRef.current.readyState >= 1) {
      const dur = videoRef.current.duration || 0;
      const clamped = dur > 0 ? Math.min(targetSec, Math.max(0, dur - 0.5)) : targetSec;
      videoRef.current.currentTime = clamped;
      videoRef.current.play().catch(() => {});
      setIsPlaying(true);
      pendingSeekRef.current = null;
    } else {
      pendingSeekRef.current = {
        seriesId: String(seriesId),
        episodeId: currentEpId,
        assetId: selectedAsset?.id || '',
        sceneId: null,
        targetSec,
        generation: currentGen,
      };
    }
  };

  const handleLoadedMetadata = () => {
    const pending = pendingSeekRef.current;
    if (!pending || !videoRef.current) return;

    // Strict identity tuple & generation verification (F6, G6)
    if (
      pending.generation === playGenRef.current &&
      pending.seriesId === String(seriesId) &&
      pending.episodeId === selectedEpisode?.id &&
      pending.assetId === selectedAsset?.id
    ) {
      const dur = videoRef.current.duration || 0;
      const clamped = dur > 0 ? Math.min(pending.targetSec, Math.max(0, dur - 0.5)) : pending.targetSec;
      videoRef.current.currentTime = clamped;
      videoRef.current.play().catch(() => {});
      setIsPlaying(true);
      if (pending.sceneId) {
        setActiveSceneId(pending.sceneId);
      }
      if (pending.segmentId) {
        setActiveSegmentId(pending.segmentId);
      }
      pendingSeekRef.current = null;
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const cur = videoRef.current.currentTime;
      setCurrentTime(cur);
      setDuration(videoRef.current.duration || 0);

      const curMs = cur * 1000;

      // Highlight active scene matching current media asset
      if (episodeDetail?.scenes) {
        const matching = episodeDetail.scenes.find(
          (s) => curMs >= s.startMs && curMs < s.endMs && (!selectedAsset || !s.mediaAssetId || s.mediaAssetId === selectedAsset.id)
        );
        setActiveSceneId(matching ? matching.id : null);
      }

      // Highlight active segment
      if (episodeDetail?.segments) {
        const matchingSeg = episodeDetail.segments.find((seg) => {
          const sStart = seg.episodeStartMs ?? 0;
          const sEnd = seg.episodeEndMs ?? Infinity;
          return curMs >= sStart && curMs < sEnd;
        });
        setActiveSegmentId(matchingSeg ? matchingSeg.id : null);
      }
    }
  };

  if (isLoadingSeries) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-muted">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand border-t-transparent" />
          <span>Đang nạp dữ liệu bộ hoạt hình...</span>
        </div>
      </div>
    );
  }

  if (error || !seriesData) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <AlertCircle size={40} className="mx-auto text-red-400" />
        <h2 className="mt-4 text-xl font-bold text-ink">Lỗi hiển thị bộ phim</h2>
        <p className="mt-2 text-sm text-muted">{error || 'Không tìm thấy dữ liệu bộ phim.'}</p>
        <Link href="/admin/import" className="btn-secondary mt-6 inline-flex items-center gap-2 text-xs">
          <ArrowLeft size={14} />
          <span>Quay lại trang quản lý</span>
        </Link>
      </div>
    );
  }

  const { series, seasons, episodes } = seriesData;

  return (
    <main className="series-page mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Breadcrumb Navigation */}
      <div className="mb-6 flex items-center gap-2 text-xs text-muted">
        <Link href="/" className="hover:text-ink transition-colors">Trang chủ</Link>
        <ChevronRight size={12} />
        <Link href="/search" className="hover:text-ink transition-colors">Kho phim</Link>
        <ChevronRight size={12} />
        <span className="text-ink font-medium">{series.title}</span>
      </div>

      {/* Series Hero Metadata Card */}
      <div className="rounded-xl border border-surface-border bg-surface p-6 shadow-md mb-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded bg-brand/10 px-2 py-0.5 text-xs font-bold text-brand border border-brand/20">
                Bộ Hoạt Hình
              </span>
              {series.releaseYearStart && (
                <span className="rounded bg-surface-elevated px-2 py-0.5 text-xs text-muted border border-surface-border">
                  Năm {series.releaseYearStart}
                  {series.releaseYearEnd ? ` - ${series.releaseYearEnd}` : ''}
                </span>
              )}
            </div>

            <h1 className="mt-2 text-2xl font-extrabold text-ink sm:text-3xl">
              {series.title}
            </h1>
            {series.originalTitle && (
              <p className="text-xs text-muted italic">Tên gốc: {series.originalTitle}</p>
            )}

            {series.synopsis && (
              <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">
                {series.synopsis}
              </p>
            )}

            {/* Tags / Genres / Keywords */}
            <div className="mt-4 flex flex-wrap items-center gap-2">
              {series.genreIds && (
                <div className="flex items-center gap-1.5 text-xs text-muted">
                  <Tag size={12} className="text-brand" />
                  <span>Thể loại:</span>
                  <span className="text-ink font-medium">{series.genreIds}</span>
                </div>
              )}
              {series.studios && (
                <div className="ml-4 flex items-center gap-1.5 text-xs text-muted">
                  <span>Studio:</span>
                  <span className="text-ink font-medium">{series.studios}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Layout: Player & Episode Detail */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Left 2 Cols: Video Player & Scene Navigator */}
        <div className="lg:col-span-2 space-y-6">
          {/* Playback Warning Banner */}
          {playbackWarning && (
            <div className="flex items-center justify-between gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300">
              <div className="flex items-center gap-2">
                <AlertCircle size={16} className="text-amber-400 shrink-0" />
                <span>{playbackWarning}</span>
              </div>
              <button
                onClick={() => setPlaybackWarning(null)}
                className="text-muted hover:text-ink"
              >
                ✕
              </button>
            </div>
          )}

          {/* Production Video Player */}
          <div className="relative overflow-hidden rounded-xl border border-surface-border bg-black shadow-2xl aspect-video flex items-center justify-center">
            {streamUrl ? (
              <video
                ref={videoRef}
                data-testid="series-video-player"
                src={streamUrl}
                controls
                playsInline
                onLoadedMetadata={handleLoadedMetadata}
                onCanPlay={handleLoadedMetadata}
                onTimeUpdate={handleTimeUpdate}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                className="h-full w-full object-contain"
              />
            ) : (
              <div className="flex flex-col items-center justify-center text-center p-6 text-zinc-200">
                <Film size={36} className="mb-2 text-zinc-400" />
                <p className="text-xs">Tập này chưa có luồng video Google Drive được cấu hình.</p>
              </div>
            )}
          </div>

          {/* Episode Info & Media Assets Selector */}
          {selectedEpisode && (
            <div className="rounded-xl border border-surface-border bg-surface p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-surface-border pb-3">
                <div>
                  <span className="text-xs font-bold text-brand">
                    Tập {selectedEpisode.number ?? selectedEpisode.episodeNumber}
                  </span>
                  <h2 className="text-lg font-bold text-ink">{selectedEpisode.title}</h2>
                </div>
                {selectedEpisode.durationMs && (
                  <span className="flex items-center gap-1 rounded bg-surface-elevated px-2 py-1 text-xs text-muted border border-surface-border">
                    <Clock size={12} />
                    {formatDuration(selectedEpisode.durationMs)}
                  </span>
                )}
              </div>

              {selectedEpisode.synopsis && (
                <p className="mt-3 text-xs leading-relaxed text-muted">
                  {selectedEpisode.synopsis}
                </p>
              )}

              {/* Media Assets (Storage info: Google Drive) */}
              {episodeDetail?.mediaAssets && episodeDetail.mediaAssets.length > 0 && (
                <div className="mt-4 pt-3 border-t border-surface-border flex items-center gap-2 text-xs">
                  <span className="text-muted">Nguồn phát:</span>
                  {episodeDetail.mediaAssets.map((asset) => (
                    <button
                      key={asset.id}
                      data-testid="media-asset-button"
                      data-asset-id={asset.id}
                      onClick={() => setSelectedAsset(asset)}
                      className={`rounded px-2.5 py-1 text-xs font-semibold transition-colors cursor-pointer border ${
                        selectedAsset?.id === asset.id
                          ? 'border-brand bg-brand/10 text-brand'
                          : 'border-surface-border bg-surface-elevated text-muted hover:text-ink'
                      }`}
                    >
                      {asset.storageProvider === 'drive' ? 'Google Drive Video' : 'Local Video'} [{asset.id}]
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Segments List with Seek Trigger */}
          {episodeDetail?.segments && episodeDetail.segments.length > 0 && (
            <div className="rounded-xl border border-surface-border bg-surface p-5">
              <div className="flex items-center justify-between border-b border-surface-border pb-3">
                <div className="flex items-center gap-2">
                  <Layers size={16} className="text-brand" />
                  <h3 className="text-sm font-bold text-ink">
                    Truyện ngắn / Phân đoạn ({episodeDetail.segments.length})
                  </h3>
                </div>
                <span className="text-xs text-muted">Nhấp vào phân đoạn để tua video</span>
              </div>

              <div className="mt-3 divide-y divide-surface-border">
                {episodeDetail.segments.map((seg) => {
                  const isActive = activeSegmentId === seg.id;
                  const timeLabel =
                    seg.episodeStartMs !== undefined
                      ? `${formatDuration(seg.episodeStartMs)}${seg.episodeEndMs ? ` – ${formatDuration(seg.episodeEndMs)}` : ''}`
                      : `Phân đoạn ${seg.position}`;
                  return (
                    <div
                      key={seg.id}
                      data-segment-id={seg.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => handleSeekSegment(seg)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          handleSeekSegment(seg);
                        }
                      }}
                      className={`flex items-start justify-between gap-4 p-3 rounded-lg transition-colors cursor-pointer outline-none focus:ring-2 focus:ring-brand ${
                        isActive
                          ? 'bg-brand/15 border border-brand/30'
                          : 'hover:bg-surface-hover/60 border border-transparent'
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-brand">
                            {timeLabel}
                          </span>
                          <span className="text-xs font-bold text-ink">
                            {seg.title || `Phân đoạn ${seg.position}`}
                          </span>
                        </div>
                        {seg.synopsis && (
                          <p className="text-xs text-muted line-clamp-2">
                            {seg.synopsis}
                          </p>
                        )}
                      </div>

                      <span className="btn-secondary flex items-center gap-1 text-[11px] font-semibold shrink-0 py-1 px-2.5 pointer-events-none">
                        <Play size={11} className="text-brand" />
                        <span>Tua tới</span>
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Scenes List with Seek Trigger */}
          {episodeDetail?.scenes && episodeDetail.scenes.length > 0 && (
            <div className="rounded-xl border border-surface-border bg-surface p-5">
              <div className="flex items-center justify-between border-b border-surface-border pb-3">
                <div className="flex items-center gap-2">
                  <Sparkles size={16} className="text-brand" />
                  <h3 className="text-sm font-bold text-ink">
                    Phân cảnh chi tiết ({episodeDetail.scenes.length})
                  </h3>
                </div>
                <span className="text-xs text-muted">Nhấp vào phân cảnh để tua video</span>
              </div>

              <div className="mt-3 divide-y divide-surface-border">
                {episodeDetail.scenes.map((scene) => {
                  const isActive = activeSceneId === scene.id;
                  const timeLabel = `${formatDuration(scene.startMs)} – ${formatDuration(scene.endMs)}`;
                  return (
                    <div
                      key={scene.id}
                      data-scene-id={scene.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => handleSeekScene(scene)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          handleSeekScene(scene);
                        }
                      }}
                      className={`flex items-start justify-between gap-4 p-3 rounded-lg transition-colors cursor-pointer outline-none focus:ring-2 focus:ring-brand ${
                        isActive
                          ? 'bg-brand/15 border border-brand/30'
                          : 'hover:bg-surface-hover/60 border border-transparent'
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-brand">
                            {timeLabel}
                          </span>
                          <span className="text-xs font-bold text-ink">
                            {scene.title || 'Phân cảnh'}
                          </span>
                        </div>
                        {scene.visualDescription && (
                          <p className="text-xs text-muted line-clamp-2">
                            {scene.visualDescription}
                          </p>
                        )}
                        {scene.summary && !scene.visualDescription && (
                          <p className="text-xs text-muted line-clamp-2">
                            {scene.summary}
                          </p>
                        )}
                      </div>

                      <span
                        className="btn-secondary flex items-center gap-1 text-[11px] font-semibold shrink-0 py-1 px-2.5 pointer-events-none"
                      >
                        <Play size={11} className="text-brand" />
                        <span>Tua tới</span>
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Right Col: Episodes List */}
        <div className="space-y-6">
          <div className="rounded-xl border border-surface-border bg-surface p-5">
            <div className="flex items-center justify-between border-b border-surface-border pb-3">
              <div className="flex items-center gap-2">
                <Layers size={16} className="text-brand" />
                <h3 className="text-sm font-bold text-ink">
                  Danh sách tập ({episodes.length})
                </h3>
              </div>
            </div>

            <div className="mt-3 space-y-2 max-h-[600px] overflow-y-auto">
              {episodes.map((ep) => {
                const isSelected = selectedEpisode?.id === ep.id;
                return (
                  <button
                    key={ep.id}
                    data-episode-id={ep.id}
                    aria-pressed={isSelected}
                    onClick={() => handleSelectEpisode(ep)}
                    className={`flex w-full items-start justify-between gap-3 rounded-lg p-3 text-left transition-colors cursor-pointer border ${
                      isSelected
                        ? 'border-brand bg-brand/10 text-ink'
                        : 'border-surface-border bg-surface-elevated text-muted hover:bg-surface-hover hover:text-ink'
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="grid h-5 w-5 place-items-center rounded bg-surface text-[10px] font-bold text-brand border border-surface-border">
                          {ep.number ?? ep.episodeNumber}
                        </span>
                        <strong className="text-xs font-semibold">{ep.title}</strong>
                      </div>
                      {ep.synopsis && (
                        <p className="mt-1 line-clamp-2 text-[11px] text-muted">
                          {ep.synopsis}
                        </p>
                      )}
                    </div>

                    {ep.durationMs && (
                      <span className="font-mono text-[10px] text-muted shrink-0">
                        {formatDuration(ep.durationMs)}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
