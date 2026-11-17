'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/context/AuthContext';
import { getRecommendations } from '@/lib/services/recommendationService';
import { FilmShelf } from '@/features/movies/components/FilmShelf';
import type { Movie } from '@/types/movie';

function Shelf({ token }: { token: string | null }) {
  const [result, setResult] = useState<{ movies: Movie[]; reasoning: string } | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(false);
    getRecommendations(token, controller.signal).then((value) => {
      if (!controller.signal.aborted) setResult(value);
    }).catch(() => {
      if (!controller.signal.aborted) setError(true);
    });
    return () => controller.abort();
  }, [token, retry]);

  if (error) return <section className="comic-loading" role="alert"><p>Không thể tải gợi ý.</p><button className="btn-secondary" onClick={() => setRetry((n) => n + 1)}>Thử lại</button></section>;
  if (!result) return <div className="comic-loading" role="status">Đang tải gợi ý…</div>;
  return <FilmShelf movies={result.movies} title="Gợi ý cho bạn" subtitle={result.reasoning} />;
}

export function RecommendationShelf() {
  const { token, status } = useAuth();
  if (status === 'checking') return null;
  return <Shelf key={token || 'guest'} token={status === 'authenticated' ? token : null} />;
}
