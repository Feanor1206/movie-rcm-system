# M4-F02 Engineering Report — Media Descriptor Lifecycle, Bounded Stream Admission & Empirical Browser Evidence

**Milestone:** M4 Follow-Up 02 (M4-F02)  
**Workspace:** `D:\Class\movie-rcm-system`  
**Branch:** `dev`  
**Timestamp:** 2026-10-14T23:25:00+07:00  
**Status:** `READY FOR REVIEW`  
**Review Target:** Codex Verification  
**Reviewed Checkpoint:** `M4-F01-CHECKPOINT-01`

---

## 1. Executive Summary

Milestone M4-F02 completely closes the three remaining P2 findings (F1, F2, F3) and resolves the walkthrough harness execution block as specified in `docs/prompts/GEMINI_CURRENT_TASK.md`, `docs/reviews/M4_F01_REVIEW.md`, and `docs/prompts/M4_F02_HARNESS_UNBLOCK.md`.

This milestone achieves:
1. **F1 — Truthful Media Descriptor Lifecycle & Error Handling:** Descriptor failures (500, 503, timeout, malformed payload) are decoupled from valid `hasFeature=false` empty states. A visible error alert (`role="alert"`) and explicit retry control (`data-testid="descriptor-retry-btn"`) allow users to recover without full page reload. Legacy trailers remain distinct previews and do not mask feature lookup failures. Route swap immediately resets descriptor state and cancels in-flight fetches. Dynamic detail route bundle remains within the strict 140 KiB budget (143,249 bytes / 143,360 bytes).
2. **F2 — Bounded Local Stream Admission Policy & Observable Cleanup:** Introduced a configurable stream admission policy (`app.media.max-concurrent-streams`, default 10 permits) backed by a `Semaphore` in `MediaStreamService`. Overload requests deterministically receive HTTP 429 Too Many Requests with standard `Retry-After: 5` and `Cache-Control: no-store, no-cache, must-revalidate` headers. Stream permits are released in a strict `finally` block in `MediaStreamController`, even when clients abruptly disconnect (`ClientAbortException`). Active streams are tracked via an observable atomic counter (`getActiveStreamCount()`) rather than inferring zero leaks from HTTP 200 health endpoints.
3. **F3 & Harness Unblock — Empirical Browser Evidence & Hardened Walkthrough:** Eliminated infinite CDP and in-browser evaluation hangs by establishing finite deadlines (15s CDP, 8s in-browser promises, 10s evaluation) with listener cleanup. Automated the controlled timeline slider using `HTMLInputElement.prototype` value setter dispatching to properly trigger React's synthetic event tracker. Replaced artificial test manipulation (`v.play()`, `v.currentTime`) with a strictly observational retry wait predicate. Validated mobile 375px touch target layout ($\ge 44 \times 44$ px) with zero collisions across all 5 controls. Captured before/after SHA-256 disk snapshots proving zero filesystem mutations in the test-media root. Ensured complete process tree cleanup on test exit (`taskkill /T /F`).

No live databases, GPUs, Qwen/FastAPI AI, or external network services were used. Google Drive streaming remains classified as `BLOCKED_EXTERNAL_INPUT / NOT_IMPLEMENTED`. All existing M1, M2, and M3 accepted behaviors remain fully intact.

---

## 2. Findings Resolution Detail (F1, F2, F3)

### F1: Truthful Media Descriptor Lifecycle, Error Presentation & Retry Recovery
* **Problem Identified in Review:**
  In `MovieDetail.tsx`, any network or server error (e.g. 500, 503, timeout) during `getMediaDescriptor()` silently fell back to `{ movieId, hasFeature: false, assets: [] }`. This caused server outages to falsely appear as "movie has no media", completely hiding the failure from the user and denying any retry mechanism. Furthermore, reviewer reproduction `docs/reviews/repro/M4_F01_descriptor_failure.cjs` failed because no error alert or retry button was rendered.
