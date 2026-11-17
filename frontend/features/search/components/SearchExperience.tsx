'use client';

import { genreLabel, movieSynopsis } from '@/lib/labels';

import React, { useEffect, useRef, useState } from 'react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { browseCatalog } from '@/lib/services/catalogService';
import { buildMediaItemHref } from '@/lib/services/mediaRouting';
import type { Movie } from '@/types/movie';

type SearchSnapshot = {
  query: string;
  genre: string;
  page: number;
  size: number;
  results: Movie[];
  totalElements: number;
  totalPages: number;
};

const PAGE_SIZE_DEFAULT = 12;

function parseNonNegativeInteger(value: string | null, fallback: number): number {
  if (!value || !/^\d+$/.test(value)) return fallback;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : fallback;
}

function emptySnapshot(query: string, genre: string, page: number, size: number): SearchSnapshot {
  return { query, genre, page, size, results: [], totalElements: 0, totalPages: 0 };
}

export function SearchExperience() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const urlQuery = (searchParams.get('q') || searchParams.get('query') || '').trim();
  const genre = (searchParams.get('genre') || '').trim();
  const page = parseNonNegativeInteger(searchParams.get('page'), 0);
  const requestedSize = parseNonNegativeInteger(searchParams.get('size'), PAGE_SIZE_DEFAULT);
  const pageSize = requestedSize >= 1 && requestedSize <= 48 ? requestedSize : PAGE_SIZE_DEFAULT;

  const [inputValue, setInputValue] = useState(urlQuery);
  const [snapshot, setSnapshot] = useState<SearchSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryTrigger, setRetryTrigger] = useState(0);
  const lastPushedQueryRef = useRef<string | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    if (lastPushedQueryRef.current !== null && urlQuery === lastPushedQueryRef.current) {
      lastPushedQueryRef.current = null;
      return;
    }
    setInputValue(urlQuery);
  }, [urlQuery]);

  const updateUrl = (updates: { q?: string; page?: number }) => {
    const params = new URLSearchParams(searchParams.toString());
    if (updates.q !== undefined) {
      params.delete('query');
      if (updates.q.trim()) {
        params.set('q', updates.q.trim());
        lastPushedQueryRef.current = updates.q.trim();
      } else {
        params.delete('q');
        lastPushedQueryRef.current = '';
      }
    }
    if (updates.page !== undefined) {
      if (updates.page > 0) params.set('page', String(updates.page));
      else params.delete('page');
    }
    const queryString = params.toString();
    router.push(queryString ? `${pathname}?${queryString}` : pathname, { scroll: false });
  };

  useEffect(() => {
    if (inputValue.trim() === urlQuery) return;
    const timer = setTimeout(() => updateUrl({ q: inputValue, page: 0 }), 350);
    return () => clearTimeout(timer);
  }, [inputValue, urlQuery, searchParams, pathname, router]);

  useEffect(() => {
    const requestId = ++requestIdRef.current;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    browseCatalog({
      query: urlQuery || undefined,
      genre: genre || undefined,
      animationOnly: true,
      page,
      size: pageSize,
      signal: controller.signal,
    }).then((result) => {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      setSnapshot({
        query: urlQuery,
        genre,
        page,
        size: pageSize,
        results: result.items,
        totalElements: result.totalElements,
        totalPages: result.totalPages,
      });
      setLoading(false);
    }).catch((err: any) => {
      if (controller.signal.aborted || requestId !== requestIdRef.current || err?.name === 'AbortError' || err?.isCanceled) return;
      setSnapshot(emptySnapshot(urlQuery, genre, page, pageSize));
      setError(err?.message || 'Không thể tải kho phim hoạt hình.');
      setLoading(false);
    });

    return () => controller.abort();
  }, [urlQuery, genre, page, pageSize, retryTrigger]);

  const isCurrentSnapshot = snapshot?.query === urlQuery && snapshot.genre === genre && snapshot.page === page && snapshot.size === pageSize;
  const currentResults = isCurrentSnapshot ? snapshot.results : [];
  const totalElements = isCurrentSnapshot ? snapshot.totalElements : 0;
  const totalPages = Math.max(1, isCurrentSnapshot ? snapshot.totalPages : 1);
  const safePage = isCurrentSnapshot && snapshot.totalPages > 0 ? Math.min(page, snapshot.totalPages - 1) : page;

  useEffect(() => {
    if (isCurrentSnapshot && snapshot.totalPages > 0 && page !== safePage) updateUrl({ page: safePage });
  }, [isCurrentSnapshot, page, safePage, searchParams, pathname, router]);

  const clearQuery = () => {
    setInputValue('');
    updateUrl({ q: '', page: 0 });
  };

  return (
    <main className="page-shell min-h-[75vh] py-8 sm:py-12">
      <header className="catalog-cover">
        <h1 className="comic-heading text-3xl font-bold text-ink sm:text-5xl">Kho phim hoạt hình</h1>
        <div className="catalog-cover-art" aria-hidden="true" />
      </header>

      <div className="mt-6">
        <div className="flex max-w-2xl items-center rounded-lg border border-surface-border bg-surface px-3 focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/30">
          <input
            data-testid="search-query-input"
            aria-label="Tìm phim hoạt hình"
            autoFocus
            type="text"
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            placeholder="Tìm theo tên hoặc nội dung"
            className="min-h-12 min-w-0 flex-1 bg-transparent px-1 text-base text-ink placeholder:text-muted focus:outline-none focus-visible:shadow-none"
          />
          {inputValue && (
            <button
              onClick={clearQuery}
              className="min-h-[44px] min-w-[44px] cursor-pointer rounded-md px-2 text-sm text-muted hover:bg-surface-elevated hover:text-ink"
              aria-label="Xóa từ khóa"
            >
              Xóa
            </button>
          )}
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-y border-ink/20 py-3 text-sm text-muted">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 break-words">
          {urlQuery && <span className="min-w-0">Kết quả cho “{urlQuery}”</span>}
          {genre && <span>Thể loại {genreLabel(genre)}</span>}
        </div>
        <div className="flex items-center gap-2">
          {loading && snapshot && (
            <span className="text-brand-dark">Đang cập nhật…</span>
          )}
          {isCurrentSnapshot && !loading && <span className="font-medium text-ink">{totalElements} phim</span>}
        </div>
      </div>

      <section className="mt-6" aria-live="polite">
        {error && isCurrentSnapshot ? (
          <div role="alert" className="flex flex-col items-center rounded-xl border border-red-500/30 bg-red-950/10 px-6 py-12 text-center">
            <h2 className="mt-3 font-bold text-ink">Không thể tải kho phim</h2>
            <p className="mt-1 max-w-md text-sm text-muted">{error}</p>
            <button type="button" onClick={() => setRetryTrigger((value) => value + 1)} className="btn-primary mt-5 flex items-center gap-2 text-xs">
              Thử lại
            </button>
          </div>
        ) : !isCurrentSnapshot ? (
          <div data-testid="catalog-skeleton" role="status" className="rounded-xl border border-surface-border bg-surface p-12 text-center text-sm text-muted animate-pulse">
            Đang tải kho phim…
          </div>
        ) : isCurrentSnapshot && currentResults.length === 0 ? (
          <div className="rounded-xl border border-dashed border-surface-border bg-surface px-6 py-16 text-center">
            <h2 className="mt-2 font-bold text-ink text-base">Không tìm thấy phim phù hợp</h2>
            <p className="mt-1 text-sm text-muted max-w-md mx-auto">
              {urlQuery ? `Không có phim hoạt hình khớp với “${urlQuery}”.` : genre ? `Không có phim hoạt hình thuộc thể loại ${genreLabel(genre)}.` : 'Kho hiện chưa có phim hoạt hình nào.'}
            </p>
          </div>
        ) : isCurrentSnapshot ? (
          <>
            <div data-testid="catalog-results" className={`grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 ${loading ? 'opacity-60' : ''}`}>
              {currentResults.map((movie) => (
                <Link
                  key={movie.id}
                  href={buildMediaItemHref(movie)}
                  data-testid="search-result-card"
                  data-result-id={movie.id}
                  data-result-type={movie.item_type || 'movie'}
                  className="comic-card group flex flex-col justify-between p-4 sm:p-5 hover:border-brand/40 hover:bg-surface-elevated"
                >
                  <div>
                    <h2 className="comic-heading line-clamp-2 break-words text-base font-bold text-ink group-hover:text-brand-dark transition-colors">
                      {movie.title}
                    </h2>
                    {movie.description && (
                      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted">
                        {movieSynopsis(movie.description)}
                      </p>
                    )}
                  </div>
                  <div className="mt-4 flex items-center justify-between gap-3 text-xs">
                    <span className="text-muted">{movie.year || ''}</span>
                    <span className="font-semibold text-brand-dark">{movie.item_type === 'series' ? 'Chọn tập' : 'Xem phim'}</span>
                  </div>
                </Link>
              ))}
            </div>
            {totalPages > 1 && (
              <nav aria-label="Phân trang kho phim" className="mt-8 flex items-center justify-between rounded-xl border border-surface-border bg-surface px-5 py-3 text-xs text-muted">
                <span>Trang {safePage + 1} / {totalPages}</span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => updateUrl({ page: Math.max(0, safePage - 1) })}
                    disabled={safePage === 0 || loading}
                    className="btn-secondary flex items-center gap-1 text-xs py-1.5 px-3 disabled:opacity-40"
                  >
                    Trước
                  </button>
                  <button
                    type="button"
                    onClick={() => updateUrl({ page: Math.min(totalPages - 1, safePage + 1) })}
                    disabled={safePage >= totalPages - 1 || loading}
                    className="btn-secondary flex items-center gap-1 text-xs py-1.5 px-3 disabled:opacity-40"
                  >
                    Sau
                  </button>
                </div>
              </nav>
            )}
          </>
        ) : null}
      </section>
    </main>
  );
}
