'use client';

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Bookmark, Check, Play, Star } from 'lucide-react';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';

type MovieCardProps = {
  movie: Movie;
  fluid?: boolean;
};

export function MovieCard({ movie, fluid = false }: MovieCardProps) {
  const { isWatchlisted, toggleWatchlist } = useWatchlist();
  const inWatchlist = isWatchlisted(movie.id);

  return (
    <div
      className={`group relative block outline-none transition-transform duration-200 hover:-translate-y-1 ${
        fluid ? 'w-full' : 'w-[155px] shrink-0 sm:w-[185px] md:w-[205px]'
      }`}
    >
      <article className="overflow-hidden rounded-lg border border-zinc-850 bg-zinc-950 transition-all duration-200 group-hover:border-zinc-650 group-hover:shadow-card-hover">
        {/* Poster Media */}
        <div className="relative aspect-[2/3] w-full overflow-hidden bg-zinc-900">
          <Image
            src={movie.poster}
            alt={movie.title}
            fill
            sizes={
              fluid
                ? '(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw'
                : '(max-width: 640px) 155px, (max-width: 1024px) 185px, 205px'
            }
            className="object-cover transition-transform duration-300 group-hover:scale-105"
          />

          {/* Overlay gradient */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/30 opacity-70" />

          {/* Rating Badge */}
          <span className="absolute top-2 left-2 flex items-center gap-1 rounded bg-black/80 px-2 py-0.5 text-[11px] font-bold text-amber-400 border border-white/10 backdrop-blur-md">
            <Star size={11} className="fill-amber-400" />
            {movie.rating}
          </span>

          {/* Quick Watchlist Toggle */}
          <button
            type="button"
            aria-label={inWatchlist ? `Xóa ${movie.title} khỏi watchlist` : `Thêm ${movie.title} vào watchlist`}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              toggleWatchlist(movie.id, movie.title);
            }}
            className={`absolute top-2 right-2 rounded-full p-2 backdrop-blur-md transition-all duration-150 cursor-pointer ${
              inWatchlist
                ? 'bg-cinema-red text-white'
                : 'bg-black/70 text-zinc-300 opacity-90 hover:bg-cinema-red hover:text-white'
            }`}
          >
            {inWatchlist ? <Check size={13} /> : <Bookmark size={13} />}
          </button>

          {/* Hover Play Overlay */}
          <Link
            href={`/movies/${movie.id}`}
            aria-label={`Xem ${movie.title}`}
            className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition-opacity duration-200 group-hover:opacity-100 cursor-pointer"
          >
            <span className="grid h-11 w-11 place-items-center rounded-full bg-cinema-red text-white shadow-red-sm transition-transform duration-150 hover:scale-110">
              <Play size={16} className="fill-current ml-0.5" />
            </span>
          </Link>
        </div>

        {/* Content Info */}
        <div className="p-3">
          <Link
            href={`/movies/${movie.id}`}
            className="block truncate text-sm font-semibold text-white transition-colors hover:text-cinema-red"
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
