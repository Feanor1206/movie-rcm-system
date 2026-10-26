'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';
import type { CatalogSeriesSummary } from '@/lib/services/catalogService';

type SeriesShelfProps = {
  series: CatalogSeriesSummary[];
  title?: string;
  subtitle?: string;
  exploreHref?: string;
};

export function SeriesShelf({
  series,
  title = 'Những bộ hoạt hình trong kho',
  subtitle = 'Chọn một bộ để xem mùa và tập.',
  exploreHref = '/search',
}: SeriesShelfProps) {
  return (
    <section data-testid="series-shelf" className="mt-8">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h2 className="comic-heading text-2xl font-bold text-ink">{title}</h2>
          <p className="mt-1 text-sm text-muted">{subtitle}</p>
        </div>
        <Link href={exploreHref} className="hidden items-center gap-1 text-xs font-semibold text-brand-dark sm:flex">
          Mở kho <ArrowUpRight size={15} />
        </Link>
      </div>
      {series.length === 0 ? (
        <div className="comic-card border-dashed p-6 text-sm text-muted">Chưa có bộ hoạt hình nào trong catalog.</div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {series.map((item) => {
            const years = [item.releaseYearStart, item.releaseYearEnd]
              .filter((year): year is number => typeof year === 'number' && Number.isFinite(year));
            const yearLabel = years.length > 1 && years[0] !== years[1]
              ? `${years[0]}–${years[1]}`
              : years[0] !== undefined ? String(years[0]) : '';
            return (
              <Link
                key={item.id}
                href={`/series/${encodeURIComponent(item.id)}`}
                data-testid="series-card"
                data-series-id={item.id}
                className="comic-card group flex min-h-40 flex-col justify-between p-4 transition-colors hover:bg-mint"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="comic-heading text-lg font-bold text-ink">{item.title}</h3>
                    {yearLabel && <span className="shrink-0 text-xs text-muted">{yearLabel}</span>}
                  </div>
                  {item.originalTitle && item.originalTitle !== item.title && (
                    <p className="mt-1 text-xs italic text-muted">{item.originalTitle}</p>
                  )}
                  {item.synopsis && <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-muted">{item.synopsis}</p>}
                </div>
                <span className="mt-4 flex items-center justify-end gap-1 text-xs font-semibold text-brand-dark">
                  Mở bộ <ArrowUpRight size={14} className="transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}
