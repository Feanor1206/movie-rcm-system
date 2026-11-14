export const MOVIE_PROGRESS_KEY = 'dippie_movie_progress_v1';
export const MOVIE_PROGRESS_LIMIT = 30;

export type MovieProgressRecord = {
  movieId: string;
  title: string;
  positionMs: number;
  durationMs: number | null;
  completed: boolean;
  updatedAt: string;
};

export type MovieProgressDraft = {
  movieId: string;
  title: string;
  positionMs: number;
  durationMs?: number | null;
  completed?: boolean;
};

function nonEmpty(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function storage(): Storage | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function normalizeMovieProgress(raw: unknown): MovieProgressRecord | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const record = raw as Partial<MovieProgressRecord>;
  if (!nonEmpty(record.movieId) || !nonEmpty(record.title)) return null;
  if (typeof record.positionMs !== 'number' || !Number.isSafeInteger(record.positionMs) || record.positionMs < 0) return null;
  if (typeof record.completed !== 'boolean') return null;
  if (!nonEmpty(record.updatedAt) || !Number.isFinite(Date.parse(record.updatedAt))) return null;
  const durationMs = typeof record.durationMs === 'number' && Number.isSafeInteger(record.durationMs) && record.durationMs > 0
    ? record.durationMs
    : null;
  return {
    movieId: record.movieId.trim(),
    title: record.title.trim(),
    positionMs: durationMs === null ? record.positionMs : Math.min(record.positionMs, durationMs),
    durationMs,
    completed: record.completed,
    updatedAt: new Date(Date.parse(record.updatedAt)).toISOString(),
  };
}

export function listMovieProgress(): MovieProgressRecord[] {
  const store = storage();
  if (!store) return [];
  try {
    const parsed = JSON.parse(store.getItem(MOVIE_PROGRESS_KEY) || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map(normalizeMovieProgress)
      .filter((item): item is MovieProgressRecord => item !== null)
      .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
      .slice(0, MOVIE_PROGRESS_LIMIT);
  } catch {
    return [];
  }
}

export function getMovieProgress(movieId: string): MovieProgressRecord | null {
  if (!nonEmpty(movieId)) return null;
  return listMovieProgress().find((item) => item.movieId === movieId.trim()) || null;
}

export function saveMovieProgress(draft: MovieProgressDraft, now = Date.now()): MovieProgressRecord | null {
  const store = storage();
  if (!store || !draft || !nonEmpty(draft.movieId) || !nonEmpty(draft.title)) return null;
  if (!Number.isSafeInteger(draft.positionMs) || draft.positionMs < 0) return null;
  const durationMs = typeof draft.durationMs === 'number' && Number.isSafeInteger(draft.durationMs) && draft.durationMs > 0
    ? draft.durationMs
    : null;
  const record: MovieProgressRecord = {
    movieId: draft.movieId.trim(),
    title: draft.title.trim(),
    positionMs: durationMs === null ? draft.positionMs : Math.min(draft.positionMs, durationMs),
    durationMs,
    completed: Boolean(draft.completed),
    updatedAt: new Date(now).toISOString(),
  };
  const next = [record, ...listMovieProgress().filter((item) => item.movieId !== record.movieId)]
    .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
    .slice(0, MOVIE_PROGRESS_LIMIT);
  try {
    store.setItem(MOVIE_PROGRESS_KEY, JSON.stringify(next));
  } catch {
    return null;
  }
  return record;
}

export function isUsableMovieProgress(record: MovieProgressRecord | null | undefined): record is MovieProgressRecord {
  return Boolean(
    record && !record.completed && nonEmpty(record.movieId) && nonEmpty(record.title) &&
    record.positionMs > 0 && (record.durationMs === null || record.positionMs < record.durationMs)
  );
}

export function buildMovieProgressHref(record: MovieProgressRecord): string {
  const params = new URLSearchParams();
  params.set('t', String(record.positionMs));
  return `/movies/${encodeURIComponent(record.movieId)}?${params.toString()}`;
}

export function readFilmResumeSeconds(movieId: string): number {
  try {
    if (typeof window !== 'undefined' && window.location?.search) {
      const raw = new URLSearchParams(window.location.search).get('t');
      const positionMs = raw === null ? NaN : Number(raw);
      if (Number.isSafeInteger(positionMs) && positionMs > 0) return positionMs / 1000;
    }
  } catch {
  }
  const saved = getMovieProgress(movieId);
  if (saved && !saved.completed && saved.positionMs > 0) return saved.positionMs / 1000;
  return 0;
}
