import type { Movie } from '@/types/movie';

const API = process.env.NEXT_PUBLIC_SPRINGBOOT_API_URL || '/api';

export async function getRecommendations(token: string | null, signal?: AbortSignal): Promise<{ movies: Movie[]; reasoning: string }> {
  const response = await fetch(`${API}/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ limit: 6 }),
    signal,
  });
  if (!response.ok) throw new Error('Không thể tải gợi ý');
  const data = await response.json();
  if (!data || !Array.isArray(data.recommendedMovies) || typeof data.reasoning !== 'string' ||
      !data.recommendedMovies.every((movie: Movie) => movie && typeof movie.id === 'string' && typeof movie.title === 'string')) {
    throw new Error('Dữ liệu gợi ý không hợp lệ');
  }
  return { movies: data.recommendedMovies, reasoning: data.reasoning };
}
