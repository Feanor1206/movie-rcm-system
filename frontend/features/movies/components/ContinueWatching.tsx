import { Link } from 'react-router';
import { useWatchProgress } from '@/lib/hooks/useWatchProgress';
import { buildWatchProgressHref, isUsableResumeProgress } from '@/lib/services/watchProgressService';
import {
  buildMovieProgressHref,
  isUsableMovieProgress,
  type MovieProgressRecord,
} from '@/lib/services/movieProgress';

function formatMark(positionMs: number): string {
  const totalSeconds = Math.floor(positionMs / 1000);
  return `${Math.floor(totalSeconds / 60)}:${String(totalSeconds % 60).padStart(2, '0')}`;
}

export function ContinueWatching({ films }: { films: MovieProgressRecord[] }) {
  const { records } = useWatchProgress();
  const entries = [
    ...records.filter(isUsableResumeProgress).map((episode) => ({
      id: episode.episodeId, title: episode.episodeTitle || episode.seriesTitle,
      href: buildWatchProgressHref(episode), position: episode.positionMs, updatedAt: episode.updatedAt,
    })),
    ...films.filter(isUsableMovieProgress).map((film) => ({
      id: film.movieId, title: film.title, href: buildMovieProgressHref(film),
      position: film.positionMs, updatedAt: film.updatedAt,
    })),
  ];
  const unique = [...new Map(entries.reverse().map((entry) => [entry.id, entry])).values()]
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).slice(0, 3);
  if (!unique.length) return null;

  return (
    <section className="shelf-section" aria-labelledby="continue-title" data-testid="continue-watching">
      <h2 id="continue-title" className="section-title mb-4">Xem tiếp</h2>
      <div className="film-grid">
        {unique.map((entry) => (
          <Link
            key={entry.id}
            to={entry.href}
            data-testid="continue-card"
            className="continue-card"
          >
            <h3 className="line-clamp-2 font-semibold text-ink">{entry.title}</h3>
            <span className="resume-mark">{formatMark(entry.position)}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