* **Implementation:**
  - `MovieDetail.tsx`:
    - Separated media state into three distinct concerns: `descriptorLoading` (boolean), `descriptorError` (string | null), and `descriptor` (`MediaDescriptorResponse | null`).
    - Handled `fetchMediaDescriptor` catch block: if `error.name !== 'AbortError'`, sets `descriptorError` to a descriptive error message (`"Không thể tải thông tin phát phim. Vui lòng thử lại."`) and clears `descriptor` to `null`.
    - Added an inline error banner rendered when `descriptorError` is non-null:
      ```tsx
      <div role="alert" className="flex items-center justify-between gap-3 p-3 bg-red-950/60 border border-red-800 rounded-lg text-sm text-red-200">
        <span>{descriptorError}</span>
        <button
          type="button"
          data-testid="descriptor-retry-btn"
          onClick={() => void loadDescriptor()}
          className="px-3 py-1.5 text-xs font-semibold rounded bg-red-800 hover:bg-red-700 text-white min-h-[44px] min-w-[44px]"
        >
          Thử lại
        </button>
      </div>
      ```
    - Preserved legacy trailer button as an independent preview option without masking the feature descriptor error.
    - Verified route swaps (Movie A $\rightarrow$ Movie B) immediately reset `descriptorError = null`, `descriptor = null`, and abort pending requests.
    - Optimized dynamic route bundle size (`/movies/[id]`): through component inlining and lazy helper logic, the first-load JS bundle measures **143,249 bytes (139.89 KiB)**, strictly satisfying the $\le 143,360$ bytes (140 KiB) limit (111 bytes of headroom).
* **Verification:**
  - Reviewer repro script `node docs/reviews/repro/M4_F01_descriptor_failure.cjs`:
    ```json
    {"legacy":false,"descriptorCalls":1,"featureButton":false,"trailerButton":false,"retryControls":1,"errorMessagePresent":true}
    {"legacy":true,"descriptorCalls":1,"featureButton":false,"trailerButton":true,"retryControls":1,"errorMessagePresent":true}
    ```
    Exited with code 0.
  - Unit test in `frontend/tests/media_playback_suite.mjs` (Test 13): verifies 503 error renders `role="alert"`, displays retry button, and clicking retry re-fetches and restores 200 feature playback button.

---

### F2: Bounded Local Stream Admission Policy & Observable Cleanup
* **Problem Identified in Review:**
  `MediaStreamController` streamed 64 KiB chunks iteratively without any concurrency bound or admission control. Under high request volume or stalled clients, unbounded parallel streams could exhaust thread pools, file handles, or network sockets. Cleanup was not verifiable because tests relied on `health=UP (200)` rather than inspecting active stream permits.
* **Implementation:**
  - `application.yml` and `application-test.yml`:
    - Added configurable concurrency parameter: `app.media.max-concurrent-streams: ${APP_MEDIA_MAX_CONCURRENT_STREAMS:10}`.
  - `MediaStreamService.java`:
    - Initialized a `Semaphore streamPermits` with configurable permits.
    - Initialized an `AtomicInteger activeStreams = new AtomicInteger(0)`.
    - Implemented `acquireStreamPermit()`: uses `streamPermits.tryAcquire()`. If false, increments rejection metrics and throws `MediaOverloadException("Quá tải máy chủ truyền thông. Vui lòng thử lại sau.")`.
    - Implemented `releaseStreamPermit()`: releases semaphore permit and decrements `activeStreams`.
    - Implemented `getActiveStreamCount()`: returns real-time count of active streams.
    - Defined `MediaOverloadException` holding HTTP 429 status and `Retry-After: 5` header.
    - Added test instrumentation hooks (`setTestStreamGate()` / `awaitTestStreamGate()`) allowing integration tests and walkthrough scripts to hold a stream open deterministically to verify concurrency bounds and disconnect recovery.
  - `MediaStreamController.java`:
    - Added exception handler for `MediaOverloadException` returning `HttpStatus.TOO_MANY_REQUESTS` (429) with headers:
      - `Retry-After: 5`
      - `Cache-Control: no-store, no-cache, must-revalidate`
    - Wrapped streaming execution in a `try ... finally` block:
      ```java
      boolean permitAcquired = false;
      try {
          mediaStreamService.acquireStreamPermit();
          permitAcquired = true;
          // stream chunks iteratively...
      } finally {
          if (permitAcquired) {
              mediaStreamService.releaseStreamPermit();
          }
      }
      ```
    - Even if `ClientAbortException` or `IOException` is thrown when a client disconnects mid-stream, the permit is unconditionally released in `finally`.
  - `MediaStreamingIntegrationTest.java`:
    - Added unit and integration tests verifying:
      - Normal stream acquires and releases permit (`activeStreams` returns to 0).
      - Concurrency limit saturation returns HTTP 429 with `Retry-After: 5` and `no-store`.
      - Mid-stream client socket abort releases permit and returns `activeStreams` to baseline 0.
