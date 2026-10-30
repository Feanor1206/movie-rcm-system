# Dippie

Animation discovery, catalog management, personal library and video playback.

- **Next.js:** browsing, search, account/library, episode player and CineBot interface.
- **Spring Boot:** authentication, catalog source of truth, library, progress and HTTP Range streaming.
- **FastAPI:** intent parsing and catalog-grounded discovery; model optimization remains separate.

## Run locally on Windows

Requires Node.js 20+, Java 17+ and Python for the optional AI service. Install frontend dependencies first:

```powershell
cd frontend
npm ci
cd ..
.\start-all.ps1 -Background
```

The launcher builds the application, checks service readiness and keeps isolated preview state. AI is off by default, so browsing and playback do not depend on model loading. Open http://localhost:3000. Stop owned services with `.\scripts\stop_preview_stack.ps1`.

The preview profile includes local demo accounts. Import a catalog through the admin screen or `scripts/import_preview_catalog.ps1`; catalog payloads are in `data/` and schema fixtures in `docs/`. Local video files or a configured Drive mount must exist for playback.

For AI, provide the external catalog sync secret and model paths, then launch with `-ModelMode full` (or `light`). No credentials or model weights belong in Git. Frontend same-origin API defaults are in `frontend/.env.example`.

## Verify

```powershell
cd frontend
npm test
npm run typecheck
npm run build
```

Spring: run `.\mvnw.cmd test -Dspring.profiles.active=test` from `backend/springboot`. Python: run `python -m pytest tests backend/fastapi/tests` from the root. The regression suites use lexical retrieval and mocked model serving; live GPU integration requires explicit opt-in.

CI checks the frontend, Spring and offline Python suites. Docker configuration is in `infrastructure/`; supply real environment values before deployment. Live Docker/PostgreSQL deployment has not been verified on the development host.

Generated indexes, analysis graphs, temporary experiments and captured reports are ignored. Product documentation will be written after implementation.
