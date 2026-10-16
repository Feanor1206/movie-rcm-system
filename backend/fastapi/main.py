import os
import sys

# Khắc phục xung đột OpenMP trên môi trường Windows Anaconda
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
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
    IndexSyncRequest,
    IndexSyncResponse,
)
from services.qwen_service import (
    qwen_service,
    InferenceCapacityError,
    ModelNotReadyError,
    InferenceGenerationError,
    ModelOutputParseError,
)
from services.ai_pipeline import cascading_pipeline, DEFAULT_MOVIES
from services.catalog_sync import catalog_sync_manager

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("fastapi_app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Đang khởi động FastAPI Cascading AI Recommendation Gateway (Phase 23 & CATALOG-01)...")
    try:
        catalog_sync_manager.load_default_catalog()
    except Exception as e:
        logger.warning(f"Chưa thể tự động nạp catalog mặc định: {e}")
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


import json
import threading
from pathlib import Path

FASTAPI_SYNC_SECRET = os.environ.get("CATALOG_SYNC_TOKEN", os.environ.get("FASTAPI_SYNC_SECRET", "")).strip()
_publish_lock = threading.Lock()
_current_sync_generation: int = 0
_current_sync_hash: str = ""
_active_catalog_payload: Optional[Dict[str, Any]] = None

SYNC_STATE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "indices" / "catalog_sync_state.json"


def _save_sync_state(generation: int, content_hash: str):
    try:
        SYNC_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = SYNC_STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps({"generation": generation, "content_hash": content_hash}), encoding="utf-8")
        tmp.replace(SYNC_STATE_PATH)
    except Exception as e:
        logger.warning(f"Không thể lưu sync state: {e}")


def _load_sync_state():
    try:
        if SYNC_STATE_PATH.exists():
            data = json.loads(SYNC_STATE_PATH.read_text(encoding="utf-8"))
            return int(data.get("generation", 0)), str(data.get("content_hash", ""))
    except Exception as e:
        logger.warning(f"Không thể nạp sync state: {e}")
    return 0, ""


_current_sync_generation, _current_sync_hash = _load_sync_state()


