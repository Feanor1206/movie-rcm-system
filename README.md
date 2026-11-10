# Dippie

Animation discovery, catalog management, personal library and video playback.

- **Next.js:** browsing, search, account/library, episode player and CineBot interface.
- **Spring Boot:** authentication, catalog source of truth, library, progress and HTTP Range streaming.
- **FastAPI:** intent parsing and catalog-grounded discovery; model optimization remains separate.

## Run locally on Windows

Requires Node.js 20+, Java 17+ and Python 3.11+. Install the serving and frontend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/fastapi/requirements.txt
cd frontend
npm ci
cd ..
.\start-all.ps1 -Background
```

The launcher builds the application, checks service readiness and keeps isolated preview state. The default `-ModelMode light` serves catalog search and template-based CineBot without loading an LLM. `-ModelMode off` starts only Spring and Next.js. Open http://localhost:3000. Stop owned services with `.\scripts\stop_preview_stack.ps1`.

The preview profile includes local demo accounts. Import a catalog through the admin screen or `scripts/import_preview_catalog.ps1`; catalog payloads are in `data/` and schema fixtures in `docs/`. Local video files or a configured Drive mount must exist for playback.

`full` calls an external CUDA llama-server configured by `LLAMA_SERVER_URL` and `LLM_MODEL`; start that server separately with one parallel slot. `cloud` uses `DEEPSEEK_API_KEY`. The launcher does not download weights or start a second model process. Missing LLM availability does not block catalog features. `/ready` reports search, frames, recommendations, chat, LLM and reranker separately; frame search stays unavailable until a frame model/index is registered.

Local encoder and reranker artifacts use `TEXT_ENCODER_PATH` and `RERANKER_MODEL_PATH`. Initial document embeddings must be prepared offline; sync reads cached vectors and queues only bounded missing deltas. `202 BUILDING` is pending, not an accepted snapshot. Spring waits without consuming its failure retry budget. Large missing caches return 503 until offline preparation finishes. Accepted generations survive restarts and switch atomically. Requests cannot supply a separate `availableMovies` catalog.

See [embedding preparation](ai/EMBEDDING_CACHE.md), [retrieval evaluation](ai/evaluation/README.md), and the [serving contract](docs/fastapi-v2-serving.md). Chat now uses SSE throughout FastAPI, Next.js and the browser. Results retain legacy fields and add episode/time, scores and evidence. Missing trained artifacts or calibration are reported explicitly. No credentials or model weights belong in Git. Example environment files live under `backend/fastapi/` and `frontend/`.

## Verify

```powershell
cd frontend
npm test
npm run typecheck
npm run build
```

Spring: run `.\mvnw.cmd test '-Dspring.profiles.active=test'` from `backend/springboot`. Python: install `backend/fastapi/requirements-test.txt`, then run `python -m pytest -q tests backend/fastapi/tests` from the root. Offline tests cover API/snapshot boundaries, a tiny real ONNX graph and mocked model providers. Live external-model integration requires `RUN_FULL_INTEGRATION=1`. Training dependencies are separate in `ai/requirements-training.txt`.

CI checks the frontend, Spring and offline Python suites. Docker configuration is in `infrastructure/`; supply real environment values before deployment. Live Docker/PostgreSQL deployment has not been verified on the development host.

Generated indexes, analysis graphs, temporary experiments and captured reports are ignored. Product documentation will be written after implementation.
