from fastapi import APIRouter, HTTPException, Request

from schemas import DiscoverRequest, DiscoverResponse


router = APIRouter()


@router.post("/v1/search", response_model=DiscoverResponse)
@router.post("/v1/discover", response_model=DiscoverResponse)
def search(request: DiscoverRequest, http_request: Request):
    if not request.query.strip():
        raise HTTPException(400, "Thiếu trường query.")
    snapshot = http_request.app.state.runtime.snapshot
    if snapshot is None or not snapshot.is_ready:
        raise HTTPException(503, "Chưa có snapshot catalog được chấp nhận.")
    constraints = request.constraints.model_dump(exclude_none=True) if request.constraints else None
    results = http_request.app.state.runtime.search.search(snapshot, request.query, limit=request.limit, constraints=constraints)
    return DiscoverResponse(structuredIntent={"intent_type": "DISCOVERY", "semantic_query": request.query},
        results=results, explanation="Đã tìm trong catalog hiện tại." if results else "Không tìm thấy nội dung phù hợp.",
        pipelineStages={"snapshotGeneration": snapshot.generation, "denseReady": snapshot.hybrid_index.dense_ready,
                        "missingEmbeddings": snapshot.hybrid_index.missing_embeddings})
