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
const SPRINGBOOT_API = process.env.NEXT_PUBLIC_SPRINGBOOT_API_URL || '/api';

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

// =============================================================================
// CATALOG-01 ANIMATION CATALOG CONTRACT & API METHODS
// =============================================================================

export interface CatalogValidationError {
  path: string;
  code: string;
  message: string;
}

export interface CatalogValidationResult {
  valid: boolean;
  packageId?: string;
  revision?: number;
  contentHash?: string;
  toCreate: number;
  toUpdate: number;
  unchanged: number;
  conflicts: number;
  errors: CatalogValidationError[];
}

export interface CatalogImportResponse {
  success: boolean;
  importId: string;
  packageId: string;
  revision: number;
  contentHash: string;
  importedAt: string;
  counts: Record<string, number>;
  indexStatus: string;
  message: string;
}

export interface CatalogSeriesSummary {
  id: string;
  title: string;
  originalTitle?: string;
  synopsis?: string;
  primaryLanguage?: string;
  releaseYearStart?: number;
  releaseYearEnd?: number;
  releaseStatus?: string;
  genreIds?: string;
  genreIdsJson?: string;
  keywords?: string;
  themes?: string;
  creators?: string;
  studios?: string;
  characterIds?: string;
}

export interface CatalogSeason {
  id: string;
  seriesId: string;
  number?: number;
  seasonNumber?: number;
  title: string;
  synopsis?: string;
  episodeCount?: number;
}

export interface CatalogEpisode {
  id: string;
  seriesId: string;
  seasonId?: string;
  number?: number;
  episodeNumber?: number;
  title: string;
  synopsis?: string;
  airDate?: string;
  durationMs?: number;
  plotFacts?: string;
  keywords?: string;
  themes?: string;
  primaryMediaAssetId?: string;
}

export interface CatalogSegment {
  id: string;
  episodeId: string;
  position: number;
  title: string;
  synopsis?: string;
  episodeStartMs?: number;
  episodeEndMs?: number;
  plotFacts?: string;
}

export interface CatalogScene {
  id: string;
  episodeId: string;
  mediaAssetId?: string;
  startMs: number;
  endMs: number;
  title?: string;
  summary?: string;
  visualDescription?: string;
  keywords?: string;
  themes?: string;
}

export interface CatalogMediaAsset {
  id: string;
  contentType: string;
  role: string;
  storageProvider: string;
  storageKey?: string;
  relativePath?: string;
  driveFolderId?: string;
  driveFileId?: string;
  durationMs?: number;
  coverageJson?: string;
  accessPolicy?: 'public' | 'authenticated' | 'private' | string;
}

export interface CatalogSnapshot {
  id: string;
  snapshotVersion: number;
  contentHash: string;
  totalItems: number;
  status: 'PENDING' | 'SYNCING' | 'READY' | 'BLOCKED' | 'SYNC_FAILED' | string;
  errorMessage?: string;
  retryCount?: number;
  createdAt?: string;
  completedAt?: string;
  updatedAt?: string;
}

export interface CatalogSeriesResponse {
  series: CatalogSeriesSummary;
  seasons: CatalogSeason[];
  episodes: CatalogEpisode[];
}

export interface CatalogEpisodeResponse {
  episode: CatalogEpisode;
  segments: CatalogSegment[];
  mediaAssets: CatalogMediaAsset[];
  scenes: CatalogScene[];
}

export interface CatalogSearchResult {
  id: string;
  type: 'series' | 'episode' | 'segment' | 'scene';
  title: string;
  parentTitle?: string;
  seriesId?: string;
  episodeId?: string;
  mediaAssetId?: string;
  startMs?: number;
  endMs?: number;
  snippet?: string;
  releaseYearStart?: number;
}

function getAuthHeader(): Record<string, string> {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('dippie_auth_token') || localStorage.getItem('token');
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
  }
  return {};
}

/**
 * Validate an external animation catalog JSON payload (dry-run preview).
 */
