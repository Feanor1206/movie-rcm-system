import React, { useState, useEffect } from 'react';

import { Link, useParams } from 'react-router';
import { MovieDetail } from '@/features/movies/components/MovieDetail';
import { getCatalogMovieById, browseCatalog } from '@/lib/services/catalogService';
import type { Movie } from '@/types/movie';

export default function MovieDetailPage() {
  const canonicalId = useParams<'id'>().id?.trim() || '';

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
          setNotFoundState(true);
          setMovie(null);
          setLoading(false);
          return;
        }

        setMovie(fetchedMovie);
        setLoading(false);

        browseCatalog({
          animationOnly: true,
          genres: fetchedMovie.genres?.length ? fetchedMovie.genres.slice(0, 2) : ['Animation'],
          size: 6,
          signal: controller.signal,
        })
          .then((res) => isCurrent && setSimilarMovies(res.items.filter((m) => m.id !== fetchedMovie.id).slice(0, 5)))
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

      {loading ? (
        <main className="min-h-screen bg-background">
          <div className="min-h-[420px] bg-surface animate-pulse" />
        </main>
      ) : notFoundState || error ? (
        <main className="min-h-[70vh] flex items-center justify-center bg-background px-4 py-16 text-center">
          <div className="max-w-md space-y-4 rounded-xl border border-surface-border bg-surface p-8">
            <div className="grid h-12 w-12 place-items-center rounded-full mx-auto bg-zinc-800 text-zinc-300 font-bold">
              {notFoundState ? '404' : '!'}
            </div>
            <h1 className="text-xl font-bold text-ink">
              {notFoundState ? 'Không tìm thấy phim hoạt hình' : 'Không thể kết nối đến máy chủ'}
            </h1>
            <p className="text-sm text-muted">
              {notFoundState ? `Mã phim "${canonicalId}" không tồn tại.` : error}
            </p>
            <div className="pt-2 flex flex-wrap justify-center gap-3">
              {notFoundState ? (
                <Link to="/search?genre=Animation" className="btn-primary text-xs">
                  Khám phá kho hoạt hình
                </Link>
              ) : (
                <button
                  onClick={() => setRetryTrigger((c) => c + 1)}
                  className="btn-primary text-xs cursor-pointer"
                >
                  Thử kết nối lại
                </button>
              )}
              <Link to="/" className="btn-secondary text-xs">
                Về trang chủ
              </Link>
            </div>
          </div>
        </main>
      ) : movie ? (
        <MovieDetail movie={movie} similarMovies={similarMovies} />
      ) : null}

    </>
  );
}
