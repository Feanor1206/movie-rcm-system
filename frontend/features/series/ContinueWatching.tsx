'use client';

import Link from 'next/link';
import { useWatchProgress } from '@/lib/hooks/useWatchProgress';
import { buildWatchProgressHref, isUsableResumeProgress } from '@/lib/services/watchProgressService';

export function ContinueWatching() {
  const { records, loading, error, reload, isGuest } = useWatchProgress();
  const saved = records.filter(isUsableResumeProgress);
  if (loading || (!saved.length && !error)) return null;
  return <section className="my-8" aria-labelledby="continue-title" data-testid="continue-watching">
    <h2 id="continue-title" className="comic-heading text-2xl font-bold">Chuyện còn đang kể</h2>
    <p className="mt-1 text-sm text-muted">{isGuest ? 'Mốc xem lưu trên thiết bị này.' : 'Mốc xem riêng của tài khoản bạn.'}</p>
    {error && <p role="status" className="mt-3 text-sm">{error} <button className="underline" onClick={reload}>Thử lại</button></p>}
    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {saved.map(record => <Link key={record.episodeId} href={buildWatchProgressHref(record)}
        data-testid="continue-card" className="comic-card p-4 hover:bg-mint">
        <p className="text-xs text-muted">{record.seriesTitle}{record.seasonNumber != null ? ` · Mùa ${record.seasonNumber}` : ''}</p>
        <h3 className="mt-1 font-bold">{record.episodeNumber != null ? `Tập ${record.episodeNumber}: ` : ''}{record.episodeTitle}</h3>
        <p className="mt-3 text-sm text-brand-dark">Xem tiếp từ {Math.floor(record.positionMs / 60000)}:{String(Math.floor(record.positionMs / 1000) % 60).padStart(2, '0')} →</p>
      </Link>)}
    </div>
  </section>;
}
