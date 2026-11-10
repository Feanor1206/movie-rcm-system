# FastAPI v2 serving contract

Scope: implement the six serving changes requested on 2026-11-10. The supplied
RTX 3050 design is architectural context, not authorization to run enrichment,
download weights, train models, call paid APIs, or change the Spring database.

## Interfaces and implementation order

1. Text index owns immutable catalog documents, numeric vectors, and a cache
   keyed by document content and encoder identity. Initial embeddings are built
   offline. Sync reads the cache without encoding; bounded deltas can be prepared
   by one background worker. Large missing caches require offline preparation.
2. Sync validates authentication, schema, hash and generation before publication.
   Preparation never holds the publication lock. Persistence precedes one atomic
   snapshot swap. Retained readers keep the entire old snapshot, including empty
   snapshots. A 202 `BUILDING` response is not a durable acceptance acknowledgement.
3. `app.state.runtime` owns accepted state, locks, model registry and worker.
   Routers cover health, sync, search, chat, frames and recommendations. Serving
   uses exactly one Uvicorn worker without reload.
4. Requests cannot inject `availableMovies`. Search and recommendations capture
   one accepted snapshot. The old result fields remain, with `episodeId`,
   `startMs`, `score`, `calibratedScore` and catalog evidence added. Missing
   calibration is reported as null, never a fabricated probability.
5. `light` uses deterministic chat; `full` calls external llama-server; `cloud`
   calls an OpenAI-compatible DeepSeek endpoint. One GPU semaphore covers local
   heavy inference. Readiness reports each feature independently; missing frame
   or reranker artifacts cannot be reported as loaded.
6. Chat is async SSE: `metadata` carries result fields, `token` carries
   `{ "text": "delta" }`, `done` carries the full legacy ChatResponse, and
   `error` carries a safe `{ "text": "message" }`. Cancellation closes upstream
   streams. The Next.js gateway relays chunks and the browser renders deltas.

## Verification

- API validation and sync authentication, hash mismatch, empty acceptance,
  generation ordering/conflict, idempotency, failed build/persistence, retained
  reader isolation, concurrent sync, recovery and app-instance ownership.
- Embedding reuse/content changes/model identity, invalid vectors and cache
  durability; query results retain episode/time/evidence fields.
- Registry feature readiness, GPU serialization/cancellation, async upstream SSE
  parsing, grounded output and safe provider failures.
- Frontend gateway/client split UTF-8 SSE, cancellation, partial rendering and
  existing behavioral suites, typecheck and production build.
- Legacy tests tied to the removed Qwen/hybrid internals migrate to boundary
  tests and a retrieval evaluation gate. Quality measurements require explicit
  human labels/baseline artifacts; synthetic unit fixtures are not quality proof.

Commands: `python -m pytest -q tests backend/fastapi/tests`; from `frontend`,
`npm test`, `npm run typecheck`, `npm run build`. Live model quality, VRAM and
latency targets require supplied artifacts and a separate run on the target GPU.

## Migration and operational details

The Qwen/PEFT in-process service, old hybrid implementation, cascading stubs and
two training stubs are removed. Actual importing scripts now use the offline
cache CLI and external-provider benchmark. Historical evidence scripts that
only list old filenames remain historical records.

The old retrieval suites contributed 140 scenarios. Their queries and original
assertion expressions are preserved in `ai/evaluation/legacy_scenarios.jsonl` for
label migration; this file is not an executable quality gate or a labeled human
test set. Synthetic catalog retrieval checks exercise the new evaluation port.
API validation and snapshot safety use real routers/runtime, replacing tests
that compiled selected functions from `main.py` using AST. Live model tests keep
their existing opt-in requirement.

`startMs` uses logical episode time when media coverage provides a mapping.
Legacy `start_ms` retains source-file time. Evidence carries both positions,
asset identity and timeline. Private, authenticated, disabled and unpublished
media/text tracks cannot contribute public dialogue windows or scene summaries.

`SCORE_CALIBRATION_PATH` loads only a calibration matching the active reranker
fingerprint. Without it, `calibratedScore` and `matchPercentage` remain null.
The `light`, `full` and `cloud` modes use the same retrieval path. Frame serving
is an explicit registry boundary; no trained frame encoder/index is supplied.
No latency, VRAM or model-quality target has been established by unit tests.

## Local verification on 2026-11-10

- Python: 109 passed, two existing external-model opt-in tests skipped. Serving
  package pins were installed in a local environment that reuses the existing
  Torch installation; ONNX Runtime 1.23.2 and tokenizers 0.22.1 were exercised.
- Frontend: 147 passed; typecheck, production build and route budgets passed.
  A native Next.js HTTP smoke test observed early chunks and upstream closure
  after downstream cancellation.
- Spring: 213 passed, including seven real-HTTP async-sync acknowledgement cases.
- Launcher helpers passed on Windows PowerShell 5.1 and PowerShell 7.
- Native FastAPI HTTP startup, sync, search and a 31-token SSE response passed
  with the LLM disabled. Changed Python and TypeScript/JavaScript code contains
  no comments or docstrings; changed Java and PowerShell files were also checked.
- Compose YAML was inspected; Docker is unavailable on this host. Graphify local
  AST extraction is blocked by `uv trampoline failed to canonicalize script path`;
  the configured isolated interpreter is absent, so source was inspected directly.
- No trained model, human quality gate, GPU memory benchmark, paid provider call
  or live Docker deployment was run. Synthetic fixtures do not establish these.
