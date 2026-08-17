'use client';

import React, { useRef } from 'react';
import Link from 'next/link';
import { ArrowLeft, ArrowRight, ArrowUpRight } from 'lucide-react';
import type { Movie } from '@/types/movie';
import { MovieCard } from './MovieCard';

type MovieSectionProps = {
  title: string;
  subtitle?: string;
  movies: Movie[];
  exploreHref?: string;
};

export function MovieSection({
  title,
  subtitle,
  movies,
  exploreHref = '/search',
}: MovieSectionProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const handleScroll = (direction: 'left' | 'right') => {
    if (scrollRef.current) {
      const scrollAmount = direction === 'left' ? -420 : 420;
      scrollRef.current.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    }
  };

  return (
    <section className="py-6 sm:py-8">
      {/* Header */}
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h2 className="section-title">{title}</h2>
          {subtitle && <p className="mt-1 text-xs sm:text-sm text-zinc-400">{subtitle}</p>}
        </div>

        <div className="flex items-center gap-2">
          {/* Scroll Navigation Controls */}
          <div className="hidden sm:flex items-center gap-1">
            <button
              onClick={() => handleScroll('left')}
              aria-label={`Cuộn ${title} sang trái`}
              className="rounded-md border border-zinc-800 bg-zinc-900 p-1.5 text-zinc-400 transition hover:border-zinc-600 hover:text-white cursor-pointer"
            >
              <ArrowLeft size={14} />
            </button>
            <button
              onClick={() => handleScroll('right')}
              aria-label={`Cuộn ${title} sang phải`}
              className="rounded-md border border-zinc-800 bg-zinc-900 p-1.5 text-zinc-400 transition hover:border-zinc-600 hover:text-white cursor-pointer"
            >
              <ArrowRight size={14} />
            </button>
          </div>

          <Link
            href={exploreHref}
            className="flex items-center gap-1 text-xs font-medium text-zinc-400 transition hover:text-cinema-red ml-2"
          >
            <span>Tất cả</span>
            <ArrowUpRight size={13} />
          </Link>
        </div>
      </div>

      {/* Row */}
      <div
        ref={scrollRef}
        className="movie-row -mx-4 flex gap-3 overflow-x-auto px-4 pb-3 sm:mx-0 sm:px-0 sm:gap-4 scroll-smooth"
      >
        {movies.map((movie) => (
          <MovieCard key={movie.id} movie={movie} />
        ))}
      </div>
    </section>
  );
}
