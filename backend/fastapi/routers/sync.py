import hmac
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from schemas import CacheRequiredResponse, IndexSyncRequest, IndexSyncResponse
from services.catalog_sync import CatalogSyncError


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/index/sync", response_model=IndexSyncResponse, responses={503: {"model": CacheRequiredResponse}})
def sync_index(http_request: Request, request: IndexSyncRequest):
    runtime = http_request.app.state.runtime
    if not runtime.sync_secret:
        raise HTTPException(503, "Chưa cấu hình token đồng bộ catalog.")
    token = http_request.headers.get("X-Service-Token")
    authorization = http_request.headers.get("Authorization", "")
    if token is None and not authorization:
        raise HTTPException(401, "Thiếu token dịch vụ.")
    if token is None:
        parts = authorization.split()
        token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else ""
    if not hmac.compare_digest(token.strip().encode(), runtime.sync_secret.encode()):
        raise HTTPException(403, "Token dịch vụ không hợp lệ.")
    try:
        result, status = runtime.sync(request)
        return JSONResponse(result, status_code=status)
    except HTTPException:
        raise
    except CatalogSyncError:
        raise HTTPException(400, "Catalog không hợp lệ.")
    except Exception:
        logger.exception("Catalog sync failed")
        raise HTTPException(500, "Lỗi đồng bộ catalog.")
