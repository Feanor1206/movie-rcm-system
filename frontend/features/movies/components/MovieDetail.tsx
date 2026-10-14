'use client';

import React, { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import {
  ArrowLeft,
  Check,
  Heart,
  Play,
  Star,
  X,
  Loader2,
  Maximize2,
  Volume2,
  VolumeX,
  RefreshCw,
  AlertCircle,
  Film,
  Pause,
} from 'lucide-react';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';
import { getMediaDescriptor, MediaDescriptor, resolveStreamUrl } from '@/lib/services/mediaService';
import { MovieSection } from './MovieSection';


const BTN_PLAY = 'min-h-[44px] px-4 py-2.5 text-xs sm:px-6 sm:text-sm font-bold shadow-brand-sm inline-flex items-center justify-center gap-1.5 cursor-pointer';
const BTN_ICON = 'flex h-11 w-11 min-h-[44px] min-w-[44px] items-center justify-center rounded-md text-zinc-300 hover:text-white hover:bg-zinc-800 transition cursor-pointer';
const UNCONF_CLS = 'border-amber-400 bg-amber-400/15 text-amber-300 hover:bg-amber-400/25 ring-1 ring-amber-400/40';
const ALERT_BOX = 'mt-4 flex items-center justify-between gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3.5 py-2.5 text-xs text-amber-200';
const ALERT_BTN = 'flex items-center gap-1 rounded bg-amber-500/20 px-2.5 py-1 text-xs font-bold text-amber-300 hover:bg-amber-500/30 transition cursor-pointer shrink-0';

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

    getMediaDescriptor(movie.id, { signal: abortController?.signal })
      .then((desc) => {
        if (mounted && desc && desc.movieId === movie.id) {
          setDescriptor(desc);
          setDescriptorLoading(false);
          setDescriptorError(null);
        }
      })
      .catch((err: any) => {
        if (!mounted || (abortController && abortController.signal.aborted) || err?.name === 'AbortError') {
          return;
        }
        setDescriptor(null);
        setDescriptorLoading(false);
        setDescriptorError('Không thể nạp dữ liệu phim từ máy chủ.');
      });

    return () => {
      mounted = false;
      abortController?.abort();
    };
  }, [movie.id, descriptorNonce]);

  const formatTime = (s: number) =>
    isNaN(s) || s < 0 ? '00:00' : `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

  const startPlayback = (kind: 'feature' | 'trailer', opener?: HTMLElement | null) => {
    if (opener) playerOpenerRef.current = opener;
    setActiveMediaKind(kind);
    const url = kind === 'feature'
      ? (descriptor?.movieId === movie.id ? descriptor?.feature?.streamUrl : '')
      : (descriptor?.movieId === movie.id && descriptor?.trailer?.streamUrl ? descriptor.trailer.streamUrl : (hasVideo ? movie.videoUrl : ''));
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
      if (retryTime > 0 && retryTime < (v.duration || Infinity)) {
        try { v.currentTime = retryTime; } catch (_) {}
      }
      v.play().catch(() => setPlayerState('paused'));
    }, { once: true });
  };

  const togglePlayPause = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play().catch(() => setPlayerState('paused'));
      setPlayerState('playing');
    } else {
      videoRef.current.pause();
      setPlayerState('paused');
    }
  };

  const toggleMute = () => {
    if (!videoRef.current) return;
    const m = !videoRef.current.muted;
    setIsMuted(m);
    videoRef.current.muted = m;
  };

  const toggleFullscreen = () => {
    if (!videoModalRef.current) return;
    document.fullscreenElement ? document.exitFullscreen().catch(() => {}) : videoModalRef.current.requestFullscreen().catch(() => {});
  };

  const seekBy = (sec: number) => {
    if (!videoRef.current) return;
    const t = Math.min(Math.max(0, videoRef.current.currentTime + sec), videoRef.current.duration || duration || 100);
    videoRef.current.currentTime = t;
    setCurrentTime(t);
  };

  const adjustVolume = (delta: number) => {
    if (!videoRef.current) return;
    const v = Math.min(Math.max(0, videoRef.current.volume + delta), 1);
    setVolume(v);
    setIsMuted(v === 0);
    videoRef.current.volume = v;
    videoRef.current.muted = v === 0;
  };

  // Autoplay rejection handler: transition to paused so user can click to play
  useEffect(() => {
    if (isPlaying && videoRef.current && activeMediaUrl) {
      const playPromise = videoRef.current.play();
      if (playPromise !== undefined) {
        playPromise.catch((err: any) => {
          if (err?.name === 'AbortError') return;
          setPlayerState('paused');
        });
      }
    }
  }, [isPlaying, activeMediaUrl]);

  // Video modal accessibility: Escape key, body scroll lock, focus trap, focus restoration, shortcuts
  // Decoupled from playback progress/volume changes so focus never jumps back prematurely
  useEffect(() => {
    if (!isPlaying) return;

    if (
      document.activeElement &&
      (!videoModalRef.current ||
        (typeof videoModalRef.current.contains === 'function' && !videoModalRef.current.contains(document.activeElement)))
    ) {
      playerOpenerRef.current = document.activeElement as HTMLElement | null;
    }

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const timer = setTimeout(() => {
      if (videoModalRef.current) {
        const focusable = videoModalRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), video, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length > 0) {
          focusable[0].focus();
        }
      }
    }, 40);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        setIsPlaying(false);
        return;
      }

      if (e.key === 'Tab' && videoModalRef.current) {
        const focusable = videoModalRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), video, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (!videoModalRef.current.contains(document.activeElement)) {
          e.preventDefault();
          if (e.shiftKey) last.focus();
          else first.focus();
          return;
        }

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
        return;
      }

      // Respect editable targets (native sliders, text inputs)
      const target = e.target as HTMLElement | null;
      const isEditable = target && (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      );

      if (isEditable) {
        return;
      }

      // Keyboard shortcuts when playing and not inside native control
      if (e.key === ' ' || e.code === 'Space') {
        if (target?.tagName !== 'BUTTON') {
          e.preventDefault();
          togglePlayPause();
        }
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        e.preventDefault();
        seekBy(e.key === 'ArrowLeft' ? -5 : 5);
      } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        e.preventDefault();
        adjustVolume(e.key === 'ArrowUp' ? 0.1 : -0.1);
      } else if (e.key === 'm' || e.key === 'M') {
        e.preventDefault();
        toggleMute();
      } else if (e.key === 'f' || e.key === 'F') {
        e.preventDefault();
        toggleFullscreen();
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


  const inWatchlist = isWatchlisted(movie.id);
  const favorite = isFavorite(movie.id);
  const currentRating = getRating(movie.id);
  const isWatchlistPending = isActionPending(movie.id, 'watchlist');
  const isFavoritePending = isActionPending(movie.id, 'favorite');
  const isRatingPending = isActionPending(movie.id, 'rating');

  const isWatchlistUnconfirmed = isActionUnconfirmed(movie.id, 'watchlist');
  const watchlistIntent = isWatchlistUnconfirmed ? getActionIntent(movie.id, 'watchlist') : null;

  const isFavoriteUnconfirmed = isActionUnconfirmed(movie.id, 'favorite');
  const favoriteIntent = isFavoriteUnconfirmed ? getActionIntent(movie.id, 'favorite') : null;

  const isRatingUnconfirmed = isActionUnconfirmed(movie.id, 'rating');
  const ratingIntent = isRatingUnconfirmed ? getActionIntent(movie.id, 'rating') : null;
  const unconfirmedRatingScore = isRatingUnconfirmed ? getUnconfirmedRating(movie.id) : undefined;

  const hasVideo = Boolean(movie.videoUrl && movie.videoUrl.trim());
  const videoSource = hasVideo ? (movie.videoUrl as string) : '';

  return (
    <main className="min-h-screen bg-background">
      {/* Video Player Modal / Player Overlay */}
      {isPlaying && (
        <div
          ref={videoModalRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="video-player-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/95 backdrop-blur-md p-4 sm:p-8 animate-fade-in"
        >
          <div className="relative w-full max-w-5xl overflow-hidden rounded-xl border border-surface-border bg-surface shadow-2xl flex flex-col">
            {/* Player Header Bar */}
            <div className="flex items-center justify-between border-b border-surface-border bg-surface-muted px-4 py-3">
              <div className="flex items-center gap-2 truncate">
                <span className="h-2.5 w-2.5 rounded-full bg-brand shadow-brand-sm shrink-0" />
                <h3 id="video-player-title" className="text-sm font-bold text-white truncate">
                  {movie.title}
                </h3>
                <span className="text-xs text-zinc-400 shrink-0">
                  • {activeMediaKind === 'feature' ? 'Bản phim chính' : 'Trailer / Giới thiệu'}
                </span>
              </div>
              <button
                onClick={() => setIsPlaying(false)}
                className={`shrink-0 ${BTN_ICON}`}
                aria-label="Đóng trình phát"
              >
                <X size={20} />
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
                onLoadedMetadata={() => {
                  if (videoRef.current) {
                    setDuration(videoRef.current.duration || 0);
                    if (retryTime > 0) {
                      videoRef.current.currentTime = retryTime;
                    }
                  }
                }}
                onTimeUpdate={() => {
                  if (videoRef.current) {
                    setCurrentTime(videoRef.current.currentTime);
                  }
                }}
                onWaiting={() => setPlayerState('buffering')}
                onPlaying={() => setPlayerState('playing')}
                onPause={() => {
                  if (playerState !== 'buffering' && playerState !== 'error') {
                    setPlayerState('paused');
                  }
                }}
                onEnded={() => setPlayerState('paused')}
                onError={() => {
                  setPlayerState('error');
                  if (videoRef.current) {
                    setRetryTime(videoRef.current.currentTime);
                  }
                  setPlaybackError('Không thể nạp luồng phát video hoặc kết nối mạng bị gián đoạn.');
                }}
                className="h-full w-full object-contain cursor-pointer"
                onClick={togglePlayPause}
              >
                Trình duyệt của bạn không hỗ trợ thẻ video HTML5.
              </video>

              {/* Buffering Indicator */}
              {playerState === 'buffering' && (
                <div
                  data-testid="video-buffering"
                  className="absolute inset-0 flex items-center justify-center bg-black/40 backdrop-blur-xs pointer-events-none"
                >
                  <div className="flex flex-col items-center gap-2 p-4 rounded-xl bg-black/75 border border-emerald-500/30">
                    <Loader2 size={36} className="animate-spin text-brand" />
                    <span className="text-xs font-semibold text-emerald-400">Đang đệm luồng phát...</span>
                  </div>
                </div>
              )}

              {/* Error Overlay with Retry */}
              {playerState === 'error' && (
                <div
                  data-testid="video-error-overlay"
                  className="absolute inset-0 flex flex-col items-center justify-center bg-black/85 p-6 text-center z-20"
                >
                  <AlertCircle size={44} className="text-amber-400 mb-3" />
                  <h4 className="text-sm font-bold text-white mb-1">Gián đoạn luồng phát video</h4>
                  <p className="text-xs text-zinc-300 max-w-md mb-4 leading-relaxed">
                    {playbackError || 'Không thể đọc luồng HTTP Range từ máy chủ.'}
                  </p>
                  <button
                    data-testid="video-retry-btn"
                    onClick={handleRetry}
                    className="btn-primary min-h-[44px] min-w-[44px] px-5 py-2.5 text-xs sm:text-sm font-bold shadow-brand-sm inline-flex items-center gap-2 cursor-pointer"
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
                    const newTime = parseFloat(e.target.value);
                    setCurrentTime(newTime);
                    if (videoRef.current) {
                      videoRef.current.currentTime = newTime;
                    }
                  }}
                  aria-label="Thanh tua video"
                  className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-zinc-700 accent-emerald-500 min-h-[44px]"
                />
              </div>

              {/* Player Control Buttons */}
              <div className="flex items-center justify-between pt-1">
                <div className="flex items-center gap-2">
                  <button
                    data-testid="video-play-pause-btn"
                    onClick={togglePlayPause}
                    className="flex h-11 w-11 min-h-[44px] min-w-[44px] items-center justify-center rounded-md bg-brand text-zinc-950 font-bold hover:bg-brand-hover transition cursor-pointer"
                    aria-label={playerState === 'playing' ? 'Tạm dừng video' : 'Phát video'}
                  >
                    {playerState === 'playing' ? (
                      <Pause size={18} className="fill-current" />
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
                      {isMuted || volume === 0 ? <VolumeX size={18} /> : <Volume2 size={18} />}
                    </button>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={isMuted ? 0 : volume}
                      onChange={(e) => {
                        const v = parseFloat(e.target.value);
                        setVolume(v);
                        setIsMuted(v === 0);
                        if (videoRef.current) {
                          videoRef.current.volume = v;
                          videoRef.current.muted = v === 0;
                        }
                      }}
                      aria-label="Thanh âm lượng"
                      className="w-16 sm:w-20 h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-emerald-500 min-h-[44px]"
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
                    <Maximize2 size={18} />
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
          {movie.backdrop && movie.backdrop.trim() && !backdropError ? (
            <Image
              src={movie.backdrop}
              alt={movie.title}
              fill
              priority
              onError={() => setBackdropError(true)}
              className="object-cover opacity-75 sm:opacity-85"
            />
          ) : (
            <div className="h-full w-full bg-gradient-to-br from-zinc-900 via-zinc-950 to-black" />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-background via-background/80 to-transparent" />
        </div>

        {/* Content Layer */}
        <div className="page-shell relative z-10 pb-12 pt-6 sm:pt-10">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-zinc-400 transition hover:text-white mb-6 cursor-pointer"
          >
            <ArrowLeft size={14} /> Quay lại trang chủ
          </Link>

          <div className="flex flex-col gap-6 md:flex-row md:items-end">
            {/* Poster */}
            <div className="relative shrink-0">
              <div className="relative aspect-[2/3] w-44 overflow-hidden rounded-lg border border-surface-border bg-surface shadow-2xl sm:w-56">
                {movie.poster && movie.poster.trim() && !posterError ? (
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
                <span className="absolute top-2.5 left-2.5 flex items-center gap-1 rounded bg-black/80 px-2 py-0.5 text-xs font-bold text-amber-400 border border-white/10">
                  <Star size={12} className="fill-amber-400" /> {movie.rating}
                </span>
              </div>
            </div>

            {/* Info */}
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded bg-brand px-2 py-0.5 font-bold text-zinc-950 uppercase text-[10px] shadow-brand-sm">
                  Tuyển chọn Dippie
                </span>
              </div>

              <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-white sm:text-5xl drop-shadow-md">
                {movie.title}
              </h1>

              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs sm:text-sm text-zinc-400">
                <span className="flex items-center gap-1 text-white font-bold">
                  <Star size={14} className="fill-amber-400 text-amber-400" />
                  {movie.rating} / 10
                </span>
                <span>{movie.year}</span>
                <span>•</span>
                <span>{movie.runtime}</span>
                <span>{movie.genres.join(', ')}</span>
              </div>

              <p className="mt-4 max-w-2xl text-sm sm:text-base leading-relaxed text-zinc-200 drop-shadow">
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
                    onClick={() => {
                      setDescriptorError(null);
                      setDescriptorLoading(true);
                      setDescriptorNonce((n) => n + 1);
                    }}
                    className={ALERT_BTN}
                  >
                    <RefreshCw size={13} /> Thử lại
                  </button>
                </div>
              )}

              {/* Action Buttons */}
              <div className="mt-6 flex flex-wrap items-center gap-3">
                {descriptor && descriptor.movieId === movie.id && descriptor.hasFeature ? (
                  <>
                    <button
                      ref={playButtonRef}
                      data-testid="play-feature-btn"
                      onClick={(e) => startPlayback('feature', e.currentTarget)}
                      className={`btn-primary ${BTN_PLAY}`}
                    >
                      <Play size={16} className="fill-current" />
                      Xem phim
                    </button>

                    {(descriptor.hasTrailer || hasVideo) && (
                      <button
                        data-testid="play-trailer-btn"
                        onClick={(e) => startPlayback('trailer', e.currentTarget)}
                        className="btn-secondary min-h-[44px] px-3 py-2 text-xs sm:px-4 sm:text-sm font-semibold text-zinc-300 hover:text-white inline-flex items-center justify-center gap-1.5 cursor-pointer"
                      >
                        <Film size={15} />
                        Xem trailer
                      </button>
                    )}
                  </>
                ) : descriptor && descriptor.movieId === movie.id && descriptor.hasTrailer ? (
                  <button
                    ref={playButtonRef}
                    data-testid="play-trailer-btn"
                    onClick={(e) => startPlayback('trailer', e.currentTarget)}
                    className={`btn-primary ${BTN_PLAY}`}
                  >
                    <Play size={16} className="fill-current" />
                    Xem trailer / giới thiệu
                  </button>
                ) : hasVideo ? (
                  <button
                    ref={playButtonRef}
                    data-testid="play-trailer-btn"
                    onClick={(e) => startPlayback('trailer', e.currentTarget)}
                    className={`${BTN_PLAY} ${
                      descriptorError ? 'btn-secondary text-zinc-300 hover:text-white' : 'btn-primary'
                    }`}
                  >
                    <Film size={16} />
                    {descriptorError ? 'Xem trailer' : 'Xem trailer / giới thiệu'}
                  </button>
                ) : null}


                <button
                  disabled={isWatchlistPending}
                  onClick={() => toggleWatchlist(movie.id, movie.title, movie.poster)}
                  className={`min-h-[44px] inline-flex items-center justify-center px-4 py-2.5 text-sm font-semibold disabled:opacity-60 cursor-pointer rounded-md border transition-all ${
                    isWatchlistUnconfirmed
                      ? UNCONF_CLS
                      : inWatchlist
                      ? 'btn-secondary text-white'
                      : 'btn-secondary text-zinc-300'
                  }`}
                  aria-label={
                    isWatchlistPending
                      ? 'Đang cập nhật Watchlist...'
                      : isWatchlistUnconfirmed
                      ? watchlistIntent === 'add'
                        ? 'Chưa xác nhận lưu • Thử lưu lại vào Danh sách xem'
                        : 'Chưa xác nhận xóa • Thử xóa lại khỏi Danh sách xem'
                      : inWatchlist
                      ? 'Xóa khỏi Watchlist'
                      : 'Thêm vào Watchlist'
                  }
                  title={
                    isWatchlistUnconfirmed
                      ? watchlistIntent === 'add'
                        ? 'Chưa xác nhận lưu • Nhấn để thử lưu lại'
                        : 'Chưa xác nhận xóa • Nhấn để thử xóa lại'
                      : undefined
                  }
                >
                  {isWatchlistPending ? (
                    <span className="flex items-center gap-1.5">
                      <Loader2 size={15} className="animate-spin text-zinc-400" /> Đang cập nhật...
                    </span>
                  ) : isWatchlistUnconfirmed ? (
                    <span className="flex items-center gap-1.5 font-bold">
                      <RefreshCw size={15} className="text-amber-400" />
                      {watchlistIntent === 'add' ? 'Chưa xác nhận • Thử lưu lại' : 'Chưa xác nhận • Thử xóa lại'}
                    </span>
                  ) : inWatchlist ? (
                    <>
                      <Check size={15} className="text-brand" /> Đã lưu Watchlist
                    </>
                  ) : (
                    '+ Thêm vào Watchlist'
                  )}
                </button>

                <button
                  disabled={isFavoritePending}
                  onClick={() => toggleFavorite(movie.id, movie.title, movie.poster)}
                  className={`min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-md border p-2.5 transition-colors cursor-pointer disabled:opacity-60 ${
                    isFavoriteUnconfirmed
                      ? UNCONF_CLS
                      : favorite
                      ? 'border-brand bg-brand/15 text-brand'
                      : 'border-zinc-700 bg-surface text-zinc-300 hover:border-zinc-500 hover:text-white'
                  }`}
                  aria-label={
                    isFavoritePending
                      ? 'Đang cập nhật Yêu thích...'
                      : isFavoriteUnconfirmed
                      ? favoriteIntent === 'add'
                        ? 'Chưa xác nhận thích • Thử thêm lại vào Yêu thích'
                        : 'Chưa xác nhận bỏ thích • Thử xóa lại khỏi Yêu thích'
                      : favorite
                      ? 'Đã yêu thích'
                      : 'Thêm vào Yêu thích'
                  }
                  title={
                    isFavoriteUnconfirmed
                      ? favoriteIntent === 'add'
                        ? 'Chưa xác nhận thích • Nhấn để thử thêm lại'
                        : 'Chưa xác nhận bỏ thích • Nhấn để thử xóa lại'
                      : favorite
                      ? 'Đã yêu thích'
                      : 'Thêm vào Yêu thích'
                  }
                >
                  {isFavoritePending ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : isFavoriteUnconfirmed ? (
                    <RefreshCw size={16} className="text-amber-400 stroke-[2.5]" />
                  ) : (
                    <Heart size={16} className={favorite ? 'fill-current' : ''} />
                  )}
                </button>

                <button
                  onClick={openChat}
                  className="min-h-[44px] inline-flex items-center justify-center rounded-md border border-zinc-700 bg-surface px-3.5 py-2.5 text-xs font-medium text-zinc-300 hover:border-brand hover:text-white cursor-pointer"
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
            <div className="rounded-xl border border-surface-border bg-surface p-5 sm:p-6">
              <h2 className="text-base font-bold text-white">Đánh giá bộ phim này</h2>
              <p className="mt-1 text-xs text-zinc-400">
                Chấm điểm giúp hệ thống hiểu rõ gu phim của bạn hơn.
              </p>

              <div className="mt-4 flex flex-wrap items-center gap-1.5">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((star) => {
                  const isSelected = (currentRating || 0) >= star;
                  const isHovered = (hoverRating || 0) >= star;
                  const active = hoverRating !== null ? isHovered : isSelected;

                  return (
                    <button
                      key={star}
                      disabled={isRatingPending}
                      onMouseEnter={() => setHoverRating(star)}
                      onMouseLeave={() => setHoverRating(null)}
                      onClick={() => rateMovie(movie.id, star, movie.title)}
                      className={`flex h-9 w-9 items-center justify-center rounded-md text-xs font-bold transition-all duration-150 cursor-pointer disabled:opacity-60 ${
                        active
                          ? 'bg-amber-400 text-black scale-105'
                          : 'border border-surface-border bg-surface-muted text-zinc-400 hover:border-zinc-600 hover:text-white'
                      }`}
                      aria-label={`Chấm ${star} trên 10 sao`}
                    >
                      {star}
                    </button>
                  );
                })}
              </div>

              {isRatingUnconfirmed && (
                <div data-testid="rating-unconfirmed-banner" className={ALERT_BOX}>
                  <span className="flex items-center gap-1.5 font-medium">
                    <AlertCircle size={14} className="text-amber-400 shrink-0" />
                    {ratingIntent === 'rate'
                      ? `Chưa xác nhận điểm ${unconfirmedRatingScore || currentRating}/10 ★ trên máy chủ`
                      : 'Chưa xác nhận xóa điểm đánh giá trên máy chủ'}
                  </span>
                  <button
                    disabled={isRatingPending}
                    onClick={() =>
                      ratingIntent === 'rate'
                        ? rateMovie(movie.id, unconfirmedRatingScore || currentRating || 10, movie.title)
                        : removeRating(movie.id, movie.title)
                    }
                    className={ALERT_BTN}
                    aria-label={ratingIntent === 'rate' ? 'Thử lưu lại điểm đánh giá' : 'Thử xóa lại điểm đánh giá'}
                  >
                    <RefreshCw size={12} /> {ratingIntent === 'rate' ? 'Thử lưu lại' : 'Thử xóa lại'}
                  </button>
                </div>
              )}

              {!isRatingUnconfirmed && currentRating && (
                <div className="mt-3 flex items-center justify-between text-xs">
                  <p className="text-amber-400 flex items-center gap-1 font-medium">
                    <Check size={14} /> Bạn đã chấm bộ phim này {currentRating}/10 điểm.
                  </p>
                  <button
                    disabled={isRatingPending}
                    onClick={() => removeRating(movie.id, movie.title)}
                    className="text-zinc-400 hover:text-red-400 underline transition-colors cursor-pointer disabled:opacity-50"
                  >
                    Xóa đánh giá
                  </button>
                </div>
              )}
            </div>

            {/* Synopsis Section */}
            <div className="rounded-xl border border-surface-border bg-surface p-5 sm:p-6">
              <h2 className="text-base font-bold text-white mb-2">Tóm tắt nội dung</h2>
              <p className="text-sm text-zinc-300 leading-relaxed">
                {movie.description}
              </p>
            </div>
          </div>

          {/* Right: Technical Attributes */}
          <div className="rounded-xl border border-surface-border bg-surface p-5 sm:p-6 h-fit">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 mb-3">
              Thông tin phát hành
            </h3>

            <dl className="space-y-3 text-xs">
              <div>
                <dt className="text-zinc-500">Thể loại</dt>
                <dd className="mt-1 flex flex-wrap gap-1">
                  {movie.genres.map((genre) => (
                    <Link
                      key={genre}
                      href={`/search?genre=${encodeURIComponent(genre)}`}
                      className="rounded bg-surface-muted border border-surface-border px-2 py-0.5 text-zinc-300 hover:border-brand hover:text-white transition-colors"
                    >
                      {genre}
                    </Link>
                  ))}
                </dd>
              </div>

              {[
                ['Năm sản xuất', movie.year],
                ['Thời lượng', movie.runtime],
                ['Điểm đánh giá', `${movie.rating} / 10`],
                ['Định dạng phát hành', 'Chưa có thông tin ấn bản'],
              ].map(([k, v]) => (
                <div key={k} className="pt-2 border-t border-surface-border">
                  <dt className="text-zinc-500">{k}</dt>
                  <dd className="text-white font-medium mt-0.5">{v}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>

        {/* Similar Movies */}
        <div className="mt-12 pt-8 border-t border-surface-border">
          <MovieSection
            title="Phim tương tự"
            subtitle="Các tác phẩm có phong cách và chủ đề tương tự"
            movies={similarMovies}
          />
        </div>
      </div>
    </main>
  );
}
