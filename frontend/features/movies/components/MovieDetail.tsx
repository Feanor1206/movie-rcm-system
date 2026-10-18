'use client';

import React, { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import {
  Play,
  Star,
  Loader2,
  RefreshCw,
  AlertCircle,
  Film,
} from 'lucide-react';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';
import { getMediaDescriptor, MediaDescriptor, resolveStreamUrl } from '@/lib/services/mediaService';
import { MovieSection } from './MovieSection';

const BTN_ACT = 'min-h-[44px] inline-flex items-center justify-center rounded border cursor-pointer disabled:opacity-60';
const BTN_PLAY = 'min-h-[44px] px-4 py-2 text-xs font-bold inline-flex items-center justify-center gap-1.5 cursor-pointer';
const BTN_FEAT = `btn-primary ${BTN_PLAY}`;
const BTN_PRI = `btn-primary min-h-[44px] ${BTN_PLAY}`;
const BTN_SEC = `btn-secondary text-zinc-300 ${BTN_PLAY}`;
const BTN_SQ = 'flex h-11 w-11 min-h-[44px] min-w-[44px] items-center justify-center rounded cursor-pointer';
const BTN_ICON = `${BTN_SQ} text-zinc-300 hover:text-white`;
const BTN_PLAY_PAUSE = `${BTN_SQ} bg-brand text-zinc-950 font-bold`;
const UNCONF_CLS = 'border-amber-400 bg-amber-400/20 text-amber-300';
const ALERT_BOX = 'mt-4 flex items-center justify-between gap-2 rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-200';
const ALERT_BTN = 'flex items-center gap-1 rounded bg-amber-500/20 px-2 py-1 text-xs font-bold text-amber-300 cursor-pointer shrink-0';
const SLIDER_CLS = 'h-2 rounded cursor-pointer bg-zinc-700 accent-emerald-500 min-h-[44px]';
const FOCUS_SEL = 'button:not([disabled]), input:not([disabled]), video, [tabindex]:not([tabindex="-1"])';
const STARS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
const STAR_BASE = 'flex h-9 w-9 items-center justify-center rounded text-xs font-bold cursor-pointer disabled:opacity-60';
const STAR_ACT = `${STAR_BASE} bg-amber-400 text-black`;
const STAR_INACT = `${STAR_BASE} border border-surface-border bg-surface-muted text-zinc-400`;
const BTN_WATCH = `${BTN_ACT} px-4 py-2 text-sm font-semibold`;
const WATCH_CONF = `${BTN_WATCH} btn-secondary text-white`;
const WATCH_DEF = `${BTN_WATCH} btn-secondary text-zinc-300`;
const WATCH_UNCONF = `${BTN_WATCH} ${UNCONF_CLS}`;
const BTN_FAV_BASE = `${BTN_ACT} min-w-[44px] p-2`;
const FAV_CONF = `${BTN_FAV_BASE} border-brand bg-brand/15 text-brand`;
const FAV_DEF = `${BTN_FAV_BASE} border-zinc-700 bg-surface text-zinc-300 hover:text-white`;
const FAV_UNCONF = `${BTN_FAV_BASE} ${UNCONF_CLS}`;
const formatTime = (s: number) => s > 0 ? `${Math.floor(s / 60)}`.padStart(2, '0') + ':' + `${Math.floor(s % 60)}`.padStart(2, '0') : '00:00';
const CARD = 'rounded-lg border border-surface-border bg-surface p-4';
const BORDER_T = 'pt-2 border-t border-surface-border';
const STREAM_ERR = 'Không thể nạp luồng phát video.';
const CHAT_BTN = `border border-zinc-700 bg-surface text-zinc-300 ${BTN_PLAY}`;
const Icon = ({ d, fill = 'none', s = 18, c }: { d: string; fill?: string; s?: number; c?: string }) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill={fill} stroke="currentColor" strokeWidth={2} className={c}><path d={d} /></svg>
);

