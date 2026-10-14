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

/**
 * Fetches the media descriptor for a given movie.
 * Supports public access, handles both direct payloads and wrapped ApiResponse payloads.
 */
export async function getMediaDescriptor(
  movieId: string,
  options?: { timeoutMs?: number; signal?: AbortSignal }
): Promise<MediaDescriptor> {
  const timeoutMs = options?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  let removeExternalListener: (() => void) | null = null;
  if (options?.signal) {
    if (options.signal.aborted) {
      controller.abort();
    } else {
      const onAbort = () => controller.abort();
      options.signal.addEventListener('abort', onAbort, { once: true });
      removeExternalListener = () => options.signal?.removeEventListener('abort', onAbort);
    }
  }

  try {
    const url = `${SPRINGBOOT_API}/movies/${encodeURIComponent(movieId)}/media-descriptor`;
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Lỗi tải mô tả media (${response.status})`);
    }

    const json = await response.json();
    const data = json && typeof json === 'object' && 'data' in json ? json.data : json;

    return {
      movieId: data.movieId || movieId,
      hasFeature: Boolean(data.hasFeature),
      hasTrailer: Boolean(data.hasTrailer),
      feature: data.feature
        ? {
            ...data.feature,
            streamUrl: resolveStreamUrl(data.feature.streamUrl),
          }
        : null,
      trailer: data.trailer
        ? {
            ...data.trailer,
            streamUrl: resolveStreamUrl(data.trailer.streamUrl),
          }
        : null,
    };
  } finally {
    clearTimeout(timeoutId);
    if (removeExternalListener) {
      removeExternalListener();
    }
  }
}
