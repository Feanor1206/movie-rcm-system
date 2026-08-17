'use client';

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Check, Play, Star } from 'lucide-react';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';

export function EditorialHero({ movie }: { movie: Movie }) {
  const { isWatchlisted, toggleWatchlist, openChat } = useWatchlist();
  const inWatchlist = isWatchlisted(movie.id);

  return (
    <section className="relative min-h-[560px] sm:min-h-[640px] flex items-center overflow-hidden border-b border-zinc-800 bg-black">
      {/* 1. Backdrop Image Layer - z-0 with vivid visibility */}
      <div className="absolute inset-0 z-0 h-full w-full">
        <Image
          priority
          src={movie.backdrop}
          alt={movie.title}
          fill
          sizes="100vw"
          className="object-cover object-center sm:object-right"
        />

        {/* 2. Directional gradient overlays for maximum text legibility & seamless fade to black */}
        {/* Left-to-right fade: Solid black on far left behind text -> semi-transparent -> reveals movie art on right */}
        <div className="absolute inset-0 bg-gradient-to-r from-black via-black/85 to-black/30 sm:via-black/75 sm:to-transparent" />
        
        {/* Top & Bottom edge soft fades */}
        <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-black/40" />
      </div>

      {/* 3. Foreground Text & Controls - z-10 */}
      <div className="page-shell relative z-10 py-16 sm:py-24">
        <div className="max-w-2xl">
          {/* Metadata Line */}
          <div className="flex items-center gap-3 text-xs font-semibold tracking-wider text-zinc-300">
            <span className="text-cinema-red font-bold uppercase">Phim tiêu điểm</span>
            <span className="text-zinc-500">/</span>
            <span className="text-zinc-300">4K Ultra HD</span>
            <span className="text-zinc-500">/</span>
            <span className="flex items-center gap-1 font-bold text-amber-400">
              <Star size={13} className="fill-amber-400" /> {movie.rating}
            </span>
          </div>

          {/* Main Title */}
          <h1 className="mt-4 text-4xl font-extrabold tracking-tight text-white sm:text-6xl lg:text-7xl drop-shadow-md">
            {movie.title}
          </h1>

          {/* Quick Specs */}
          <div className="mt-3 flex items-center gap-3 text-sm text-zinc-300">
            <span className="font-semibold text-white">{movie.year}</span>
            <span className="text-zinc-600">•</span>
            <span>{movie.runtime}</span>
            <span className="text-zinc-600">•</span>
            <span>{movie.genres.join(', ')}</span>
          </div>

          {/* Synopsis */}
          <p className="mt-4 max-w-xl text-sm sm:text-base leading-relaxed text-zinc-200 drop-shadow">
            {movie.description}
          </p>

          {/* Action CTAs */}
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              href={`/movies/${movie.id}`}
              className="btn-primary px-6 py-3 text-sm font-bold shadow-red-sm"
            >
              <Play size={16} className="fill-current" /> Xem phim
            </Link>

            <button
              onClick={() => toggleWatchlist(movie.id, movie.title)}
              className="btn-secondary px-5 py-3 text-sm font-semibold"
              aria-label={inWatchlist ? 'Xóa khỏi Watchlist' : 'Thêm vào Watchlist'}
            >
              {inWatchlist ? (
                <>
                  <Check size={16} className="text-cinema-red" /> Đã lưu Watchlist
                </>
              ) : (
                '+ Thêm vào Watchlist'
              )}
            </button>

            <button
              onClick={openChat}
              className="rounded-md border border-zinc-700 bg-zinc-900/90 px-4 py-3 text-xs font-semibold text-zinc-200 transition hover:border-cinema-red hover:text-white cursor-pointer"
            >
              Hỏi CineBot về phim này
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
