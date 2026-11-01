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
    <section className="my-8" aria-labelledby="continue-title" data-testid="continue-watching">
      <h2 id="continue-title" className="comic-heading text-2xl font-bold">Phim còn dang dở</h2>
      <p className="mt-1 text-sm text-muted">Mốc xem lưu trên thiết bị này, theo từng phim.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {records.map((record) => (
          <Link
            key={record.movieId}
            href={buildMovieProgressHref(record)}
            data-testid="continue-card"
            className="comic-card p-4 hover:bg-mint"
          >
            <h3 className="font-bold">{record.title}</h3>
            <p className="mt-3 text-sm text-brand-dark">Xem tiếp từ {formatMark(record.positionMs)} →</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