export async function validateCatalogPackage(
  payload: any,
  baseUrl = SPRINGBOOT_API
): Promise<CatalogValidationResult> {
  const url = `${baseUrl}/admin/catalog/validate`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok && res.status !== 400) throw new CatalogApiError(`Không thể kiểm tra gói catalog (${res.status})`, res.status);
  const result = await res.json();
  if (!result || typeof result.valid !== 'boolean' || !Array.isArray(result.errors)) {
    throw new CatalogApiError('Phản hồi kiểm tra gói catalog không hợp lệ', 502);
  }
  return result;
}

/**
 * Atomically commit and import an animation catalog JSON package into the database.
 */
export async function importCatalogPackage(
  payload: any,
  baseUrl = SPRINGBOOT_API
): Promise<CatalogImportResponse> {
  const url = `${baseUrl}/admin/catalog/import`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let errBody: any;
    try {
      errBody = await res.json();
    } catch {
      // non-JSON
    }
    throw new CatalogApiError(
      errBody?.message || `Lỗi khi nhập dữ liệu catalog (HTTP ${res.status})`,
      res.status,
      errBody
    );
  }

  return await res.json();
}

/**
 * Fetch catalog packages import history.
 */
export async function getImportHistory(
  baseUrl = SPRINGBOOT_API,
  signal?: AbortSignal,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<any[]> {
  const url = `${baseUrl}/admin/catalog/history`;
  return executeWithLifecycle(async (requestSignal) => {
    const res = await fetch(url, { method: 'GET', headers: { Accept: 'application/json', ...getAuthHeader() }, signal: requestSignal });
    if (!res.ok) throw new CatalogApiError(`Không thể tải lịch sử nhập (${res.status})`, res.status);
    const data = await res.json();
    if (!Array.isArray(data)) throw new CatalogApiError('Dữ liệu lịch sử nhập không hợp lệ', 502);
    return data;
  }, { signal, timeoutMs });
}

/**
 * Fetch catalog sync snapshots history and status.
 */
export async function getCatalogSnapshots(
  baseUrl = SPRINGBOOT_API,
  signal?: AbortSignal,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<CatalogSnapshot[]> {
  const url = `${baseUrl}/admin/catalog/snapshots`;
  return executeWithLifecycle(async (requestSignal) => {
    const res = await fetch(url, { method: 'GET', headers: { Accept: 'application/json', ...getAuthHeader() }, signal: requestSignal });
    if (!res.ok) throw new CatalogApiError(`Không thể tải trạng thái đồng bộ (${res.status})`, res.status);
    const data = await res.json();
    if (!Array.isArray(data)) throw new CatalogApiError('Dữ liệu trạng thái đồng bộ không hợp lệ', 502);
    return data;
  }, { signal, timeoutMs });
}

/**
 * Retry an outbox catalog snapshot sync.
 */
export async function retryCatalogSnapshot(
  snapshotId: string,
  baseUrl = SPRINGBOOT_API
): Promise<CatalogSnapshot> {
  const url = `${baseUrl}/admin/catalog/snapshots/${encodeURIComponent(snapshotId)}/retry`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      ...getAuthHeader(),
    },
  });
  if (!res.ok) {
    throw new CatalogApiError(`Không thể thử lại snapshot (${res.status})`, res.status);
  }
  return await res.json();
}

/**
 * Fetch all imported animation series.
 */
export async function getCatalogSeriesList(
  baseUrl = SPRINGBOOT_API,
  signal?: AbortSignal,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<CatalogSeriesSummary[]> {
  const url = `${baseUrl}/catalog/series`;
  return executeWithLifecycle(async (requestSignal) => {
    const res = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json', ...getAuthHeader() },
      signal: requestSignal,
    });
    if (!res.ok) throw new CatalogApiError(`Lỗi tải danh mục bộ hoạt hình (${res.status})`, res.status);
    const body = await res.json();
    if (!Array.isArray(body)) throw new CatalogApiError('Danh mục bộ hoạt hình không hợp lệ (thiếu mảng dữ liệu)', 502, body);
    return body.map(normalizeCatalogSeriesSummary);
  }, { signal, timeoutMs });
}

