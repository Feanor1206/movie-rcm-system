import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import { FilmShelf } from '@/features/movies/components/FilmShelf';
import { ContinueWatching } from '@/features/movies/components/ContinueWatching';
import { useAuth } from '@/lib/context/AuthContext';
import { listMovieProgress } from '@/lib/services/movieProgress';
import { getGuestWatchProgress } from '@/lib/services/watchProgressService';
import { getRecommendations } from '@/lib/services/recommendationService';
import coverArt from '@/assets/dippie-cover.svg';

const quickTopics = [
  { label: 'Gia đình', href: '/search?genre=Family' },
  { label: 'Phiêu lưu', href: '/search?genre=Adventure' },
  { label: 'Hài', href: '/search?genre=Comedy' },
  { label: 'Giả tưởng', href: '/search?genre=Fantasy' },
];

export default function HomePage() {
  const { status, token } = useAuth();
  const [films] = useState(listMovieProgress);
  const watched = useMemo(() => [
    ...films.filter((film) => film.positionMs > 0).map((film) => film.movieId),
    ...getGuestWatchProgress().filter((episode) => episode.positionMs > 0).map((episode) => episode.episodeId),
  ].filter((id) => id.length <= 100), [films, status]);
  const [state, setState] = useState<{
    scope: string;
    result: Awaited<ReturnType<typeof getRecommendations>> | null;
  } | null>(null);
  const [retry, setRetry] = useState(0);
  const accountToken = status === 'authenticated' ? token : null;
  const scope = accountToken || status;
  const result = state?.scope === scope ? state.result : undefined;

  useEffect(() => {
    if (status === 'checking') return;
    const controller = new AbortController();
    getRecommendations(accountToken, controller.signal, status === 'guest' ? watched : [])
      .then((value) => {
        if (!controller.signal.aborted) setState({ scope, result: value });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ scope, result: null });
      });
    return () => controller.abort();
  }, [accountToken, scope, retry, status, watched]);

  return (
    <main className="page-shell home-page">
      <section className="cover-grid" aria-labelledby="cover-title">
        <div className="cover-copy">
          <h1 id="cover-title">Kho phim hoạt hình</h1>
          <p className="cover-intro">Tìm theo tên tập hoặc nội dung.</p>
          <Link to="/search" className="cover-cta">Tìm phim</Link>

          <nav className="topics-list" aria-label="Gợi ý tìm phim">
            {quickTopics.map((topic) => (
              <Link key={topic.label} to={topic.href} className="topic-chip">
                {topic.label}
              </Link>
            ))}
          </nav>
        </div>

        <div className="cover-art-panel">
          <img
            src={coverArt}
            alt="Bạn nhỏ và thỏ đi đến rạp chiếu phim trong rừng"
            width="760"
            height="580"
          />
        </div>
      </section>

      <ContinueWatching films={films} />
      <FilmShelf
        movies={result?.movies || []}
        subtitle={result?.reasoning === 'Gợi ý từ kho phim.' ? '' : result?.reasoning}
        loading={result === undefined}
        onRetry={result === null ? () => {
          setState(null);
          setRetry((n) => n + 1);
        } : undefined}
      />
    </main>
  );
}
