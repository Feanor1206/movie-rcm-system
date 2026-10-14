# M4-F03 Engineering Report — Descriptor Terminal Failures, Multi-Agent Ownership & Empirical Recovery

**Milestone:** M4 Follow-Up 03 (M4-F03)  
**Workspace:** `D:\Class\movie-rcm-system`  
**Branch:** `dev`  
**Timestamp:** 2026-10-15T00:50:00+07:00  
**Status:** `READY FOR REVIEW`  
**Review Target:** Codex Verification  
**Reviewed Checkpoint:** `M4-F02-CHECKPOINT-01`  
**Baseline HEAD Commit:** `409235f`

---

## 1. Executive Summary

Milestone M4-F03 resolves the single remaining P2 finding (**T1 — Descriptor Terminal Failures: Timeout, Malformed Payload & ID Mismatch Handling**) identified in Codex's review (`docs/reviews/M4_F02_REVIEW.md`).

In strict accordance with the user's explicit directive to employ **three parallel agents with dedicated file ownership**, the task was partitioned and executed cleanly across three specialized subagents and an integrating orchestrator:
1. **Agent A — Client Boundary Engineer (`1c80818c`):** Implemented strict timeout vs external abort distinction and schema validation in `mediaService.ts`, accompanied by a new dedicated unit suite `media_descriptor_boundary_suite.mjs` (9/9 pass).
2. **Agent B — Component Lifecycle Engineer (`ccd6d779`):** Updated `MovieDetail.tsx` to handle in-flight request lifecycles, error alert rendering (`role="alert"`), retry recovery (`data-testid="descriptor-retry-btn"`), silent cancellation on route swaps, and dynamic route bundle optimization maintaining strict budget compliance (143,264 bytes $\le$ 143,360 bytes). Expanded `media_playback_suite.mjs` (17/17 pass) and satisfied reviewer repro `M4_F02_descriptor_timeout.cjs` (3/3 pass).
3. **Agent C — Browser Verification Engineer (`2f7f5172`):** Enhanced `scripts/run_m4_media_walkthrough.cjs` and `M4WalkthroughServer.java` with end-to-end descriptor failure (HTTP 503) injection and browser retry recovery verification via Chrome CDP, preserving 100% of the F02 happy path playback, scrubber seek, mobile 375px audit, stream admission, and disk snapshot benchmarks (Exit 0).
4. **Parent Orchestrator:** Integrated new test suites into `package.json`, validated regressions across backend and frontend on both Node 26 and Node 20 LTS, audited dynamic bundle limits, and authored deliverable artifacts.

All previous accepted milestones (M1–M3, F01, F02 backend admission, cleanup, and storage) remain fully intact. Google Drive streaming remains classified as `BLOCKED_EXTERNAL_INPUT / NOT_IMPLEMENTED`.

---

## 2. Multi-Agent Partitioning & Ownership Matrix

| Agent | Role | Conversation ID | Owned Files | Responsibilities |
|:---|:---|:---:|:---|:---|
| **Agent A** | Client Boundary Engineer | `1c80818c` | `frontend/lib/services/mediaService.ts`<br>`frontend/tests/media_descriptor_boundary_suite.mjs` | Internal timeout vs external cancellation; strict validation of HTTP 200 payload (exact movieId, boolean flags, valid advertised streams); Node 20 test suite. |
| **Agent B** | Component Lifecycle Engineer | `ccd6d779` | `frontend/features/movies/components/MovieDetail.tsx`<br>`frontend/tests/media_playback_suite.mjs` | Request lifecycle with AbortController; terminal error state transitions; `role="alert"` and `descriptor-retry-btn`; route swap silent abort; dynamic JS bundle budget $\le 143,360$ bytes. |
| **Agent C** | Browser Verification Engineer | `2f7f5172` | `scripts/run_m4_media_walkthrough.cjs`<br>`backend/.../M4WalkthroughServer.java` | End-to-end browser descriptor fault injection (Step A0); verify alert and retry button visibility; verify feature button absence during fault; interact with retry button and verify recovery. Preserve all F02 benchmarks. |
| **Parent** | Orchestrator & Integrator | `db189d79` | `frontend/package.json`<br>`docs/reports/M4_F03_*` | Wire new suite to `npm test`; execute full verification matrix (bare Maven, CI profile, Node 20, tsc, bundle budget); generate patch, status, manifest. |

No file collisions occurred between agents. No new git branches were created.

---

## 3. Technical Implementation Details (Finding T1)