function normalizeCatalogSeriesSummary(raw: any): CatalogSeriesSummary {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new CatalogApiError('Bộ hoạt hình từ máy chủ không hợp lệ (không phải object)', 502, raw);
  }
  if (typeof raw.id !== 'string' || !raw.id.trim()) {
    throw new CatalogApiError('Bộ hoạt hình thiếu ID bắt buộc', 502, raw);
  }
  if (typeof raw.title !== 'string' || !raw.title.trim()) {
    throw new CatalogApiError(`Bộ hoạt hình [${raw.id.trim()}] thiếu tiêu đề bắt buộc`, 502, raw);
  }
  for (const key of ['releaseYearStart', 'releaseYearEnd'] as const) {
    if (raw[key] != null && (typeof raw[key] !== 'number' || !Number.isFinite(raw[key]))) {
      throw new CatalogApiError(`Bộ hoạt hình [${raw.id.trim()}] có ${key} không hợp lệ`, 502, raw);
    }
  }
  return {
    id: raw.id.trim(),
    title: raw.title.trim(),
    originalTitle: typeof raw.originalTitle === 'string' ? raw.originalTitle : undefined,
    synopsis: typeof raw.synopsis === 'string' ? raw.synopsis : undefined,
    primaryLanguage: typeof raw.primaryLanguage === 'string' ? raw.primaryLanguage : undefined,
    releaseYearStart: raw.releaseYearStart ?? undefined,
    releaseYearEnd: raw.releaseYearEnd ?? undefined,
    releaseStatus: typeof raw.releaseStatus === 'string' ? raw.releaseStatus : undefined,
    genreIds: typeof raw.genreIds === 'string' ? raw.genreIds : undefined,
    genreIdsJson: typeof raw.genreIdsJson === 'string' ? raw.genreIdsJson : undefined,
  };
}

/**
 * Fetch series detail with seasons and episodes.
 */
export async function getCatalogSeriesDetail(
  id: string,
  baseUrl = SPRINGBOOT_API,
  signal?: AbortSignal
): Promise<CatalogSeriesResponse | null> {
  const url = `${baseUrl}/catalog/series/${encodeURIComponent(id)}`;
  const res = await fetch(url, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
      ...getAuthHeader(),
    },
    signal,
  });
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new CatalogApiError(`Lỗi xem chi tiết bộ phim (${res.status})`, res.status);
  }
  return await res.json();
}

/**
 * Fetch episode detail with segments, media assets, and scenes.
 */
export async function getCatalogEpisodeDetail(
  id: string,
  baseUrl = SPRINGBOOT_API,
  signal?: AbortSignal
): Promise<CatalogEpisodeResponse | null> {
  const url = `${baseUrl}/catalog/episodes/${encodeURIComponent(id)}`;
  const res = await fetch(url, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
      ...getAuthHeader(),
    },
    signal,
  });
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new CatalogApiError(`Lỗi xem chi tiết tập phim (${res.status})`, res.status);
  }
  return await res.json();
}

/**
 * Search animation catalog across series, episodes, segments, and scenes.
 */
export async function searchAnimationCatalog(
  q: string,
  baseUrl = SPRINGBOOT_API,
  signal?: AbortSignal,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<CatalogSearchResult[]> {
  if (!q.trim()) return [];
  const url = `${baseUrl}/catalog/search?q=${encodeURIComponent(q.trim())}`;
  return executeWithLifecycle(async (requestSignal) => {
    const res = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json', ...getAuthHeader() },
      signal: requestSignal,
    });
    if (!res.ok) throw new CatalogApiError(`Lỗi tìm kiếm danh mục hoạt hình (${res.status})`, res.status);
    const body = await res.json();
    if (!Array.isArray(body)) throw new CatalogApiError('Kết quả tìm kiếm danh mục không hợp lệ (thiếu mảng dữ liệu)', 502, body);
    const validTypes = new Set(['series', 'episode', 'segment', 'scene']);
    return body.map((item: any) => {
      if (!item || typeof item !== 'object' || Array.isArray(item)
          || typeof item.id !== 'string' || !item.id.trim()
          || typeof item.title !== 'string' || !item.title.trim()
          || !validTypes.has(item.type)) {
        throw new CatalogApiError('Kết quả tìm kiếm thiếu ID, tiêu đề hoặc loại nội dung hợp lệ', 502, item);
      }
      return {
        ...item,
        id: item.id.trim(),
        title: item.title.trim(),
      } as CatalogSearchResult;
    });
  }, { signal, timeoutMs });
}


