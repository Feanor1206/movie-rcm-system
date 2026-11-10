from fastapi import APIRouter, HTTPException, Request

from schemas import RecommendRequest, RecommendResponse


router = APIRouter()


@router.post("/v1/recommend", response_model=RecommendResponse)
@router.post("/api/recommend", response_model=RecommendResponse)
def recommend(request: RecommendRequest, http_request: Request):
    runtime = http_request.app.state.runtime
    snapshot = runtime.snapshot
    if snapshot is None or not snapshot.is_ready:
        raise HTTPException(503, "Chưa có snapshot catalog được chấp nhận.")
    items = [item for item in snapshot.get_flattened_catalog() if item.get("item_type") in ("episode", "movie")]
    liked = set(request.likedMovieIds or [])
    preferred = {genre.casefold() for genre in request.genres or []}
    for item in items:
        if item["id"] in liked:
            preferred.update(str(genre).casefold() for genre in item.get("genres", []))
    if preferred:
        items = [item for item in items if preferred.intersection(str(genre).casefold() for genre in item.get("genres", []))]
    if request.mood:
        results = runtime.search.search(snapshot, request.mood, limit=100,
                                        constraints={"include_genres": list(preferred)})
        results = [item for item in results if item["id"] not in liked][:request.limit]
        return RecommendResponse(recommendedMovies=results, reasoning="Gợi ý theo nội dung trong catalog.")
    items = [item for item in items if item["id"] not in liked]
    items.sort(key=lambda item: (-float(item.get("rating") or 0), item["id"]))
    results = []
    for item in items[:request.limit]:
        results.append({**item, "episodeId": item.get("episode_id") or item["id"],
                        "startMs": item.get("start_ms"), "score": 0.0, "calibratedScore": None,
                        "evidence": [{"documentId": item["id"], "text": item.get("description", ""),
                                      "startMs": item.get("start_ms"), "endMs": item.get("end_ms"),
                                      "itemType": item.get("item_type", "episode")}]})
    return RecommendResponse(recommendedMovies=results,
                             reasoning="Gợi ý theo thể loại trong catalog." if preferred else "Gợi ý phổ biến trong catalog.")
