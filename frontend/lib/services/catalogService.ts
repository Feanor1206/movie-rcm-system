import type { Movie } from '@/types/movie';

export type PageResponse<T> = {
  items: T[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
  hasNext: boolean;
  hasPrevious: boolean;
};

export type CatalogBrowseOptions = {
  query?: string;
  search?: string;
  genre?: string;
  genres?: string | string[];
  animationOnly?: boolean;
  yearMin?: number;
  yearMax?: number;
  sort?: 'rating' | 'year' | 'title';
  direction?: 'asc' | 'desc';
  page?: number;
  size?: number;
  timeoutMs?: number;
  signal?: AbortSignal;
};

export class CatalogApiError extends Error {
  status: number;
  data?: unknown;
  isCanceled?: boolean;
  isTimeout?: boolean;

  constructor(
    message: string,
    status: number,
    data?: unknown,
    options?: { isCanceled?: boolean; isTimeout?: boolean }
  ) {
    super(message);
    this.name = options?.isCanceled ? 'AbortError' : 'CatalogApiError';
    this.status = status;
    this.data = data;
    this.isCanceled = Boolean(options?.isCanceled);
    this.isTimeout = Boolean(options?.isTimeout);
  }
}

const DEFAULT_TIMEOUT_MS = 7000;
const SPRINGBOOT_API = process.env.NEXT_PUBLIC_SPRINGBOOT_API_URL || 'http://localhost:8080/api';

/**
 * Normalizes a raw backend movie response into the frontend Movie type.
 * Validates required contract fields (id, title, year, rating) and throws 502 for malformed payloads.
 * Safe fallback for optional/nullable media fields (poster, backdrop, videoUrl).
 */
export function normalizeCatalogMovie(raw: any): Movie {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new CatalogApiError('Dữ liệu phim từ máy chủ không hợp lệ (không phải object)', 502);
  }

  // 1. Required ID: non-empty string
  if (typeof raw.id !== 'string' || !raw.id.trim()) {
    throw new CatalogApiError('Dữ liệu phim thiếu hoặc sai định dạng ID bắt buộc', 502);
  }
  const id = raw.id.trim();

  // 2. Required Title: non-empty string
  if (typeof raw.title !== 'string' || !raw.title.trim()) {
    throw new CatalogApiError(`Phim [${id}] thiếu hoặc sai tiêu đề bắt buộc`, 502);
  }
  const title = raw.title.trim();

  // 3. Required Year: finite number > 1800 (reject missing/0/negative)
  if (typeof raw.year !== 'number' || !Number.isFinite(raw.year) || raw.year <= 1800) {
    throw new CatalogApiError(`Phim [${id}] thiếu hoặc sai định dạng năm phát hành (year)`, 502);
  }
  const year = Math.round(raw.year);

  // 4. Required Rating: finite number between 0 and 10
  if (typeof raw.rating !== 'number' || !Number.isFinite(raw.rating) || raw.rating < 0 || raw.rating > 10) {
    throw new CatalogApiError(`Phim [${id}] thiếu hoặc sai định dạng điểm đánh giá (rating: 0..10)`, 502);
  }
  const rating = Number(raw.rating.toFixed(1));

  // 5. Genres: list of trimmed non-empty strings
  let genres: string[] = [];
  if (Array.isArray(raw.genres)) {
    genres = raw.genres
      .map((g: unknown) => (typeof g === 'string' ? g.trim() : ''))
      .filter((g: string) => g.length > 0);
  } else if (typeof raw.genres === 'string' && raw.genres.trim()) {
    genres = raw.genres
      .split(',')
      .map((g: string) => g.trim())
      .filter((g: string) => g.length > 0);
  }

  // 6. Optional & Nullable media/metadata fields
  const runtime = (typeof raw.runtime === 'string' || typeof raw.runtime === 'number')
    ? String(raw.runtime).trim()
    : '';
  const description = typeof raw.description === 'string' ? raw.description.trim() : '';
  const poster = typeof raw.poster === 'string' && raw.poster.trim() ? raw.poster.trim() : '';
  const backdrop = typeof raw.backdrop === 'string' && raw.backdrop.trim() ? raw.backdrop.trim() : '';
  const videoUrl = typeof raw.videoUrl === 'string' && raw.videoUrl.trim() ? raw.videoUrl.trim() : undefined;

  return {
    id,
    title,
    year,
    rating,
    runtime,
    genres,
    description,
    poster,
    backdrop,
    videoUrl,
  };
}

