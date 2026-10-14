'use client';

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Check, Play, Star, RefreshCw, Loader2 } from 'lucide-react';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';

export function EditorialHero({ movie }: { movie: Movie | null }) {
  const {
    isWatchlisted,
    toggleWatchlist,
    openChat,
    isActionPending,
    isActionUnconfirmed,
    getActionIntent,
  } = useWatchlist();
  if (!movie) return null;

  const inWatchlist = isWatchlisted(movie.id);
  const isPending = isActionPending ? isActionPending(movie.id, 'watchlist') : false;
  const isUnconfirmed = isActionUnconfirmed ? isActionUnconfirmed(movie.id, 'watchlist') : false;
  const unconfirmedIntent = isUnconfirmed && getActionIntent ? getActionIntent(movie.id, 'watchlist') : null;

  const buttonAriaLabel = isPending
    ? `Đang xử lý ${movie.title}...`
    : isUnconfirmed
    ? unconfirmedIntent === 'add'
      ? `Chưa xác nhận lưu • Thử lưu lại ${movie.title} vào danh sách xem`
      : `Chưa xác nhận xóa • Thử xóa lại ${movie.title} khỏi danh sách xem`
    : inWatchlist
    ? 'Xóa khỏi Watchlist'
    : 'Thêm vào Watchlist';

  return (
    <section className="relative min-h-[420px] sm:min-h-[500px] lg:min-h-[560px] flex items-center overflow-hidden border-b border-surface-border bg-background">
      {/* 1. Backdrop Image Layer - z-0 with vivid visibility */}
      <div className="absolute inset-0 z-0 h-full w-full">
        {movie.backdrop && movie.backdrop.trim() ? (
          <Image
            priority
            src={movie.backdrop}
            alt={movie.title}
            fill
            sizes="100vw"
            className="object-cover object-center sm:object-right opacity-70 sm:opacity-85"
          />
        ) : (
          <div className="h-full w-full bg-gradient-to-br from-zinc-900 via-zinc-950 to-black flex items-center justify-center">
            <span className="text-zinc-800 font-bold text-4xl select-none">DIPPIE ANIMATION</span>
          </div>
        )}

        {/* 2. Directional gradient overlays for maximum text legibility & gentle fade */}
        <div className="absolute inset-0 bg-gradient-to-r from-background via-background/90 to-background/40 sm:via-background/80 sm:to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-background/50" />
      </div>

      {/* 3. Foreground Text & Controls - z-10 */}
      <div className="page-shell relative z-10 py-10 sm:py-16 lg:py-20">
        <div className="max-w-2xl">
          {/* Metadata Line */}
          <div className="flex items-center gap-3 text-xs font-semibold tracking-wider text-zinc-300">
            <span className="text-brand font-bold uppercase tracking-wider">Hoạt hình tiêu điểm</span>
            <span className="text-zinc-600">•</span>
            <span className="flex items-center gap-1 font-bold text-amber-400">
              <Star size={13} className="fill-amber-400" /> {movie.rating}
            </span>
            <span className="text-zinc-600">•</span>
            <span className="text-zinc-400">{movie.year}</span>
          </div>

          {/* Main Title */}
          <h1 className="mt-2.5 text-3xl font-extrabold tracking-tight text-white sm:text-5xl lg:text-6xl drop-shadow-md">
            {movie.title}
          </h1>

          {/* Quick Specs */}
          <div className="mt-2.5 flex items-center gap-2.5 text-xs sm:text-sm text-zinc-300">
            <span>{movie.runtime}</span>
            <span className="text-zinc-600">•</span>
            <span>{movie.genres.join(', ')}</span>
          </div>

          {/* Synopsis */}
          <p className="mt-3.5 max-w-xl text-xs sm:text-sm leading-relaxed text-zinc-200 line-clamp-3 sm:line-clamp-none drop-shadow">
            {movie.description}
          </p>

          {/* Action CTAs */}
          <div className="mt-6 flex flex-wrap items-center gap-2.5 sm:gap-3">
            <Link
              href={`/movies/${movie.id}`}
              className="btn-primary px-5 py-2.5 text-xs sm:text-sm font-bold shadow-brand-sm"
            >
              Xem chi tiết
            </Link>

            {isUnconfirmed && (
              <span
                data-testid="hero-unconfirmed-badge"
                className="inline-flex items-center gap-1 rounded bg-amber-500/90 px-2.5 py-1 text-[11px] font-bold text-zinc-950 shadow-md border border-amber-300"
              >
                <RefreshCw size={11} className="stroke-[2.5]" />
                Chưa xác nhận
              </span>
            )}

            <button
              onClick={() => toggleWatchlist(movie.id, movie.title, movie.poster)}
              disabled={isPending}
              className={`btn-secondary px-4 py-2.5 text-xs sm:text-sm font-semibold flex items-center gap-2 cursor-pointer transition disabled:opacity-60 ${
                isUnconfirmed
                  ? 'border-amber-400/60 bg-amber-500/15 text-amber-300 hover:bg-amber-500/25 ring-1 ring-amber-400/40'
                  : ''
              }`}
              aria-label={buttonAriaLabel}
            >
              {isPending ? (
                <>
                  <Loader2 size={15} className="animate-spin text-zinc-400" />
                  <span>Đang cập nhật...</span>
                </>
              ) : isUnconfirmed ? (
                <>
                  <RefreshCw size={15} className="text-amber-400 stroke-[2.5]" />
                  <span>{unconfirmedIntent === 'add' ? 'Thử lưu lại' : 'Thử xóa lại'}</span>
                </>
              ) : inWatchlist ? (
                <>
                  <Check size={15} className="text-brand" />
                  <span>Đã lưu Watchlist</span>
                </>
              ) : (
                '+ Thêm vào Watchlist'
              )}
            </button>

            <button
              onClick={openChat}
              className="rounded-md border border-surface-border bg-surface-elevated/90 px-3.5 py-2.5 text-xs font-semibold text-zinc-200 transition hover:border-brand hover:text-white cursor-pointer"
            >
              Hỏi CineBot
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
