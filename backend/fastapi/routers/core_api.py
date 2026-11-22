from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import logging
import math
import os
from pathlib import Path
import re
import secrets
from stat import FILE_ATTRIBUTE_REPARSE_POINT, S_ISDIR, S_ISLNK, S_ISREG

from types import SimpleNamespace

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import LargeBinary, case, cast, func, or_, select
from sqlalchemy.exc import DataError, IntegrityError, OperationalError, StatementError
from sqlalchemy.orm.exc import StaleDataError
from starlette.concurrency import run_in_threadpool

from services.database import (
    CatalogConflictError,
    CatalogEpisode,
    CatalogEpisodeAsset,
    CatalogInputError,
    CatalogMediaAsset,
    CatalogPackage,
    CatalogScene,
    CatalogSeason,
    CatalogSegment,
    CatalogSeries,
    CatalogSnapshot,
    FavoriteItem,
    MediaAsset,
    Movie,
    MovieRating,
    User,
    WatchProgress,
    WatchlistItem,
    catalog_diff,
    compute_sha256,
    create_jwt_token,
    create_playback_grant_token,
    decode_jwt_token,
    export_eligible_catalog,
    hash_password,
    import_catalog_package,
    is_published,
    is_relative_media_path,
    validate_catalog_input,
    validate_playback_grant_token,
    verify_password,
)
from services.runtime import ROOT

router = APIRouter()


def api_response(data=None, message: str = "Thành công", success: bool = True, status_code: int = 200):
    body = {
        "success": success,
        "message": message,
        "data": data,
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }
    return JSONResponse(body, status_code=status_code)


def get_db(request: Request):
    return request.app.state.runtime.db.session()


def get_optional_user(request: Request, db, authorization: str | None = Header(default=None)) -> User | None:
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    if not token:
        return None
    username = decode_jwt_token(token)
    if not username:
        return None
    return db.query(User).filter(User.username == username).first()


def require_user(request: Request, db, authorization: str | None) -> User | None:
    return get_optional_user(request, db, authorization)


class LoginPayload(BaseModel):
    usernameOrEmail: str = Field(default="", max_length=100)
    username: str = Field(default="", max_length=100)
    password: str = Field(default="", max_length=72)


class RegisterPayload(BaseModel):
    username: str = Field(default="", max_length=50)
    email: str = Field(default="", max_length=100)
    password: str = Field(default="", max_length=72)
    fullName: str | None = Field(default=None, max_length=100)


class MovieIdPayload(BaseModel):
    movieId: str = ""


class RatingPayload(BaseModel):
    movieId: str = ""
    rating: int | None = None


@router.get("/api/health")
def api_health(request: Request):
    if not request.app.state.runtime.db.healthy():
        return api_response({"status": "DOWN"}, "Không thể kết nối cơ sở dữ liệu.", False, 503)
    return api_response(
        data={"status": "UP", "service": "Dippie MovieRCM Backend", "version": "1.0.0"},
        message="Dịch vụ đang hoạt động.",
    )


@router.post("/api/auth/login")
def login(payload: LoginPayload, request: Request):
    limited = _auth_limit(request, payload.usernameOrEmail or payload.username)
    if limited is not None:
        return limited
    ident = (payload.usernameOrEmail or payload.username or "").strip()
    password = payload.password or ""
    if not ident or not password:
        return api_response(None, "Tên đăng nhập và mật khẩu không được để trống", False, 400)
    if len(password.encode("utf-8")) > 72:
        return api_response(None, "Sai tên đăng nhập hoặc mật khẩu", False, 401)
    with get_db(request) as db:
        user = db.query(User).filter((User.username == ident) | (User.email == ident)).first()
        if not user or not verify_password(password, user.password):
            return api_response(None, "Sai tên đăng nhập hoặc mật khẩu", False, 401)
        token = create_jwt_token(user.username)
        return api_response(
            data={
                "token": token,
                "type": "Bearer",
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "fullName": user.full_name,
                "role": user.role,
            },
            message="Đăng nhập thành công",
        )