/**
 * C1 Helper: Executes a network request and response body parsing under a single unified lifecycle.
 * - Timer and caller abort listener cover BOTH fetch() and res.json() (streaming body).
 * - Distinguishes intentional caller cancellation (499, isCanceled: true) from timeout (408, isTimeout: true) and network errors (0).
 * - Guaranteed cleanup in finally after all promises resolve or reject.
 */
async function executeWithLifecycle<T>(
  action: (signal: AbortSignal) => Promise<T>,
  options: {
    timeoutMs?: number;
    signal?: AbortSignal;
  } = {}
): Promise<T> {
  const timeoutMs = typeof options.timeoutMs === 'number' && options.timeoutMs > 0
    ? options.timeoutMs
    : DEFAULT_TIMEOUT_MS;

  // Immediate rejection for pre-aborted signal
  if (options.signal?.aborted) {
    throw new CatalogApiError('Yêu cầu đã bị hủy bởi người dùng', 499, undefined, { isCanceled: true });
  }

  const controller = new AbortController();
  let timedOut = false;
  let callerCanceled = false;

  const abortListener = () => {
    callerCanceled = true;
    controller.abort(options.signal?.reason || new Error('Request aborted by caller'));
  };

  if (options.signal) {
    options.signal.addEventListener('abort', abortListener);
  }

  let timer: any = null;
  timer = setTimeout(() => {
    timedOut = true;
    controller.abort(new Error(`Catalog request timed out after ${timeoutMs}ms`));
  }, timeoutMs);

  try {
    return await action(controller.signal);
  } catch (err: any) {
    if (callerCanceled || options.signal?.aborted) {
      throw new CatalogApiError('Yêu cầu đã bị hủy bởi người dùng', 499, undefined, { isCanceled: true });
    }
    if (timedOut || (err?.name === 'AbortError' && !callerCanceled)) {
      throw new CatalogApiError('Yêu cầu danh mục quá thời gian phản hồi (timeout)', 408, undefined, { isTimeout: true });
    }
    if (err instanceof CatalogApiError) {
      throw err;
    }
    throw new CatalogApiError(
      err?.message ? `Không thể kết nối đến máy chủ danh mục phim: ${err.message}` : 'Không thể kết nối đến máy chủ danh mục phim',
      0,
      err
    );
  } finally {
    if (timer !== null) {
      clearTimeout(timer);
    }
    if (options.signal) {
      options.signal.removeEventListener('abort', abortListener);
    }
  }
}

/**
 * Browse catalog movies with pagination, filtering, and sorting.
 * C2: Validates success=true, page numbers, sizes, and item payloads.
 * C2: Preserves search/query precedence (query takes precedence unless empty, falling back to search).
 */
