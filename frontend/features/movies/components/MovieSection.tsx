'use client';

import React, { useRef, useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { ChevronLeft, ChevronRight, ArrowRight, Film } from 'lucide-react';
import type { Movie } from '@/types/movie';
import { MovieCard } from './MovieCard';

type MovieSectionProps = {
  title: string;
  subtitle?: string;
  movies: Movie[];
  exploreHref?: string;
};

const BTN_HEADER_SCROLL =
  'rounded-lg border border-surface-border/80 bg-surface/80 p-2 text-zinc-400 transition-all hover:border-brand/50 hover:bg-surface-hover hover:text-white active:scale-95 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed';

export function MovieSection({
  title,
  subtitle,
  movies,
  exploreHref = '/search',
}: MovieSectionProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  // Check scroll boundary to toggle arrow states and gradient masks
  const checkScrollState = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const { scrollLeft, scrollWidth, clientWidth } = el;
    setCanScrollLeft(scrollLeft > 10);
    setCanScrollRight(scrollLeft + clientWidth < scrollWidth - 10);
  }, []);

  useEffect(() => {
    checkScrollState();
    const el = scrollRef.current;
    if (!el) return;

    el.addEventListener('scroll', checkScrollState, { passive: true });
    window.addEventListener('resize', checkScrollState);
    return () => {
      el.removeEventListener('scroll', checkScrollState);
      window.removeEventListener('resize', checkScrollState);
    };
  }, [checkScrollState, movies]);

  const handleScroll = (dir: number) => {
    if (!scrollRef.current) return;
    const scrollAmount = Math.max(scrollRef.current.clientWidth * 0.75, 320);
    scrollRef.current.scrollBy({ left: dir * scrollAmount, behavior: 'smooth' });
  };

  return (
    <section className="group/section relative py-7 sm:py-9">
      {/* Header */}
      <div className="mb-4 sm:mb-5 flex items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="h-5 w-1 rounded-full bg-brand shadow-brand-sm" />
            <h2 className="section-title text-xl font-extrabold tracking-tight text-white sm:text-2xl">
              {title}
            </h2>
          </div>
          {subtitle && (
            <p className="mt-1.5 pl-3.5 text-xs text-zinc-400 sm:text-sm">{subtitle}</p>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Header Scroll Navigation Controls (Desktop) */}
          <div className="hidden sm:flex items-center gap-1.5">
            <button
              onClick={() => handleScroll(-1)}
              disabled={!canScrollLeft}
              aria-label={`Cuộn ${title} sang trái`}
              className={BTN_HEADER_SCROLL}
            >
              <ChevronLeft size={16} />
            </button>
            <button
              onClick={() => handleScroll(1)}
              disabled={!canScrollRight}
              aria-label={`Cuộn ${title} sang phải`}
              className={BTN_HEADER_SCROLL}
            >
              <ChevronRight size={16} />
            </button>
          </div>

          <Link
            href={exploreHref}
            className="group/link flex items-center gap-1 text-xs font-semibold text-zinc-400 transition hover:text-brand"
          >
            <span>Tất cả</span>
            <ArrowRight
              size={13}
              className="transition-transform duration-200 group-hover/link:translate-x-1"
            />
          </Link>
        </div>
      </div>

      {/* Row or Empty State */}
      {movies.length > 0 ? (
        <div className="relative">
          {/* Left Fading Edge Vignette */}
          <div
            className={`pointer-events-none absolute -left-4 sm:left-0 top-0 bottom-0 z-20 w-8 sm:w-16 bg-gradient-to-r from-background to-transparent transition-opacity duration-300 ${
              canScrollLeft ? 'opacity-100' : 'opacity-0'
            }`}
          />

          {/* Right Fading Edge Vignette */}
          <div
            className={`pointer-events-none absolute -right-4 sm:right-0 top-0 bottom-0 z-20 w-8 sm:w-16 bg-gradient-to-l from-background to-transparent transition-opacity duration-300 ${
              canScrollRight ? 'opacity-100' : 'opacity-0'
            }`}
          />

          {/* Floating Left Carousel Arrow (Netflix style overlay) */}
          {canScrollLeft && (
            <button
              type="button"
              onClick={() => handleScroll(-1)}
              aria-label={`Cuộn ${title} sang trái`}
              className="absolute left-2 top-1/2 -translate-y-1/2 z-30 hidden sm:flex h-11 w-11 items-center justify-center rounded-full bg-black/85 text-white border border-white/20 backdrop-blur-md shadow-2xl opacity-0 group-hover/section:opacity-100 transition-all duration-200 hover:scale-115 hover:bg-brand hover:text-zinc-950 hover:border-brand active:scale-95 cursor-pointer"
            >
              <ChevronLeft size={22} className="stroke-[2.5]" />
            </button>
          )}

          {/* Floating Right Carousel Arrow (Netflix style overlay) */}
          {canScrollRight && (
            <button
              type="button"
              onClick={() => handleScroll(1)}
              aria-label={`Cuộn ${title} sang phải`}
              className="absolute right-2 top-1/2 -translate-y-1/2 z-30 hidden sm:flex h-11 w-11 items-center justify-center rounded-full bg-black/85 text-white border border-white/20 backdrop-blur-md shadow-2xl opacity-0 group-hover/section:opacity-100 transition-all duration-200 hover:scale-115 hover:bg-brand hover:text-zinc-950 hover:border-brand active:scale-95 cursor-pointer"
            >
              <ChevronRight size={22} className="stroke-[2.5]" />
            </button>
          )}

          {/* Movie Cards Container */}
          <div
            ref={scrollRef}
            className="movie-row -mx-4 flex gap-3 overflow-x-auto px-4 py-3 sm:mx-0 sm:px-0 sm:gap-4.5 scroll-smooth"
          >
            {movies.map((movie) => (
              <MovieCard key={movie.id} movie={movie} />
            ))}
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-surface-border/80 bg-surface/50 p-8 text-center backdrop-blur-sm">
          <Film size={32} className="text-zinc-600 mb-1" />
          <p className="text-sm font-medium text-zinc-400">
            Hiện chưa có tác phẩm hoạt hình nào trong danh mục này.
          </p>
        </div>
      )}
    </section>
  );
}
