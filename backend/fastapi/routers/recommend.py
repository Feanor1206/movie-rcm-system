from fastapi import APIRouter, Header, HTTPException, Request

from routers.core_api import get_optional_user
from schemas import RecommendRequest, RecommendResponse
from services.recommendations import profile_signals, recommend_items


router = APIRouter()


@router.post('/v1/recommend', response_model=RecommendResponse)
@router.post('/api/recommend', response_model=RecommendResponse)
def recommend(request: RecommendRequest, http_request: Request, authorization: str | None = Header(default=None)):
    runtime = http_request.app.state.runtime
    snapshot = runtime.snapshot
    if snapshot is None or not snapshot.is_ready:
        raise HTTPException(503, 'Chưa có snapshot catalog được chấp nhận.')
    with runtime.db.session() as db:
        user = get_optional_user(http_request, db, authorization)
        liked, seen = profile_signals(db, user.id if user else None, snapshot, request.likedMovieIds or [])
    return recommend_items(snapshot, runtime.search, request, liked, seen)
