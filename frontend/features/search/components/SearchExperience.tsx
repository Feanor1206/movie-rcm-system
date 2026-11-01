'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { AlertCircle, ChevronLeft, ChevronRight, Film, RefreshCw, Search, X } from 'lucide-react';
import Link from 'next/link';
import { browseCatalog } from '@/lib/services/catalogService';
import type { Movie } from '@/types/movie';

type SearchSnapshot = {
  query: string;
  page: number;
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

function emptySnapshot(query: string, page: number): SearchSnapshot {
  return { query, page, results: [], totalElements: 0, totalPages: 0 };
}

export function SearchExperience() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const urlQuery = (searchParams.get('q') || searchParams.get('query') || '').trim();
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
      animationOnly: true,
      page,
      size: pageSize,
      signal: controller.signal,
    }).then((result) => {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      setSnapshot({
        query: urlQuery,
        page,
        results: result.items,
        totalElements: result.totalElements,
        totalPages: result.totalPages,
      });
      setLoading(false);
    }).catch((err: any) => {
      if (controller.signal.aborted || requestId !== requestIdRef.current || err?.name === 'AbortError' || err?.isCanceled) return;
      setSnapshot(emptySnapshot(urlQuery, page));
      setError(err?.message || 'Không thể tải kho phim hoạt hình.');
      setLoading(false);
    });

    return () => controller.abort();
  }, [urlQuery, page, pageSize, retryTrigger]);

  const isCurrentSnapshot = snapshot?.query === urlQuery && snapshot.page === page;
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
      <header>
        <h1 className="comic-heading text-3xl font-bold tracking-tight text-ink sm:text-4xl">Tìm một phim.</h1>
        <p className="mt-1.5 text-sm text-muted">Tìm phim hoạt hình lẻ trong kho.</p>
      </header>

      <div className="mt-6">
        <div className="relative flex max-w-2xl items-center border-2 border-ink bg-surface px-3.5 py-3 shadow-brand-sm focus-within:bg-mint/30">
          <Search className="shrink-0 text-muted" size={18} />
          <input
            data-testid="search-query-input"
            aria-label="Tìm phim hoạt hình"
            autoFocus
            type="text"
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            placeholder="Tên phim hoạt hình…"
            className="w-full bg-transparent px-3 text-sm text-ink placeholder:text-muted focus:outline-none"
          />
          {inputValue && (
            <button
              onClick={clearQuery}
              className="cursor-pointer rounded p-1 text-muted hover:bg-surface-elevated hover:text-ink"
              aria-label="Xóa từ khóa"
            >
              <X size={15} />
            </button>
          )}
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-y border-surface-border py-3 text-xs text-muted">
        <div className="flex items-center gap-2"><Film size={14} /><span>{urlQuery ? `Kết quả cho “${urlQuery}”` : 'Phim hoạt hình trong kho'}</span></div>
        <div className="flex items-center gap-2">
          {loading && snapshot && <span className="flex items-center gap-1 text-brand"><RefreshCw size={11} className="animate-spin" />Đang cập nhật…</span>}
          {isCurrentSnapshot && !loading && <span>{totalElements} phim</span>}
        </div>
      </div>

      <section className="mt-6" aria-live="polite">
        {error ? (
          <div role="alert" className="flex flex-col items-center rounded-lg border border-red-500/30 bg-red-950/10 px-6 py-12 text-center">
            <AlertCircle size={24} className="text-red-400" />
            <h2 className="mt-3 font-bold text-ink">Không thể tải kho phim</h2>
            <p className="mt-1 max-w-md text-sm text-muted">{error}</p>
            <button type="button" onClick={() => setRetryTrigger((value) => value + 1)} className="btn-primary mt-5 flex items-center gap-2 text-xs">
              <RefreshCw size={13} /> Thử lại
            </button>
          </div>
        ) : loading && !isCurrentSnapshot ? (
          <div data-testid="catalog-skeleton" role="status" className="rounded-lg border border-surface-border bg-surface p-8 text-center text-sm text-muted">Đang tải kho phim…</div>
        ) : isCurrentSnapshot && currentResults.length === 0 ? (
          <div className="rounded-lg border border-dashed border-surface-border bg-surface px-6 py-16 text-center">
            <Search size={22} className="mx-auto text-muted" />
            <h2 className="mt-3 font-bold text-ink">Không tìm thấy phim phù hợp</h2>
            <p className="mt-1 text-sm text-muted">{urlQuery ? `Không có phim hoạt hình khớp với “${urlQuery}”.` : 'Kho hiện chưa có phim hoạt hình nào.'}</p>
          </div>
        ) : isCurrentSnapshot ? (
          <>
            <div data-testid="catalog-results" className={`grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 ${loading ? 'opacity-60' : ''}`}>
              {currentResults.map((movie) => (
                <Link
                  key={movie.id}
                  href={`/movies/${encodeURIComponent(movie.id)}`}
                  data-testid="search-result-card"
                  data-result-id={movie.id}
                  data-result-type="movie"
                  className="comic-card flex min-h-36 flex-col justify-between p-4 transition-colors hover:bg-mint"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="border border-ink/30 bg-mint px-1.5 py-0.5 text-[10px] font-bold text-ink">Phim hoạt hình</span>
                      {movie.year ? <span className="text-xs text-muted">{movie.year}</span> : null}
                    </div>
                    <h2 className="comic-heading mt-2 line-clamp-2 text-base font-bold text-ink">{movie.title}</h2>
                    {movie.description && <p className="mt-1.5 line-clamp-3 text-xs leading-relaxed text-muted">{movie.description}</p>}
                  </div>
                  <span className="mt-3 text-right text-xs font-semibold text-brand-dark">Xem phim →</span>
                </Link>
              ))}
            </div>
            {totalPages > 1 && (
              <nav aria-label="Phân trang kho phim" className="mt-6 flex items-center justify-between rounded-lg border border-surface-border bg-surface px-4 py-3 text-xs text-muted">
                <span>Trang {safePage + 1} / {totalPages}</span>
                <div className="flex gap-2">
                  <button type="button" onClick={() => updateUrl({ page: Math.max(0, safePage - 1) })} disabled={safePage === 0 || loading} className="btn-secondary flex items-center gap-1 text-xs disabled:opacity-40"><ChevronLeft size={14} />Trước</button>
                  <button type="button" onClick={() => updateUrl({ page: Math.min(totalPages - 1, safePage + 1) })} disabled={safePage >= totalPages - 1 || loading} className="btn-secondary flex items-center gap-1 text-xs disabled:opacity-40">Sau<ChevronRight size={14} /></button>
                </div>
              </nav>
            )}
          </>
        ) : null}
      </section>
    </main>
  );
}
