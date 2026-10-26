import os
import sys
import hmac

# Khắc phục xung đột OpenMP trên môi trường Windows Anaconda
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any, Tuple
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
from services.catalog_sync import (
    catalog_sync_manager,
    CatalogSyncManager,
    AcceptedSnapshot,
    get_accepted_snapshot,
    set_accepted_snapshot
)


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("fastapi_app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Đang khởi động FastAPI Cascading AI Recommendation Gateway (Phase 23 & CATALOG-01)...")
    # Single source of accepted state (F3/F08 R1, F09): Only load default catalog when no accepted state was recovered
    active_gen = globals().get("_current_sync_generation", 0)
    current_snap = get_accepted_snapshot()
    if (current_snap is None or not getattr(current_snap, "is_ready", False)) and active_gen == 0:
        try:
            default_manager = CatalogSyncManager()
            loaded = default_manager.load_default_catalog()
            if loaded:
                flattened = default_manager.get_flattened_catalog()
                active_idx = getattr(cascading_pipeline.retrieval_node, "hybrid_index", None) if hasattr(cascading_pipeline, "retrieval_node") else None
                if flattened and active_idx and hasattr(active_idx, "build_from_catalog"):
                    active_idx.build_from_catalog(flattened, save_to_disk=False)
                default_snap = AcceptedSnapshot(
                    generation=0,
                    content_hash=default_manager.content_hash,
                    catalog_manager=default_manager,
                    hybrid_index=active_idx,
                    payload=getattr(default_manager, "_raw_catalog", None),
                )
                set_accepted_snapshot(default_snap)
                globals()["_current_sync_generation"] = 0
                globals()["_current_sync_hash"] = default_manager.content_hash
                logger.info("[Startup] Đã nạp và lập chỉ mục catalog mặc định (generation=0, chưa có accepted state).")
        except Exception as e:
            logger.warning(f"Chưa thể tự động nạp catalog mặc định: {e}")
    else:
        logger.info(f"[Startup] Đã phục hồi accepted catalog (generation={active_gen}), bỏ qua load_default_catalog.")

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
_env_sync_path = os.environ.get("SYNC_STATE_PATH")
SYNC_STATE_PATH = Path(_env_sync_path) if _env_sync_path else (
    Path(__file__).resolve().parent.parent.parent / "data" / "indices" / "catalog_sync_state.json"
)


def _save_sync_state(generation: int, content_hash: str, payload: Optional[Dict[str, Any]] = None):
    SYNC_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state_data: Dict[str, Any] = {
        "generation": generation,
        "content_hash": content_hash,
    }
    if payload is not None:
        state_data["catalog"] = payload
    tmp = SYNC_STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state_data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SYNC_STATE_PATH)


def _load_sync_state() -> Tuple[int, str, Optional[Dict[str, Any]]]:
    try:
        if SYNC_STATE_PATH.exists():
            data = json.loads(SYNC_STATE_PATH.read_text(encoding="utf-8"))
            gen = int(data.get("generation", 0))
            chash = str(data.get("content_hash", ""))
            cat = data.get("catalog")
            return gen, chash, cat
    except Exception as e:
        logger.warning(f"Không thể nạp sync state: {e}")
    return 0, "", None


_current_sync_generation, _current_sync_hash, _loaded_cat = _load_sync_state()
if _loaded_cat:
    _active_catalog_payload = _loaded_cat
    try:
        recovered_manager = CatalogSyncManager()
        recovered_manager.load_from_payload(_loaded_cat, include_draft=False, include_private=False)
        flattened = recovered_manager.get_flattened_catalog()
        active_idx = getattr(cascading_pipeline.retrieval_node, "hybrid_index", None) if hasattr(cascading_pipeline, "retrieval_node") else None
        if flattened and active_idx and hasattr(active_idx, "build_from_catalog"):
            active_idx.build_from_catalog(flattened, save_to_disk=False)
        init_snap = AcceptedSnapshot(
            generation=_current_sync_generation,
            content_hash=_current_sync_hash,
            catalog_manager=recovered_manager,
            hybrid_index=active_idx,
            payload=_loaded_cat,
        )
        set_accepted_snapshot(init_snap)
        logger.info(f"[Startup] Đã phục hồi catalog snapshot nhất quán: gen={_current_sync_generation}, hash={_current_sync_hash}")
    except Exception as e:
        logger.warning(f"[Startup] Không thể nạp lại catalog snapshot từ state: {e}")



