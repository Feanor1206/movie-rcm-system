import type { Movie } from '@/types/movie';

export interface StructuredIntent {
  intent_type: 'DISCOVERY' | 'CONVERSATIONAL_PATCH' | 'CLARIFICATION' | 'NO_OP' | string;
  semantic_query?: string | null;
  reference_films?: string[];
  include_genres?: string[];
  exclude_genres?: string[];
  year_min?: number | null;
  year_max?: number | null;
  requested_k?: number | null;
  requires_clarification?: boolean;
  clarification_reason_code?: string | null;
  no_op?: boolean;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: string;
  movies?: Movie[];
  followUps?: string[];
  structuredIntent?: StructuredIntent | null;
  pipelineStages?: string[];
}

export interface ChatServiceResponse {
  text: string;
  recommendedMovies: Movie[];
  followUps: string[];
  structuredIntent?: StructuredIntent | null;
  pipelineStages?: string[];
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
