const SPRINGBOOT_API = process.env.NEXT_PUBLIC_SPRINGBOOT_API_URL || '/api';
export const WATCH_PROGRESS_LIMIT = 30;
export const GUEST_WATCH_PROGRESS_KEY = 'dippie_guest_watch_progress_v1';
export const AUTO_NEXT_PREFERENCE_KEY = 'dippie_auto_next_enabled_v1';
const DEFAULT_TIMEOUT_MS = 7000;

export type WatchProgressRecord = {
  episodeId: string;
  seriesId: string;
  seriesTitle: string;
  seasonId: string | null;
  seasonNumber: number | null;
  seasonTitle: string | null;
  episodeNumber: number | null;
  episodeTitle: string;
  assetId: string;
  positionMs: number;
  durationMs: number | null;
  completed: boolean;
  version: number;
  updatedAt: string;
};

export type WatchProgressDraft = {
  episodeId: string;
  seriesId: string;
  seriesTitle: string;
  seasonId?: string | null;
  seasonNumber?: number | null;
  seasonTitle?: string | null;
  episodeNumber?: number | null;
  episodeTitle: string;
  assetId: string;
  positionMs: number;
  durationMs?: number | null;
  completed?: boolean;
};

export class WatchProgressError extends Error {
  status: number;
  isCanceled: boolean;
  isTimeout: boolean;

  constructor(message: string, status: number, options: { isCanceled?: boolean; isTimeout?: boolean } = {}) {
    super(message);
    this.name = options.isCanceled ? 'AbortError' : 'WatchProgressError';
    this.status = status;
    this.isCanceled = Boolean(options.isCanceled);
    this.isTimeout = Boolean(options.isTimeout);
  }
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function nullableString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function nullableNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? Math.floor(value) : null;
}

export function normalizeWatchProgressRecord(raw: any): WatchProgressRecord {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new WatchProgressError('Dữ liệu tiến độ xem không hợp lệ.', 502);
  }
  if (
    !nonEmptyString(raw.episodeId) || !nonEmptyString(raw.seriesId) || !nonEmptyString(raw.seriesTitle) ||
    !nonEmptyString(raw.episodeTitle) || !nonEmptyString(raw.assetId) ||
    typeof raw.positionMs !== 'number' || !Number.isSafeInteger(raw.positionMs) || raw.positionMs < 0 ||
    typeof raw.completed !== 'boolean' || !Number.isSafeInteger(raw.version) || raw.version < 0 ||
    !nonEmptyString(raw.updatedAt) || !Number.isFinite(Date.parse(raw.updatedAt))
  ) {
    throw new WatchProgressError('Dữ liệu tiến độ xem thiếu trường bắt buộc.', 502);
  }
  return {
    episodeId: raw.episodeId.trim(),
    seriesId: raw.seriesId.trim(),
    seriesTitle: raw.seriesTitle.trim(),
    seasonId: nullableString(raw.seasonId),
    seasonNumber: nullableNumber(raw.seasonNumber),
    seasonTitle: nullableString(raw.seasonTitle),
    episodeNumber: nullableNumber(raw.episodeNumber),
    episodeTitle: raw.episodeTitle.trim(),
    assetId: raw.assetId.trim(),
    positionMs: raw.positionMs,
    durationMs: nullableNumber(raw.durationMs),
    completed: raw.completed,
    version: raw.version,
    updatedAt: new Date(Date.parse(raw.updatedAt)).toISOString(),
  };
}

function normalizeDraft(draft: WatchProgressDraft): WatchProgressDraft {
  if (!draft || !nonEmptyString(draft.episodeId) || !nonEmptyString(draft.seriesId) ||
      !nonEmptyString(draft.seriesTitle) || !nonEmptyString(draft.episodeTitle) || !nonEmptyString(draft.assetId)) {
    throw new WatchProgressError('Tiến độ xem thiếu thông tin bộ, tập hoặc tệp video.', 400);
  }
  if (!Number.isSafeInteger(draft.positionMs) || draft.positionMs < 0) {
    throw new WatchProgressError('Mốc phát video không hợp lệ.', 400);
  }
  const durationMs = nullableNumber(draft.durationMs);
  return {
    episodeId: draft.episodeId.trim(),
    seriesId: draft.seriesId.trim(),
    seriesTitle: draft.seriesTitle.trim(),
    seasonId: nullableString(draft.seasonId),
    seasonNumber: nullableNumber(draft.seasonNumber),
    seasonTitle: nullableString(draft.seasonTitle),
    episodeNumber: nullableNumber(draft.episodeNumber),
    episodeTitle: draft.episodeTitle.trim(),
    assetId: draft.assetId.trim(),
    positionMs: durationMs === null ? draft.positionMs : Math.min(draft.positionMs, durationMs),
    durationMs,
    completed: Boolean(draft.completed),
  };
}

