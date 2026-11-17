import { Link } from 'react-router';
import { movieSynopsis } from '@/lib/labels';
import { buildMediaItemHref } from '@/lib/services/mediaRouting';
import type { Movie } from '@/types/movie';

function filmLabel(movie: Movie, type: string) {
  if (type === 'episode') {
    const number = movie.episode_number || movie.episodeNumber;
    return number ? `Tập ${number}` : 'Tập phim';
  }
  if (type === 'series') return 'Bộ phim';
  if (type === 'segment' || type === 'scene') return 'Đoạn phim';
  return movie.year || '';
}

export function FilmGrid({ movies, search = false, loading = false }: {
  movies: Movie[];
  search?: boolean;
  loading?: boolean;
}) {
  const Title = search ? 'h2' : 'h3';
  return (
    <div data-testid={search ? 'catalog-results' : undefined} className="film-grid" aria-busy={loading}>
      {movies.map((movie) => {
        const type = movie.item_type || 'movie';
        const label = filmLabel(movie, type);
        const title = movie.title.charAt(0).toLocaleUpperCase('vi') + movie.title.slice(1);
        return (
          <Link
            key={movie.id}
            to={buildMediaItemHref(movie)}
            data-testid={search ? 'search-result-card' : 'film-card'}
            data-movie-id={movie.id}
            data-result-id={search ? movie.id : undefined}
            data-result-type={search ? type : undefined}
            className="film-tile"
          >
            {label && <span className="film-label">{label}</span>}
            <Title>{title}</Title>
            {movie.description && <p className="film-summary">{movieSynopsis(movie.description)}</p>}
            <span className="film-action">{type === 'series' ? 'Chọn tập' : 'Xem phim'}</span>
          </Link>
        );
      })}
    </div>
  );
}

export function FilmShelf({ movies, subtitle, loading, onRetry }: {
  movies: Movie[];
  subtitle?: string;
  loading?: boolean;
  onRetry?: () => void;
}) {
  return (
    <section id="goi-y" data-testid="film-shelf" className="shelf-section" aria-labelledby="recommend-title">
      <div className="shelf-heading">
        <div>
          <h2 id="recommend-title" className="section-title">Gợi ý cho bạn</h2>
          {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
        </div>
        <Link to="/search" className="shelf-link">Mở kho phim</Link>
      </div>
      {loading ? (
        <div className="shelf-message" role="status">Đang tải gợi ý…</div>
      ) : onRetry ? (
        <div className="shelf-message" role="alert">
          Không thể tải gợi ý.
          <button type="button" className="btn-secondary" onClick={onRetry}>Thử lại</button>
        </div>
      ) : movies.length ? (
        <FilmGrid movies={movies} />
      ) : (
        <div className="shelf-message">Chưa có phim phù hợp.</div>
      )}
    </section>
  );
}
