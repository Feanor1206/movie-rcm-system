'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { RefreshCw, AlertCircle, Film } from 'lucide-react';
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

        browseCatalog({
          animationOnly: true,
          genres: fetchedMovie.genres && fetchedMovie.genres.length > 0 ? fetchedMovie.genres.slice(0, 2) : ['Animation'],
          size: 6,
          signal: controller.signal,
        })
          .then((res) => {
            if (isCurrent) setSimilarMovies(res.items.filter((m) => m.id !== fetchedMovie.id).slice(0, 5));
          })
          .catch(() => {});
      })
      .catch((err: any) => {
        if (!isCurrent || err?.isCanceled || err?.name === 'AbortError') return;
        setError(err?.message || 'Không thể kết nối đến máy chủ');
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
          <div className="min-h-[420px] bg-surface animate-pulse" />
        </main>
      ) : notFoundState || error ? (
        <main className="min-h-[70vh] flex items-center justify-center bg-background px-4 py-16 text-center">
          <div className="max-w-md space-y-4 rounded-xl border border-surface-border bg-surface p-8">
            <div className="grid h-12 w-12 place-items-center rounded-full mx-auto bg-zinc-800 text-zinc-300">
              {notFoundState ? <Film size={24} /> : <AlertCircle size={24} />}
            </div>
            <h1 className="text-xl font-bold text-white">
              {notFoundState ? 'Không tìm thấy phim hoạt hình' : 'Không thể kết nối đến máy chủ'}
            </h1>
            <p className="text-xs text-zinc-400">
              {notFoundState ? `Mã phim "${canonicalId}" không tồn tại.` : error}
            </p>
            <div className="pt-2 flex flex-wrap justify-center gap-3">
              {notFoundState ? (
                <Link href="/search?genre=Animation" className="btn-primary text-xs flex items-center gap-1.5">
                  <Film size={14} /> Khám phá kho hoạt hình
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
