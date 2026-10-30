import { NextResponse } from 'next/server';

const MAX_MESSAGE_LENGTH = 4000;
const MAX_HISTORY = 40;

type HistoryMessage = { role: 'user' | 'assistant'; content: string };

function unavailable(status: number) {
  return NextResponse.json({
    text: status === 429
      ? 'CineBot đang bận. Bạn thử lại sau một chút nhé.'
      : 'CineBot hiện chưa sẵn sàng. Bạn vẫn có thể tìm phim trong Kho phim nhé.',
    recommendedMovies: [], followUps: [], structuredIntent: null, pipelineStages: {},
  }, { status });
}

export async function POST(req: Request) {
  let body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ text: 'Câu hỏi gửi lên không hợp lệ.' }, { status: 400 });
  }
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return NextResponse.json({ text: 'Câu hỏi gửi lên không hợp lệ.' }, { status: 400 });
  }
  const invalid = () => NextResponse.json({ text: 'Câu hỏi hoặc lịch sử trò chuyện không hợp lệ.' }, { status: 400 });
  if (body.messages !== undefined && !Array.isArray(body.messages)) return invalid();
  const rawHistory = body.messages || [];
  if (rawHistory.length > MAX_HISTORY) return invalid();
  const messages: HistoryMessage[] = [];
  for (const item of rawHistory) {
    if (!item || typeof item !== 'object' || !['user', 'assistant'].includes(item.role)) return invalid();
    const content = item.content ?? item.text;
    if (typeof content !== 'string' || !content.trim() || content.length > MAX_MESSAGE_LENGTH) return invalid();
    messages.push({ role: item.role, content: content.trim() });
  }
  const queryText = body.message ?? messages[messages.length - 1]?.content;
  if (typeof queryText !== 'string' || !queryText.trim() || queryText.length > MAX_MESSAGE_LENGTH) return invalid();
  if (body.sessionId !== undefined && (typeof body.sessionId !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(body.sessionId))) return invalid();

  const timeout = AbortSignal.timeout(180_000);
  const signal = req.signal ? AbortSignal.any([req.signal, timeout]) : timeout;
  try {
    signal.throwIfAborted();
    const modelApiUrl = process.env.MODEL_API_URL || process.env.NEXT_PUBLIC_MODEL_API_URL || 'http://localhost:8000/api/chat';
    const response = await fetch(modelApiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal,
      body: JSON.stringify({
        query: queryText.trim(),
        messages: messages.length ? messages : [{ role: 'user', content: queryText.trim() }],
        sessionId: body.sessionId,
      }),
    });
    if (!response.ok) {
      return unavailable([400, 429, 502, 503, 504].includes(response.status) ? response.status : 502);
    }
    let data;
    try {
      data = await response.json();
    } catch {
      signal.throwIfAborted();
      return unavailable(502);
    }
    const text = data?.text || data?.reply || data?.response;
    if (!data || Array.isArray(data) || typeof text !== 'string' || !text.trim()
      || (data.recommendedMovies !== undefined && !Array.isArray(data.recommendedMovies))
      || (data.followUps !== undefined && (!Array.isArray(data.followUps) || !data.followUps.every((item: unknown) => typeof item === 'string')))) {
      return unavailable(502);
    }
    return NextResponse.json({
      text,
      recommendedMovies: data.recommendedMovies || [],
      followUps: data.followUps || [],
      structuredIntent: data.structuredIntent || null,
      pipelineStages: data.pipelineStages && typeof data.pipelineStages === 'object' && !Array.isArray(data.pipelineStages) ? data.pipelineStages : {},
    });
  } catch {
    return unavailable(req.signal?.aborted ? 499 : timeout.aborted ? 504 : 503);
  }
}
