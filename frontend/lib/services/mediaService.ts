export interface MediaAssetInfo {
  assetId: string;
  kind: 'feature' | 'trailer';
  streamUrl: string;
  mimeType: string;
  byteLength: number;
  durationSeconds?: number | null;
  isPublic: boolean;
  version: string;
}

export interface MediaDescriptor {
  movieId: string;
  hasFeature: boolean;
  hasTrailer: boolean;
  feature?: MediaAssetInfo | null;
  trailer?: MediaAssetInfo | null;
}

const DEFAULT_TIMEOUT_MS = 6000;
const SPRINGBOOT_API = process.env.NEXT_PUBLIC_SPRINGBOOT_API_URL || 'http://localhost:8080/api';

/**
 * Resolves a stream URL returned by descriptor into a full URL if relative.
 */
export function resolveStreamUrl(streamUrl: string): string {
  if (!streamUrl) return '';
  if (streamUrl.startsWith('http://') || streamUrl.startsWith('https://')) {
    return streamUrl;
  }
  // Strip trailing '/api' from SPRINGBOOT_API to get base host
  const baseHost = SPRINGBOOT_API.replace(/\/api\/?$/, '');
  const cleanPath = streamUrl.startsWith('/') ? streamUrl : `/${streamUrl}`;
  return `${baseHost}${cleanPath}`;
}

function createDOMException(message: string, name: string): DOMException {
  const Ctor = typeof DOMException !== 'undefined' ? DOMException : (Error as any);
  try {
    return new Ctor(message, name);
  } catch {
    const err = new Error(message) as any;
    err.name = name;
    return err;
  }
}

/**
 * Fetches the media descriptor for a given movie.
 * Supports public access, handles both direct payloads and wrapped ApiResponse payloads.
 */
export async function getMediaDescriptor(
  movieId: string,
  options?: { timeoutMs?: number; signal?: AbortSignal }
): Promise<MediaDescriptor> {
  const timeoutMs = options?.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  let isTimeout = false;
  let isExternalAbort = false;

  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  let removeExternalListener: (() => void) | null = null;

  try {
    if (options?.signal?.aborted) {
      isExternalAbort = true;
      throw createDOMException('The operation was aborted.', 'AbortError');
    }

    const controller = new AbortController();

    if (options?.signal) {
      const onAbort = () => {
        if (!isTimeout) {
          isExternalAbort = true;
        }
        controller.abort();
      };
      options.signal.addEventListener('abort', onAbort, { once: true });
      removeExternalListener = () => {
        options.signal?.removeEventListener('abort', onAbort);
      };
    }

    timeoutId = setTimeout(() => {
      if (!options?.signal?.aborted) {
        isTimeout = true;
        controller.abort();
      }
    }, timeoutMs);

    const url = `${SPRINGBOOT_API}/movies/${encodeURIComponent(movieId)}/media-descriptor`;
    const response = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Lỗi tải mô tả media (${response.status})`);
    }

    const json = await response.json();
    if (!json || typeof json !== 'object' || Array.isArray(json)) {
      throw new Error('Dữ liệu mô tả media không hợp lệ');
    }

    const data =
      json.data && typeof json.data === 'object' && !Array.isArray(json.data)
        ? json.data
        : json;

    if (typeof data.movieId !== 'string' || data.movieId.trim() === '' || data.movieId !== movieId) {
      throw new Error('Dữ liệu mô tả media không khớp mã phim');
    }

    if (typeof data.hasFeature !== 'boolean' || typeof data.hasTrailer !== 'boolean') {
      throw new Error('Thiếu hoặc sai trường hasFeature/hasTrailer');
    }

    const isInvalid = (a: any, k: string) =>
      !a || typeof a !== 'object' || Array.isArray(a) || a.kind !== k || typeof a.streamUrl !== 'string' || !a.streamUrl.trim();
    if (data.hasFeature && isInvalid(data.feature, 'feature')) throw new Error('Dữ liệu feature không hợp lệ');
    if (data.hasTrailer && isInvalid(data.trailer, 'trailer')) throw new Error('Dữ liệu trailer không hợp lệ');

    return {
      movieId: data.movieId,
      hasFeature: data.hasFeature,
      hasTrailer: data.hasTrailer,
      feature: data.hasFeature && data.feature
        ? {
            ...data.feature,
            streamUrl: resolveStreamUrl(data.feature.streamUrl),
          }
        : null,
      trailer: data.hasTrailer && data.trailer
        ? {
            ...data.trailer,
            streamUrl: resolveStreamUrl(data.trailer.streamUrl),
          }
        : null,
    };
  } catch (err: any) {
    if (isExternalAbort || options?.signal?.aborted) {
      throw createDOMException('The operation was aborted.', 'AbortError');
    }
    if (isTimeout) {
      const timeoutErr = createDOMException('Hết thời gian tải mô tả media', 'TimeoutError');
      (timeoutErr as any).isTimeout = true;
      throw timeoutErr;
    }
    throw err;
  } finally {
    if (timeoutId !== null) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
    if (removeExternalListener) {
      removeExternalListener();
      removeExternalListener = null;
    }
  }
}

export interface PlaybackGrantResponse {
  assetId: string;
  grant: string;
  streamUrl: string;
  expiresIn: number;
}

export function getStoredAuthToken(): string | null {
  return typeof window !== 'undefined'
    ? localStorage.getItem('dippie_auth_token') || localStorage.getItem('token') || localStorage.getItem('auth_token')
    : null;
}

export async function requestPlaybackGrant(
  assetId: string,
  signal?: AbortSignal
): Promise<PlaybackGrantResponse | null> {
  if (!assetId) return null;
  const token = getStoredAuthToken();
  try {
    const res = await fetch(`${SPRINGBOOT_API}/media/grant/${assetId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      signal,
    });
    if (!res.ok) return null;
    const d = await res.json();
    return { assetId: d.assetId, grant: d.grant, streamUrl: resolveStreamUrl(d.streamUrl), expiresIn: d.expiresIn };
  } catch {
    return null;
  }
}
