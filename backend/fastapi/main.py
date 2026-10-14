import os
import sys

# Khắc phục xung đột OpenMP trên môi trường Windows Anaconda
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from schemas import (
    ChatRequest,
    ChatResponse,
    DiscoverRequest,
    DiscoverResponse,
    RecommendRequest,
    RecommendResponse,
    HealthResponse,
    ReadinessResponse,
)
from services.qwen_service import (
    qwen_service,
    InferenceCapacityError,
    ModelNotReadyError,
    InferenceGenerationError,
    ModelOutputParseError,
)
from services.ai_pipeline import cascading_pipeline, DEFAULT_MOVIES

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("fastapi_app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Đang khởi động FastAPI Cascading AI Recommendation Gateway (Phase 23)...")
    try:
        qwen_service.load_model()
    except Exception as e:
        logger.warning(f"Chưa thể nạp model, kích hoạt chế độ chuẩn hóa Phase 23: {e}")
    yield
    logger.info("Đang tắt FastAPI AI Gateway...")


app = FastAPI(
    title="Dippie Cascading AI Movie Recommendation Gateway",
    description="Multi-stage Pipeline: Phase 23 Qwen Intent Parser -> Hard Constraints & Retrieval -> 0.6B Recommender -> 0.6B Ranker & MMR -> Grounded Explanation",
    version="2.3.0",
    lifespan=lifespan
)


@app.exception_handler(InferenceCapacityError)
async def inference_capacity_handler(request: Request, exc: InferenceCapacityError):
    return JSONResponse(
        status_code=429,
        content={"detail": str(exc)}
    )


@app.exception_handler(ModelNotReadyError)
async def model_not_ready_handler(request: Request, exc: ModelNotReadyError):
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)}
    )


@app.exception_handler(InferenceGenerationError)
async def inference_generation_handler(request: Request, exc: InferenceGenerationError):
    return JSONResponse(
        status_code=502,
        content={"detail": str(exc)}
    )


@app.exception_handler(ModelOutputParseError)
async def model_output_parse_handler(request: Request, exc: ModelOutputParseError):
    return JSONResponse(
        status_code=502,
        content={"detail": str(exc)}
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
    health = qwen_service.get_health_status()
    return {
        "service": "Dippie Cascading AI Movie Recommendation Gateway",
        "version": "2.3.0",
        "pipeline": [
            "1. Phase 23 Qwen Intent Parser (StructuredDiscoveryIntent v1 + Conversational Patch Merger)",
            "2. Hard Constraint Engine & Hybrid TF-IDF / Reference Retrieval",
            "3. Qwen 0.6B Recommender (Domain Candidate Filtering)",
            "4. Qwen 0.6B Ranker + MMR Diversity Reranker",
            "5. Qwen Grounded Explanation (Vietnamese Storytelling)"
        ],
        "status": "online",
        "docs": "/docs",
        **health
    }


@app.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(**qwen_service.get_health_status())


@app.get("/ready", response_model=ReadinessResponse)
@app.get("/api/readiness", response_model=ReadinessResponse)
def readiness_check():
    is_ready, http_code, resp_dict = qwen_service.get_readiness_status()
    if not is_ready:
        raise HTTPException(status_code=http_code, detail=resp_dict)
    return ReadinessResponse(**resp_dict)


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Chạy qua toàn bộ Cascading AI Pipeline 5 tầng tích hợp Phase 23 Intent Parser.
    """
    query = request.query
    if not query and request.messages:
        last_msg = request.messages[-1]
        query = last_msg.get("content") or last_msg.get("text") or ""

    if not query:
        raise HTTPException(status_code=400, detail="Thiếu trường 'query' hoặc 'messages'")

    available_movies = [m.model_dump() for m in request.availableMovies] if request.availableMovies else DEFAULT_MOVIES

    result = cascading_pipeline.run(
        query=query,
        catalog=available_movies,
        history=request.messages,
        session_id=request.sessionId or "default"
    )

    return ChatResponse(
        text=result["text"],
        recommendedMovies=result.get("recommendedMovies", []),
        followUps=result.get("followUps", []),
        structuredIntent=result.get("structuredIntent"),
        pipelineStages=result.get("pipelineStages")
    )


@app.post("/v1/discover", response_model=DiscoverResponse)
def discover_endpoint(request: DiscoverRequest):
    """
    Unified Discovery Endpoint (Phase 12 & Phase 23):
    Trả về đối tượng StructuredDiscoveryIntent v1, danh sách kết quả đã xếp hạng và lời giải thích.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Thiếu trường 'query'")

    available_movies = [m.model_dump() for m in request.availableMovies] if request.availableMovies else DEFAULT_MOVIES

    result = cascading_pipeline.run(
        query=request.query,
        catalog=available_movies,
        session_id=request.sessionId or "default"
    )

    return DiscoverResponse(
        structuredIntent=result["structuredIntent"],
        explanation=result["text"],
        results=result.get("recommendedMovies", []),
        followUps=result.get("followUps", []),
        pipelineStages=result.get("pipelineStages", {})
    )


@app.post("/api/recommend", response_model=RecommendResponse)
def recommend_endpoint(request: RecommendRequest):
    """
    Endpoint gợi ý phim theo danh sách thể loại hoặc tâm trạng.
    """
    query_parts = []
    if request.genres:
        query_parts.append(f"phim thể loại {', '.join(request.genres)}")
    if request.mood:
        query_parts.append(f"tâm trạng {request.mood}")
    synth_query = " ".join(query_parts) if query_parts else "gợi ý phim điểm cao nhất"

    result = cascading_pipeline.run(query=synth_query, catalog=DEFAULT_MOVIES)
    matched = result.get("recommendedMovies", [])[: request.limit]

    return RecommendResponse(
        recommendedMovies=matched or DEFAULT_MOVIES[: request.limit],
        reasoning=result.get("text") or "Gợi ý được tối ưu hóa dựa trên các thể loại yêu thích và mô hình đối sánh ngữ nghĩa."
    )


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
