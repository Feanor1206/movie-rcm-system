import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

load_dotenv()

from routers import chat, frame, health, recommend, search, sync
from services.chat import ChatService
from services.llm_client import LLMClient
from services.model_registry import InferenceCapacityError
from services.rerank import ScoreCalibration
from services.runtime import ROOT, Runtime
from services.search import SearchService


def _load_deepseek_config():
    path = ROOT / ".env.deepseek.local"
    if path.is_file():
        settings = dotenv_values(path, encoding="utf-8-sig", interpolate=False)
        for name in ("DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "DEEPSEEK_API_KEY"):
            if settings.get(name):
                os.environ[name] = settings[name]


def create_app(**options):
    @asynccontextmanager
    async def lifespan(application):
        runtime = application.state.runtime
        if runtime.registry.mode == "cloud":
            _load_deepseek_config()
        await runtime.registry.initialize()
        await run_in_threadpool(runtime.restore)
        reranker = runtime.registry.get("reranker")
        calibration = None
        path = os.getenv("SCORE_CALIBRATION_PATH")
        if path:
            try:
                if reranker is None:
                    raise ValueError("Calibration requires a loaded reranker")
                calibration = ScoreCalibration.from_file(Path(path), model_id=reranker.model_id)
            except Exception:
                logging.getLogger(__name__).exception("Score calibration could not be loaded")
                runtime.registry.errors["calibration"] = "Configured score calibration could not be loaded"
        runtime.search = SearchService(registry=runtime.registry, reranker=reranker, calibration=calibration)
        runtime.llm = LLMClient(runtime.registry)
        runtime.chat = ChatService(runtime.registry, runtime.search.search, runtime.llm)
        try:
            yield
        finally:
            try:
                await runtime.llm.aclose()
            finally:
                await run_in_threadpool(runtime.close)

    application = FastAPI(title="Dippie AI Gateway", version="3.0.0", lifespan=lifespan)
    application.state.runtime = Runtime(**options)
    @application.exception_handler(InferenceCapacityError)
    async def capacity_error(request, error):
        return JSONResponse({"detail": "GPU đang bận. Vui lòng thử lại sau."}, status_code=429,
                            headers={"Retry-After": "1"})
    origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    application.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in origins],
                               allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["*"])
    for router in (health, sync, search, chat, frame, recommend):
        application.include_router(router.router)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=os.getenv("HOST", "127.0.0.1"),
                port=int(os.getenv("PORT", "8000")), workers=1, reload=False)
