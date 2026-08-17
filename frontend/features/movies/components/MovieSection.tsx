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
      const scrollAmount = direction === 'left' ? -460 : 460;
      scrollRef.current.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    }
  };

  return (
    <section className="py-8 sm:py-12">
      {/* Section Header */}
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h2 className="section-title">{title}</h2>
          {subtitle && <p className="mt-1 text-xs sm:text-sm text-cinema-400">{subtitle}</p>}
        </div>

        <div className="flex items-center gap-3">
          {/* Scroll Navigation Controls (Desktop) */}
          <div className="hidden sm:flex items-center gap-1.5">
            <button
              onClick={() => handleScroll('left')}
              aria-label={`Scroll ${title} left`}
              className="rounded-full border border-cinema-800 bg-cinema-900/80 p-2 text-cinema-400 transition hover:border-cinema-600 hover:text-white cursor-pointer"
            >
              <ArrowLeft size={14} />
            </button>
            <button
              onClick={() => handleScroll('right')}
              aria-label={`Scroll ${title} right`}
              className="rounded-full border border-cinema-800 bg-cinema-900/80 p-2 text-cinema-400 transition hover:border-cinema-600 hover:text-white cursor-pointer"
            >
              <ArrowRight size={14} />
            </button>
          </div>

          <Link
            href={exploreHref}
            className="flex shrink-0 items-center gap-1 font-mono text-[11px] uppercase tracking-wider text-cinema-400 transition hover:text-rose-400"
          >
            <span>View all</span>
            <ArrowUpRight size={14} />
          </Link>
        </div>
      </div>

      {/* Horizontal Carousel Row */}
      <div
        ref={scrollRef}
        className="movie-row -mx-4 flex gap-3 overflow-x-auto px-4 pb-4 sm:mx-0 sm:px-0 sm:gap-4 scroll-smooth"
      >
        {movies.map((movie) => (
          <MovieCard key={movie.id} movie={movie} />
        ))}
      </div>
    </section>
  );
}