### 3.1 Client Boundary & Contract Specification (Agent A)
* **Internal Timeout vs External Abort:**
  - `getMediaDescriptor(movieId, options)` creates an internal `AbortController` bounded by `options?.timeoutMs ?? 6000`.
  - When the timeout expires and `options?.signal?.aborted` is false: throws `DOMException('Hết thời gian tải mô tả media', 'TimeoutError')` with property `(err).isTimeout = true`.
  - When `options?.signal?.aborted` is true (caller aborted externally, e.g. unmount or route change): throws `DOMException('Aborted', 'AbortError')`.
  - Timer and external event listeners are unconditionally cleaned up in a `finally` block.
* **Strict Payload Validation:**
  - Handles direct payloads and wrapped payloads (`{ data: ... }`).
  - **Movie ID Invariance:** `data.movieId` must be a non-empty string matching `movieId` verbatim. If missing or different, throws `Error('Dữ liệu mô tả media không khớp mã phim')`. Never falls back to request parameter.
  - **Boolean Integrity:** `typeof data.hasFeature === 'boolean'` and `typeof data.hasTrailer === 'boolean'`. Boolean coercion (`Boolean(undefined)`) is eliminated. Missing/non-boolean flags throw `Error('Thiếu hoặc sai trường hasFeature/hasTrailer')`.
  - **Advertised Media Integrity:**
    - If `data.hasFeature === true`: `data.feature` must be an object with `kind === 'feature'` and a non-empty `streamUrl`.
    - If `data.hasTrailer === true`: `data.trailer` must be an object with `kind === 'trailer'` and a non-empty `streamUrl`.
  - **Valid Empty Representation:** `{ movieId, hasFeature: false, hasTrailer: false, feature: null, trailer: null }` cleanly returns as a valid descriptor.
  - Stream URLs are resolved using `resolveStreamUrl()`.
* **Verification Suite (`media_descriptor_boundary_suite.mjs`):**
  - 9 tests passing covering valid normalization, valid empty, internal timeout, external abort, empty `{}` payload, mismatched movieId, non-boolean flags, empty streamUrl, and HTTP 500/503.

### 3.2 Component Lifecycle, Error Presentation & Retry Recovery (Agent B)
* **Request Lifecycle & Abort Management:**
  - `MovieDetail.tsx` binds descriptor fetching to `[movie.id, descriptorNonce]` using an `AbortController`.
  - On route swap (Movie A $\rightarrow$ Movie B) or unmount, the prior controller is aborted.
  - In `catch`: if `abortController?.signal.aborted` is true, the error is dropped silently, preventing cross-route error banners or stale overwrites.
* **Terminal Error State & UI Alert Banner:**
  - When an active request fails (`signal.aborted === false`), whether from timeout, malformed payload, wrong movieId, HTTP 500/503, or network outage:
    - `descriptorLoading` is set to `false`.
    - `descriptor` is set to `null`.
    - `descriptorError` is populated with `'Không thể tải thông tin phát phim. Vui lòng thử lại.'`.
    - Renders `<div role="alert">...<button data-testid="descriptor-retry-btn">Thử lại</button></div>`.
  - Clicking `descriptor-retry-btn` increments `descriptorNonce`, clearing the error and re-executing the fetch. Upon HTTP 200, restores the "Xem phim" feature playback button.
  - Trailer preview (`movie.videoUrl`) remains operable independently even when descriptor lookup fails.
* **Dynamic Route JS Budget Compliance:**
  - Detailed bundle audit (`node scripts/compute_build_bytes.cjs`):
    - Route `/movies/[id]`: **143,264 bytes (139.91 KiB)** gzip.
    - Budget limit: **143,360 bytes (140 KiB)**.
    - Status: **PASS** (96 bytes under budget).

### 3.3 End-to-End Browser Walkthrough with Fault Injection (Agent C)
* **CDP Descriptor Fault Injection (Step A0):**
  - Armed `M4WalkthroughServer` and Chrome CDP `Fetch.requestPaused` to intercept `/api/movies/m4-walkthrough-movie/media-descriptor` and return HTTP 503.
  - Navigated to `/movies/m4-walkthrough-movie`:
    - Verified catalog movie title renders immediately.
    - Verified `[role="alert"]` appears with text: `"Không thể tải thông tin phát phim. Vui lòng thử lại. Thử lại"`.
    - Verified `button[data-testid="descriptor-retry-btn"]` is visible and enabled.
    - Verified "Xem phim" button is absent from DOM.
    - Captured screenshot: `docs/reports/screenshots/M4_F03/00_desktop_descriptor_failure.png` (221.8 KiB).
  - Disarmed fault simulation and dispatched click to `button[data-testid="descriptor-retry-btn"]`.
  - Observed descriptor re-fetch returning HTTP 200:
    - Alert banner dismissed (`null`).
    - Feature button `"Xem phim"` (`button[data-testid="play-feature-btn"]`) rendered and clickable.
