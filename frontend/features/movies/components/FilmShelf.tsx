'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';
import type { Movie } from '@/types/movie';

type FilmShelfProps = {
  movies: Movie[];
  title?: string;
  subtitle?: string;
  exploreHref?: string;
};

export function FilmShelf({
  movies,
  title = 'Phim hoạt hình trong kho',
  subtitle = 'Chọn một phim để xem.',
  exploreHref = '/search',
}: FilmShelfProps) {
  return (
    <section data-testid="film-shelf" className="mt-8">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h2 className="comic-heading text-2xl font-bold text-ink">{title}</h2>
          <p className="mt-1 text-sm text-muted">{subtitle}</p>
        </div>
        <Link href={exploreHref} className="hidden items-center gap-1 text-xs font-semibold text-brand-dark sm:flex">
          Mở kho <ArrowUpRight size={15} />
        </Link>
      </div>
      {movies.length === 0 ? (
        <div className="comic-card border-dashed p-6 text-sm text-muted">Chưa có phim hoạt hình nào trong kho.</div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {movies.map((movie) => (
            <Link
              key={movie.id}
              href={`/movies/${encodeURIComponent(movie.id)}`}
              data-testid="film-card"
              data-movie-id={movie.id}
              className="comic-card group flex min-h-40 flex-col justify-between p-4 transition-colors hover:bg-mint"
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <h3 className="comic-heading text-lg font-bold text-ink">{movie.title}</h3>
                  {movie.year ? <span className="shrink-0 text-xs text-muted">{movie.year}</span> : null}
                </div>
                {movie.description && (
                  <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-muted">{movie.description}</p>
                )}
              </div>
              <span className="mt-4 flex items-center justify-end gap-1 text-xs font-semibold text-brand-dark">
                Xem phim <ArrowUpRight size={14} className="transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
              </span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