* **Verification:**
  - All 43 backend tests in Maven bare and test profiles pass cleanly (exit code 0).

---

### F3 & Harness Unblock: Empirical Browser Evidence & Hardened Walkthrough
* **Problem Identified in Review:**
  1. The walkthrough script `scripts/run_m4_media_walkthrough.cjs` hung indefinitely due to lack of timeouts in `awaitPromise` / CDP commands.
  2. Directly setting `input.value = target` bypassed React 18/19 synthetic event tracking, causing the timeline scrubber not to trigger `onChange`.
  3. Retry assertion artificially called `v.play()` or modified `v.currentTime` inside the polling predicate rather than observing natural app recovery.
  4. Mobile 375px test checked only close button width $\ge 40$ px rather than auditing all interactive controls $\ge 44 \times 44$ px with collision checks.
  5. Disk assertions assumed zero writes without verifying before/after file lists, hashes, and sizes.
* **Implementation:**
  - **Harness Deadlines & Process Management:**
    - Established strict timeouts: CDP commands default to 15s; in-browser `new Promise` wrappers carry explicit 8s rejection timers; evaluate calls time out after 10s.
    - Replaced hung process handling with verified process tree termination (`taskkill /T /F` on Windows) in the `finally` block, ensuring no orphan Java, Node, or Chrome processes linger.
  - **React Controlled Input Interaction:**
    - Replaced direct assignment with prototype setter call before event dispatch:
      ```javascript
      const prototypeValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value'
      ).set;
      prototypeValueSetter.call(timelineInput, targetSeconds.toString());
      timelineInput.dispatchEvent(new Event('input', { bubbles: true }));
      timelineInput.dispatchEvent(new Event('change', { bubbles: true }));
      ```
  - **Strictly Observational Retry Wait Predicate:**
    - Removed all `v.play()`, `v.currentTime = ...`, or artificial DOM manipulations from the retry evaluation predicate.
    - The test clicks the UI button `button[data-testid="video-retry-btn"]` and purely polls `video.currentTime`, `video.paused`, and `video.readyState` until natural playback resumes past 15.35s.
  - **Mobile 375px Touch Target & Collision Audit:**
    - Configured CDP viewport to $375 \times 667$.
    - Audited 5 critical player controls:
      1. Close button (`button[aria-label="Đóng trình phát"]`): $44 \times 44$ px.
      2. Play/Pause button (`button[data-testid="video-play-pause-btn"]`): $44 \times 44$ px.
      3. Volume button (`button[data-testid="video-volume-btn"]`): $44 \times 44$ px.
      4. Fullscreen button (`button[data-testid="video-fullscreen-btn"]`): $44 \times 44$ px.
      5. Timeline scrubber (`input[data-testid="video-timeline"]`): $219 \times 44$ px.
    - Ran geometric collision detection: checked all pairwise bounding boxes for overlap (`r1.left < r2.right && r1.right > r2.left && r1.top < r2.bottom && r1.bottom > r2.top`). Found **0 collisions**.
  - **Storage Snapshot Audit:**
    - Monitored directory `backend/springboot/target/test-media`.
    - Computed before/after file inventory with SHA-256 hashes and byte lengths.
    - Result: **0 mutations detected** across all 3 files (`feature_test.mp4`, `trailer_test.mp4`, `walkthrough_feature.mp4`).

