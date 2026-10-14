'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Bookmark, Check, Loader2, Star, RefreshCw, Film } from 'lucide-react';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';

type MovieCardProps = {
  movie: Movie;
  fluid?: boolean;
};

export function MovieCard({ movie, fluid = false }: MovieCardProps) {
  const {
    isWatchlisted,
    toggleWatchlist,
    isActionPending,
    isActionUnconfirmed,
    getActionIntent,
  } = useWatchlist();
  const [posterError, setPosterError] = useState(false);

  const inWatchlist = isWatchlisted(movie.id);
  const isPending = isActionPending(movie.id, 'watchlist');
  const isUnconfirmed = isActionUnconfirmed(movie.id, 'watchlist');
  const unconfirmedIntent = isUnconfirmed ? getActionIntent(movie.id, 'watchlist') : null;

  const buttonAriaLabel = isPending
    ? `Đang xử lý ${movie.title}...`
    : isUnconfirmed
    ? unconfirmedIntent === 'add'
      ? `Chưa xác nhận lưu • Thử lưu lại ${movie.title} vào danh sách xem`
      : `Chưa xác nhận xóa • Thử xóa lại ${movie.title} khỏi danh sách xem`
    : inWatchlist
    ? `Xóa ${movie.title} khỏi watchlist`
    : `Thêm ${movie.title} vào watchlist`;

  const buttonTitle = isUnconfirmed
    ? unconfirmedIntent === 'add'
      ? 'Chưa xác nhận lưu • Nhấn để thử lưu lại'
      : 'Chưa xác nhận xóa • Nhấn để thử xóa lại'
    : undefined;

  const hasPoster = Boolean(movie.poster && movie.poster.trim() && !posterError);

  return (
    <div
      className={`group relative block outline-none transition-transform duration-200 hover:-translate-y-1 ${
        fluid ? 'w-full' : 'w-[155px] shrink-0 sm:w-[185px] md:w-[205px]'
      }`}
    >
      <article className="overflow-hidden rounded-lg border border-surface-border bg-surface transition-all duration-200 group-hover:border-brand/40 group-hover:shadow-card-hover">
        {/* Poster Media */}
        <div className="relative aspect-[2/3] w-full overflow-hidden bg-surface-elevated">
          {hasPoster ? (
            <Image
              src={movie.poster}
              alt={movie.title}
              fill
              onError={() => setPosterError(true)}
              sizes={
                fluid
                  ? '(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw'
                  : '(max-width: 640px) 155px, (max-width: 1024px) 185px, 205px'
              }
              className="object-cover transition-transform duration-300 group-hover:scale-105"
            />
          ) : (
            <div className="flex h-full w-full flex-col items-center justify-center p-3 text-center bg-zinc-900 text-zinc-500">
              <Film size={28} className="mb-2 text-zinc-600" />
              <span className="text-[11px] font-medium leading-tight line-clamp-2 text-zinc-400">
                {movie.title}
              </span>
            </div>
          )}

          {/* Overlay gradient */}
          <div className="absolute inset-0 bg-gradient-to-t from-background/90 via-transparent to-background/30 opacity-70" />

          {/* Rating Badge */}
          <span className="absolute top-2 left-2 z-10 flex items-center gap-1 rounded bg-surface/80 px-2 py-0.5 text-[11px] font-bold text-amber-400 border border-surface-border backdrop-blur-md">
            <Star size={11} className="fill-amber-400" />
            {movie.rating}
          </span>

          {/* Unconfirmed Status Badge */}
          {isUnconfirmed && (
            <span
              data-testid="unconfirmed-badge"
              className="absolute bottom-2 left-2 z-10 flex items-center gap-1 rounded bg-amber-500/95 px-2 py-0.5 text-[10px] font-bold text-zinc-950 shadow-md border border-amber-300 backdrop-blur-md"
            >
              <RefreshCw size={10} className="stroke-[2.5]" />
              Chưa xác nhận
            </span>
          )}

          {/* Hover / Focus Overlay: Navigate to Details */}
          <Link
            href={`/movies/${movie.id}`}
            aria-label={`Xem chi tiết ${movie.title}`}
            className="absolute inset-0 z-10 flex items-center justify-center bg-black/40 opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-within:opacity-100 cursor-pointer"
          >
            <span className="inline-flex items-center gap-1.5 rounded-full bg-brand px-3.5 py-1.5 text-xs font-bold text-zinc-950 shadow-brand-sm backdrop-blur-sm transition-transform duration-150 hover:scale-105 hover:bg-brand-hover">
              Xem chi tiết
            </span>
          </Link>

          {/* Quick Watchlist Toggle - z-20 so it is NEVER blocked by the overlay link */}
          <button
            type="button"
            aria-label={buttonAriaLabel}
            title={buttonTitle}
            disabled={isPending}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              toggleWatchlist(movie.id, movie.title, movie.poster);
            }}
            className={`absolute top-2 right-2 z-20 rounded-full p-2 backdrop-blur-md transition-all duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-brand focus-visible:outline-none disabled:opacity-60 ${
              isUnconfirmed
                ? 'bg-amber-400 text-zinc-950 shadow-md border border-amber-300 hover:bg-amber-300 ring-2 ring-amber-400/40'
                : inWatchlist
                ? 'bg-brand text-zinc-950 shadow-brand-sm'
                : 'bg-surface/85 text-zinc-300 border border-surface-border hover:bg-brand hover:text-zinc-950 hover:border-brand'
            }`}
          >
            {isPending ? (
              <Loader2 size={13} className="animate-spin" />
            ) : isUnconfirmed ? (
              <RefreshCw size={13} className="stroke-[2.5]" />
            ) : inWatchlist ? (
              <Check size={13} />
            ) : (
              <Bookmark size={13} />
            )}
          </button>
        </div>

        {/* Content Info */}
        <div className="p-3">
          <Link
            href={`/movies/${movie.id}`}
            className="block truncate text-sm font-semibold text-white transition-colors hover:text-brand focus-visible:outline-none focus-visible:text-brand"
          >
            {movie.title}
          </Link>

          <div className="mt-1 flex items-center justify-between text-xs text-zinc-400">
            <span>{movie.year} · {movie.runtime}</span>
          </div>

          <p className="mt-1 truncate text-xs text-zinc-500">
            {movie.genres.join(', ')}
          </p>
        </div>
      </article>
    </div>
  );
}