@app.post("/api/index/sync", response_model=IndexSyncResponse)
def sync_index(
    http_request: Request,
    request: Optional[IndexSyncRequest] = None
):
    """
    Đồng bộ chỉ mục truy xuất với catalog dữ liệu thực tế (C1/F1/F2/G2/H2).
    Yêu cầu xác thực qua token dịch vụ (header X-Service-Token hoặc Bearer Authorization).
    Thực hiện qua candidate manager và chỉ publish atomic khi toàn bộ validation, hash check và index build thành công.
    """
    if not FASTAPI_SYNC_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Chức năng đồng bộ chỉ mục bị vô hiệu hóa: Chưa cấu hình CATALOG_SYNC_TOKEN hoặc FASTAPI_SYNC_SECRET ngoài Git."
        )

    service_token = http_request.headers.get("X-Service-Token")
    auth_header = http_request.headers.get("Authorization")
    if service_token is None and not auth_header:
        raise HTTPException(status_code=401, detail="Unauthorized: missing X-Service-Token or Authorization header")
    if service_token is not None:
        token = service_token.strip()
    else:
        auth_parts = auth_header.split()
        token = auth_parts[1] if len(auth_parts) == 2 and auth_parts[0].casefold() == "bearer" else ""
    if not hmac.compare_digest(token.encode("utf-8"), FASTAPI_SYNC_SECRET.encode("utf-8")):
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

    # 1. Early stale check (before building candidate)
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
                content_hash=globals().get("_current_sync_hash", "") or catalog_sync_manager.content_hash,
                index_ready=True
            )

    try:
        # 2. Build candidate manager isolated from active global catalog_sync_manager (H2)
        candidate_manager = catalog_sync_manager.__class__()
        if req_catalog:
            counts = candidate_manager.load_from_payload(req_catalog, include_draft=False, include_private=False)
            computed_hash = candidate_manager.content_hash
            msg = f"Đã đồng bộ thành công catalog từ payload ({counts['total']} mục)."
        else:
            loaded = candidate_manager.load_default_catalog(include_draft=False, include_private=False)
            if not loaded:
                raise HTTPException(status_code=404, detail="Không tìm thấy tệp catalog snapshot hợp lệ trên đĩa để đồng bộ.")
            counts = candidate_manager.item_counts
            computed_hash = candidate_manager.content_hash
            msg = f"Đã tải lại danh mục từ snapshot thành công ({counts['total']} mục)."

        # 3. Verify content hash BEFORE acquiring publish lock and BEFORE modifying active state (H1, H2)
        if req_hash and str(req_hash).strip():
            if str(req_hash).strip().lower() != computed_hash.lower():
                raise HTTPException(
                    status_code=400,
                    detail=f"Mã băm không khớp: khai báo {req_hash} != tính toán {computed_hash}"
                )

        # 4. Compare-and-Swap Publication under lock (H2)
        with publish_lock:
            active_hash = globals().get("_current_sync_hash", "")
            active_gen = globals().get("_current_sync_generation", _current_sync_generation)
            if req_gen is not None:
                if req_gen < active_gen:
                    logger.warning(
                        f"[IndexSync] Phát hiện thế hệ cũ sau khi chuẩn bị candidate: incoming={req_gen} < current={active_gen}."
                    )
                    return IndexSyncResponse(
                        status="SKIPPED",
                        message=f"Bỏ qua snapshot stale: generation {req_gen} < {active_gen}",
                        generation=active_gen,
                        item_counts=catalog_sync_manager.item_counts,
                        content_hash=active_hash or catalog_sync_manager.content_hash,
                        index_ready=True
                    )
                elif req_gen == active_gen and active_gen > 0:
                    if active_hash and computed_hash.lower() != active_hash.lower():
                        raise HTTPException(
                            status_code=409,
                            detail=f"Xung đột: Generation {req_gen} đã tồn tại nhưng có nội dung khác ({computed_hash} != {active_hash})"
                        )
                    return IndexSyncResponse(
                        status="UNCHANGED",
                        message="Snapshot đã được đồng bộ với cùng generation và nội dung.",
                        generation=active_gen,
                        item_counts=counts,
                        content_hash=active_hash or computed_hash,
                        index_ready=True
                    )

            # 5. Build candidate index FIRST on an isolated instance before touching disk or active state (S1, F1)
            flattened = candidate_manager.get_flattened_catalog()
            active_index = cascading_pipeline.retrieval_node.hybrid_index

            candidate_index = None
            if hasattr(active_index, "build_from_catalog"):
                try:
                    candidate_index = active_index.__class__()
                    for k, v in active_index.__dict__.items():
                        if k not in ("documents", "embeddings", "bm25", "metadata_index", "is_ready", "titles"):
                            setattr(candidate_index, k, v)
                except Exception:
                    from services.hybrid_retrieval import HybridMovieIndex
                    candidate_index = HybridMovieIndex()
                if hasattr(active_index, "encoder"):
                    candidate_index.encoder = active_index.encoder
                if hasattr(active_index, "index_path"):
                    candidate_index.index_path = active_index.index_path
                candidate_index.build_from_catalog(flattened, save_to_disk=False)

            # 6. Only after candidate index build succeeds, save durable state to disk (S1, F1)
            if req_gen is not None:
                if "_save_sync_state" in globals():
                    globals()["_save_sync_state"](req_gen, computed_hash, req_catalog)

            # 7. Atomic publication via AcceptedSnapshot single reference swap (CATALOG-01-F08 R1)
            target_index = candidate_index if candidate_index is not None else active_index
            snap_cls = globals().get("AcceptedSnapshot")
            if snap_cls is None:
                from services.catalog_sync import AcceptedSnapshot as snap_cls
            set_snap_fn = globals().get("set_accepted_snapshot")
            if set_snap_fn is None:
                from services.catalog_sync import set_accepted_snapshot as set_snap_fn

            new_snapshot = snap_cls(
                generation=req_gen if req_gen is not None else active_gen,
                content_hash=computed_hash,
                catalog_manager=candidate_manager,
                hybrid_index=target_index,
                payload=req_catalog,
            )

            # Atomic reference swap under publish_lock:
            # - In-flight readers continue querying their captured snapshot without disruption or mixed state.
            # - New readers immediately acquire new_snapshot.
            set_snap_fn(new_snapshot)


            # Synchronize active pipeline reference in lockstep (single pointer swap)
            cascading_pipeline.retrieval_node.hybrid_index = target_index


            if req_gen is not None:
                _current_sync_generation = req_gen
                globals()["_current_sync_generation"] = req_gen
                globals()["_current_sync_hash"] = computed_hash
                if req_catalog:
                    globals()["_active_catalog_payload"] = req_catalog


        return IndexSyncResponse(
            status="success",
            message=msg,
            generation=globals().get("_current_sync_generation", _current_sync_generation),
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
    snap = get_accepted_snapshot()

    result = cascading_pipeline.run(
        query=query,
        catalog=available_movies,
        history=request.messages,
        session_id=request.sessionId or "default",
        snapshot=snap
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
    snap = get_accepted_snapshot()

    result = cascading_pipeline.run(
        query=request.query,
        catalog=available_movies,
        session_id=request.sessionId or "default",
        snapshot=snap
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

    snap = get_accepted_snapshot()
    active_cat = snap.get_flattened_catalog() if (snap and getattr(snap, "is_ready", False)) else (
        catalog_sync_manager.get_flattened_catalog() if catalog_sync_manager.is_loaded else DEFAULT_MOVIES
    )
    result = cascading_pipeline.run(query=synth_query, catalog=active_cat, snapshot=snap)
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
