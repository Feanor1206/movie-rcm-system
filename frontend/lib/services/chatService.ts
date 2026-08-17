import { movies } from '@/lib/data/movies';
import type { Movie } from '@/types/movie';

export type ChatMessage = {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: string;
  movies?: Movie[];
  followUps?: string[];
};

/**
 * Gửi câu hỏi đến model (thông qua /api/chat - nơi bạn có thể cắm FastAPI/Ollama/LLM)
 */
export async function sendChatMessage(
  message: string,
  history: ChatMessage[]
): Promise<{ text: string; recommendedMovies: Movie[]; followUps?: string[] }> {
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        messages: history.map((m) => ({ role: m.sender === 'user' ? 'user' : 'assistant', text: m.text })),
      }),
    });

    if (res.ok) {
      const data = await res.json();
      return {
        text: data.text,
        recommendedMovies: data.recommendedMovies || [],
        followUps: data.followUps || [],
      };
    }
  } catch (error) {
    console.error('Lỗi khi gọi API chat:', error);
  }

  // Fallback nếu API có sự cố mạng
  return processChatQuery(message);
}

/**
 * Local Recommendation Matcher Logic (Fallback khi chưa cắm backend ngoài)
 */
export function processChatQuery(userQuery: string): {
  text: string;
  recommendedMovies: Movie[];
  followUps: string[];
} {
  const query = userQuery.toLowerCase().trim();

  // 1. Sci-Fi / Space / Viễn tưởng
  if (
    query.includes('sci-fi') ||
    query.includes('viễn tưởng') ||
    query.includes('vũ trụ') ||
    query.includes('không gian') ||
    query.includes('the last orbit') ||
    query.includes('interstellar') ||
    query.includes('space')
  ) {
    const matched = movies.filter((m) => m.genres.includes('Sci-Fi'));
    return {
      text: 'Dành cho người yêu thích không gian kỳ vĩ và khoa học viễn tưởng, đây là những tựa phim tiêu biểu:',
      recommendedMovies: matched.length > 0 ? matched : movies.slice(0, 2),
      followUps: [
        'Tìm phim trinh thám hồi hộp',
        'Top phim đánh giá cao nhất',
        'Gợi ý phim ngắn dưới 2 tiếng',
      ],
    };
  }

  // 2. Mystery / Thriller / Trinh thám / Giật gân / Đấu trí
  if (
    query.includes('trinh thám') ||
    query.includes('hồi hộp') ||
    query.includes('giật gân') ||
    query.includes('bí ẩn') ||
    query.includes('đấu trí') ||
    query.includes('thriller') ||
    query.includes('mystery') ||
    query.includes('crime') ||
    query.includes('nocturne') ||
    query.includes('tội phạm')
  ) {
    const matched = movies.filter(
      (m) => m.genres.includes('Thriller') || m.genres.includes('Mystery') || m.genres.includes('Crime')
    );
    return {
      text: 'Dưới đây là các tác phẩm trinh thám - giật gân với cốt truyện ly kỳ và nhiều nút thắt bất ngờ:',
      recommendedMovies: matched,
      followUps: [
        'Phim tâm lý tình cảm nhẹ nhàng',
        'Top phim điểm cao nhất',
        'Phim mới phát hành 2026',
      ],
    };
  }

  // 3. Drama / Romance / Tình cảm / Lãng mạn / Nhẹ nhàng
  if (
    query.includes('tình cảm') ||
    query.includes('lãng mạn') ||
    query.includes('nhẹ nhàng') ||
    query.includes('chữa lành') ||
    query.includes('romance') ||
    query.includes('drama') ||
    query.includes('quiet places') ||
    query.includes('afterlight')
  ) {
    const matched = movies.filter(
      (m) => m.genres.includes('Romance') || m.genres.includes('Drama')
    );
    return {
      text: 'Những bộ phim giàu cảm xúc và nghệ thuật thích hợp cho một buổi tối thư giãn lắng đọng:',
      recommendedMovies: matched.slice(0, 3),
      followUps: [
        'Phim phiêu lưu thám hiểm',
        'Phim khoa học viễn tưởng hay',
        'Phim phát hành năm 2026',
      ],
    };
  }

  // 4. Adventure / Phiêu lưu
  if (
    query.includes('phiêu lưu') ||
    query.includes('adventure') ||
    query.includes('thám hiểm') ||
    query.includes('biển') ||
    query.includes('deep blue')
  ) {
    const matched = movies.filter((m) => m.genres.includes('Adventure'));
    return {
      text: 'Bộ phim phiêu lưu vượt đại dương đầy cảm hứng dành cho bạn:',
      recommendedMovies: matched,
      followUps: [
        'Phim khoa học viễn tưởng hay nhất',
        'Tìm phim trinh thám',
        'Gợi ý phim xem tối nay',
      ],
    };
  }

  // 5. Top Rated / Điểm cao
  if (
    query.includes('điểm cao') ||
    query.includes('top') ||
    query.includes('hay nhất') ||
    query.includes('rating') ||
    query.includes('đánh giá') ||
    query.includes('imdb')
  ) {
    const matched = [...movies].sort((a, b) => b.rating - a.rating).slice(0, 3);
    return {
      text: 'Top các bộ phim đạt điểm đánh giá cao nhất từ các nhà phê bình và người xem:',
      recommendedMovies: matched,
      followUps: [
        'Phim khoa học viễn tưởng',
        'Phim trinh thám hồi hộp',
        'Phim mới năm 2026',
      ],
    };
  }

  // 6. Năm 2026 / Phim mới
  if (query.includes('2026') || query.includes('mới nhất') || query.includes('mới')) {
    const matched = movies.filter((m) => m.year === 2026);
    return {
      text: 'Các tác phẩm phát hành năm 2026 có chất lượng 4K HDR và âm thanh tiêu chuẩn phòng vé:',
      recommendedMovies: matched,
      followUps: [
        'Phim phiêu lưu',
        'Phim tình cảm sâu lắng',
        'Xem phim điểm cao nhất',
      ],
    };
  }

  // 7. Mặc định
  const randomPicks = [...movies].sort(() => 0.5 - Math.random()).slice(0, 2);
  return {
    text: `Đã phân tích yêu cầu "${userQuery}". Đây là những bộ phim phù hợp nhất:`,
    recommendedMovies: randomPicks,
    followUps: [
      'Gợi ý phim Sci-Fi vũ trụ',
      'Tìm phim trinh thám đấu trí',
      'Top phim điểm cao nhất',
    ],
  };
}
