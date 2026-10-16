'use client';

import React, { useRef } from 'react';
import Link from 'next/link';
import type { Movie } from '@/types/movie';
import { MovieCard } from './MovieCard';

type MovieSectionProps = {
  title: string;
  subtitle?: string;
  movies: Movie[];
  exploreHref?: string;
};

const BTN_SCROLL = 'rounded-md border border-surface-border bg-surface p-1.5 text-zinc-400 transition hover:border-brand/40 hover:text-white cursor-pointer';

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
              className={BTN_SCROLL}
            >
              <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="m12 19-7-7 7-7M19 12H5"/></svg>
            </button>
            <button
              onClick={() => handleScroll('right')}
              aria-label={`Cuộn ${title} sang phải`}
              className={BTN_SCROLL}
            >
              <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </button>
          </div>

          <Link
            href={exploreHref}
            className="flex items-center gap-1 text-xs font-medium text-zinc-400 transition hover:text-brand ml-2"
          >
            <span>Tất cả</span>
            <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M7 7h10v10M7 17 17 7"/></svg>
          </Link>
        </div>
      </div>

      {/* Row or Empty State */}
      {movies.length > 0 ? (
        <div
          ref={scrollRef}
          className="movie-row -mx-4 flex gap-3 overflow-x-auto px-4 pb-3 sm:mx-0 sm:px-0 sm:gap-4 scroll-smooth"
        >
          {movies.map((movie) => (
            <MovieCard key={movie.id} movie={movie} />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-surface-border bg-surface p-6 text-center text-xs sm:text-sm text-zinc-400">
          Hiện chưa có tác phẩm hoạt hình nào trong danh mục này.
        </div>
      )}
    </section>
  );
}
