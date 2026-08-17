import os
import sys

# Khắc phục xung đột OpenMP trên môi trường Windows Anaconda
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from schemas import ChatRequest, ChatResponse, RecommendRequest, RecommendResponse, HealthResponse
from services.qwen_service import qwen_service
from services.ai_pipeline import cascading_pipeline, DEFAULT_MOVIES

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("fastapi_app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Đang khởi động FastAPI Cascading AI Recommendation Gateway...")
    try:
        qwen_service.load_model()
    except Exception as e:
        logger.warning(f"Chưa thể nạp model, kích hoạt chế độ fallback: {e}")
    yield
    logger.info("Đang tắt FastAPI AI Gateway...")


app = FastAPI(
    title="Dippie Cascading AI Movie Recommendation Gateway",
    description="Multi-stage Pipeline: Qwen 4B NLU -> Retrieval -> 0.6B Recommender -> 0.6B Ranker -> 4B Explanation",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "service": "Dippie Cascading AI Movie Recommendation Gateway",
        "pipeline": [
            "1. Qwen 4B NLU (Intent & Entity Understanding)",
            "2. Semantic Retrieval & Candidate Generation",
            "3. Qwen 0.6B Recommender (Domain Candidate Filtering)",
            "4. Qwen 0.6B Ranker (Fine-grained Scoring & Re-ranking)",
            "5. Qwen 4B Explanation (Storytelling & Persona in Vietnamese)"
        ],
        "status": "online",
        "modelLoaded": qwen_service.is_loaded,
        "device": qwen_service.actual_device,
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(
        status="healthy",
        modelLoaded=qwen_service.is_loaded,
        modelNameOrPath=qwen_service.model_name_or_path,
        device=qwen_service.actual_device
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Chạy trực tiếp qua model Qwen 0.6B và Cascading AI Pipeline để trả lời hội thoại và gợi ý phim.
    """
    query = request.query
    if not query and request.messages:
        last_msg = request.messages[-1]
        query = last_msg.get("content") or last_msg.get("text") or ""

    if not query:
        raise HTTPException(status_code=400, detail="Thiếu trường 'query' hoặc 'messages'")

    available_movies = [m.model_dump() for m in request.availableMovies] if request.availableMovies else DEFAULT_MOVIES

    # Sử dụng Qwen Service (Chạy trực tiếp qua llama-cpp / transformers)
    result = qwen_service.generate_chat_response(
        query=query,
        messages_history=request.messages,
        available_movies=available_movies
    )

    return ChatResponse(
        text=result["text"],
        recommendedMovies=result.get("recommendedMovies", []),
        followUps=result.get("followUps", [])
    )


@app.post("/api/recommend", response_model=RecommendResponse)
def recommend_endpoint(request: RecommendRequest):
    """
    Endpoint gợi ý phim theo danh sách thể loại hoặc phim đã thích.
    """
    matched = DEFAULT_MOVIES
    if request.genres:
        matched = [m for m in DEFAULT_MOVIES if any(g in m["genres"] for g in request.genres)]
    
    if not matched:
        matched = DEFAULT_MOVIES[:request.limit]
    else:
        matched = matched[:request.limit]

    return RecommendResponse(
        recommendedMovies=matched,
        reasoning="Gợi ý được tối ưu hóa dựa trên các thể loại yêu thích và mô hình đối sánh ngữ nghĩa."
    )


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
