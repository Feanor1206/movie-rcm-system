import type { Movie } from '@/types/movie';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: string;
  movies?: Movie[];
  followUps?: string[];
}

export interface ChatServiceResponse {
  text: string;
  recommendedMovies: Movie[];
  followUps: string[];
}

/**
 * Gửi tin nhắn trực tiếp đến Next.js /api/chat để chuyển thẳng sang Qwen LLM
 */
export async function sendChatMessage(
  message: string,
  history: ChatMessage[] = []
): Promise<ChatServiceResponse> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      messages: history.map((m) => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text,
      })),
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.text || 'Lỗi kết nối tới máy chủ AI');
  }

  return response.json();
}
