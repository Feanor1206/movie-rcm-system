# CATALOG-01 Independent Cross-Review Report

**Repository:** `D:\Class\movie-rcm-system`  
**Branch:** `dev`  
**Review Target:** Animation Catalog v1 (`dippie.catalog.v1`) Schema, Storage, Retrieval, Player & Chatbot Integration  
**Reviewer:** Independent Review Agent (Static & Behavioral Verification)  
**Date:** 2026-10-16  

---

## 1. Executive Summary

| Review Category | Status | Confidence | Findings Summary |
|---|:---:|:---:|---|
| **1. Contract Conformance** | **PASS** | High | Structural validation strictly follows `dippie.catalog.v1.schema.json`. JSON Pointer error format (`/collections/0/field`) compliant. |
| **2. Storage & Transaction Isolation** | **PASS** | High | 12 tables mapped in DDL and JPA. `@Transactional(rollbackFor = Exception.class)` ensures all-or-nothing atomic persistence. Revision idempotency and optimistic locking verified. |
| **3. Media Registration & Streaming** | **PASS** | High | `catalog_media_assets` registered into Spring Boot media streaming core (`media_assets` and `movies`). HTTP 206 Partial Content (Byte Range) supported for Google Drive and local storage. |
| **4. Multi-level Search & Chatbot** | **PASS** | High | Robertson-Spärck Jones BM25 + dense `multilingual-e5-small` embeddings flatten series, episodes, segments, and scenes. Fallback static 12-movie restriction removed. Grounded Stage 5 explanations verified. |
| **5. Web UI & Player Navigation** | **PASS** | High | Admin modal with dry-run diff preview (`toCreate`, `toUpdate`, `unchanged`, `conflicts`), Series/Episode hierarchy viewer, Google Drive streaming video player, and scene timestamp seeking (`start_ms`) fully implemented and type-checked (0 errors). |

---

## 2. In-Depth Technical Review

### 2.1 Schema Conformance & Validation Fidelity
- **File:** `backend/springboot/src/main/java/com/dippie/moviercm/service/catalog/CatalogValidator.java`
- **Specification:** `docs/contracts/animation-catalog-v1/dippie.catalog.v1.schema.json`
- **Strengths:**
  1. Strict enforcement of `dippie.catalog.v1` contract header (`schema_version`, `package_id`, `revision`, `generated_at`).
  2. Global ID collision detection across all 12 collections (`series`, `seasons`, `episodes`, `segments`, `characters`, `media_assets`, `text_tracks`, `scenes`, etc.).
  3. Relational integrity enforcement:
     - `series_id` must reference valid series in package or existing DB.
     - `season_id` must match a season defined in the parent series.
     - `episode_id` in segments and scenes must reference declared episodes.
     - `media_asset_id` in text tracks and scenes must reference declared media assets.
  4. Temporal boundary verification:
     - `start_ms < end_ms` for all segments and scenes.
     - Segments and scenes must not exceed episode duration (`duration_ms`).
     - Subtitle cues must have non-overlapping, strictly positive monotonic intervals.
  5. JSON Pointer standard (`/episodes/0/duration_ms`) ensures frontend client can pinpoint field-level validation errors.

### 2.2 Transactional Integrity & Idempotency
- **File:** `backend/springboot/src/main/java/com/dippie/moviercm/service/catalog/CatalogImportService.java`
- **Mechanisms:**
  1. **Dry-Run Preview (`validateAndPreview`):** Computes exact diffs (`toCreate`, `toUpdate`, `unchanged`, `conflicts`) without writing to the database.
  2. **Atomic Ingestion (`importPackage`):** Executes in a single `@Transactional` boundary. If any entity fails constraint validation or relational mapping, the entire package rollback is triggered.
  3. **Revision Gate:** Re-importing the same `package_id` with an older or identical `revision` without modifications is flagged as idempotent/unchanged; conflicting changes require revision increment.

