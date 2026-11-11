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

The launcher builds the application, checks service readiness and keeps isolated preview state. It selects `cloud` when the local DeepSeek configuration exists and `light` otherwise. Pass `-ModelMode light` for template-based CineBot or `-ModelMode off` to start only Spring and Next.js. Open http://localhost:3000. Stop owned services with `.\scripts\stop_preview_stack.ps1`.

The preview profile includes local demo accounts. Import a catalog through the admin screen or `scripts/import_preview_catalog.ps1`; catalog payloads are in `data/` and schema fixtures in `docs/`. Local video files or a configured Drive mount must exist for playback.

Run `.\scripts\configure_llm.ps1` to enter the base URL, model ID and API key in PowerShell. For DeepSeek V4.1 Flash on the official endpoint, enter `deepseek-flash` as the model ID. The script saves the ignored `.env.deepseek.local` file and sends one test request. Run it again to update the settings or pass `-Clear` to remove the file. Restart FastAPI after either change. `full` is a legacy alias for `cloud`.

Cloud chat sends evidence selected from local pilot catalog files. User messages, history and the Spring snapshot contents stay local. Chat uses the deterministic template when the provider or matching pilot evidence is unavailable. `/ready` reports search, frames, recommendations, chat, LLM and reranker separately. Frame search requires a registered frame model and index.

Local encoder and reranker artifacts use `TEXT_ENCODER_PATH` and `RERANKER_MODEL_PATH`. Initial document embeddings must be prepared offline; sync reads cached vectors and queues only bounded missing deltas. `202 BUILDING` is pending, not an accepted snapshot. Spring waits without consuming its failure retry budget. Large missing caches return 503 until offline preparation finishes. Accepted generations survive restarts and switch atomically. Requests cannot supply a separate `availableMovies` catalog.

See [embedding preparation](ai/EMBEDDING_CACHE.md), [retrieval evaluation](ai/evaluation/README.md), and the [serving contract](docs/fastapi-v2-serving.md). Chat now uses SSE throughout FastAPI, Next.js and the browser. Results retain legacy fields and add episode/time, scores and evidence. Missing trained artifacts or calibration are reported explicitly. No credentials or model weights belong in Git. Example environment files live under `backend/fastapi/` and `frontend/`.

## Verify

```powershell
cd frontend
npm test
npm run typecheck
npm run build
```

Spring tests run with `.\mvnw.cmd test '-Dspring.profiles.active=test'` from `backend/springboot`. For Python, install `backend/fastapi/requirements-test.txt` and run `python -m pytest -q tests backend/fastapi/tests` from the root. Offline tests cover API and snapshot boundaries, a tiny ONNX graph and mocked providers. Live, billed DeepSeek tests are opt-in through `RUN_DEEPSEEK_INTEGRATION=1`. Training dependencies are separate in `ai/requirements-training.txt`.

CI checks the frontend, Spring and offline Python suites. Docker configuration is in `infrastructure/`; supply real environment values before deployment. Live Docker/PostgreSQL deployment has not been verified on the development host.

Generated indexes, analysis graphs, temporary experiments and captured reports are ignored. Product documentation will be written after implementation.