---

## 3. Empirical Benchmark & Walkthrough Metrics

All measurements below are extracted directly from `docs/reports/m4_f02_benchmark_results.json`, captured from the complete live walkthrough run (`node scripts/run_m4_media_walkthrough.cjs`):

### 3.1 Browser Playback Performance (Chrome CDP)
* **Startup to First Frame Latency (`requestVideoFrameCallback`):** **235 ms**
* **Seek-to-Frame Latency (3 runs across timeline scrubber):**
  - Seek 1 (to 5.0s): **26 ms**
  - Seek 2 (to 10.0s): **50 ms**
  - Seek 3 (to 15.0s): **28 ms**
  - **Stats:** Min: 26 ms | Avg: **34.67 ms** | P95: 50 ms | Max: 50 ms
* **Continuous Playback Verification:** Continuous playback confirmed at **15.40s**.
* **Error & Retry Recovery:** Error simulated via network fault; UI error overlay rendered; retry button clicked; continuous playback naturally resumed at **15.61s** (zero harness tampering).
* **Stalls Observed:** 0 `stalled` events, 4 `waiting` events (during network pause / seek buffering).
* **Client Memory Usage:** Classified honestly as `unavailable (requires OS-level profiler; not estimated)`.

### 3.2 Spring Boot HTTP Range Streaming Benchmark
* **Initial 64 KiB Chunk TTFB (Startup, 3 runs):**
  - Runs: 21.65 ms, 17.51 ms, 16.66 ms
  - **Stats:** Min: 16.66 ms | Avg: **18.61 ms** | Max: 21.65 ms
* **Mid-Seek Chunk TTFB (`bytes=150000-215535`, 3 runs):**
  - Runs: 41.90 ms, 13.18 ms, 16.83 ms
  - **Stats:** Min: 13.18 ms | Avg: **23.97 ms** | Max: 41.90 ms
* **End-Seek Chunk TTFB (`bytes=250000-`, 3 runs):**
  - Runs: 17.31 ms, 14.63 ms, 19.91 ms
  - **Stats:** Min: 14.63 ms | Avg: **17.28 ms** | Max: 19.91 ms
* **Single Stream Download Throughput (296 KiB asset):**
  - Runs: 16.18 MB/s, 10.56 MB/s, 8.85 MB/s
  - **Stats:** Min: 8.85 MB/s | Avg: **11.86 MB/s** | Max: 16.18 MB/s
* **3 Concurrent Stream Batch Transfers (Server Batch IO):**
  - Aggregate Throughput: Min 15.45 MB/s | Avg: **18.83 MB/s** | Max: 23.32 MB/s
  - Average Stream TTFB: Min 26.06 ms | Avg: **37.71 ms** | Max: 45.44 ms

### 3.3 Stream Admission & Disconnect Lifecycle
* **Baseline Active Streams:** 0
* **Active Streams While Gated Stream Active:** 1
* **Overload 429 Response Verified:** Concurrent request when limit saturated returned HTTP 429 with `Retry-After: 5` and `Cache-Control: no-store`.
* **Client Disconnect Test:** Client closed TCP socket mid-stream.
* **Active Streams After Disconnect:** **0** (permit cleanly reclaimed).
* **Server Health Post-Disconnect:** `UP (200 OK)`.

