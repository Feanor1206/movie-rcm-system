from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter()


@router.get("/")
def root():
    return {"service": "Dippie AI Gateway", "version": "3.0.0", "status": "online", "docs": "/docs"}


@router.get("/health")
def health(request: Request):
    return request.app.state.runtime.registry.health()


@router.get("/ready")
@router.get("/api/readiness")
def ready(request: Request):
    runtime = request.app.state.runtime
    result = runtime.registry.readiness(runtime.snapshot)
    result["features"]["search"]["calibrated"] = runtime.search.calibration is not None
    if "calibration" in runtime.registry.errors:
        result["features"]["search"]["calibrationError"] = runtime.registry.errors["calibration"]
    if runtime.recovery_error:
        result["recoveryError"] = runtime.recovery_error
    return JSONResponse(result, status_code=200 if result["ready"] else 503)