export async function browseCatalog(
  options: CatalogBrowseOptions = {},
  baseUrl = SPRINGBOOT_API
): Promise<PageResponse<Movie>> {
  const params = new URLSearchParams();

  // Precedence: non-empty query takes precedence, otherwise fallback to non-empty search
  const qTrim = typeof options.query === 'string' ? options.query.trim() : '';
  const sTrim = typeof options.search === 'string' ? options.search.trim() : '';
  const effectiveQuery = qTrim || sTrim;
  if (effectiveQuery) {
    params.set('query', effectiveQuery);
  }

  if (typeof options.genre === 'string' && options.genre.trim()) {
    params.set('genre', options.genre.trim());
  }

  if (options.genres) {
    const genresStr = Array.isArray(options.genres)
      ? options.genres.map((g) => (typeof g === 'string' ? g.trim() : '')).filter(Boolean).join(',')
      : typeof options.genres === 'string' ? options.genres.trim() : '';
    if (genresStr) {
      params.set('genres', genresStr);
    }
  }

  if (options.animationOnly) {
    params.set('animationOnly', 'true');
  }

  if (typeof options.yearMin === 'number' && Number.isFinite(options.yearMin)) {
    params.set('yearMin', String(options.yearMin));
  }

  if (typeof options.yearMax === 'number' && Number.isFinite(options.yearMax)) {
    params.set('yearMax', String(options.yearMax));
  }

  if (options.sort) {
    params.set('sort', options.sort);
  }

  if (options.direction) {
    params.set('direction', options.direction);
  }

  if (typeof options.page === 'number' && Number.isFinite(options.page)) {
    params.set('page', String(options.page));
  }

  if (typeof options.size === 'number' && Number.isFinite(options.size)) {
    params.set('size', String(options.size));
  }

  const queryString = params.toString();
  const url = `${baseUrl}/movies/browse${queryString ? `?${queryString}` : ''}`;

  return executeWithLifecycle(
    async (signal) => {
      const res = await fetch(url, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        signal,
      });

      if (!res.ok) {
        let errorMsg = `Lỗi danh mục phim (${res.status})`;
        try {
          const errBody = await res.json();
          if (errBody?.message) errorMsg = errBody.message;
        } catch {
          // ignore JSON parse error on HTTP error response
        }
        throw new CatalogApiError(errorMsg, res.status);
      }

      let body: any;
      try {
        body = await res.json();
      } catch {
        throw new CatalogApiError('Máy chủ phản hồi định dạng dữ liệu không hợp lệ (không phải JSON)', res.status);
      }

      if (!body || typeof body !== 'object' || body.success !== true) {
        throw new CatalogApiError(body?.message || 'Phản hồi danh mục phim không thành công (success != true)', res.status, body);
      }

      const data = body.data;
      if (!data || typeof data !== 'object' || Array.isArray(data)) {
        throw new CatalogApiError('Dữ liệu phân trang không hợp lệ (data không phải object)', 502);
      }

      if (!Array.isArray(data.items)) {
        throw new CatalogApiError('Dữ liệu phân trang thiếu mảng items bắt buộc', 502);
      }

      if (
        typeof data.page !== 'number' || !Number.isFinite(data.page) || data.page < 0 ||
        typeof data.size !== 'number' || !Number.isFinite(data.size) || data.size < 1 ||
        typeof data.totalElements !== 'number' || !Number.isFinite(data.totalElements) || data.totalElements < 0 ||
        typeof data.totalPages !== 'number' || !Number.isFinite(data.totalPages) || data.totalPages < 0 ||
        typeof data.hasNext !== 'boolean' || typeof data.hasPrevious !== 'boolean'
      ) {
        throw new CatalogApiError('Dữ liệu phân trang không hợp lệ', 502);
      }

      const items = data.items.map(normalizeCatalogMovie);

      return {
        items,
        page: data.page,
        size: data.size,
        totalElements: data.totalElements,
        totalPages: data.totalPages,
        hasNext: data.hasNext,
        hasPrevious: data.hasPrevious,
      };
    },
    options
  );
}

/**
 * Fetch a single catalog movie by canonical ID.
 * C2: Returns null if HTTP 404 (safely distinguishes 404 HTML/empty bodies from server errors).
 * C2: Validates returned movie ID strictly equals requested canonical ID.
 */
export async function getCatalogMovieById(
  id: string,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
  baseUrl = SPRINGBOOT_API
): Promise<Movie | null> {
  const cleanId = typeof id === 'string' ? id.trim() : '';
  if (!cleanId) {
    throw new CatalogApiError('ID phim không hợp lệ', 400);
  }

  const url = `${baseUrl}/movies/${encodeURIComponent(cleanId)}`;

  return executeWithLifecycle(
    async (signal) => {
      const res = await fetch(url, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        signal,
      });

      // 404 Policy: If 404, return null directly without parsing body (safe against HTML/empty 404s)
      if (res.status === 404) {
        return null;
      }

      if (!res.ok) {
        let errorMsg = `Lỗi xem chi tiết phim (${res.status})`;
        try {
          const errBody = await res.json();
          if (errBody?.message) errorMsg = errBody.message;
        } catch {
          // non-JSON error
        }
        throw new CatalogApiError(errorMsg, res.status);
      }

      let body: any;
      try {
        body = await res.json();
      } catch {
        throw new CatalogApiError('Máy chủ phản hồi định dạng dữ liệu không hợp lệ (không phải JSON)', res.status);
      }

      if (!body || typeof body !== 'object' || body.success !== true || !body.data) {
        throw new CatalogApiError(body?.message || 'Phản hồi chi tiết phim không thành công', res.status, body);
      }

      const movie = normalizeCatalogMovie(body.data);

      // Verify literal ID equality according to contract (no case-insensitive mapping)
      if (movie.id !== cleanId) {
        throw new CatalogApiError(
          `ID phim trong phản hồi (${movie.id}) không khớp với ID yêu cầu (${cleanId})`,
          502
        );
      }

      return movie;
    },
    options
  );
}