async function executeWithTimeout<T>(
  action: (signal: AbortSignal) => Promise<T>,
  options: { signal?: AbortSignal; timeoutMs?: number } = {}
): Promise<T> {
  const timeoutMs = options.timeoutMs && options.timeoutMs > 0 ? options.timeoutMs : DEFAULT_TIMEOUT_MS;
  if (options.signal?.aborted) {
    throw new WatchProgressError('Yêu cầu đã bị hủy.', 499, { isCanceled: true });
  }
  const controller = new AbortController();
  return new Promise<T>((resolve, reject) => {
    let settled = false;
    let timedOut = false;
    let callerCanceled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const cleanup = () => {
      if (timer !== null) clearTimeout(timer);
      options.signal?.removeEventListener('abort', handleCallerAbort);
    };
    const finishError = (error: unknown) => {
      if (settled) return;
      settled = true;
      cleanup();
      if (callerCanceled) {
        reject(new WatchProgressError('Yêu cầu đã bị hủy.', 499, { isCanceled: true }));
      } else if (timedOut) {
        reject(new WatchProgressError('Yêu cầu tiến độ xem quá thời gian phản hồi.', 408, { isTimeout: true }));
      } else if (error instanceof WatchProgressError) {
        reject(error);
      } else {
        reject(new WatchProgressError('Không thể kết nối đến dịch vụ tiến độ xem.', 0));
      }
    };
    const handleCallerAbort = () => {
      if (settled) return;
      callerCanceled = true;
      controller.abort(options.signal?.reason);
      finishError(options.signal?.reason);
    };
    options.signal?.addEventListener('abort', handleCallerAbort, { once: true });
    timer = setTimeout(() => {
      if (settled) return;
      timedOut = true;
      controller.abort();
      finishError(new Error('timeout'));
    }, timeoutMs);
    Promise.resolve().then(() => action(controller.signal)).then((value) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(value);
    }).catch(finishError);
  });
}

async function readEnvelope<T>(res: Response, label: string): Promise<T> {
  let json: any;
  try {
    json = await res.json();
  } catch {
    throw new WatchProgressError(`Phản hồi ${label} không phải JSON hợp lệ.`, 502);
  }
  if (!json || json.success !== true || !Object.prototype.hasOwnProperty.call(json, 'data')) {
    throw new WatchProgressError(typeof json?.message === 'string' ? json.message : `Phản hồi ${label} không hợp lệ.`, 502);
  }
  return json.data as T;
}

function authHeaders(token: string, json = false): Record<string, string> {
  if (!nonEmptyString(token)) throw new WatchProgressError('Cần đăng nhập để đồng bộ tiến độ xem.', 401);
  return {
    Accept: 'application/json',
    ...(json ? { 'Content-Type': 'application/json' } : {}),
    Authorization: `Bearer ${token}`,
  };
}

function throwHttpError(res: Response, label: string): never {
  if (res.status === 401) throw new WatchProgressError('Phiên đăng nhập đã hết hạn.', 401);
  if (res.status === 403) throw new WatchProgressError('Bạn không có quyền xem tiến độ này.', 403);
  throw new WatchProgressError(`${label} thất bại (HTTP ${res.status}).`, res.status);
}

export async function listWatchProgress(
  token: string,
  options: { baseUrl?: string; signal?: AbortSignal; timeoutMs?: number } = {}
): Promise<WatchProgressRecord[]> {
  const headers = authHeaders(token);
  const url = `${options.baseUrl || SPRINGBOOT_API}/users/watch-progress`;
  return executeWithTimeout(async (signal) => {
    const res = await fetch(url, { headers, signal });
    if (!res.ok) throwHttpError(res, 'Tải tiến độ xem');
    const data = await readEnvelope<any>(res, 'tiến độ xem');
    if (!Array.isArray(data)) throw new WatchProgressError('Danh sách tiến độ xem không hợp lệ.', 502);
    return data.slice(0, WATCH_PROGRESS_LIMIT).map(normalizeWatchProgressRecord);
  }, options);
}

export async function getWatchProgress(
  token: string,
  episodeId: string,
  options: { baseUrl?: string; signal?: AbortSignal; timeoutMs?: number } = {}
): Promise<WatchProgressRecord | null> {
  if (!nonEmptyString(episodeId)) throw new WatchProgressError('ID tập phim không hợp lệ.', 400);
  const headers = authHeaders(token);
  const url = `${options.baseUrl || SPRINGBOOT_API}/users/watch-progress/${encodeURIComponent(episodeId.trim())}`;
  return executeWithTimeout(async (signal) => {
    const res = await fetch(url, { headers, signal });
    if (res.status === 404) return null;
    if (!res.ok) throwHttpError(res, 'Tải tiến độ tập phim');
    return normalizeWatchProgressRecord(await readEnvelope<any>(res, 'tiến độ tập phim'));
  }, options);
}