@app.post("/api/index/sync", response_model=IndexSyncResponse)
def sync_index(
    http_request: Request,
    request: Optional[IndexSyncRequest] = None
):
    """
    Đồng bộ chỉ mục truy xuất với catalog dữ liệu thực tế (C1/F1/F2/G2).
    Yêu cầu xác thực qua token dịch vụ (header X-Service-Token hoặc Bearer Authorization).
    Chỉ chấp nhận payload catalog hoặc nạp lại từ snapshot đĩa đã cam kết.
    Thực thi fail-closed khi thiếu cấu hình secret và chống stale generation.
    """
    if not FASTAPI_SYNC_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Chức năng đồng bộ chỉ mục bị vô hiệu hóa: Chưa cấu hình CATALOG_SYNC_TOKEN hoặc FASTAPI_SYNC_SECRET ngoài Git."
        )

    auth_header = http_request.headers.get("X-Service-Token") or http_request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Unauthorized: missing X-Service-Token or Authorization header")
    token = auth_header.replace("Bearer ", "").strip()
    if token != FASTAPI_SYNC_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden: invalid service token")

    global _current_sync_generation, _current_sync_hash, _active_catalog_payload

    req_gen = getattr(request, "generation", None) if request else None
    req_catalog = getattr(request, "catalog", None) if request else None
    req_hash = getattr(request, "content_hash", None) if request else None

    publish_lock = globals().get("_publish_lock")
    if publish_lock is None:
        import threading
        publish_lock = threading.Lock()
        globals()["_publish_lock"] = publish_lock

    active_hash = globals().get("_current_sync_hash", "")
    active_payload = globals().get("_active_catalog_payload", None)

    # 1. Early stale check
    if req_gen is not None:
        if req_gen < _current_sync_generation:
            logger.warning(
                f"[IndexSync] Bỏ qua snapshot thế hệ cũ (stale generation): incoming={req_gen}, current={_current_sync_generation}"
            )
            return IndexSyncResponse(
                status="SKIPPED",
                message=f"Bỏ qua snapshot stale: generation {req_gen} < {_current_sync_generation}",
                generation=_current_sync_generation,
                item_counts=catalog_sync_manager.item_counts,
                content_hash=active_hash or catalog_sync_manager.content_hash,
                index_ready=True
            )

    try:
        # 2. Load payload or default snapshot
        if req_catalog:
            counts = catalog_sync_manager.load_from_payload(req_catalog, include_draft=False, include_private=False)
            computed_hash = catalog_sync_manager.content_hash
            msg = f"Đã đồng bộ thành công catalog từ payload ({counts['total']} mục)."
        else:
            loaded = catalog_sync_manager.load_default_catalog(include_draft=False, include_private=False)
            if not loaded:
                raise HTTPException(status_code=404, detail="Không tìm thấy tệp catalog snapshot hợp lệ trên đĩa để đồng bộ.")
            counts = catalog_sync_manager.item_counts
            computed_hash = catalog_sync_manager.content_hash
            msg = f"Đã tải lại danh mục từ snapshot thành công ({counts['total']} mục)."

        # 3. Verify content hash if declared by caller
        if req_hash and str(req_hash).strip():
            if str(req_hash).strip().lower() != computed_hash.lower():
                raise HTTPException(
                    status_code=400,
                    detail=f"Mã băm không khớp: khai báo {req_hash} != tính toán {computed_hash}"
                )

        # 4. Compare-and-Swap Publication under lock (G2)
        with publish_lock:
            active_hash = globals().get("_current_sync_hash", "")
            active_payload = globals().get("_active_catalog_payload", None)
            if req_gen is not None:
                if req_gen < _current_sync_generation:
                    logger.warning(
                        f"[IndexSync] Phát hiện thế hệ cũ sau khi load: incoming={req_gen} < current={_current_sync_generation}. Phục hồi snapshot hiện hành."
                    )
                    if active_payload is not None:
                        catalog_sync_manager.load_from_payload(active_payload, include_draft=False, include_private=False)
                    return IndexSyncResponse(
                        status="SKIPPED",
                        message=f"Bỏ qua snapshot stale: generation {req_gen} < {_current_sync_generation}",
                        generation=_current_sync_generation,
                        item_counts=catalog_sync_manager.item_counts,
                        content_hash=active_hash or catalog_sync_manager.content_hash,
                        index_ready=True
                    )
                elif req_gen == _current_sync_generation and _current_sync_generation > 0:
                    if active_hash and computed_hash.lower() != active_hash.lower():
                        raise HTTPException(
                            status_code=409,
                            detail=f"Xung đột: Generation {req_gen} đã tồn tại nhưng có nội dung khác ({computed_hash} != {active_hash})"
                        )
                    return IndexSyncResponse(
                        status="UNCHANGED",
                        message="Snapshot đã được đồng bộ với cùng generation và nội dung.",
                        generation=_current_sync_generation,
                        item_counts=counts,
                        content_hash=active_hash or computed_hash,
                        index_ready=True
                    )

            # Rebuild index atomically
            flattened = catalog_sync_manager.get_flattened_catalog()
            cascading_pipeline.retrieval_node.hybrid_index.build_from_catalog(flattened, save_to_disk=True)

            if req_gen is not None:
                _current_sync_generation = req_gen
                globals()["_current_sync_generation"] = req_gen
                globals()["_current_sync_hash"] = computed_hash
                if req_catalog:
                    globals()["_active_catalog_payload"] = req_catalog
                if "_save_sync_state" in globals():
                    globals()["_save_sync_state"](_current_sync_generation, computed_hash)

        return IndexSyncResponse(
            status="success",
            message=msg,
            generation=_current_sync_generation,
            item_counts=counts,
            content_hash=computed_hash,
            index_ready=True
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lỗi khi đồng bộ chỉ mục catalog: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi đồng bộ catalog: {str(e)}")


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Chạy qua toàn bộ Cascading AI Pipeline 5 tầng tích hợp Phase 23 Intent Parser và Catalog dữ liệu thực tế.
    """
    query = request.query
    if not query and request.messages:
        last_msg = request.messages[-1]
        query = last_msg.get("content") or last_msg.get("text") or ""

    if not query:
        raise HTTPException(status_code=400, detail="Thiếu trường 'query' hoặc 'messages'")

    available_movies = [m.model_dump() for m in request.availableMovies] if request.availableMovies else None

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
    Unified Discovery Endpoint (Phase 12, Phase 23 & CATALOG-01):
    Trả về đối tượng StructuredDiscoveryIntent v1, danh sách kết quả đã xếp hạng và lời giải thích grounded.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Thiếu trường 'query'")

    available_movies = [m.model_dump() for m in request.availableMovies] if request.availableMovies else None

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
    Endpoint gợi ý phim theo danh sách thể loại hoặc tâm trạng từ kho catalog thực tế.
    """
    query_parts = []
    if request.genres:
        query_parts.append(f"phim thể loại {', '.join(request.genres)}")
    if request.mood:
        query_parts.append(f"tâm trạng {request.mood}")
    synth_query = " ".join(query_parts) if query_parts else "gợi ý phim điểm cao nhất"

    active_cat = catalog_sync_manager.get_flattened_catalog() if catalog_sync_manager.is_loaded else DEFAULT_MOVIES
    result = cascading_pipeline.run(query=synth_query, catalog=active_cat)
    matched = result.get("recommendedMovies", [])[: request.limit]

    return RecommendResponse(
        recommendedMovies=matched or active_cat[: request.limit],
        reasoning=result.get("text") or "Gợi ý được tối ưu hóa dựa trên các thể loại yêu thích và mô hình đối sánh ngữ nghĩa."
    )



if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
