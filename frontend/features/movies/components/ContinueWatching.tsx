'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  buildMovieProgressHref,
  isUsableMovieProgress,
  listMovieProgress,
  type MovieProgressRecord,
} from '@/lib/services/movieProgress';

function formatMark(positionMs: number): string {
  const totalSeconds = Math.floor(positionMs / 1000);
  return `${Math.floor(totalSeconds / 60)}:${String(totalSeconds % 60).padStart(2, '0')}`;
}

export function ContinueWatching() {
  const [records, setRecords] = useState<MovieProgressRecord[]>([]);

  useEffect(() => {
    setRecords(listMovieProgress().filter(isUsableMovieProgress));
  }, []);

  if (!records.length) return null;

  return (
    <section className="my-10" aria-labelledby="continue-title" data-testid="continue-watching">
      <h2 id="continue-title" className="section-title mb-4">Xem tiếp</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {records.map((record) => (
          <Link
            key={record.movieId}
            href={buildMovieProgressHref(record)}
            data-testid="continue-card"
            className="comic-card group px-4 py-3 hover:border-brand/40 hover:bg-surface-elevated"
          >
            <h3 className="line-clamp-2 font-semibold text-ink group-hover:text-brand">{record.title}</h3>
            <p className="mt-1 text-sm text-muted">Xem tiếp từ {formatMark(record.positionMs)}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