export async function saveWatchProgress(
  token: string,
  episodeId: string,
  draft: Pick<WatchProgressDraft, 'assetId' | 'positionMs'>,
  expectedVersion: number,
  options: { baseUrl?: string; signal?: AbortSignal; timeoutMs?: number } = {}
): Promise<WatchProgressRecord> {
  if (!nonEmptyString(episodeId) || !nonEmptyString(draft?.assetId)) {
    throw new WatchProgressError('ID tập hoặc tệp video không hợp lệ.', 400);
  }
  if (!Number.isSafeInteger(draft.positionMs) || draft.positionMs < 0) {
    throw new WatchProgressError('Mốc phát video không hợp lệ.', 400);
  }
  if (!Number.isSafeInteger(expectedVersion) || expectedVersion < -1) {
    throw new WatchProgressError('Phiên bản tiến độ không hợp lệ.', 400);
  }
  const headers = authHeaders(token, true);
  const url = `${options.baseUrl || SPRINGBOOT_API}/users/watch-progress/${encodeURIComponent(episodeId.trim())}`;
  const payload = { assetId: draft.assetId.trim(), positionMs: Math.floor(draft.positionMs), expectedVersion };
  return executeWithTimeout(async (signal) => {
    const res = await fetch(url, { method: 'PUT', headers, body: JSON.stringify(payload), signal });
    if (!res.ok) throwHttpError(res, 'Lưu tiến độ xem');
    return normalizeWatchProgressRecord(await readEnvelope<any>(res, 'tiến độ xem'));
  }, options);
}

export async function deleteWatchProgress(
  token: string,
  episodeId: string,
  options: { baseUrl?: string; signal?: AbortSignal; timeoutMs?: number } = {}
): Promise<void> {
  if (!nonEmptyString(episodeId)) throw new WatchProgressError('ID tập phim không hợp lệ.', 400);
  const headers = authHeaders(token);
  const url = `${options.baseUrl || SPRINGBOOT_API}/users/watch-progress/${encodeURIComponent(episodeId.trim())}`;
  return executeWithTimeout(async (signal) => {
    const res = await fetch(url, { method: 'DELETE', headers, signal });
    if (!res.ok) throwHttpError(res, 'Xóa tiến độ xem');
    const data = await readEnvelope<any>(res, 'tiến độ xem');
    if (data !== null) throw new WatchProgressError('Phản hồi xóa tiến độ không hợp lệ.', 502);
  }, options);
}

function readGuestStorage(): WatchProgressRecord[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(GUEST_WATCH_PROGRESS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.map((item) => {
      try { return normalizeWatchProgressRecord(item); } catch { return null; }
    }).filter((item): item is WatchProgressRecord => item !== null)
      .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
      .slice(0, WATCH_PROGRESS_LIMIT);
  } catch {
    return [];
  }
}

export function getGuestWatchProgress(): WatchProgressRecord[] {
  return readGuestStorage();
}

export function saveGuestWatchProgress(draft: WatchProgressDraft, now = Date.now()): WatchProgressRecord[] {
  if (typeof window === 'undefined') throw new WatchProgressError('Bộ nhớ thiết bị không khả dụng.', 0);
  const clean = normalizeDraft(draft);
  const prior = readGuestStorage().find((item) => item.episodeId === clean.episodeId);
  const record = normalizeWatchProgressRecord({
    ...clean,
    seasonId: clean.seasonId ?? null,
    seasonNumber: clean.seasonNumber ?? null,
    seasonTitle: clean.seasonTitle ?? null,
    episodeNumber: clean.episodeNumber ?? null,
    durationMs: clean.durationMs ?? null,
    version: prior?.version ?? 0,
    updatedAt: new Date(now).toISOString(),
  });
  const next = [record, ...readGuestStorage().filter((item) => item.episodeId !== record.episodeId)]
    .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
    .slice(0, WATCH_PROGRESS_LIMIT);
  try {
    window.localStorage.setItem(GUEST_WATCH_PROGRESS_KEY, JSON.stringify(next));
  } catch {
    throw new WatchProgressError('Không thể lưu tiến độ xem vào bộ nhớ thiết bị.', 0);
  }
  return next;
}

export function clearGuestWatchProgress(): void {
  if (typeof window === 'undefined') return;
  try { window.localStorage.removeItem(GUEST_WATCH_PROGRESS_KEY); } catch {}
}

export function isUsableResumeProgress(record: WatchProgressRecord | null | undefined): record is WatchProgressRecord {
  return Boolean(
    record && !record.completed && nonEmptyString(record.episodeId) && nonEmptyString(record.seriesId) &&
    nonEmptyString(record.assetId) && Number.isSafeInteger(record.positionMs) && record.positionMs > 0 &&
    (record.durationMs === null || record.positionMs < record.durationMs)
  );
}

export function buildWatchProgressHref(record: WatchProgressRecord): string {
  const params = new URLSearchParams();
  params.set('episode', record.episodeId);
  params.set('asset', record.assetId);
  params.set('t', String(record.positionMs));
  params.set('timeline', 'file');
  return `/series/${encodeURIComponent(record.seriesId)}?${params.toString()}`;
}

export function readAutoNextPreference(): boolean {
  if (typeof window === 'undefined') return false;
  try { return window.localStorage.getItem(AUTO_NEXT_PREFERENCE_KEY) === 'true'; } catch { return false; }
}

export function writeAutoNextPreference(enabled: boolean): void {
  if (typeof window === 'undefined') return;
  try { window.localStorage.setItem(AUTO_NEXT_PREFERENCE_KEY, enabled ? 'true' : 'false'); } catch {}
}
