import { NextResponse } from 'next/server';
import { movies } from '@/lib/data/movies';

/**
 * AI Chatbot Endpoint
 * Chuyển tiếp 100% câu hỏi sang FastAPI Backend để sinh câu trả lời bằng model Qwen thực tế.
 * Không dùng bất kỳ thuật toán giả lập fallback nào.
 */
export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { message, messages } = body;
    const queryText = message || (messages && messages[messages.length - 1]?.text) || '';

    const modelApiUrl = process.env.MODEL_API_URL || process.env.NEXT_PUBLIC_MODEL_API_URL || 'http://localhost:8000/api/chat';

    const response = await fetch(modelApiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: queryText,
        messages: messages || [{ role: 'user', content: queryText }],
        availableMovies: movies,
      }),
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`FastAPI trả về lỗi ${response.status}: ${errText}`);
    }

    const data = await response.json();
    return NextResponse.json({
      text: data.text || data.reply || data.response,
      recommendedMovies: data.recommendedMovies || [],
      followUps: data.followUps || [],
    });
  } catch (error: any) {
    console.error('Chatbot API Error (Qwen LLM):', error);
    return NextResponse.json(
      {
        text: `⚠️ [Lỗi kết nối AI Gateway]: Không thể nhận phản hồi từ model Qwen (:8000). Chi tiết: ${error?.message || error}`,
        recommendedMovies: [],
        followUps: []
      },
      { status: 500 }
    );
  }
}
