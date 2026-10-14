'use client';

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import {
  Search,
  X,
  SlidersHorizontal,
  RotateCcw,
  AlertCircle,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Calendar,
} from 'lucide-react';
import { MovieCard } from '@/features/movies/components/MovieCard';
import { browseCatalog, type PageResponse } from '@/lib/services/catalogService';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';

const DISCOVERY_GENRES = ['Adventure', 'Family', 'Fantasy', 'Sci-Fi', 'Drama', 'Romance', 'Comedy'];

type SortOption = 'rating' | 'year' | 'title';

type DataSnapshot = {
  key: string;
  query: string;
  genres: string[];
  yearMin?: number;
  yearMax?: number;
  sort: string;
  direction: string;
  page: number;
  size: number;
  data: PageResponse<Movie>;
};

export function SearchExperience() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { openChat } = useWatchlist();

  // 1. Read URL parameters as Single Source of Truth
  const urlQuery = (searchParams.get('q') || searchParams.get('query') || '').trim();
  const urlGenre = (searchParams.get('genre') || '').trim();
  const urlGenresParam = (searchParams.get('genres') || '').trim();
  const urlSort = searchParams.get('sort') || 'rating';
  const urlDirection = searchParams.get('direction') || (urlSort === 'title' ? 'asc' : 'desc');

  // Strict integer helper: rejects non-numeric or fractional strings like '1.5' or '2junk'
  const parseStrictInteger = (val: string | null): number | undefined => {
    if (!val || typeof val !== 'string') return undefined;
    const trimmed = val.trim();
    if (!/^\d+$/.test(trimmed)) return undefined;
    const n = Number(trimmed);
    return Number.isSafeInteger(n) ? n : undefined;
  };

  // Page validation: strict non-negative integer >= 0
  const urlPageRaw = parseStrictInteger(searchParams.get('page'));
  const validatedPage = urlPageRaw !== undefined && urlPageRaw >= 0 ? urlPageRaw : 0;

  // Size validation: strict integer 1..100 (default 12)
  const urlSizeRaw = parseStrictInteger(searchParams.get('size'));
  const validatedSize = urlSizeRaw !== undefined && urlSizeRaw >= 1 && urlSizeRaw <= 100 ? urlSizeRaw : 12;

  // Year bounds validation: strict integers 1888..2100
  const parsedYearMin = parseStrictInteger(searchParams.get('yearMin'));
  const parsedYearMax = parseStrictInteger(searchParams.get('yearMax'));
  const validatedYearMin =
    parsedYearMin !== undefined && parsedYearMin >= 1888 && parsedYearMin <= 2100
      ? parsedYearMin
      : undefined;
  const validatedYearMax =
    parsedYearMax !== undefined && parsedYearMax >= 1888 && parsedYearMax <= 2100
      ? parsedYearMax
      : undefined;

  // Genres deduplication (supports ?genre=... and ?genres=...)
  const selectedGenres = useMemo(() => {
    const list: string[] = [];
    if (urlGenre) list.push(urlGenre);
    if (urlGenresParam) {
      urlGenresParam.split(',').forEach((g) => {
        const trimmed = g.trim();
        if (trimmed && !list.includes(trimmed)) list.push(trimmed);
      });
    }
    return list;
  }, [urlGenre, urlGenresParam]);

  const validatedSort: SortOption =
    urlSort === 'year' || urlSort === 'title' ? urlSort : 'rating';
  const validatedDirection: 'asc' | 'desc' =
    urlDirection === 'asc' || urlDirection === 'desc'
      ? urlDirection
      : validatedSort === 'title'
      ? 'asc'
      : 'desc';

  // 2. Canonical Params Key for Data Snapshot (S2)
  const currentParamsKey = useMemo(() => {
    return JSON.stringify({
      q: urlQuery,
      genres: [...selectedGenres].sort(),
      yearMin: validatedYearMin,
      yearMax: validatedYearMax,
      sort: validatedSort,
      direction: validatedDirection,
      page: validatedPage,
      size: validatedSize,
    });
  }, [urlQuery, selectedGenres, validatedYearMin, validatedYearMax, validatedSort, validatedDirection, validatedPage, validatedSize]);

  // 3. S1: Local input draft with pending navigation tracking
  const [inputValue, setInputValue] = useState(urlQuery);
  const lastPushedQueryRef = useRef<string | null>(null);

  // S1 Fix: Synchronize draft with URL only on external navigation or when not actively advanced
  useEffect(() => {
    if (lastPushedQueryRef.current !== null && urlQuery === lastPushedQueryRef.current) {
      // This URL update is the acknowledgment of our own push!
      // If user has already typed ahead (e.g. C while B was in-flight), DO NOT overwrite draft!
      lastPushedQueryRef.current = null;
      return;
    }
    // External navigation (back/forward button, deep link): sync draft
    setInputValue(urlQuery);
  }, [urlQuery]);

  // 4. URL Updater helper (S3: preserves yearMin/yearMax/size)
  const updateUrl = useCallback(
    (updates: {
      q?: string | null;
      genres?: string[] | null;
      yearMin?: number | null;
      yearMax?: number | null;
      sort?: string;
      direction?: string;
      page?: number;
      size?: number;
    }) => {
      const params = new URLSearchParams(searchParams.toString());

      if (updates.q !== undefined) {
        params.delete('query');
        if (updates.q && updates.q.trim()) {
          const qVal = updates.q.trim();
          params.set('q', qVal);
          lastPushedQueryRef.current = qVal;
        } else {
          params.delete('q');
          lastPushedQueryRef.current = '';
        }
      }

      if (updates.genres !== undefined) {
        params.delete('genre');
        if (updates.genres && updates.genres.length > 0) {
          params.set('genres', updates.genres.join(','));
        } else {
          params.delete('genres');
        }
      }

      if (updates.yearMin !== undefined) {
        if (typeof updates.yearMin === 'number') {
          params.set('yearMin', String(updates.yearMin));
        } else {
          params.delete('yearMin');
        }
      }

      if (updates.yearMax !== undefined) {
        if (typeof updates.yearMax === 'number') {
          params.set('yearMax', String(updates.yearMax));
        } else {
          params.delete('yearMax');
        }
      }

      if (updates.sort !== undefined) {
        params.set('sort', updates.sort);
      }

      if (updates.direction !== undefined) {
        params.set('direction', updates.direction);
      }

      if (updates.size !== undefined) {
        if (typeof updates.size === 'number' && updates.size !== 12) {
          params.set('size', String(updates.size));
        } else {
          params.delete('size');
        }
      }

      if (updates.page !== undefined) {
        if (updates.page > 0) {
          params.set('page', String(updates.page));
        } else {
          params.delete('page');
        }
      }

      const queryString = params.toString();
      const newUrl = queryString ? `${pathname}?${queryString}` : pathname;
      router.push(newUrl, { scroll: false });
    },
    [searchParams, pathname, router]
  );

  // Debounce input value changes to URL
  useEffect(() => {
    if (inputValue.trim() === urlQuery.trim()) {
      return;
    }

    const timer = setTimeout(() => {
      updateUrl({ q: inputValue.trim(), page: 0 });
    }, 350);

    return () => clearTimeout(timer);
  }, [inputValue, urlQuery, updateUrl]);

  // 5. Data Fetching States with Query Snapshot & Generation Guard
  const [dataSnapshot, setDataSnapshot] = useState<DataSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryTrigger, setRetryTrigger] = useState(0);

  const requestIdRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  // S2: Data is only considered CURRENT if snapshot key matches current params key
  const isCurrentData = dataSnapshot !== null && dataSnapshot.key === currentParamsKey;

  // Data fetching effect
  useEffect(() => {
    const currentRequestId = ++requestIdRef.current;

    // Check yearMin > yearMax invalid range
    if (
      typeof validatedYearMin === 'number' &&
      typeof validatedYearMax === 'number' &&
      validatedYearMin > validatedYearMax
    ) {
      setError(`Khoảng năm không hợp lệ: năm bắt đầu (${validatedYearMin}) không được lớn hơn năm kết thúc (${validatedYearMax})`);
      setLoading(false);
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);

    browseCatalog({
      query: urlQuery,
      genres: selectedGenres,
      animationOnly: true, // Always constrained to Animation
      yearMin: validatedYearMin,
      yearMax: validatedYearMax,
      sort: validatedSort,
      direction: validatedDirection,
      page: validatedPage,
      size: validatedSize,
      signal: controller.signal,
    })
      .then((response) => {
        if (currentRequestId === requestIdRef.current) {
          setDataSnapshot({
            key: currentParamsKey,
            query: urlQuery,
            genres: selectedGenres,
            yearMin: validatedYearMin,
            yearMax: validatedYearMax,
            sort: validatedSort,
            direction: validatedDirection,
            page: validatedPage,
            size: validatedSize,
            data: response,
          });
          setLoading(false);
        }
      })
      .catch((err: any) => {
        if (currentRequestId !== requestIdRef.current) {
          return;
        }
        if (err?.isCanceled || err?.name === 'AbortError') {
          return; // Silent caller cancellation
        }
        setError(err?.message || 'Không thể kết nối đến máy chủ danh mục phim');
        setLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [
    currentParamsKey,
    urlQuery,
    selectedGenres,
    validatedYearMin,
    validatedYearMax,
    validatedSort,
    validatedDirection,
    validatedPage,
    validatedSize,
    retryTrigger,
  ]);

  const toggleGenre = (genre: string) => {
    const newGenres = selectedGenres.includes(genre)
      ? selectedGenres.filter((g) => g !== genre)
      : [...selectedGenres, genre];
    updateUrl({ genres: newGenres, page: 0 });
  };

  const handleSortChange = (newSort: SortOption) => {
    const newDir = newSort === 'title' ? 'asc' : 'desc';
    updateUrl({ sort: newSort, direction: newDir, page: 0 });
  };

  const clearAllFilters = () => {
    lastPushedQueryRef.current = '';
    setInputValue('');
    router.push(pathname, { scroll: false });
  };

  const handlePageChange = (newPage: number) => {
    updateUrl({ page: newPage });
  };

  const activeFilterCount =
    (urlQuery ? 1 : 0) +
    selectedGenres.length +
    (validatedYearMin !== undefined ? 1 : 0) +
    (validatedYearMax !== undefined ? 1 : 0) +
    (validatedSize !== 12 ? 1 : 0);

  return (
    <main className="page-shell min-h-[75vh] py-8 sm:py-12">
      {/* Title */}
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
          Kho phim hoạt hình & tuyển chọn
        </h1>
        <p className="mt-1.5 text-sm text-zinc-400">
          Khám phá và lọc danh mục phim hoạt hình chính thức từ máy chủ Dippie Cinema.
        </p>
      </div>

      {/* Search Input Bar */}
      <div className="mt-6">
        <div className="relative flex max-w-2xl items-center rounded-md border border-surface-border bg-surface px-3.5 py-3 shadow-lg focus-within:border-brand">
          <Search className="text-zinc-400 shrink-0" size={18} />
          <input
            autoFocus
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Tìm theo tên phim hoặc từ khóa cốt truyện..."
            className="w-full bg-transparent px-3 text-sm text-white placeholder:text-zinc-500 focus:outline-none"
          />
          {inputValue && (
            <button
              onClick={() => {
                lastPushedQueryRef.current = '';
                setInputValue('');
                updateUrl({ q: '', page: 0 });
              }}
              className="rounded p-1 text-zinc-400 hover:bg-zinc-800 hover:text-white cursor-pointer"
              aria-label="Xóa từ khóa"
            >
              <X size={15} />
            </button>
          )}
        </div>
      </div>

      {/* Filter Bar */}
      <div className="mt-5 flex flex-col gap-3 rounded-lg border border-surface-border bg-surface p-4">
        {/* Genre Chips */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Lọc theo thể loại phụ hoạt hình:
            </span>
            {activeFilterCount > 0 && (
              <button
                onClick={clearAllFilters}
                className="flex items-center gap-1 text-xs text-brand hover:underline cursor-pointer"
              >
                <RotateCcw size={12} /> Đặt lại bộ lọc ({activeFilterCount})
              </button>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {DISCOVERY_GENRES.map((genre) => {
              const selected = selectedGenres.includes(genre);
              return (
                <button
                  key={genre}
                  onClick={() => toggleGenre(genre)}
                  className={`rounded-md px-3 py-1 text-xs font-medium transition-colors cursor-pointer ${
                    selected
                      ? 'bg-brand text-zinc-950 font-bold shadow-brand-sm'
                      : 'border border-surface-border bg-surface-muted text-zinc-300 hover:border-zinc-600 hover:text-white'
                  }`}
                >
                  {genre} {selected && '✓'}
                </button>
              );
            })}
          </div>
        </div>

        {/* Year & Size Active Summary (S3) */}
        {(validatedYearMin !== undefined || validatedYearMax !== undefined || validatedSize !== 12) && (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-zinc-850/60 text-xs text-zinc-300">
            <span className="text-zinc-400 flex items-center gap-1">
              <Calendar size={13} /> Bộ lọc nâng cao:
            </span>
            {validatedYearMin !== undefined && (
              <span className="rounded bg-zinc-800 px-2 py-0.5 text-[11px] text-zinc-300">
                Từ năm: {validatedYearMin}
              </span>
            )}
            {validatedYearMax !== undefined && (
              <span className="rounded bg-zinc-800 px-2 py-0.5 text-[11px] text-zinc-300">
                Đến năm: {validatedYearMax}
              </span>
            )}
            {validatedSize !== 12 && (
              <span className="rounded bg-zinc-800 px-2 py-0.5 text-[11px] text-zinc-300">
                Cỡ trang: {validatedSize}
              </span>
            )}
          </div>
        )}

        {/* Sort & Stats Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-zinc-850 text-xs text-zinc-400">
          <div className="flex items-center gap-2">
            <SlidersHorizontal size={14} />
            <span>Sắp xếp theo:</span>
            <div className="flex items-center gap-1 ml-1">
              {[
                { id: 'rating', label: 'Điểm cao nhất' },
                { id: 'year', label: 'Năm mới nhất' },
                { id: 'title', label: 'Tên (A-Z)' },
              ].map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => handleSortChange(opt.id as SortOption)}
                  className={`rounded px-2.5 py-1 transition-colors cursor-pointer ${
                    validatedSort === opt.id
                      ? 'bg-zinc-800 text-white font-bold'
                      : 'hover:text-white'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {loading && dataSnapshot && (
              <span className="flex items-center gap-1 text-[11px] text-brand animate-pulse">
                <RefreshCw size={11} className="animate-spin" /> Đang cập nhật...
              </span>
            )}
            <span>
              {loading && !isCurrentData
                ? 'Đang tải dữ liệu...'
                : isCurrentData
                ? `Tìm thấy ${dataSnapshot.data.totalElements} phim hoạt hình`
                : dataSnapshot
                ? `Kết quả trước: ${dataSnapshot.data.totalElements} phim`
                : ''}
            </span>
          </div>
        </div>
      </div>

      {/* Main Results Section */}
      <section className="mt-8">
        {/* Error State */}
        {error ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-red-500/30 bg-red-950/20 px-6 py-12 text-center">
            <div className="grid h-12 w-12 place-items-center rounded bg-red-900/40 text-red-400 mb-3">
              <AlertCircle size={22} />
            </div>
            <h3 className="text-base font-bold text-white">Không thể nạp danh mục phim</h3>
            <p className="mt-1 max-w-md text-xs sm:text-sm text-zinc-400">{error}</p>
            <div className="mt-5 flex gap-3">
              <button
                onClick={() => setRetryTrigger((c) => c + 1)}
                className="btn-primary flex items-center gap-1.5 text-xs"
              >
                <RefreshCw size={12} /> Thử kết nối lại
              </button>
              <button onClick={clearAllFilters} className="btn-secondary text-xs">
                Xóa bộ lọc
              </button>
            </div>
          </div>
        ) : loading && !isCurrentData ? (
          /* S2: Loading Skeleton State while new query is in-flight */
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5 xl:grid-cols-6">
            {Array.from({ length: validatedSize }).map((_, i) => (
              <div
                key={i}
                className="overflow-hidden rounded-lg border border-surface-border bg-surface animate-pulse"
              >
                <div className="aspect-[2/3] w-full bg-surface-elevated" />
                <div className="p-3 space-y-2">
                  <div className="h-4 w-3/4 rounded bg-zinc-800" />
                  <div className="h-3 w-1/2 rounded bg-zinc-800" />
                </div>
              </div>
            ))}
          </div>
        ) : isCurrentData && dataSnapshot.data.items.length === 0 ? (
          /* S2: Empty State only when current query response has completed with 0 items */
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-surface-border bg-surface px-6 py-16 text-center">
            <div className="grid h-12 w-12 place-items-center rounded bg-surface-muted text-zinc-400 mb-3">
              <Search size={20} />
            </div>
            <h3 className="text-base font-bold text-white">Không tìm thấy bộ phim hoạt hình nào</h3>
            <p className="mt-1 max-w-md text-xs sm:text-sm text-zinc-400">
              {dataSnapshot.query
                ? `Không có phim hoạt hình nào khớp với từ khóa "${dataSnapshot.query}".`
                : 'Không có phim nào thỏa mãn các bộ lọc thể loại đang chọn.'}
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <button onClick={openChat} className="btn-primary text-xs">
                Hỏi CineBot gợi ý ngay
              </button>
              <button onClick={clearAllFilters} className="btn-secondary text-xs">
                Xem toàn bộ kho hoạt hình
              </button>
            </div>
          </div>
        ) : isCurrentData && dataSnapshot.data.items.length > 0 ? (
          /* Results Grid & Pagination */
          <>
            <div
              className={`grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5 xl:grid-cols-6 transition-opacity duration-200 ${
                loading ? 'opacity-60 pointer-events-none' : ''
              }`}
            >
              {dataSnapshot.data.items.map((movie) => (
                <MovieCard key={movie.id} movie={movie} fluid />
              ))}
            </div>

            {/* Pagination Controls */}
            {dataSnapshot.data.totalPages > 1 && (
              <nav
                aria-label="Phân trang danh mục phim"
                className="mt-8 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-surface-border bg-surface px-4 py-3 text-xs text-zinc-400"
              >
                <span>
                  Trang <strong className="text-white">{dataSnapshot.data.page + 1}</strong> / {dataSnapshot.data.totalPages} (Tổng cộng {dataSnapshot.data.totalElements} phim)
                </span>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handlePageChange(dataSnapshot.data.page - 1)}
                    disabled={!dataSnapshot.data.hasPrevious || loading}
                    className="flex items-center gap-1 rounded border border-surface-border bg-surface-muted px-3 py-1.5 font-medium text-zinc-300 hover:border-zinc-600 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
                  >
                    <ChevronLeft size={14} /> Trang trước
                  </button>

                  <button
                    onClick={() => handlePageChange(dataSnapshot.data.page + 1)}
                    disabled={!dataSnapshot.data.hasNext || loading}
                    className="flex items-center gap-1 rounded border border-surface-border bg-surface-muted px-3 py-1.5 font-medium text-zinc-300 hover:border-zinc-600 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
                  >
                    Trang sau <ChevronRight size={14} />
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
