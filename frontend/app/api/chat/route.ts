import { NextResponse } from 'next/server';
import { movies } from '@/lib/data/movies';
import { processChatQuery } from '@/lib/services/chatService';

/**
 * Pluggable AI / Chatbot Model Endpoint
 * 
 * Hướng dẫn cắm model của bạn:
 * 1. Nếu bạn có backend Python (FastAPI/Flask/Ollama/vLLM/LangChain):
 *    - Đặt biến môi trường `MODEL_API_URL=http://localhost:8000/api/chat` trong file `.env.local`
 * 2. Nếu bạn dùng OpenAI / Gemini / Claude API:
 *    - Đặt `OPENAI_API_KEY` hoặc gọi trực tiếp SDK trong hàm POST dưới đây.
 */
export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { message, messages } = body;
    const queryText = message || (messages && messages[messages.length - 1]?.text) || '';

    // =========================================================================
    // OPTION 1: CẮM BACKEND MODEL RIÊNG (FastAPI, Python RCM model, Ollama, v.v.)
    // =========================================================================
    const externalModelUrl = process.env.MODEL_API_URL || process.env.NEXT_PUBLIC_MODEL_API_URL;
    
    if (externalModelUrl) {
      try {
        const modelResponse = await fetch(externalModelUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: queryText,
            messages: messages || [{ role: 'user', content: queryText }],
            availableMovies: movies,
          }),
        });

        if (modelResponse.ok) {
          const data = await modelResponse.json();
          return NextResponse.json({
            text: data.text || data.reply || data.response,
            recommendedMovies: data.recommendedMovies || data.movies || [],
            followUps: data.followUps || [],
          });
        }
      } catch (err) {
        console.warn('Không thể kết nối đến external MODEL_API_URL, đang dùng local matcher fallback:', err);
      }
    }

    // =========================================================================
    // OPTION 2: LOCAL SMART RECOMMENDATION MATCHER (Dự phòng khi chưa cắm model)
    // =========================================================================
    const result = processChatQuery(queryText);

    return NextResponse.json({
      text: result.text,
      recommendedMovies: result.recommendedMovies,
      followUps: result.followUps,
    });
  } catch (error) {
    console.error('Chat API Error:', error);
    return NextResponse.json(
      { error: 'Lỗi xử lý tin nhắn', text: 'Có lỗi xảy ra khi xử lý câu hỏi. Vui lòng thử lại.' },
      { status: 500 }
    );
  }
}
