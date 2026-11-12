from fastapi import APIRouter, HTTPException, Request

from schemas import RecommendRequest, RecommendResponse


router = APIRouter()


def _affinity_score(
    item: dict,
    liked_items: list[dict] | None,
    preferred_genres: set[str],
    liked_themes: set[str] | None = None,
    liked_chars: set[str] | None = None,
    liked_series: set[str] | None = None,
) -> float:
    score = float(item.get("rating") or 0.0) * 0.1
    item_genres = {str(g).casefold() for g in item.get("genres") or []}
    if preferred_genres:
        score += 2.0 * len(item_genres & preferred_genres) / max(1, len(preferred_genres))
    if not liked_items and not liked_themes and not liked_chars and not liked_series:
        return round(score, 4)
    if liked_themes is None and liked_items:
        liked_themes = {str(t).casefold() for src in liked_items for t in (src.get("themes") or []) + (src.get("keywords") or [])}
        liked_chars = {str(c).casefold() for src in liked_items for c in src.get("characters") or []}
        liked_series = {src.get("series_id") for src in liked_items if src.get("series_id")}
    item_themes = {str(t).casefold() for t in (item.get("themes") or []) + (item.get("keywords") or [])}
    item_chars = {str(c).casefold() for c in item.get("characters") or []}
    if liked_themes and item_themes:
        score += 1.5 * len(item_themes & liked_themes) / max(1, len(liked_themes))
    if liked_chars and item_chars:
        score += 1.2 * len(item_chars & liked_chars) / max(1, len(liked_chars))
    if liked_series and item.get("series_id") in liked_series:
        score += 0.8
    return round(score, 4)


@router.post("/v1/recommend", response_model=RecommendResponse)
@router.post("/api/recommend", response_model=RecommendResponse)
def recommend(request: RecommendRequest, http_request: Request):
    runtime = http_request.app.state.runtime
    snapshot = runtime.snapshot
    if snapshot is None or not snapshot.is_ready:
        raise HTTPException(503, "Chưa có snapshot catalog được chấp nhận.")
    all_items = [item for item in snapshot.get_flattened_catalog() if item.get("item_type") in ("episode", "movie")]
    liked = set(request.likedMovieIds or [])
    liked_items = [item for item in all_items if item["id"] in liked]
    preferred = {genre.casefold() for genre in request.genres or []}
    for item in liked_items:
        preferred.update(str(genre).casefold() for genre in item.get("genres", []))
    items = all_items
    if preferred:
        items = [item for item in items if preferred.intersection(str(genre).casefold() for genre in item.get("genres", []))]
    if request.mood:
        results = runtime.search.search(snapshot, request.mood, limit=100,
                                        constraints={"include_genres": list(preferred)})
        results = [item for item in results if item["id"] not in liked][:request.limit]
        return RecommendResponse(recommendedMovies=results, reasoning="Gợi ý theo tâm trạng và nội dung trong catalog.")
    items = [item for item in items if item["id"] not in liked]
    liked_themes = {str(t).casefold() for src in liked_items for t in (src.get("themes") or []) + (src.get("keywords") or [])} if liked_items else set()
    liked_chars = {str(c).casefold() for src in liked_items for c in src.get("characters") or []} if liked_items else set()
    liked_series = {src.get("series_id") for src in liked_items if src.get("series_id")} if liked_items else set()
    scored_items = [
        (_affinity_score(item, liked_items, preferred, liked_themes, liked_chars, liked_series),
         float(item.get("rating") or 0.0),
         item)
        for item in items
    ]
    scored_items.sort(key=lambda t: (-t[0], -t[1], t[2]["id"]))
    results = []
    for affinity, _, item in scored_items[:request.limit]:
        results.append({**item, "year": item.get("year") or item.get("release_year") or 0,
                        "episodeId": item.get("episode_id") or item["id"],
                        "startMs": item.get("start_ms"), "score": affinity, "calibratedScore": None,
                        "evidence": [{"documentId": item["id"], "text": item.get("description", ""),
                                      "startMs": item.get("start_ms"), "endMs": item.get("end_ms"),
                                      "itemType": item.get("item_type", "episode")}]})
    reasoning = (
        "Gợi ý dựa trên nội dung, chủ đề và nhân vật tương đồng với phim đã thích."
        if liked_items else "Gợi ý theo thể loại trong catalog."
        if preferred else "Gợi ý phổ biến trong catalog."
    )
    return RecommendResponse(recommendedMovies=results, reasoning=reasoning)
