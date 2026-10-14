'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { RefreshCw, AlertCircle, Film, Compass } from 'lucide-react';
import { Footer } from '@/components/layout/Footer';
import { Navbar } from '@/components/layout/Navbar';
import { MovieDetail } from '@/features/movies/components/MovieDetail';
import { getCatalogMovieById, browseCatalog } from '@/lib/services/catalogService';
import type { Movie } from '@/types/movie';

export default function MovieDetailPage() {
  const params = useParams();
  const rawId = params?.id;
  const canonicalId = typeof rawId === 'string' ? rawId.trim() : Array.isArray(rawId) ? rawId[0] : '';

  const [loading, setLoading] = useState(true);
  const [movie, setMovie] = useState<Movie | null>(null);
  const [notFoundState, setNotFoundState] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [similarMovies, setSimilarMovies] = useState<Movie[]>([]);
  const [retryTrigger, setRetryTrigger] = useState(0);

  useEffect(() => {
    if (!canonicalId) {
      setNotFoundState(true);
      setLoading(false);
      return;
    }

    let isCurrent = true;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setNotFoundState(false);
    setMovie(null);
    setSimilarMovies([]);

    getCatalogMovieById(canonicalId, { signal: controller.signal })
      .then((fetchedMovie) => {
        if (!isCurrent) return;
        if (!fetchedMovie) {
          // Real 404 from backend catalog
          setNotFoundState(true);
          setMovie(null);
          setLoading(false);
          return;
        }

        // D1: Render main detail immediately as soon as main lookup succeeds
        setMovie(fetchedMovie);
        setLoading(false);

        // Fetch candidate similar animations in background, decoupled from main loading
        const candidateGenres = fetchedMovie.genres && fetchedMovie.genres.length > 0
          ? fetchedMovie.genres.slice(0, 2)
          : ['Animation'];

        browseCatalog({
          animationOnly: true,
          genres: candidateGenres,
          size: 6,
          signal: controller.signal,
        })
          .then((similarRes) => {
            if (!isCurrent) return;
            const filtered = similarRes.items.filter((m) => m.id !== fetchedMovie.id).slice(0, 5);
            setSimilarMovies(filtered);
          })
          .catch((similarErr: any) => {
            if (!isCurrent || similarErr?.isCanceled || similarErr?.name === 'AbortError') return;
            // Failure to fetch similar rail does not break or alter movie detail view
            setSimilarMovies([]);
          });
      })
      .catch((err: any) => {
        if (!isCurrent || err?.isCanceled || err?.name === 'AbortError') {
          return; // Caller unmounted / changed page
        }
        setError(err?.message || 'Không thể kết nối đến máy chủ danh mục phim');
        setLoading(false);
      });

    return () => {
      isCurrent = false;
      controller.abort();
    };
  }, [canonicalId, retryTrigger]);

  return (
    <>
      <Navbar />
      {loading ? (
        <main className="min-h-screen bg-background">
          {/* Skeleton Hero Backdrop */}
          <div className="relative min-h-[420px] sm:min-h-[480px] bg-surface animate-pulse border-b border-surface-border">
            <div className="page-shell pt-10 pb-12 flex flex-col md:flex-row gap-6 md:items-end">
              <div className="aspect-[2/3] w-44 sm:w-56 rounded-lg bg-surface-elevated shrink-0" />
              <div className="space-y-3 flex-1">
                {['h-4 w-28', 'h-10 w-3/4', 'h-4 w-1/2', 'h-16 max-w-2xl'].map((c) => (
                  <div key={c} className={`${c} rounded bg-zinc-800`} />
                ))}
                <div className="flex gap-3 pt-3">
                  <div className="h-10 w-36 rounded bg-zinc-800" />
                  <div className="h-10 w-36 rounded bg-zinc-800" />
                </div>
              </div>
            </div>
          </div>
        </main>
      ) : notFoundState || error ? (
        <main className="min-h-[70vh] flex items-center justify-center bg-background px-4 py-16 text-center">
          <div className={`max-w-md space-y-4 rounded-xl border p-8 shadow-xl ${
            notFoundState ? 'border-surface-border bg-surface' : 'border-red-500/30 bg-red-950/20'
          }`}>
            <div className={`grid h-14 w-14 place-items-center rounded-full mx-auto ${
              notFoundState ? 'bg-zinc-850 text-zinc-400' : 'bg-red-900/40 text-red-400'
            }`}>
              {notFoundState ? <Film size={26} /> : <AlertCircle size={26} />}
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-white">
              {notFoundState ? 'Không tìm thấy phim hoạt hình' : 'Không thể kết nối đến máy chủ'}
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400">
              {notFoundState
                ? `Tác phẩm có mã định danh "${canonicalId}" không tồn tại trên hệ thống hoặc đã được cập nhật.`
                : error}
            </p>
            <div className="pt-2 flex flex-wrap justify-center gap-3">
              {notFoundState ? (
                <Link href="/search?genre=Animation" className="btn-primary text-xs flex items-center gap-1.5">
                  <Compass size={14} /> Khám phá kho hoạt hình
                </Link>
              ) : (
                <button
                  onClick={() => setRetryTrigger((c) => c + 1)}
                  className="btn-primary text-xs flex items-center gap-1.5 cursor-pointer"
                >
                  <RefreshCw size={13} /> Thử kết nối lại
                </button>
              )}
              <Link href="/" className="btn-secondary text-xs">
                Về trang chủ
              </Link>
            </div>
          </div>
        </main>
      ) : movie ? (
        /* Valid 200 Movie Detail Presentation */
        <MovieDetail movie={movie} similarMovies={similarMovies} />
      ) : null}
      <Footer />
    </>
  );
}