### 3.4 Monitored Filesystem Snapshot Audit
* **Scope:** `backend/springboot/target/test-media`
* **File 1 (`synthetic/feature_test.mp4`):** 137,961 bytes | SHA-256: `4937606abe951b1c7c3f97cb0a0bacc2adb8ee8ed0efa56d0115fdf6873d80d9` (Unchanged)
* **File 2 (`synthetic/trailer_test.mp4`):** 45,095 bytes | SHA-256: `56c4ad574057a4184b9930bde1d552baaa6f26ffad3e8a1f0c72c4909677f3e7` (Unchanged)
* **File 3 (`synthetic/walkthrough_feature.mp4`):** 303,333 bytes | SHA-256: `121eda278647dc6f48210bf0f2ca54299770d02d7022b80a94309cc440ba8389` (Unchanged)
* **Total Mutations Detected:** **0** (Strict read-only storage verified).

---

## 4. Honest Technical Limitations

1. **Local Loopback vs WAN Streaming:**
   Benchmarks were executed over local loopback TCP. Loopback network latency is typically under 10 ms for established sockets. Production WAN streaming will experience higher latency governed by client network round-trip time (RTT), packet jitter, and edge CDN topology.
2. **Batch Transfers vs Human Viewers:**
   The 3-stream concurrency test measures Spring Boot's iterative chunked IO transfer throughput under concurrent socket demand. It is explicitly labeled as a server batch IO benchmark, not an emulation of 3 concurrent human viewers consuming video at playback bitrate.
3. **Storage Mutation Scope:**
   Read-only verification is strictly scoped to the backend's designated test-media root directory. OS-wide filesystem writes (such as Chrome browser disk cache or OS temporary paging) are not audited without kernel-level system tracing.
4. **Google Drive External Dependency:**
   Google Drive streaming remains in `BLOCKED_EXTERNAL_INPUT / NOT_IMPLEMENTED` status because mounting or authenticating with Google Drive requires external OAuth credentials and rclone daemon installation, which are not present in this local automated test environment.

---

## 5. Verification Commands and Results

| Command | Working Directory | Result | Notes |
|:---|:---|:---:|:---|
| `mvnw.cmd test` | `backend/springboot` | **43/43 PASS** | Bare Maven build (Exit 0) |
| `mvnw.cmd test "-Dspring.profiles.active=test"` | `backend/springboot` | **43/43 PASS** | CI profile with isolated H2 DB (Exit 0) |
| `npm test` | `frontend` | **70/70 PASS** | Node 26 active environment (Exit 0) |
| `npx --package=node@20.20.2 node --test ...` | `frontend` | **70/70 PASS** | Node 20 LTS CI runtime compatibility (Exit 0) |
| `npx tsc --noEmit` | `frontend` | **0 ERRORS** | Full TypeScript strict verification (Exit 0) |
| `node docs/reviews/repro/M4_F01_descriptor_failure.cjs` | Root | **PASS** | Reviewer descriptor failure repro check (Exit 0) |
| `node scripts/compute_build_bytes.cjs` | Root | **PASS** | Dynamic `/movies/[id]` bundle: 143,249 B $\le$ 143,360 B |
| `node scripts/run_m4_media_walkthrough.cjs` | Root | **EXIT 0** | End-to-end browser walkthrough + benchmarks |
| `git apply --check -R docs/reports/M4_F02.patch` | Root | **VERIFIED CLEAN** | Patch cleanly applies and reverses |

---

## 6. Deliverable Artifacts

- **Report:** `docs/reports/M4_F02_REPORT.md` (this document)
- **Status Metadata:** `docs/reports/M4_F02_STATUS.json`
- **Git Patch:** `docs/reports/M4_F02.patch`
- **Manifest:** `docs/reports/M4_F02_MANIFEST.json`
- **Walkthrough Evidence:** `docs/reports/m4_f02_benchmark_results.json`
- **Screenshots:**
  - `docs/reports/screenshots/M4_F02/01_desktop_playback_playing.png`
  - `docs/reports/screenshots/M4_F02/02_desktop_seek_near_end.png`
  - `docs/reports/screenshots/M4_F02/03_desktop_retry_recovery.png`
  - `docs/reports/screenshots/M4_F02/04_mobile_playback_375px.png`

All source files are now **FROZEN**. Ready for Codex review.
