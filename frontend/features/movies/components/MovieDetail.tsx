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
  Clock,
  Calendar,
  X,
  Loader2,
  Maximize2,
  Volume2,
  VolumeX,
  RefreshCw,
  AlertCircle,
  Film,
} from 'lucide-react';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';
import { MovieSection } from './MovieSection';

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
  const videoRef = useRef<HTMLVideoElement>(null);
  const videoModalRef = useRef<HTMLDivElement>(null);
  const playButtonRef = useRef<HTMLButtonElement>(null);

  // Video modal accessibility: Escape key, body scroll lock, focus trap, focus restoration
  useEffect(() => {
    if (!isPlaying) return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    // Trap focus inside modal & listen for Escape
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        setIsPlaying(false);
        return;
      }

      if (e.key === 'Tab' && videoModalRef.current) {
        const focusable = videoModalRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), video, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
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
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
      playButtonRef.current?.focus();
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
      {isPlaying && hasVideo && (
        <div
          ref={videoModalRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="video-player-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/95 backdrop-blur-md p-4 sm:p-8 animate-fade-in"
        >
          <div className="relative w-full max-w-5xl overflow-hidden rounded-xl border border-surface-border bg-surface shadow-2xl">
            {/* Player Header Bar */}
            <div className="flex items-center justify-between border-b border-surface-border bg-surface-muted px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-brand shadow-brand-sm" />
                <h3 id="video-player-title" className="text-sm font-bold text-white truncate">
                  {movie.title}
                </h3>
                <span className="text-xs text-zinc-400">• Bản xem trước</span>
              </div>
              <button
                onClick={() => setIsPlaying(false)}
                className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-white transition-colors cursor-pointer"
                aria-label="Đóng trình phát"
              >
                <X size={18} />
              </button>
            </div>

            {/* Video Container */}
            <div className="relative aspect-video w-full bg-black">
              <video
                ref={videoRef}
                src={videoSource}
                controls
                autoPlay
                className="h-full w-full object-contain"
              >
                Trình duyệt của bạn không hỗ trợ thẻ video HTML5.
              </video>
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
          <div className="absolute inset-0 bg-gradient-to-t from-background via-background/80 to-background/30" />
          <div className="absolute inset-0 bg-gradient-to-r from-background via-background/75 to-transparent" />
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

              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs sm:text-sm text-zinc-300">
                <span className="flex items-center gap-1 text-white font-bold">
                  <Star size={14} className="fill-amber-400 text-amber-400" />
                  {movie.rating} / 10
                </span>
                <span className="flex items-center gap-1 text-zinc-400">
                  <Calendar size={13} /> {movie.year}
                </span>
                <span className="flex items-center gap-1 text-zinc-400">
                  <Clock size={13} /> {movie.runtime}
                </span>
                <span className="text-zinc-400">
                  {movie.genres.join(', ')}
                </span>
              </div>

              <p className="mt-4 max-w-2xl text-sm sm:text-base leading-relaxed text-zinc-200 drop-shadow">
                {movie.description}
              </p>

              {/* Action Buttons */}
              <div className="mt-6 flex flex-wrap items-center gap-3">
                {hasVideo && (
                  <button
                    ref={playButtonRef}
                    onClick={() => setIsPlaying(true)}
                    className="btn-primary px-6 py-2.5 text-sm font-bold shadow-brand-sm"
                  >
                    <Play size={16} className="fill-current" />
                    Xem trailer / giới thiệu
                  </button>
                )}

                <button
                  disabled={isWatchlistPending}
                  onClick={() => toggleWatchlist(movie.id, movie.title, movie.poster)}
                  className={`px-4 py-2.5 text-sm font-semibold disabled:opacity-60 cursor-pointer rounded-md border transition-all ${
                    isWatchlistUnconfirmed
                      ? 'border-amber-400 bg-amber-400/15 text-amber-300 hover:bg-amber-400/25 ring-1 ring-amber-400/40'
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
                  className={`rounded-md border p-2.5 transition-colors cursor-pointer disabled:opacity-60 ${
                    isFavoriteUnconfirmed
                      ? 'border-amber-400 bg-amber-400/15 text-amber-300 hover:bg-amber-400/25 ring-1 ring-amber-400/40'
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
                  className="rounded-md border border-zinc-700 bg-surface px-3.5 py-2.5 text-xs font-medium text-zinc-300 hover:border-brand hover:text-white cursor-pointer"
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

              {isRatingUnconfirmed && ratingIntent === 'rate' && (
                <div
                  data-testid="rating-unconfirmed-banner"
                  className="mt-3 flex items-center justify-between rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-300"
                >
                  <span className="flex items-center gap-1.5 font-medium">
                    <AlertCircle size={14} className="text-amber-400 shrink-0" />
                    Chưa xác nhận điểm {unconfirmedRatingScore || currentRating}/10 ★ trên máy chủ
                  </span>
                  <button
                    disabled={isRatingPending}
                    onClick={() => rateMovie(movie.id, unconfirmedRatingScore || currentRating || 10, movie.title)}
                    className="flex items-center gap-1 rounded bg-amber-500/20 px-2 py-1 font-bold text-amber-300 hover:bg-amber-500/30 transition-colors cursor-pointer"
                    aria-label="Thử lưu lại điểm đánh giá"
                  >
                    <RefreshCw size={12} /> Thử lưu lại
                  </button>
                </div>
              )}

              {isRatingUnconfirmed && ratingIntent === 'remove_rating' && (
                <div
                  data-testid="rating-unconfirmed-banner"
                  className="mt-3 flex items-center justify-between rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-300"
                >
                  <span className="flex items-center gap-1.5 font-medium">
                    <AlertCircle size={14} className="text-amber-400 shrink-0" />
                    Chưa xác nhận xóa điểm đánh giá trên máy chủ
                  </span>
                  <button
                    disabled={isRatingPending}
                    onClick={() => removeRating(movie.id, movie.title)}
                    className="flex items-center gap-1 rounded bg-amber-500/20 px-2 py-1 font-bold text-amber-300 hover:bg-amber-500/30 transition-colors cursor-pointer"
                    aria-label="Thử xóa lại điểm đánh giá"
                  >
                    <RefreshCw size={12} /> Thử xóa lại
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

              <div className="pt-2 border-t border-surface-border">
                <dt className="text-zinc-500">Năm sản xuất</dt>
                <dd className="text-white font-medium mt-0.5">{movie.year}</dd>
              </div>

              <div className="pt-2 border-t border-surface-border">
                <dt className="text-zinc-500">Thời lượng</dt>
                <dd className="text-white font-medium mt-0.5">{movie.runtime}</dd>
              </div>

              <div className="pt-2 border-t border-surface-border">
                <dt className="text-zinc-500">Điểm đánh giá</dt>
                <dd className="text-white font-medium mt-0.5">{movie.rating} / 10</dd>
              </div>

              <div className="pt-2 border-t border-surface-border">
                <dt className="text-zinc-500">Định dạng phát hành</dt>
                <dd className="text-zinc-400 mt-0.5">Chưa có thông tin ấn bản</dd>
              </div>
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