export function MovieDetail({
  movie,
  similarMovies,
}: {
  movie: Movie;
  similarMovies: Movie[];
}) {
  const {
    isWatchlisted,
    toggleWatchlist,
    isFavorite,
    toggleFavorite,
    getRating,
    rateMovie,
    removeRating,
    isActionPending,
    isActionUnconfirmed,
    getActionIntent,
    getUnconfirmedRating,
    openChat,
  } = useWatchlist();
  const [hoverRating, setHoverRating] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [posterError, setPosterError] = useState(false);
  const [backdropError, setBackdropError] = useState(false);
  const [descriptor, setDescriptor] = useState<MediaDescriptor | null>(null);
  const [descriptorLoading, setDescriptorLoading] = useState(true);
  const [descriptorError, setDescriptorError] = useState<string | null>(null);
  const [descriptorNonce, setDescriptorNonce] = useState(0);
  const [activeMediaKind, setActiveMediaKind] = useState<'feature' | 'trailer'>('trailer');
  const [activeMediaUrl, setActiveMediaUrl] = useState<string>('');
  const [playerState, setPlayerState] = useState<'idle' | 'loading' | 'buffering' | 'playing' | 'paused' | 'error'>('idle');
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(0);
  const [volume, setVolume] = useState<number>(1);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [playbackError, setPlaybackError] = useState<string | null>(null);
  const [retryTime, setRetryTime] = useState<number>(0);

  const videoRef = useRef<HTMLVideoElement>(null);
  const videoModalRef = useRef<HTMLDivElement>(null);
  const playButtonRef = useRef<HTMLButtonElement>(null);
  const playerOpenerRef = useRef<HTMLElement | null>(null);

  // Fetch descriptor for movie
  useEffect(() => {
    setDescriptor(null);
    setDescriptorError(null);
    setDescriptorLoading(true);
    setIsPlaying(false);
    setActiveMediaUrl('');
    setPlayerState('idle');
    setPlaybackError(null);
    setCurrentTime(0);
    setDuration(0);
    setRetryTime(0);

    const abortController = typeof AbortController !== 'undefined' ? new AbortController() : null;
    let mounted = true;

    const fail = () => {
      setDescriptor(null);
      setDescriptorLoading(false);
      setDescriptorError('Lỗi tải thông tin phát phim. Vui lòng thử lại.');
    };

    getMediaDescriptor(movie.id, { signal: abortController?.signal })
      .then((desc) => {
        if (!mounted || abortController?.signal.aborted) return;
        if (
          desc &&
          desc.movieId === movie.id &&
          typeof desc.hasFeature === 'boolean' &&
          typeof desc.hasTrailer === 'boolean' &&
          (!desc.hasFeature || desc.feature?.streamUrl) &&
          (!desc.hasTrailer || desc.trailer?.streamUrl)
        ) {
          setDescriptor(desc);
          setDescriptorLoading(false);
          setDescriptorError(null);
        } else {
          fail();
        }
      })
      .catch(() => {
        if (mounted && !abortController?.signal.aborted) fail();
      });

    return () => {
      mounted = false;
      abortController?.abort();
    };
  }, [movie.id, descriptorNonce]);


  const hasVideo = Boolean(movie.videoUrl?.trim());
  const hasValidFeature = Boolean(descriptor?.movieId === movie.id && descriptor.hasFeature);
  const hasValidTrailer = Boolean(descriptor?.movieId === movie.id && descriptor.hasTrailer);

  const startPlayback = (kind: 'feature' | 'trailer', opener?: HTMLElement | null) => {
    if (opener) playerOpenerRef.current = opener;
    setActiveMediaKind(kind);
    const url = kind === 'feature' ? descriptor?.feature?.streamUrl : (descriptor?.trailer?.streamUrl || movie.videoUrl);
    if (!url) return;
    setActiveMediaUrl(resolveStreamUrl(url));
    setPlayerState('buffering');
    setPlaybackError(null);
    setCurrentTime(0);
    setRetryTime(0);
    setIsPlaying(true);
  };

  const handleRetry = () => {
    setPlaybackError(null);
    setPlayerState('buffering');
    const v = videoRef.current;
    if (!v) return;
    v.load();
    v.addEventListener('loadedmetadata', () => {
      if (retryTime > 0) try { v.currentTime = retryTime; } catch (_) {}
      v.play().catch(() => setPlayerState('paused'));
    }, { once: true });
  };

  const togglePlayPause = () => {
    const v = videoRef.current;
    if (v) v.paused ? (v.play().catch(() => setPlayerState('paused')), setPlayerState('playing')) : (v.pause(), setPlayerState('paused'));
  };

  const toggleMute = () => {
    const v = videoRef.current;
    if (v) setIsMuted(v.muted = !v.muted);
  };

  const toggleFullscreen = () => {
    const m = videoModalRef.current;
    if (m) (document.fullscreenElement ? document.exitFullscreen() : m.requestFullscreen()).catch(() => {});
  };

  const seekBy = (sec: number) => {
    const v = videoRef.current;
    if (v) setCurrentTime(v.currentTime = Math.min(Math.max(0, v.currentTime + sec), v.duration || duration || 100));
  };

  const adjustVolume = (delta: number) => {
    const v = videoRef.current;
    if (v) {
      const vol = Math.min(Math.max(0, v.volume + delta), 1);
      setVolume(vol);
      setIsMuted(v.muted = !vol);
      v.volume = vol;
    }
  };

  // Autoplay rejection handler: transition to paused so user can click to play
  useEffect(() => {
    if (isPlaying && activeMediaUrl) {
      videoRef.current?.play()?.catch((err: any) => {
        if (err?.name !== 'AbortError') setPlayerState('paused');
      });
    }
  }, [isPlaying, activeMediaUrl]);

  // Video modal accessibility: Escape key, body scroll lock, focus trap, focus restoration, shortcuts
  useEffect(() => {
    if (!isPlaying) return;

    if (document.activeElement && !videoModalRef.current?.contains?.(document.activeElement)) {
      playerOpenerRef.current = document.activeElement as HTMLElement | null;
    }

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const timer = setTimeout(() => {
      const focusable = videoModalRef.current?.querySelectorAll<HTMLElement>(FOCUS_SEL);
      if (focusable?.length) focusable[0].focus();
    }, 40);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        setIsPlaying(false);
        return;
      }

      if (e.key === 'Tab' && videoModalRef.current) {
        const focusable = videoModalRef.current.querySelectorAll<HTMLElement>(FOCUS_SEL);
        if (!focusable.length) return;
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (!videoModalRef.current.contains(document.activeElement) || (e.shiftKey ? document.activeElement === first : document.activeElement === last)) {
          e.preventDefault();
          (e.shiftKey ? last : first).focus();
        }
        return;
      }

      const target = e.target as HTMLElement | null, k = e.key;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
      if (k === ' ' || e.code === 'Space') {
        if (target?.tagName !== 'BUTTON') { e.preventDefault(); togglePlayPause(); }
      } else if (k.startsWith('Arrow')) {
        e.preventDefault();
        k === 'ArrowLeft' ? seekBy(-5) : k === 'ArrowRight' ? seekBy(5) : adjustVolume(k === 'ArrowUp' ? 0.1 : -0.1);
      } else if (k.toLowerCase() === 'm') {
        e.preventDefault(); toggleMute();
      } else if (k.toLowerCase() === 'f') {
        e.preventDefault(); toggleFullscreen();
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      clearTimeout(timer);
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
      (playerOpenerRef.current || playButtonRef.current)?.focus();
    };
  }, [isPlaying]);

  const mid = movie.id;
  const inWatchlist = isWatchlisted(mid);
  const favorite = isFavorite(mid);
  const currentRating = getRating(mid);
  const isWatchlistPending = isActionPending(mid, 'watchlist');
  const isFavoritePending = isActionPending(mid, 'favorite');
  const isRatingPending = isActionPending(mid, 'rating');

  const isWatchlistUnconfirmed = isActionUnconfirmed(mid, 'watchlist');
  const isAddWatch = getActionIntent(mid, 'watchlist') === 'add';

  const isFavoriteUnconfirmed = isActionUnconfirmed(mid, 'favorite');
  const isAddFav = getActionIntent(mid, 'favorite') === 'add';

  const isRatingUnconfirmed = isActionUnconfirmed(mid, 'rating');
  const isRate = getActionIntent(mid, 'rating') === 'rate';
  const unconfirmedRatingScore = getUnconfirmedRating(mid);

  const retryDescriptor = () => {
    setDescriptorError(null);
    setDescriptorLoading(true);
    setDescriptorNonce(n => n + 1);
  };

  return (
    <main className="min-h-screen bg-background">
      {/* Video Player Modal / Player Overlay */}
      {isPlaying && (
        <div
          ref={videoModalRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="video-player-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/95 p-4"
        >
          <div className="relative w-full max-w-5xl overflow-hidden rounded-lg border border-surface-border bg-surface flex flex-col">
            {/* Player Header Bar */}
            <div className="flex items-center justify-between border-b border-surface-border bg-surface-muted px-4 py-3">
              <div className="flex items-center gap-2 truncate">
                <span className="h-2.5 w-2.5 rounded-full bg-brand shadow-brand-sm shrink-0" />
                <h3 id="video-player-title" className="text-sm font-bold text-white truncate">
                  {movie.title}
                </h3>
                <span className="text-xs text-zinc-400 shrink-0">
                  • {activeMediaKind === 'feature' ? 'Phim chính' : 'Trailer'}
                </span>
              </div>
              <button
                onClick={() => setIsPlaying(false)}
                className={BTN_ICON}
                aria-label="Đóng trình phát"
              >
                ✕
              </button>
            </div>

            {/* Video Container with Overlays */}
            <div className="relative aspect-video w-full bg-black flex items-center justify-center overflow-hidden">
              <video
                ref={videoRef}
                src={activeMediaUrl}
                autoPlay
                playsInline
                preload="metadata"
                onLoadedMetadata={(e) => {
                  const v = videoRef.current;
                  setDuration(e?.currentTarget?.duration || v?.duration || 0);
                  if (retryTime > 0 && v) v.currentTime = retryTime;
                }}
                onTimeUpdate={() => setCurrentTime(videoRef.current?.currentTime || 0)}
                onWaiting={() => setPlayerState('buffering')}
                onPlaying={() => setPlayerState('playing')}
                onPause={() => playerState !== 'buffering' && playerState !== 'error' && setPlayerState('paused')}
                onEnded={() => setPlayerState('paused')}
                onError={() => {
                  setPlayerState('error');
                  setRetryTime(videoRef.current?.currentTime || 0);
                  setPlaybackError(STREAM_ERR);
                }}
                className="h-full w-full object-contain cursor-pointer"
                onClick={togglePlayPause}
              />

              {/* Buffering Indicator */}
              {playerState === 'buffering' && (
                <div data-testid="video-buffering" className="absolute inset-0 flex items-center justify-center bg-black/40 pointer-events-none">
                  <Loader2 size={36} className="animate-spin text-brand" />
                </div>
              )}

              {/* Error Overlay with Retry */}
              {playerState === 'error' && (
                <div data-testid="video-error-overlay" className="absolute inset-0 flex flex-col items-center justify-center bg-black/85 p-6 text-center z-20">
                  <AlertCircle size={44} className="text-amber-400 mb-3" />
                  <p className="text-xs text-zinc-300 max-w-md mb-4 leading-relaxed">
                    {playbackError || STREAM_ERR}
                  </p>
                  <button
                    data-testid="video-retry-btn"
                    onClick={handleRetry}
                    className={BTN_FEAT}
                  >
                    <RefreshCw size={16} /> Thử lại ({formatTime(retryTime)})
                  </button>
                </div>
              )}
            </div>

            {/* Custom Control Bar with HTTP Range Timeline */}
            <div className="flex flex-col gap-2 border-t border-surface-border bg-surface-muted/95 p-3 sm:px-4">
              {/* Timeline Scrubber */}
              <div className="flex items-center gap-3">
                <span data-testid="video-time-display" className="text-xs font-mono text-zinc-300 shrink-0 min-w-[80px]">
                  {formatTime(currentTime)} / {formatTime(duration)}
                </span>
                <input
                  data-testid="video-timeline"
                  type="range"
                  min={0}
                  max={duration || 100}
                  step="0.1"
                  value={currentTime}
                  onChange={(e) => {
                    const t = +e.target.value;
                    setCurrentTime(t);
                    if (videoRef.current) videoRef.current.currentTime = t;
                  }}
                  aria-label="Thanh tua video"
                  className={`w-full ${SLIDER_CLS}`}
                />
              </div>

              {/* Player Control Buttons */}
              <div className="flex items-center justify-between pt-1">
                <div className="flex items-center gap-2">
                  <button
                    data-testid="video-play-pause-btn"
                    onClick={togglePlayPause}
                    className={BTN_PLAY_PAUSE}
                    aria-label={playerState === 'playing' ? 'Tạm dừng video' : 'Phát video'}
                  >
                    {playerState === 'playing' ? (
                      <Icon d="M6 4h4v16H6zM14 4h4v16h-4z" fill="currentColor" />
                    ) : (
                      <Play size={18} className="fill-current" />
                    )}
                  </button>

                  <div className="flex items-center gap-1.5 ml-2">
                    <button
                      data-testid="video-volume-btn"
                      onClick={toggleMute}
                      className={BTN_ICON}
                      aria-label={isMuted || volume === 0 ? 'Bật âm thanh' : 'Tắt âm thanh'}
                    >
                      <Icon d={isMuted || !volume ? 'M11 5L6 9H2v6h4l5 4V5zM22 9l-6 6M16 9l6 6' : 'M11 5L6 9H2v6h4l5 4V5zM15.54 8.46a5 5 0 0 1 0 7.07'} />
                    </button>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={isMuted ? 0 : volume}
                      onChange={(e) => {
                        const val = +e.target.value, v = videoRef.current;
                        setVolume(val);
                        setIsMuted(!val);
                        if (v) { v.volume = val; v.muted = !val; }
                      }}
                      aria-label="Thanh âm lượng"
                      className={`w-16 sm:w-20 ${SLIDER_CLS}`}
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    data-testid="video-fullscreen-btn"
                    onClick={toggleFullscreen}
                    className={BTN_ICON}
                    aria-label="Toàn màn hình"
                  >
                    <Icon d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}


      {/* Hero Backdrop */}
      <section className="relative overflow-hidden border-b border-surface-border bg-background">
        {/* Backdrop Image Layer */}
        <div className="absolute inset-0 z-0 h-full w-full">
          {movie.backdrop?.trim() && !backdropError ? (
            <Image
              src={movie.backdrop}
              alt={movie.title}
              fill
              priority
              onError={() => setBackdropError(true)}
              className="object-cover opacity-75 sm:opacity-85"
            />
          ) : (
            <div className="h-full w-full bg-zinc-950" />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-background via-background/80 to-transparent" />
        </div>

        {/* Content Layer */}
        <div className="page-shell relative z-10 pb-12 pt-6 sm:pt-10">
          <Link href="/" className="inline-flex items-center gap-1 text-xs text-zinc-400 mb-6">
            <Icon d="m12 19-7-7 7-7M19 12H5" s={14} /> Trang chủ
          </Link>

          <div className="flex flex-col gap-6 md:flex-row md:items-end">
            {/* Poster */}
            <div className="relative shrink-0">
              <div className="relative aspect-[2/3] w-44 overflow-hidden rounded-lg border border-surface-border bg-surface sm:w-56">
                {movie.poster?.trim() && !posterError ? (
                  <Image
                    src={movie.poster}
                    alt={movie.title}
                    fill
                    onError={() => setPosterError(true)}
                    sizes="(max-width: 640px) 176px, 224px"
                    className="object-cover"
                  />
                ) : (
                  <div data-testid="movie-poster-placeholder" className="flex h-full w-full flex-col items-center justify-center p-4 text-center bg-zinc-900 text-zinc-500">
                    <Film size={36} className="mb-2 text-zinc-600" />
                    <span className="text-xs font-medium leading-tight text-zinc-400">
                      {movie.title}
                    </span>
                  </div>
                )}
                <span className="absolute top-2 left-2 flex items-center gap-1 rounded bg-black/80 px-2 py-0.5 text-xs font-bold text-amber-400">
                  <Star size={12} className="fill-amber-400" /> {movie.rating}
                </span>
              </div>
            </div>

            {/* Info */}
            <div className="flex-1">
              <span className="rounded bg-brand px-2 py-0.5 font-bold text-zinc-950 text-[10px]">
                Tuyển chọn Dippie
              </span>

              <h1 className="mt-3 text-3xl font-extrabold text-white sm:text-5xl">
                {movie.title}
              </h1>

              <div className="mt-3 flex flex-wrap items-center gap-4 text-xs sm:text-sm text-zinc-400">
                <span className="flex items-center gap-1 text-white font-bold">
                  <Star size={14} className="fill-amber-400 text-amber-400" />
                  {movie.rating} / 10
                </span>
                <span>{movie.year}</span>
                <span>•</span>
                <span>{movie.runtime}</span>
                <span>{movie.genres.join(', ')}</span>
              </div>

              <p className="mt-4 max-w-2xl text-sm leading-relaxed text-zinc-200">
                {movie.description}
              </p>

              {/* Descriptor Error Alert */}
              {descriptorError && (
                <div role="alert" className={ALERT_BOX}>
                  <div className="flex items-center gap-2 truncate">
                    <AlertCircle size={15} className="text-amber-400 shrink-0" />
                    <span className="truncate">{descriptorError}</span>
                  </div>
                  <button
                    type="button"
                    data-testid="descriptor-retry-btn"
                    onClick={retryDescriptor}
                    className={ALERT_BTN}
                  >
                    <RefreshCw size={13} /> Thử lại
                  </button>
                </div>
              )}

              {/* Action Buttons */}
              <div className="mt-6 flex flex-wrap items-center gap-3">
                {hasValidFeature && (
                  <button
                    ref={playButtonRef}
                    data-testid="play-feature-btn"
                    onClick={(e) => startPlayback('feature', e.currentTarget)}
                    className={BTN_FEAT}
                  >
                    <Play size={16} className="fill-current" />
                    Xem phim
                  </button>
                )}

                {(hasValidTrailer || hasVideo) && (
                  <button
                    ref={hasValidFeature ? undefined : playButtonRef}
                    data-testid="play-trailer-btn"
                    onClick={(e) => startPlayback('trailer', e.currentTarget)}
                    className={hasValidFeature || descriptorError ? BTN_SEC : BTN_PRI}
                  >
                    {hasValidTrailer ? (
                      <Play size={16} className="fill-current" />
                    ) : (
                      <Film size={16} />
                    )}
                    Xem trailer
                  </button>
                )}


                <button
                  disabled={isWatchlistPending}
                  onClick={() => toggleWatchlist(mid, movie.title, movie.poster)}
                  className={isWatchlistUnconfirmed ? WATCH_UNCONF : inWatchlist ? WATCH_CONF : WATCH_DEF}
                  aria-label={
                    isWatchlistPending
                      ? 'Đang cập nhật...'
                      : isWatchlistUnconfirmed
                      ? isAddWatch
                        ? 'Chưa xác nhận lưu • Thử lưu lại vào Danh sách xem'
                        : 'Chưa xác nhận xóa • Thử xóa lại khỏi Danh sách xem'
                      : inWatchlist
                      ? 'Xóa khỏi Watchlist'
                      : 'Thêm vào Watchlist'
                  }
                >
                  {isWatchlistPending ? (
                    <span className="flex items-center gap-1.5"><Loader2 size={15} className="animate-spin text-zinc-400" /> Đang cập nhật...</span>
                  ) : isWatchlistUnconfirmed ? (
                    <span className="flex items-center gap-1.5 font-bold"><RefreshCw size={15} className="text-amber-400" /> Thử lại</span>
                  ) : inWatchlist ? (
                    '✓ Đã lưu Watchlist'
                  ) : (
                    '+ Thêm vào Watchlist'
                  )}
                </button>

                <button
                  disabled={isFavoritePending}
                  onClick={() => toggleFavorite(mid, movie.title, movie.poster)}
                  className={isFavoriteUnconfirmed ? FAV_UNCONF : favorite ? FAV_CONF : FAV_DEF}
                  aria-label={
                    isFavoritePending
                      ? 'Đang cập nhật...'
                      : isFavoriteUnconfirmed
                      ? isAddFav
                        ? 'Chưa xác nhận thích • Thử thêm lại vào Yêu thích'
                        : 'Chưa xác nhận bỏ thích • Thử xóa lại khỏi Yêu thích'
                      : favorite
                      ? 'Đã yêu thích'
                      : 'Thêm vào Yêu thích'
                  }
                >
                  {isFavoritePending ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : isFavoriteUnconfirmed ? (
                    <RefreshCw size={16} className="text-amber-400 stroke-[2.5]" />
                  ) : favorite ? (
                    '♥'
                  ) : (
                    '♡'
                  )}
                </button>

                <button
                  onClick={openChat}
                  className={CHAT_BTN}
                >
                  Hỏi CineBot
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Main Details Body */}
      <div className="page-shell py-10">
        <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
          {/* Left: Overview & Rating Selector */}
          <div className="space-y-8">
            {/* Interactive Rating Selector */}
            <div className={CARD}>
              <h2 className="text-sm font-bold text-white">Đánh giá bộ phim này</h2>

              <div className="mt-4 flex flex-wrap items-center gap-1.5">
                {STARS.map((star) => (
                  <button
                    key={star}
                    disabled={isRatingPending}
                    onMouseEnter={() => setHoverRating(star)}
                    onMouseLeave={() => setHoverRating(null)}
                    onClick={() => rateMovie(mid, star, movie.title)}
                    className={(hoverRating !== null ? hoverRating >= star : (currentRating || 0) >= star) ? STAR_ACT : STAR_INACT}
                    aria-label={`Chấm ${star} trên 10 sao`}
                  >
                    {star}
                  </button>
                ))}
              </div>

              {isRatingUnconfirmed && (
                <div data-testid="rating-unconfirmed-banner" className={ALERT_BOX}>
                  <span className="flex items-center gap-1.5 font-medium">
                    <AlertCircle size={14} className="text-amber-400 shrink-0" />
                    {isRate
                      ? `Chưa xác nhận điểm ${unconfirmedRatingScore || currentRating}/10 ★ trên máy chủ`
                      : 'Chưa xác nhận xóa điểm đánh giá trên máy chủ'}
                  </span>
                  <button
                    disabled={isRatingPending}
                    onClick={() =>
                      isRate
                        ? rateMovie(mid, unconfirmedRatingScore || currentRating || 10, movie.title)
                        : removeRating(mid, movie.title)
                    }
                    className={ALERT_BTN}
                    aria-label={isRate ? 'Thử lưu lại điểm đánh giá' : 'Thử xóa lại điểm đánh giá'}
                  >
                    <RefreshCw size={12} /> {isRate ? 'Thử lưu lại' : 'Thử xóa lại'}
                  </button>
                </div>
              )}

              {!isRatingUnconfirmed && currentRating && (
                <div className="mt-3 flex items-center justify-between text-xs">
                  <p className="text-amber-400 font-medium">✓ Đã chấm {currentRating}/10 sao.</p>
                  <button
                    disabled={isRatingPending}
                    onClick={() => removeRating(mid, movie.title)}
                    className="text-zinc-400 hover:text-red-400 underline text-xs cursor-pointer disabled:opacity-50"
                  >
                    Xóa đánh giá
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Right: Technical Attributes */}
          <div className={`${CARD} h-fit space-y-3 text-xs`}>
            <h3 className="font-bold uppercase tracking-wider text-zinc-300">Thông tin phát hành</h3>
            <p><span className="text-zinc-500">Thể loại: </span><span className="text-zinc-300">{movie.genres.join(', ')}</span></p>
            <p className={BORDER_T}><span className="text-zinc-500">Năm / Thời lượng: </span><span className="font-medium text-white">{movie.year} • {movie.runtime}</span></p>
          </div>
        </div>

        {/* Similar Movies */}
        <div className="mt-12 pt-8 border-t border-surface-border">
          <MovieSection
            title="Phim tương tự"
            movies={similarMovies}
          />
        </div>
      </div>
    </main>
  );
}