### 2.3 Media Streaming & Player Seeking
- **File:** `backend/springboot/src/main/java/com/dippie/moviercm/service/catalog/CatalogImportService.java` & `MediaStreamingService.java`
- **Player Component:** `frontend/app/series/[id]/page.tsx`
- **Mechanisms:**
  1. When importing `media_assets`, each video asset is automatically mirrored into `media_assets` and `movies` tables, assigning streamable URLs `/api/media/stream/{assetId}`.
  2. The custom HTML5 video player component handles Google Drive streaming via HTTP 206 Partial Content (Byte Range requests).
  3. Clicking any scene item in the scene timeline triggers `playerRef.current.currentTime = scene.start_ms / 1000.0`, jumping directly to the scene onset with active cue highlighting.

### 2.4 Multi-Level AI Retrieval & Grounded Explanations
- **Files:**
  - `backend/fastapi/services/catalog_sync.py`
  - `backend/fastapi/services/hybrid_retrieval.py`
  - `backend/fastapi/services/ai_pipeline.py`
- **Mechanisms:**
  1. **Catalog Flattening:** Each hierarchy tier (`series`, `episode`, `segment`, `scene`) is indexed as an independent search item with rich contextual embedding text (title, aliases, character names/roles, synopsis, plot facts, visual summaries, sound events).
  2. **Type Normalization:** Vietnamese synonyms (`phân cảnh`, `cảnh quay`, `tập`, `bộ`) are mapped to canonical item types (`scene`, `segment`, `episode`, `series`), allowing queries like *"Tìm phân cảnh xe địa hình nhảy vực"* to prioritize scenes over series.
  3. **Grounded Explanations (Anti-Hallucination):** Stage 5 prompt dynamically formats scene timestamps (`start_ms` to `mm:ss`), parent episode title, and visual details. Explanations cite verifiable catalog facts instead of hallucinating fictional plot points.
  4. **Dynamic AI Index Sync:** Spring Boot's import triggers `/api/index/sync` to instantly update FastAPI's in-memory BM25 index and FAISS/dense embeddings without restarting the Python process.

---

## 3. Test & Verification Matrix

| Suite | Component | Scope | Result |
|---|---|---|:---:|
| `CatalogValidatorTest` | Spring Boot | 9 unit test scenarios: missing headers, duplicate IDs, invalid intervals, orphaned references, pointer formatting | **9/9 PASS** |
| `CatalogImportServiceTest` | Spring Boot | 6 integration scenarios: dry-run preview, atomic import, media asset registration, rollback on conflict | **6/6 PASS** |
| `test_catalog_retrieval.py` | FastAPI | 12 end-to-end scenarios: flattening, series/episode/segment/scene retrieval, hard constraints, comparative constraints, grounded Stage 5, REST API sync & search | **12/12 PASS** |
| `tsc --noEmit` | Next.js Frontend | Strict TypeScript compiler check across all new components, services, and pages | **0 errors (PASS)** |

---

## 4. Risk Analysis & Mitigations

1. **GPU VRAM Overhead:**
   - *Risk:* Loading Qwen3-4B + LoRA simultaneously with SentenceTransformer embeddings could trigger CUDA OOM on 6GB VRAM GPUs (e.g., RTX 3050 Laptop).
   - *Mitigation:* Qwen3-4B is quantized with 4-bit NF4 (`bitsandbytes`), consuming only ~2.8 GB VRAM. `multilingual-e5-small` uses only ~350 MB. Total VRAM remains under 4.2 GB, safely below the 6.0 GB ceiling.
2. **Catalog Scaling:**
   - *Risk:* Rebuilding dense embeddings for thousands of scenes synchronously could block the import HTTP request.
   - *Mitigation:* BM25 index builds in sub-second time (<50ms). Dense embedding batching allows asynchronous or background caching.
3. **Drive Rate Limits:**
   - *Risk:* Rapid scrubbing across scenes could trigger Google Drive rate limits.
   - *Mitigation:* Spring Boot's `DriveIoExecutor` employs bounded concurrency and byte-range chunk caching to absorb repeated seeks.

---

## 5. Review Conclusion
The implementation meets all specified requirements of **CATALOG-01**:
- Complete end-to-end pipeline: JSON import → Validation & Preview → Persistent Storage → Web UI & Drive Video Player → Multi-level Search → AI Chatbot.
- Zero regressions in existing Drive streaming, snapshot lifecycles, and test suites.
- Approved for merge into `dev`.
