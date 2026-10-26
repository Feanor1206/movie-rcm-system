import { NextResponse } from 'next/server';

/**
 * AI Chatbot Endpoint
 * Chuyển tiếp 100% câu hỏi sang FastAPI Backend để sinh câu trả lời bằng model Qwen thực tế.
 * Không dùng bất kỳ thuật toán giả lập fallback nào.
 */
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
  const messages = Array.isArray(body.messages) ? body.messages : [];
  const lastMessage = messages[messages.length - 1];
  const queryText = body.message ?? lastMessage?.content ?? lastMessage?.text;
  if (typeof queryText !== 'string' || !queryText.trim()) {
    return NextResponse.json({ text: 'Bạn nhập một câu hỏi nhé.' }, { status: 400 });
  }
  try {
    const modelApiUrl = process.env.MODEL_API_URL || process.env.NEXT_PUBLIC_MODEL_API_URL || 'http://localhost:8000/api/chat';

    const response = await fetch(modelApiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(180_000),
      body: JSON.stringify({
        query: queryText,
        messages: messages.length ? messages : [{ role: 'user', content: queryText }],
        availableMovies: body.availableMovies,
      }),
    });

    if (!response.ok) {
      const status = [400, 429, 502, 503, 504].includes(response.status) ? response.status : 502;
      return NextResponse.json({
        text: status === 429 ? 'CineBot đang bận. Bạn thử lại sau một chút nhé.' : 'CineBot hiện chưa sẵn sàng. Bạn vẫn có thể tìm phim trong Kho phim nhé.',
        recommendedMovies: [], followUps: [], structuredIntent: null, pipelineStages: {},
      }, { status });
    }

    const data = await response.json();
    return NextResponse.json({
      text: data.text || data.reply || data.response,
      recommendedMovies: data.recommendedMovies || [],
      followUps: data.followUps || [],
      structuredIntent: data.structuredIntent || null,
      pipelineStages: data.pipelineStages || [],
    });
  } catch {
    return NextResponse.json(
      {
        text: 'CineBot hiện chưa sẵn sàng. Bạn vẫn có thể tìm phim trong Kho phim nhé.',
        recommendedMovies: [],
        followUps: [],
        structuredIntent: null,
        pipelineStages: [],
      },
      { status: 503 }
    );
  }
}