* **Full Happy Path Playback Preserved:**
  - Browser decode latency: **118 ms** (`requestVideoFrameCallback`).
  - Playback progression: verified `currentTime: 1.02s`.
  - 3 Seeks via timeline scrubber: 34 ms, 62 ms, 40 ms (avg **45.33 ms**). Continuous playback at 15.40s.
  - Pause / resume toggled via UI button.
  - Video retry recovery verified naturally at **15.58s** with zero harness tampering.
  - Mobile 375px audit: all 5 controls $\ge 44 \times 44$ px, **0 collisions**.
  - Spring Boot HTTP benchmarks 1–6: startup TTFB avg 21.06 ms, throughput ~18 MB/s, concurrency 3 streams ~26 MB/s, bounded admission & 429 overload verified, client disconnect active stream counter returned to 0, read-only disk snapshot 0 mutations.

---

## 4. Empirical Benchmark & Verification Summary

### 4.1 Verification Commands and Results

| Command | Working Directory | Result | Notes |
|:---|:---|:---:|:---|
| `mvnw.cmd test` | `backend/springboot` | **43/43 PASS** | Bare Maven build (Exit 0) |
| `mvnw.cmd test "-Dspring.profiles.active=test"` | `backend/springboot` | **43/43 PASS** | CI test profile (Exit 0) |
| `npm test` | `frontend` | **83/83 PASS** | Node 26 active environment (Exit 0) |
| `npx --package=node@20.20.2 node --test ...` | `frontend` | **83/83 PASS** | Node 20 LTS CI runtime (Exit 0) |
| `npx tsc --noEmit` | `frontend` | **0 ERRORS** | TypeScript strict check (Exit 0) |
| `node scripts/compute_build_bytes.cjs` | Root | **PASS** | Dynamic `/movies/[id]`: 143,264 B $\le$ 143,360 B |
| `node docs/reviews/repro/M4_F02_descriptor_timeout.cjs` | Root | **3/3 PASS** | Timeout, missing-fields, wrong-movie-id (Exit 0) |
| `node docs/reviews/repro/M4_F01_descriptor_failure.cjs` | Root | **2/2 PASS** | Non-legacy and legacy cases (Exit 0) |
| `node scripts/run_m4_media_walkthrough.cjs` | Root | **EXIT 0** | Full browser walkthrough & benchmarks |
| `git apply --check -R docs/reports/M4_F03.patch` | Root | **VERIFIED CLEAN** | Reverse patch check (Exit 0) |

### 4.2 Reviewer Repro Output Verification

Execution of `node docs/reviews/repro/M4_F02_descriptor_timeout.cjs`:
```json
{"serviceError":"TimeoutError","alertPresent":true,"retryPresent":true,"source":"production service timeout + production component via hook harness"}
{"scenario":"missing-required-fields","alertPresent":true,"retryPresent":true}
{"scenario":"wrong-movie-id","alertPresent":true,"retryPresent":true}
```
All three failure conditions produce `alertPresent: true` and `retryPresent: true`.

---

## 5. Deliverable Artifacts (M4-F03)

- **Engineering Report:** `docs/reports/M4_F03_REPORT.md` (this file)
- **Status Metadata:** `docs/reports/M4_F03_STATUS.json`
- **Git Patch:** `docs/reports/M4_F03.patch`
- **Manifest (SHA-256):** `docs/reports/M4_F03_MANIFEST.json`
- **Walkthrough Evidence JSON:** `docs/reports/m4_f03_benchmark_results.json`
- **Screenshots:**
  1. `docs/reports/screenshots/M4_F03/00_desktop_descriptor_failure.png`
  2. `docs/reports/screenshots/M4_F03/01_desktop_playback_playing.png`
  3. `docs/reports/screenshots/M4_F03/02_desktop_seek_near_end.png`
  4. `docs/reports/screenshots/M4_F03/03_desktop_retry_recovery.png`
  5. `docs/reports/screenshots/M4_F03/04_mobile_playback_375px.png`

All application source files are **FROZEN**. Ready for Codex review and acceptance.
