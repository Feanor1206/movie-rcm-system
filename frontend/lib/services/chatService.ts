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
  pipelineStages?: Record<string, unknown>;
}

export interface ChatServiceResponse {
  text: string;
  recommendedMovies: Movie[];
  followUps: string[];
  structuredIntent?: StructuredIntent | null;
  pipelineStages?: Record<string, unknown>;
}

function parseResponse(value: unknown, requireText: boolean): ChatServiceResponse {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Phản hồi CineBot không hợp lệ.');
  const data = value as Record<string, unknown>;
  if ((requireText && (typeof data.text !== 'string' || !data.text.trim()))
    || (data.text !== undefined && typeof data.text !== 'string')
    || (data.recommendedMovies !== undefined && !Array.isArray(data.recommendedMovies))
    || (data.followUps !== undefined && (!Array.isArray(data.followUps) || !data.followUps.every((item) => typeof item === 'string')))
    || (data.structuredIntent !== undefined && data.structuredIntent !== null && (typeof data.structuredIntent !== 'object' || Array.isArray(data.structuredIntent)))
    || (data.pipelineStages !== undefined && data.pipelineStages !== null && (typeof data.pipelineStages !== 'object' || Array.isArray(data.pipelineStages)))) {
    throw new Error('Phản hồi CineBot không hợp lệ.');
  }
  return {
    text: typeof data.text === 'string' ? data.text : '',
    recommendedMovies: (data.recommendedMovies as Movie[] | undefined) || [],
    followUps: (data.followUps as string[] | undefined) || [],
    structuredIntent: (data.structuredIntent as StructuredIntent | undefined) || null,
    pipelineStages: (data.pipelineStages as Record<string, unknown> | undefined) || {},
  };
}

export async function sendChatMessage(
  message: string,
  history: ChatMessage[] = [],
  options: { sessionId?: string; signal?: AbortSignal; onUpdate?: (response: ChatServiceResponse) => void } = {}
): Promise<ChatServiceResponse> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    signal: options.signal,
    body: JSON.stringify({
      message,
      sessionId: options.sessionId,
      messages: history.slice(-20).map((m) => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text,
      })),
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.text || 'Không thể kết nối CineBot. Vui lòng thử lại.');
  }

  if (!response.headers?.get('Content-Type')?.toLowerCase().includes('text/event-stream')) {
    const result = parseResponse(await response.json(), true);
    options.onUpdate?.(result);
    return result;
  }
  if (!response.body) throw new Error('CineBot không có luồng phản hồi.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result: ChatServiceResponse = { text: '', recommendedMovies: [], followUps: [] };
  let completed = false;
  const onAbort = () => { void reader.cancel(options.signal?.reason).catch(() => {}); };
  options.signal?.addEventListener('abort', onAbort, { once: true });
  try {
    while (!completed) {
      options.signal?.throwIfAborted();
      const { value, done } = await reader.read();
      options.signal?.throwIfAborted();
      buffer += decoder.decode(value, { stream: !done });
      let boundary;
      while ((boundary = /\r?\n\r?\n/.exec(buffer)) !== null) {
        const event = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary[0].length);
        if (event.length > 256_000) throw new Error('Phản hồi CineBot vượt giới hạn.');
        let type = 'message';
        const lines: string[] = [];
        for (const line of event.split(/\r?\n/)) {
          if (line.startsWith('event:')) type = line.slice(6).trim();
          else if (line.startsWith('data:')) lines.push(line.slice(5).replace(/^ /, ''));
        }
        if (!lines.length) continue;
        let data;
        try { data = JSON.parse(lines.join('\n')); } catch { throw new Error('Phản hồi CineBot không hợp lệ.'); }
        if (type === 'metadata') {
          result = { ...parseResponse(data, false), text: result.text };
        } else if (type === 'token') {
          if (!data || typeof data.text !== 'string') throw new Error('Phản hồi CineBot không hợp lệ.');
          result = { ...result, text: result.text + data.text };
          if (result.text.length > 128_000) throw new Error('Phản hồi CineBot vượt giới hạn.');
        } else if (type === 'done') {
          result = parseResponse(data, true);
          completed = true;
        } else if (type === 'error') {
          throw new Error(typeof data?.text === 'string' ? data.text : 'CineBot không thể hoàn tất phản hồi.');
        } else continue;
        options.onUpdate?.(result);
        if (completed) break;
      }
      if (buffer.length > 256_000) throw new Error('Phản hồi CineBot vượt giới hạn.');
      if (done && !completed) throw new Error('Luồng phản hồi CineBot bị gián đoạn. Vui lòng thử lại.');
    }
    return result;
  } finally {
    options.signal?.removeEventListener('abort', onAbort);
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