@router.post("/api/auth/register")
def register(payload: RegisterPayload, request: Request):
    limited = _auth_limit(request, payload.username)
    if limited is not None:
        return limited
    username = (payload.username or "").strip()
    email = (payload.email or "").strip()
    password = payload.password or ""
    if len(username) < 3 or len(username) > 50:
        return api_response(None, "Tên đăng nhập phải từ 3 đến 50 ký tự", False, 400)
    if "@" not in email:
        return api_response(None, "Định dạng email không hợp lệ", False, 400)
    if len(password) < 6:
        return api_response(None, "Mật khẩu phải có ít nhất 6 ký tự", False, 400)
    if len(password.encode("utf-8")) > 72:
        return api_response(None, "Mật khẩu được dùng tối đa 72 byte UTF-8.", False, 400)
    with get_db(request) as db:
        if db.query(User).filter(User.username == username).first():
            return api_response(None, "Tên đăng nhập đã tồn tại!", False, 400)
        if db.query(User).filter(User.email == email).first():
            return api_response(None, "Email đã được sử dụng!", False, 400)
        user = User(
            username=username,
            email=email,
            full_name=(payload.fullName or "").strip() or username,
            password=hash_password(password),
            role="ROLE_USER",
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return api_response(None, "Tên đăng nhập hoặc email đã được sử dụng.", False, 400)
        db.refresh(user)
        token = create_jwt_token(user.username)
        return api_response(
            data={
                "token": token,
                "type": "Bearer",
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "fullName": user.full_name,
                "role": user.role,
            },
            message="Đăng ký tài khoản thành công",
            status_code=201,
        )


def _auth_limit(request, identifier):
    client = request.client.host if request.client else "unknown"
    retry = request.app.state.auth_limiter.retry_after((client, identifier.strip().casefold()))
    if retry:
        response = api_response(None, "Bạn đã thử đăng nhập quá nhiều lần. Vui lòng chờ một phút.", False, 429)
        response.headers["Retry-After"] = str(retry)
        return response
    return None


@router.get("/api/auth/me")
def get_me(request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        return api_response(
            data={
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "fullName": user.full_name,
                "role": user.role,
            }
        )


def _matches_genre_token(genres_str: str | None, raw_token: str | None) -> bool:
    if not raw_token or not raw_token.strip():
        return True
    if not genres_str:
        return False
    token = raw_token.strip().lower()
    tokens = [t.strip().lower() for t in genres_str.split(",") if t.strip()]
    return token in tokens


def _matches_search(movie: Movie, raw_query: str | None) -> bool:
    if not raw_query or not raw_query.strip():
        return True
    term = raw_query.strip().lower()
    title_match = term in (movie.title or "").lower()
    desc_match = term in (movie.description or "").lower()
    return title_match or desc_match


def _published_record(column):
    status = case((func.json_valid(column) == 1, func.json_extract(column, "$.status")), else_="")
    return func.lower(status).in_(["ready", '"ready"'])


def _visible_movies(db):
    series = select(CatalogSeries.id).where(_published_record(CatalogSeries.record_json))
    seasons = select(CatalogSeason.id).where(_published_record(CatalogSeason.record_json))
    episodes = select(CatalogEpisode.id).where(
        _published_record(CatalogEpisode.record_json),
        CatalogEpisode.series_id.in_(series),
        or_(CatalogEpisode.season_id.is_(None), CatalogEpisode.season_id.in_(seasons)),
    )
    return db.query(Movie).filter(
        or_(~Movie.id.in_(select(CatalogSeries.id)), Movie.id.in_(series)),
        or_(~Movie.id.in_(select(CatalogEpisode.id)), Movie.id.in_(episodes)),
    )


def _movie_responses(db, movies):
    ids = [movie.id for movie in movies]
    if not ids:
        return []
    series_ids = set(db.scalars(select(CatalogSeries.id).where(CatalogSeries.id.in_(ids))))
    episodes = {episode_id: (series_id, number) for episode_id, series_id, number in db.execute(
        select(CatalogEpisode.id, CatalogEpisode.series_id, CatalogEpisode.number).where(CatalogEpisode.id.in_(ids))
    )}
    result = []
    for movie in movies:
        item = movie.to_response()
        if movie.id in series_ids:
            item.update(item_type="series", series_id=movie.id)
        elif movie.id in episodes:
            series_id, number = episodes[movie.id]
            item.update(item_type="episode", series_id=series_id, episode_id=movie.id, episode_number=number)
        result.append(item)
    return result


@router.get("/api/movies")
def get_all_movies(
    request: Request,
    search: str | None = Query(default=None),
    query: str | None = Query(default=None),
    q: str | None = Query(default=None),
    genre: str | None = Query(default=None),
):
    effective_search = next((v.strip() for v in (search, query, q) if v and v.strip()), None)
    with get_db(request) as db:
        all_movies = _visible_movies(db).all()
        filtered = [
            m for m in all_movies
            if _matches_search(m, effective_search) and _matches_genre_token(m.genres, genre)
        ]
        filtered.sort(key=lambda m: (-(m.rating or 0.0), m.id))
        return api_response(data=_movie_responses(db, filtered))


@router.get("/api/movies/browse")
def browse_movies(
    request: Request,
    query: str | None = Query(default=None),
    search: str | None = Query(default=None),
    q: str | None = Query(default=None),
    genre: str | None = Query(default=None),
    genres: str | None = Query(default=None),
    animationOnly: bool | None = Query(default=None),
    yearMin: int | None = Query(default=None),
    yearMax: int | None = Query(default=None),
    sort: str = Query(default="rating"),
    direction: str = Query(default="desc"),
    page: int = Query(default=0),
    size: int = Query(default=12),
):
    if page < 0:
        return api_response(None, f"Chỉ số trang (page) không được âm: {page}", False, 400)
    if size < 1 or size > 100:
        return api_response(None, f"Kích thước trang (size) phải nằm trong khoảng 1 đến 100: {size}", False, 400)
    if yearMin is not None and yearMax is not None and yearMin > yearMax:
        return api_response(None, f"Năm tối thiểu (yearMin: {yearMin}) không được lớn hơn năm tối đa (yearMax: {yearMax})", False, 400)
    sort_field = (sort or "rating").strip().lower()
    if sort_field not in {"rating", "year", "title"}:
        return api_response(None, f"Trường sắp xếp không hợp lệ: '{sort}'", False, 400)
    sort_dir = (direction or "desc").strip().lower()
    if sort_dir not in {"asc", "desc"}:
        return api_response(None, f"Chiều sắp xếp không hợp lệ: '{direction}'", False, 400)

    effective_q = next((v.strip() for v in (query, search, q) if v and v.strip()), None)

    with get_db(request) as db:
        db_query = _visible_movies(db)
        if yearMin is not None:
            db_query = db_query.filter(Movie.release_year >= yearMin)
        if yearMax is not None:
            db_query = db_query.filter(Movie.release_year <= yearMax)
        if (not effective_q and not (genre or "").strip() and not (genres or "").replace(",", "").strip()
                and animationOnly is not True and sort_field in {"rating", "year"}):
            total_elements = db_query.count()
            total_pages = math.ceil(total_elements / size) if total_elements > 0 else 0
            column = Movie.rating if sort_field == "rating" else Movie.release_year
            order = func.coalesce(column, 0)
            order = order.desc() if sort_dir == "desc" else order.asc()
            start = page * size
            items = (db_query.order_by(order, cast(Movie.id, LargeBinary).asc()).offset(start).limit(size).all()
                     if start < total_elements else [])
            return api_response(data={
                "items": _movie_responses(db, items),
                "page": page,
                "size": size,
                "totalElements": total_elements,
                "totalPages": total_pages,
                "hasNext": (page + 1) < total_pages,
                "hasPrevious": page > 0 and total_pages > 0,
            })
        items = db_query.all()
        result = []
        genre_tokens = [t.strip() for t in (genres or "").split(",") if t.strip()]
        for m in items:
            if not _matches_search(m, effective_q):
                continue
            if not _matches_genre_token(m.genres, genre):
                continue
            if any(not _matches_genre_token(m.genres, gt) for gt in genre_tokens):
                continue
            if animationOnly is True and not _matches_genre_token(m.genres, "Animation"):
                continue
            result.append(m)

        reverse = sort_dir == "desc"
        if sort_field == "rating":
            result.sort(key=lambda m: (m.id,))
            result.sort(key=lambda m: (m.rating or 0.0), reverse=reverse)
        elif sort_field == "year":
            result.sort(key=lambda m: (m.id,))
            result.sort(key=lambda m: (m.release_year or 0), reverse=reverse)
        else:
            result.sort(key=lambda m: (m.id,))
            result.sort(key=lambda m: (m.title or ""), reverse=reverse)

        total_elements = len(result)
        total_pages = math.ceil(total_elements / size) if total_elements > 0 else 0
        start = page * size
        page_items = _movie_responses(db, result[start : start + size])
        return api_response(
            data={
                "items": page_items,
                "page": page,
                "size": size,
                "totalElements": total_elements,
                "totalPages": total_pages,
                "hasNext": (page + 1) < total_pages,
                "hasPrevious": page > 0 and total_pages > 0,
            }
        )


@router.get("/api/movies/{movie_id}")
def get_movie_by_id(movie_id: str, request: Request):
    with get_db(request) as db:
        movie = _visible_movies(db).filter(Movie.id == movie_id).first()
        if not movie:
            return api_response(None, "Không tìm thấy phim.", False, 404)
        return api_response(data=_movie_responses(db, [movie])[0])


@router.get("/api/movies/{movie_id}/media-descriptor")
def get_media_descriptor(movie_id: str, request: Request):
    with get_db(request) as db:
        movie = _visible_movies(db).filter(Movie.id == movie_id).first()
        if not movie:
            return api_response(None, f"Không tìm thấy phim với mã: {movie_id}", False, 404)
        assets = (
            db.query(MediaAsset)
            .filter(MediaAsset.movie_id == movie_id, MediaAsset.is_available.is_(True), MediaAsset.is_public.is_(True))
            .all()
        )
        assets = [asset for asset in assets
                  if (catalog_asset := db.get(CatalogMediaAsset, asset.id)) is None or _asset_allowed(catalog_asset, None)]
        feature = next((a.to_dto() for a in assets if (a.kind or "").lower() == "feature"), None)
        trailer = next((a.to_dto() for a in assets if (a.kind or "").lower() == "trailer"), None)
        if not trailer and movie.video_url and movie.video_url.strip():
            trailer = {
                "assetId": f"fallback-trailer-{movie.id}",
                "kind": "trailer",
                "streamUrl": movie.video_url,
                "mimeType": "video/mp4",
                "byteLength": 0,
                "durationSeconds": None,
                "isPublic": True,
                "version": "legacy",
            }
        return api_response(
            data={
                "movieId": movie.id,
                "hasFeature": feature is not None,
                "hasTrailer": trailer is not None,
                "feature": feature,
                "trailer": trailer,
            }
        )


@router.get("/api/catalog/series")
def get_catalog_series(request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        user = get_optional_user(request, db, authorization)
        is_admin = bool(user and user.role == "ROLE_ADMIN")
        series_list = [
            s.to_dict()
            for s in db.query(CatalogSeries).all()
            if is_admin or is_published(s.record_json)
        ]
        return JSONResponse(series_list)


@router.get("/api/catalog/series/{series_id}")
def get_catalog_series_detail(series_id: str, request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        user = get_optional_user(request, db, authorization)
        is_admin = bool(user and user.role == "ROLE_ADMIN")
        series = db.get(CatalogSeries, series_id)
        if not series or (not is_admin and not is_published(series.record_json)):
            return api_response(None, f"Không tìm thấy bộ phim (series) với mã: {series_id}", False, 404)
        seasons = (
            db.query(CatalogSeason)
            .filter(CatalogSeason.series_id == series_id)
            .order_by(CatalogSeason.number.asc())
            .all()
        )
        pub_seasons = [s.to_dict() for s in seasons if is_admin or is_published(s.record_json)]
        pub_season_ids = {s["id"] for s in pub_seasons}
        episodes = (
            db.query(CatalogEpisode)
            .filter(CatalogEpisode.series_id == series_id)
            .order_by(CatalogEpisode.number.asc())
            .all()
        )
        pub_episodes = [
            e.to_dict()
            for e in episodes
            if (is_admin or is_published(e.record_json))
            and (is_admin or not e.season_id or e.season_id in pub_season_ids)
        ]
        return JSONResponse({"series": series.to_dict(), "seasons": pub_seasons, "episodes": pub_episodes})


def _asset_allowed(asset: CatalogMediaAsset, user: User | None) -> bool:
    if not asset.enabled:
        return False
    is_admin = bool(user and user.role == "ROLE_ADMIN")
    if not is_admin and not is_published(asset.record_json):
        return False
    policy = (asset.access_policy or "public").lower()
    if policy == "public":
        return True
    if not user:
        return False
    if policy == "authenticated":
        return True
    if policy == "private":
        return is_admin
    return False


def _youtube_source(episode: CatalogEpisode) -> dict[str, str | bool] | None:
    try:
        external_ids = json.loads(episode.raw_json or "{}").get("external_ids")
    except (ValueError, TypeError, AttributeError):
        return None
    if not isinstance(external_ids, list):
        return None
    watch_id = None
    for item in external_ids:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
            continue
        if item.get("namespace") == "youtube_playback":
            return {"videoId": value, "canEmbed": True}
        if item.get("namespace") == "youtube_watch" and watch_id is None:
            watch_id = value
    return {"videoId": watch_id, "canEmbed": False} if watch_id else None


@router.get("/api/catalog/episodes/{episode_id}")
def get_catalog_episode_detail(episode_id: str, request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        user = get_optional_user(request, db, authorization)
        is_admin = bool(user and user.role == "ROLE_ADMIN")
        ep = db.get(CatalogEpisode, episode_id)
        if not ep or (not is_admin and not is_published(ep.record_json)):
            return api_response(None, f"Không tìm thấy tập phim với mã: {episode_id}", False, 404)
        series = db.get(CatalogSeries, ep.series_id)
        if not is_admin and (not series or not is_published(series.record_json)):
            return api_response(None, f"Không tìm thấy tập phim với mã: {episode_id}", False, 404)
        if ep.season_id:
            sea = db.get(CatalogSeason, ep.season_id)
            if not is_admin and (not sea or sea.series_id != ep.series_id or not is_published(sea.record_json)):
                return api_response(None, f"Không tìm thấy tập phim với mã: {episode_id}", False, 404)
        segments = [
            s.to_dict()
            for s in db.query(CatalogSegment).filter(CatalogSegment.episode_id == episode_id).order_by(CatalogSegment.position.asc()).all()
            if is_admin or is_published(s.record_json)
        ]
        episode_assets = (
            db.query(CatalogMediaAsset)
            .join(CatalogEpisodeAsset, CatalogEpisodeAsset.media_asset_id == CatalogMediaAsset.id)
            .filter(CatalogEpisodeAsset.episode_id == ep.id)
            .order_by(CatalogEpisodeAsset.media_asset_id)
        )
        assets = [a.to_dict() for a in episode_assets if _asset_allowed(a, user)]
        allowed_asset_ids = {a["id"] for a in assets}
        scenes = [
            sc.to_dict()
            for sc in db.query(CatalogScene).filter(CatalogScene.episode_id == episode_id).order_by(CatalogScene.start_ms.asc()).all()
            if (is_admin or is_published(sc.record_json))
            and (is_admin or not sc.media_asset_id or sc.media_asset_id in allowed_asset_ids)
        ]
        return JSONResponse({"episode": ep.to_dict(), "segments": segments, "mediaAssets": assets,
                             "scenes": scenes, "youtube": _youtube_source(ep)})


@router.get("/api/catalog/search")
def search_catalog(request: Request, q: str = Query(default=""), authorization: str | None = Header(default=None)):
    term = (q or "").strip().lower()
    if not term:
        return JSONResponse([])
    with get_db(request) as db:
        user = get_optional_user(request, db, authorization)
        is_admin = bool(user and user.role == "ROLE_ADMIN")
        results = []
        pub_series = {s.id: s for s in db.query(CatalogSeries).all() if is_admin or is_published(s.record_json)}
        pub_seasons = {s.id: s for s in db.query(CatalogSeason).all() if is_admin or is_published(s.record_json)}
        pub_episodes = {
            e.id: e
            for e in db.query(CatalogEpisode).all()
            if (is_admin or is_published(e.record_json))
            and e.series_id in pub_series
            and (is_admin or not e.season_id or e.season_id in pub_seasons)
        }
        allowed_assets = {a.id: a for a in db.query(CatalogMediaAsset).all() if _asset_allowed(a, user)}

        for s in pub_series.values():
            if any(term in (field or "").lower() for field in (s.title, s.original_title, s.synopsis, s.keywords_json)):
                results.append({
                    "id": s.id, "type": "series", "title": s.title, "parentTitle": None,
                    "seriesId": s.id, "episodeId": None, "mediaAssetId": None,
                    "startMs": None, "endMs": None, "snippet": s.synopsis,
                })

        for ep in pub_episodes.values():
            if any(term in (field or "").lower() for field in (ep.title, ep.synopsis, ep.plot_facts_json, ep.keywords_json)):
                parent = pub_series.get(ep.series_id)
                results.append({
                    "id": ep.id, "type": "episode", "title": ep.title,
                    "parentTitle": parent.title if parent else None,
                    "seriesId": ep.series_id, "episodeId": ep.id, "mediaAssetId": None,
                    "startMs": 0, "endMs": ep.duration_ms, "snippet": ep.synopsis,
                })

        for seg in db.query(CatalogSegment).all():
            if (not is_admin and not is_published(seg.record_json)) or seg.episode_id not in pub_episodes:
                continue
            if any(term in (field or "").lower() for field in (seg.title, seg.synopsis, seg.plot_facts_json, seg.keywords_json)):
                ep = pub_episodes[seg.episode_id]
                results.append({
                    "id": seg.id, "type": "segment", "title": seg.title,
                    "parentTitle": ep.title, "seriesId": ep.series_id, "episodeId": ep.id,
                    "mediaAssetId": None, "startMs": seg.episode_start_ms, "endMs": seg.episode_end_ms,
                    "snippet": seg.synopsis,
                })

        for sc in db.query(CatalogScene).all():
            if (not is_admin and not is_published(sc.record_json)) or sc.episode_id not in pub_episodes:
                continue
            if not is_admin and sc.media_asset_id and sc.media_asset_id not in allowed_assets:
                continue
            if any(term in (field or "").lower() for field in (sc.title, sc.summary, sc.visual_description, sc.visual_tags_json)):
                ep = pub_episodes[sc.episode_id]
                results.append({
                    "id": sc.id, "type": "scene", "title": sc.title or "Phân cảnh khớp truy vấn",
                    "parentTitle": ep.title, "seriesId": ep.series_id, "episodeId": ep.id,
                    "mediaAssetId": sc.media_asset_id, "startMs": sc.start_ms, "endMs": sc.end_ms,
                    "snippet": sc.summary or sc.visual_description,
                })
        return JSONResponse(results)


@router.get("/api/users/watchlist")
def get_watchlist(request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        items = db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).order_by(WatchlistItem.added_at.desc()).all()
        return api_response(data=[i.to_dict() for i in items])


def _commit_library_item(db, item):
    model, user_id, movie_id = type(item), item.user_id, item.movie_id
    rating = item.rating if model is MovieRating else None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(model).filter(model.user_id == user_id, model.movie_id == movie_id).first()
        if existing is None:
            raise
        if model is MovieRating:
            existing.rating = rating
            existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
        item = existing
    db.refresh(item)
    return item


@router.post("/api/users/watchlist")
def add_watchlist(payload: MovieIdPayload, request: Request, authorization: str | None = Header(default=None)):
    movie_id = (payload.movieId or "").strip()
    if not movie_id:
        return api_response(None, "Movie ID is required", False, 400)
    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        movie = _visible_movies(db).filter(Movie.id == movie_id).first()
        if not movie:
            return api_response(None, f"Phim không tồn tại trong danh mục: {movie_id}", False, 400)
        existing = db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id, WatchlistItem.movie_id == movie_id).first()
        if existing:
            return api_response(data=existing.to_dict(), message="Đã thêm phim vào danh sách xem sau")
        item = WatchlistItem(user_id=user.id, movie_id=movie.id, movie_title=movie.title, poster_url=movie.poster)
        db.add(item)
        item = _commit_library_item(db, item)
        return api_response(data=item.to_dict(), message="Đã thêm phim vào danh sách xem sau")


@router.delete("/api/users/watchlist/{movie_id}")
def remove_watchlist(movie_id: str, request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id, WatchlistItem.movie_id == movie_id).delete()
        db.commit()
        return api_response(data=None, message="Đã xóa phim khỏi danh sách xem sau")


@router.get("/api/users/favorites")
def get_favorites(request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        items = db.query(FavoriteItem).filter(FavoriteItem.user_id == user.id).order_by(FavoriteItem.added_at.desc()).all()
        return api_response(data=[i.to_dict() for i in items])


@router.post("/api/users/favorites")
def add_favorite(payload: MovieIdPayload, request: Request, authorization: str | None = Header(default=None)):
    movie_id = (payload.movieId or "").strip()
    if not movie_id:
        return api_response(None, "Movie ID is required", False, 400)
    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        movie = _visible_movies(db).filter(Movie.id == movie_id).first()
        if not movie:
            return api_response(None, f"Phim không tồn tại trong danh mục: {movie_id}", False, 400)
        existing = db.query(FavoriteItem).filter(FavoriteItem.user_id == user.id, FavoriteItem.movie_id == movie_id).first()
        if existing:
            return api_response(data=existing.to_dict(), message="Đã thêm phim vào danh sách yêu thích")
        item = FavoriteItem(user_id=user.id, movie_id=movie.id, movie_title=movie.title, poster_url=movie.poster)
        db.add(item)
        item = _commit_library_item(db, item)
        return api_response(data=item.to_dict(), message="Đã thêm phim vào danh sách yêu thích")


@router.delete("/api/users/favorites/{movie_id}")
def remove_favorite(movie_id: str, request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        db.query(FavoriteItem).filter(FavoriteItem.user_id == user.id, FavoriteItem.movie_id == movie_id).delete()
        db.commit()
        return api_response(data=None, message="Đã xóa phim khỏi danh sách yêu thích")


@router.get("/api/users/ratings")
def get_ratings(request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        items = db.query(MovieRating).filter(MovieRating.user_id == user.id).order_by(MovieRating.updated_at.desc()).all()
        return api_response(data=[i.to_dict() for i in items])


@router.post("/api/users/ratings")
def add_rating(payload: RatingPayload, request: Request, authorization: str | None = Header(default=None)):
    movie_id = (payload.movieId or "").strip()
    if not movie_id or payload.rating is None or payload.rating < 1 or payload.rating > 10:
        return api_response(None, "Điểm đánh giá phải từ 1 đến 10", False, 400)
    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        movie = _visible_movies(db).filter(Movie.id == movie_id).first()
        if not movie:
            return api_response(None, f"Phim không tồn tại trong danh mục: {movie_id}", False, 400)
        existing = db.query(MovieRating).filter(MovieRating.user_id == user.id, MovieRating.movie_id == movie_id).first()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if existing:
            existing.rating = payload.rating
            existing.updated_at = now
            db.commit()
            db.refresh(existing)
            return api_response(data=existing.to_dict(), message="Đã ghi nhận đánh giá phim")
        rating = MovieRating(user_id=user.id, movie_id=movie_id, rating=payload.rating, created_at=now, updated_at=now)
        db.add(rating)
        rating = _commit_library_item(db, rating)
        return api_response(data=rating.to_dict(), message="Đã ghi nhận đánh giá phim")


@router.delete("/api/users/ratings/{movie_id}")
def remove_rating(movie_id: str, request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        db.query(MovieRating).filter(MovieRating.user_id == user.id, MovieRating.movie_id == movie_id).delete()
        db.commit()
        return api_response(data=None, message="Đã xóa đánh giá phim")


def _covers_full_episode(coverage_json: str | None, episode_id: str) -> bool:
    if not coverage_json:
        return False
    try:
        items = json.loads(coverage_json)
        if not isinstance(items, list):
            return False
        return any(
            isinstance(i, dict) and i.get("episode_id") == episode_id and str(i.get("scope", "")).lower() == "full_episode"
            for i in items
        )
    except Exception:
        return False


def _valid_episode_context(ep, series, season, asset, playable, episode_id, user):
    if not ep or not is_published(ep.record_json):
        return None
    if not series or not is_published(series.record_json):
        return None
    if ep.season_id and (not season or not is_published(season.record_json)):
        return None
    if not asset or not _asset_allowed(asset, user):
        return None
    role = (asset.role or "").lower()
    if (asset.content_type or "").lower() != "video" or role in {"dub", "audio_description"}:
        return None
    if not _covers_full_episode(asset.coverage_json, episode_id):
        return None
    if not playable or not playable.is_available or not (playable.mime_type or "").lower().startswith("video/"):
        return None
    return ep, series, season, asset


def _resolve_episode_context(db, episode_id: str, asset_id: str, user: User):
    ep = db.get(CatalogEpisode, episode_id)
    series = db.get(CatalogSeries, ep.series_id) if ep else None
    season = db.get(CatalogSeason, ep.season_id) if ep and ep.season_id else None
    asset = db.get(CatalogMediaAsset, asset_id)
    playable = db.get(MediaAsset, asset_id)
    return _valid_episode_context(ep, series, season, asset, playable, episode_id, user)


def _to_progress_response(progress: WatchProgress, ctx) -> dict:
    ep, series, season, asset = ctx
    dur = asset.duration_ms
    completed = False
    if dur is not None and dur > 0:
        five_pct = max(1, dur // 20)
        near_end = min(60000, five_pct)
        threshold = max(dur - five_pct, dur - near_end)
        completed = progress.position_ms >= threshold
    return {
        "episodeId": ep.id,
        "seriesId": series.id,
        "seriesTitle": series.title,
        "seasonId": season.id if season else None,
        "seasonNumber": season.number if season else None,
        "seasonTitle": season.title if season else None,
        "episodeNumber": ep.number,
        "episodeTitle": ep.title,
        "assetId": progress.asset_id,
        "positionMs": progress.position_ms,
        "durationMs": dur if (dur is not None and dur > 0) else None,
        "completed": completed,
        "version": progress.opt_lock_version or 0,
        "updatedAt": progress.updated_at.isoformat() if progress.updated_at else None,
    }


@router.get("/api/users/watch-progress")
def get_recent_watch_progress(request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        rows = (
            db.query(WatchProgress, CatalogEpisode, CatalogSeries, CatalogSeason, CatalogMediaAsset, MediaAsset)
            .outerjoin(CatalogEpisode, CatalogEpisode.id == WatchProgress.episode_id)
            .outerjoin(CatalogSeries, CatalogSeries.id == CatalogEpisode.series_id)
            .outerjoin(CatalogSeason, CatalogSeason.id == CatalogEpisode.season_id)
            .outerjoin(CatalogMediaAsset, CatalogMediaAsset.id == WatchProgress.asset_id)
            .outerjoin(MediaAsset, MediaAsset.id == WatchProgress.asset_id)
            .filter(WatchProgress.user_id == user.id)
            .order_by(WatchProgress.updated_at.desc())
            .limit(30)
            .all()
        )
        result = []
        for progress, ep, series, season, asset, playable in rows:
            ctx = _valid_episode_context(ep, series, season, asset, playable, progress.episode_id, user)
            if ctx:
                result.append(_to_progress_response(progress, ctx))
        return api_response(data=result)


@router.get("/api/users/watch-progress/{episode_id}")
def get_episode_watch_progress(episode_id: str, request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        p = db.query(WatchProgress).filter(WatchProgress.user_id == user.id, WatchProgress.episode_id == episode_id).first()
        if not p:
            return api_response(None, f"Không tìm thấy tập có thể phát: {episode_id}", False, 404)
        ctx = _resolve_episode_context(db, episode_id, p.asset_id, user)
        if not ctx:
            return api_response(None, f"Không tìm thấy tập có thể phát: {episode_id}", False, 404)
        return api_response(data=_to_progress_response(p, ctx))


@router.put("/api/users/watch-progress/{episode_id}")
async def save_watch_progress(episode_id: str, request: Request, authorization: str | None = Header(default=None)):
    try:
        body = await request.json()
    except Exception:
        return api_response(None, "Dữ liệu JSON không hợp lệ.", False, 400)
    return await run_in_threadpool(_save_watch_progress, episode_id, request, authorization, body)


def _save_watch_progress(episode_id, request, authorization, body):
    if not isinstance(body, dict):
        return api_response(None, "Dữ liệu tiến độ xem không hợp lệ.", False, 400)
    asset_id = str(body.get("assetId") or "").strip()
    expected_version = body.get("expectedVersion")
    raw_pos = body.get("positionMs")
    if not asset_id or expected_version is None or isinstance(expected_version, bool):
        return api_response(None, "Cần mã video và phiên bản tiến độ xem.", False, 400)
    try:
        version = Decimal(str(expected_version))
        if not version.is_finite() or version != version.to_integral_value():
            raise ValueError()
        expected_version = int(version)
    except (InvalidOperation, ValueError):
        return api_response(None, "Phiên bản tiến độ xem phải là số nguyên.", False, 400)
    if expected_version < -1:
        return api_response(None, "Dùng phiên bản -1 khi tạo mới hoặc phiên bản hiện tại khi cập nhật.", False, 400)
    if raw_pos is None or isinstance(raw_pos, bool):
        return api_response(None, "Vị trí xem phải là số nguyên từ 0 đến 24 giờ, tính bằng mili giây.", False, 400)
    try:
        dec = Decimal(str(raw_pos))
        if not dec.is_finite() or dec != dec.to_integral_value() or dec < 0 or dec > 86400000:
            return api_response(None, "Vị trí xem phải là số nguyên từ 0 đến 24 giờ, tính bằng mili giây.", False, 400)
        pos_ms = int(dec)
    except (InvalidOperation, ValueError):
        return api_response(None, "Vị trí xem phải là số nguyên từ 0 đến 24 giờ, tính bằng mili giây.", False, 400)

    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        ctx = _resolve_episode_context(db, episode_id, asset_id, user)
        if not ctx:
            return api_response(None, f"Không tìm thấy tập có thể phát: {episode_id}", False, 404)
        _, _, _, asset = ctx
        if asset.duration_ms is not None and asset.duration_ms > 0 and pos_ms > asset.duration_ms:
            return api_response(None, "Vị trí xem vượt quá thời lượng video.", False, 400)
        current = db.query(WatchProgress).filter(WatchProgress.user_id == user.id, WatchProgress.episode_id == episode_id).first()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if expected_version == -1:
            if current is not None:
                return api_response(None, "Watch progress changed since it was loaded; refresh and retry.", False, 409)
            progress = WatchProgress(
                user_id=user.id, episode_id=episode_id, asset_id=asset.id,
                position_ms=pos_ms, opt_lock_version=0, updated_at=now,
            )
            db.add(progress)
        else:
            if current is None or (current.opt_lock_version or 0) != expected_version:
                return api_response(None, "Watch progress changed since it was loaded; refresh and retry.", False, 409)
            current.asset_id = asset.id
            current.position_ms = pos_ms
            current.opt_lock_version = expected_version + 1
            current.updated_at = now
            progress = current
        try:
            db.flush()
            db.refresh(progress, attribute_names=["updated_at"])
            result = _to_progress_response(progress, ctx)
            db.commit()
        except StaleDataError:
            db.rollback()
            return api_response(None, "Watch progress changed since it was loaded; refresh and retry.", False, 409)
        except IntegrityError as exc:
            db.rollback()
            error = str(exc.orig)
            duplicate = (
                db.bind.dialect.name == "sqlite"
                and "UNIQUE constraint failed: watch_progress.user_id, watch_progress.episode_id" in error
            ) or (
                db.bind.dialect.name in {"mysql", "mariadb"}
                and exc.orig.args and exc.orig.args[0] == 1062
                and "uq_watch_progress_user_episode" in error
            )
            if expected_version != -1 or not duplicate:
                raise
            return api_response(None, "Watch progress changed since it was loaded; refresh and retry.", False, 409)
        return api_response(data=result, message="Đã lưu tiến độ xem")


@router.delete("/api/users/watch-progress/{episode_id}")
def delete_watch_progress(episode_id: str, request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        user = require_user(request, db, authorization)
        if not user:
            return api_response(None, "Chưa xác thực người dùng", False, 401)
        db.query(WatchProgress).filter(WatchProgress.user_id == user.id, WatchProgress.episode_id == episode_id).delete()
        db.commit()
        return api_response(data=None, message="Đã xóa tiến độ xem")


@router.post("/api/media/grant/{asset_id}")
def grant_media_token(asset_id: str, request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        asset = db.get(MediaAsset, asset_id)
        if not asset or not asset.is_available:
            return api_response(None, f"Không tìm thấy tài nguyên media: {asset_id}", False, 404)
        user = get_optional_user(request, db, authorization)
        catalog_asset = db.get(CatalogMediaAsset, asset_id)
        if catalog_asset is not None and not _asset_allowed(catalog_asset, user):
            return api_response(None, f"Không tìm thấy tài nguyên media: {asset_id}", False, 404)
        if not asset.is_public:
            if not user:
                return api_response(None, f"Không tìm thấy tài nguyên media: {asset_id}", False, 404)
            c_asset = db.get(CatalogMediaAsset, asset_id)
            if c_asset and (c_asset.access_policy or "").lower() == "private" and user.role != "ROLE_ADMIN":
                return api_response(None, f"Không tìm thấy tài nguyên media: {asset_id}", False, 404)
        token = create_playback_grant_token(
            asset_id,
            user.username if user else "anonymous",
            user.role if user else "ROLE_ANONYMOUS",
            300,
        )
        return JSONResponse(
            {
                "assetId": asset_id,
                "grant": token,
                "token": token,
                "streamUrl": f"/api/media/stream/{asset_id}?grant={token}",
                "expiresIn": 300,
                "expiresInSeconds": 300,
            }
        )


def _drive_file_without_volume_path(root: Path, relative_path: str) -> Path | None:
    if not is_relative_media_path(relative_path):
        return None
    target = Path(os.path.abspath(root)) / relative_path
    for path in (*reversed(target.parents), target):
        info = path.lstat()
        if S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
            return None
        if not (S_ISREG(info.st_mode) if path == target else S_ISDIR(info.st_mode)):
            return None
    return target


def _resolve_media_file(asset: MediaAsset) -> Path | None:
    rel = asset.relative_path
    if not is_relative_media_path(rel):
        return None
    local_root = os.getenv("APP_MEDIA_ROOT")
    local_roots = [Path(local_root)] if local_root else [Path("media"), ROOT / "media"]
    candidates = [(root, rel, False) for root in local_roots]
    if (asset.storage_provider or "").lower() == "drive":
        cache_root = os.getenv("APP_MEDIA_CACHE_ROOT")
        if cache_root and asset.byte_length and asset.byte_length > 0:
            try:
                cached = _drive_file_without_volume_path(Path(cache_root), rel)
                if cached is not None and cached.stat().st_size == asset.byte_length:
                    return cached
            except OSError:
                pass
        mount = os.getenv("APP_MEDIA_DRIVE_MOUNT", "X:" if os.name == "nt" else "")
        if mount:
            drive_root = Path(mount)
            if drive_root.drive and mount == drive_root.drive:
                drive_root = Path(f"{mount}/")
            drive_candidates = [(drive_root, rel, True)]
            if rel.startswith("VideoDieppie/"):
                drive_candidates.append((drive_root, rel.removeprefix("VideoDieppie/"), True))
            candidates = drive_candidates + candidates
    for root, relative_path, is_drive in candidates:
        try:
            resolved_root = root.resolve(strict=True)
            target = (resolved_root / relative_path).resolve(strict=True)
            if target.is_relative_to(resolved_root) and target.is_file():
                return target
        except OSError as exc:
            if is_drive and getattr(exc, "winerror", None) == 1005:
                try:
                    target = _drive_file_without_volume_path(root, relative_path)
                    if target is not None:
                        return target
                except OSError:
                    continue
        except (RuntimeError, ValueError):
            continue
    return None


def _stream_file(path: Path, start: int, length: int):
    with path.open("rb") as file:
        file.seek(start)
        while length > 0:
            chunk = file.read(min(length, 65536))
            if not chunk:
                break
            length -= len(chunk)
            yield chunk


@router.api_route("/api/media/stream/{asset_id}", methods=["GET", "HEAD"])
def stream_media(
    asset_id: str,
    request: Request,
    range: str | None = Header(default=None),
    grant: str | None = Query(default=None),
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
):
    effective_token = (grant or token or "").strip() or None
    with get_db(request) as db:
        asset = db.get(MediaAsset, asset_id)
        if not asset or not asset.is_available:
            return api_response(None, f"Không tìm thấy tài nguyên media: {asset_id}", False, 404)
        user = get_optional_user(request, db, authorization)
        grant_role = validate_playback_grant_token(effective_token, asset_id) if effective_token else None
        access_user = user or (SimpleNamespace(role=grant_role) if grant_role in {"ROLE_USER", "ROLE_ADMIN"} else None)
        catalog_asset = db.get(CatalogMediaAsset, asset_id)
        if ((catalog_asset is not None and not _asset_allowed(catalog_asset, access_user))
                or (not asset.is_public and not access_user)):
            return api_response(None, f"Không tìm thấy tài nguyên media: {asset_id}", False, 404)

        file_path = _resolve_media_file(asset)
        if not file_path:
            return api_response(None, "Không tìm thấy tệp video.", False, 404)
        try:
            total_length = file_path.stat().st_size
        except OSError:
            return api_response(None, "Không tìm thấy tệp video.", False, 404)
        mime = asset.mime_type or "video/mp4"

        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type=mime,
                headers={"Accept-Ranges": "bytes", "Content-Length": str(total_length)},
            )

        if not range or not range.strip():
            return StreamingResponse(
                content=_stream_file(file_path, 0, total_length),
                status_code=200,
                media_type=mime,
                headers={"Accept-Ranges": "bytes", "Content-Length": str(total_length)},
            )

        trimmed = range.strip()
        if not total_length or not trimmed.startswith("bytes=") or "-" not in trimmed[6:]:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{total_length}"})
        spec = trimmed[6:].strip()
        try:
            if spec.startswith("-"):
                suffix = int(spec[1:])
                if suffix <= 0:
                    raise ValueError()
                start = max(0, total_length - suffix)
                end = total_length - 1
            else:
                parts = spec.split("-", 1)
                start = int(parts[0].strip())
                if start < 0 or start >= total_length:
                    raise ValueError()
                end = int(parts[1].strip()) if parts[1].strip() else (total_length - 1)
                if start > end:
                    raise ValueError()
                end = min(end, total_length - 1)
        except ValueError:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{total_length}"})

        length = end - start + 1
        return StreamingResponse(
            content=_stream_file(file_path, start, length),
            status_code=206,
            media_type=mime,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {start}-{end}/{total_length}",
                "Content-Length": str(length),
            },
        )


def _require_admin(request: Request, db, authorization: str | None) -> User | None:
    user = require_user(request, db, authorization)
    if not user or user.role != "ROLE_ADMIN":
        return None
    return user


def _is_catalog_admin(request, authorization):
    with get_db(request) as db:
        return bool(_require_admin(request, db, authorization))


@router.post("/api/admin/catalog/validate")
async def admin_validate_catalog(request: Request, authorization: str | None = Header(default=None)):
    if not await run_in_threadpool(_is_catalog_admin, request, authorization):
        return api_response(None, "Quyền truy cập bị từ chối (Yêu cầu ROLE_ADMIN)", False, 403)
    try:
        body = await read_catalog_body(request)
        error = None
    except CatalogInputError as exc:
        body, error = None, exc
    return await run_in_threadpool(_validate_catalog, request, authorization, body, error)


def _validate_catalog(request, authorization, body, error):
    with get_db(request) as db:
        if not _require_admin(request, db, authorization):
            return api_response(None, "Quyền truy cập bị từ chối (Yêu cầu ROLE_ADMIN)", False, 403)
        try:
            if error:
                raise error
            pkg_id, revision = validate_catalog_input(body)
            content_hash = compute_sha256(body)
            existing_pkg = db.get(CatalogPackage, pkg_id)
            counts, _ = catalog_diff(db, body, revision, content_hash, existing_pkg)
        except CatalogInputError as exc:
            return JSONResponse(
                {
                    "valid": False,
                    "packageId": None,
                    "revision": None,
                    "contentHash": None,
                    "toCreate": 0,
                    "toUpdate": 0,
                    "unchanged": 0,
                    "conflicts": 0,
                    "errors": [{"path": exc.path, "code": "INVALID_FIELD", "message": str(exc)}],
                },
                status_code=400,
            )
        return JSONResponse(
            {
                "valid": True,
                "packageId": pkg_id,
                "revision": revision,
                "contentHash": content_hash,
                **counts,
                "errors": [],
            }
        )


async def read_catalog_body(request):
    try:
        return await request.json()
    except (ValueError, RecursionError) as exc:
        raise CatalogInputError("package", "Dữ liệu JSON không hợp lệ.") from exc


@router.post("/api/admin/catalog/import")
async def admin_import_catalog(request: Request, authorization: str | None = Header(default=None)):
    if not await run_in_threadpool(_is_catalog_admin, request, authorization):
        return api_response(None, "Quyền truy cập bị từ chối (Yêu cầu ROLE_ADMIN)", False, 403)
    try:
        body = await read_catalog_body(request)
        error = None
    except CatalogInputError as exc:
        body, error = None, exc
    return await run_in_threadpool(_import_catalog, request, authorization, body, error)


def _import_catalog(request, authorization, body, error):
    with request.app.state.runtime.catalog_lock, get_db(request) as db:
        if not _require_admin(request, db, authorization):
            return api_response(None, "Quyền truy cập bị từ chối (Yêu cầu ROLE_ADMIN)", False, 403)
        try:
            if error:
                raise error
            resp = import_catalog_package(db, body)
        except CatalogInputError as exc:
            return api_response(None, str(exc), False, 400)
        except CatalogConflictError as exc:
            return api_response(None, str(exc), False, 409)
        except IntegrityError as exc:
            code = exc.orig.args[0] if exc.orig.args else None
            sqlite_code = getattr(exc.orig, "sqlite_errorcode", None)
            if code == 1062 or sqlite_code in (1555, 2067):
                return api_response(None, "Danh mục vừa thay đổi. Kiểm tra lại gói rồi thử lại.", False, 409)
            return api_response(None, "Gói danh mục có dữ liệu hoặc liên kết không hợp lệ.", False, 400)
        except OperationalError as exc:
            code = exc.orig.args[0] if exc.orig.args else None
            sqlite_code = getattr(exc.orig, "sqlite_errorcode", 0)
            if code in (1205, 1213) or (sqlite_code & 255) in (5, 6):
                return api_response(None, "Đang có lần nhập khác. Vui lòng thử lại.", False, 409)
            raise
        except (DataError, KeyError, TypeError, ValueError, OverflowError, RecursionError):
            return api_response(None, "Dữ liệu gói danh mục không hợp lệ.", False, 400)
        except StatementError as exc:
            if not isinstance(exc.orig, (TypeError, ValueError, OverflowError)):
                raise
            return api_response(None, "Dữ liệu gói danh mục không hợp lệ.", False, 400)
        if resp.pop("unchanged", False):
            return JSONResponse(resp)
        runtime = request.app.state.runtime
        try:
            eligible = export_eligible_catalog(db)
            gen = int(resp.get("snapshotVersion") or resp.get("revision") or 1)
            ack, _ = runtime.sync(SimpleNamespace(generation=gen, content_hash=None, catalog=eligible,
                                                  force_rebuild=False, snapshot_id=resp["importId"]))
            index_status = _catalog_index_status(ack, gen)
        except Exception:
            logging.getLogger(__name__).exception("Không thể đồng bộ chỉ mục catalog")
            index_status = "SYNC_FAILED"
        resp["indexStatus"] = index_status
        snap = db.get(CatalogSnapshot, resp["importId"])
        if snap:
            snap.status = index_status
            snap.completed_at = datetime.now(timezone.utc).replace(tzinfo=None) if index_status == "READY" else None
            db.commit()
        return JSONResponse(resp)


def _catalog_index_status(ack, generation):
    if ack.get("status") == "SKIPPED" or ack.get("generation") != generation:
        return "SYNC_FAILED"
    if ack.get("status") == "CACHE_REQUIRED":
        return "BLOCKED"
    return "READY" if ack.get("index_ready") else str(ack.get("status") or "PENDING")


@router.get("/api/admin/catalog/history")
def admin_catalog_history(request: Request, authorization: str | None = Header(default=None)):
    with get_db(request) as db:
        if not _require_admin(request, db, authorization):
            return api_response(None, "Quyền truy cập bị từ chối (Yêu cầu ROLE_ADMIN)", False, 403)
        pkgs = db.query(CatalogPackage).order_by(CatalogPackage.imported_at.desc()).all()
        return JSONResponse([p.to_dict() for p in pkgs])


@router.get("/api/admin/catalog/snapshots")
def admin_catalog_snapshots(request: Request, authorization: str | None = Header(default=None)):
    with request.app.state.runtime.catalog_lock, get_db(request) as db:
        if not _require_admin(request, db, authorization):
            return api_response(None, "Quyền truy cập bị từ chối (Yêu cầu ROLE_ADMIN)", False, 403)
        snaps = db.query(CatalogSnapshot).order_by(CatalogSnapshot.snapshot_version.desc()).all()
        runtime = request.app.state.runtime
        for snap in snaps:
            if snap.status == "CACHE_REQUIRED":
                snap.status = "BLOCKED"
            if snap.status == "BUILDING" and runtime.snapshot:
                if runtime.snapshot.generation == snap.snapshot_version and runtime.snapshot.is_ready:
                    snap.status = "READY"
                    snap.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                elif runtime.snapshot.generation > snap.snapshot_version:
                    snap.status = "SYNC_FAILED"
            if (snap.status == "BUILDING" and runtime.pending and runtime.pending["finished"]
                    and runtime.pending["generation"] == snap.snapshot_version and runtime.pending["error"]):
                snap.status = "SYNC_FAILED"
            if (snap.status == "BUILDING" and (
                    runtime.pending is None or runtime.pending["generation"] != snap.snapshot_version
                    or runtime.pending["finished"])):
                snap.status = "SYNC_FAILED"
        db.commit()
        return JSONResponse([s.to_dict() for s in snaps])


@router.post("/api/admin/catalog/snapshots/{snapshot_id}/retry")
def admin_retry_snapshot(snapshot_id: str, request: Request, authorization: str | None = Header(default=None)):
    with request.app.state.runtime.catalog_lock, get_db(request) as db:
        if not _require_admin(request, db, authorization):
            return api_response(None, "Quyền truy cập bị từ chối (Yêu cầu ROLE_ADMIN)", False, 403)
        snap = db.get(CatalogSnapshot, snapshot_id)
        if not snap:
            return api_response(None, f"Không tìm thấy snapshot với ID: {snapshot_id}", False, 400)
        latest = db.query(CatalogSnapshot).order_by(CatalogSnapshot.snapshot_version.desc()).first()
        if latest.id != snap.id:
            return api_response(None, "Chỉ có thể thử lại snapshot mới nhất.", False, 409)
        runtime = request.app.state.runtime
        try:
            eligible = export_eligible_catalog(db)
            ack, _ = runtime.sync(SimpleNamespace(generation=int(snap.snapshot_version), content_hash=None, catalog=eligible,
                                                  force_rebuild=True, snapshot_id=snap.id))
            snap.status = _catalog_index_status(ack, int(snap.snapshot_version))
        except Exception:
            logging.getLogger(__name__).exception("Không thể thử lại đồng bộ chỉ mục catalog")
            snap.status = "SYNC_FAILED"
        snap.retry_count = int(snap.retry_count or 0) + 1
        snap.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        snap.completed_at = snap.updated_at if snap.status == "READY" else None
        db.commit()
        db.refresh(snap)
        return JSONResponse(snap.to_dict())


@router.get("/api/admin/catalog/export")
def admin_export_catalog(
    request: Request,
    includeDraft: bool = Query(default=True),
    includePrivate: bool = Query(default=True),
    authorization: str | None = Header(default=None),
):
    with get_db(request) as db:
        if not _require_admin(request, db, authorization):
            return api_response(None, "Quyền truy cập bị từ chối (Yêu cầu ROLE_ADMIN)", False, 403)
        return JSONResponse(
            export_eligible_catalog(db, include_draft=includeDraft, include_private=includePrivate)
        )
