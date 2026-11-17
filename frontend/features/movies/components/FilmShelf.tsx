'use client';

import React from 'react';
import Link from 'next/link';
import { movieSynopsis } from '@/lib/labels';
import { buildMediaItemHref } from '@/lib/services/mediaRouting';
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
    <section data-testid="film-shelf" className="mt-10">
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <h2 className="comic-heading text-2xl font-bold text-ink tracking-tight">{title}</h2>
          {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
        </div>
        <Link href={exploreHref} className="shrink-0 text-sm font-semibold text-brand-dark hover:text-brand-dark hover:underline">
          Mở kho
        </Link>
      </div>
      {movies.length === 0 ? (
        <div className="rounded-xl border border-dashed border-surface-border p-8 text-center text-sm text-muted">
          Chưa có phim hoạt hình nào trong kho.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {movies.map((movie) => (
            <Link
              key={movie.id}
              href={buildMediaItemHref(movie)}
              data-testid="film-card"
              data-movie-id={movie.id}
              className="comic-card group flex flex-col justify-between p-4 sm:p-5 hover:border-brand/40 hover:bg-surface-elevated"
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <h3 className="comic-heading min-w-0 break-words text-base font-bold text-ink group-hover:text-brand-dark">{movie.title}</h3>
                  {movie.year ? <span className="shrink-0 text-xs text-muted">{movie.year}</span> : null}
                </div>
                {movie.description && (
                  <p className="mt-2.5 line-clamp-3 text-sm leading-relaxed text-muted">{movieSynopsis(movie.description)}</p>
                )}
              </div>
              <span className="mt-4 text-right text-xs font-semibold text-brand-dark">
                {movie.item_type === 'series' ? 'Chọn tập' : 'Xem phim'}
              </span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
