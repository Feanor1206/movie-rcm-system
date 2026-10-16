# DRIVE-01-F05 FINAL VERIFICATION REPORT & SNAPSHOT HANDOVER

**Milestone:** DRIVE-01  
**Task ID:** `DRIVE-01-F05`  
**Run ID:** `DRIVE-01-F05-CHECKPOINT-FINAL`  
**Date:** 2026-10-16  
**Branch:** `dev`  
**Review Target:** Codex  
**Status:** **READY FOR CODEX ACCEPTANCE / 100% VERIFIED**

---

## 1. Executive Summary

This report concludes task `DRIVE-01-F05` by providing comprehensive cryptographic evidence, test execution logs, and end-to-end browser walkthroughs demonstrating:
1. **Full resolution of all residual cleanup concurrency findings** (`F05-01` through `F05-04`), verified by independent code audit (Agent E: PASS) and zero test regressions.
2. **100% green test execution** in an isolated build lane: 154 / 154 full backend suite tests passed (`GEMINI_FULL_BACKEND_TEST_RUN_F05.log`), including 111 Drive regression tests, 8 auth/library integration tests, and 8 seed/policy tests.
3. **End-to-end real Google Drive video playback** from actual cloud storage (remote `cinema-drive`, folder `1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ`, WinFsp read-only mount on drive `X:`, video `videoplayback.mp4` of 29,209,556 bytes):
   - HTTP HEAD (200) and HTTP Range (206) byte-for-byte verification.
   - Headless Chrome decoded frame playback (1080p, 445.8s duration).
   - Three UI timeline seeks (25%, 60%, and 94% near-end) verified with `requestVideoFrameCallback`.
   - UI pause/resume and mobile responsive touch controls (>= 44x44px).
4. **GPU CUDA inference of the fine-tuned Qwen model** (`Qwen/Qwen3-4B` base model + `ai/models/qwen3-4b-phase23-lora` adapter) running on an NVIDIA GeForce RTX 3050 Laptop GPU via BitsAndBytes 4-bit NF4 quantization in the `dippie-qwen` conda environment.

---

## 2. Technical Breakdown of Concurrency Fixes

### 2.1 Issue 1: Monotonic Disposal State Machine (F05-01)
- **Problem:** Resetting `disposalGate` boolean flag after a failed disposal dispatch allowed a worker checking the gate to unblock and terminate without assuming closure duty.
- **Solution:** Replaced boolean gate with an `AtomicInteger disposalState` monotonic state machine:
  - `DISPOSAL_UNCLAIMED (0)` $\to$ `DISPOSAL_CALLER_DISPATCHING (1)` $\to$ `DISPOSAL_DISPATCH_ACCEPTED (2)` | `DISPOSAL_DISPATCH_FAILED (3)` $\to$ `DISPOSAL_WORKER_CLAIMED (4)` | `DISPOSAL_RETAINED (5)`.
  - The worker outer `finally` block and caller fallback CAS arbitrate ownership so neither thread abandons open handles.

### 2.2 Issue 2: Conserved Pending Capacity & Dynamic Permit Acquisition (F05-02)
- **Problem:** Unreserved `dispatchLateDisposal` retained failed cleanups without charging pending permit; retry could decrement pending below zero (`-1`) or admit beyond capacity.
- **Solution:**
  - Encapsulated `volatile boolean chargesPending` inside `RetainedFailedCleanup`.
  - In `submitRetryTask`, if `chargesPending == false`, the executor dynamically acquires 1 pending permit in `lifecycle` bounded by `cur.getTotal() < cleanupQueueCapacity`.
  - `decrementPendingAndCheckShutdown` clamps at 0 (`Math.max(0, cur.getPending() - 1)`).

### 2.3 Issue 3: Truthful Channel Retry Evaluation (F05-03)
- **Problem:** `DriveSeekableByteChannel.retryClose()` checked reservation failed state only, falsely reporting `true` if an unreserved delegate failed physical close.
- **Solution:** `retryClose()` checks `ioExecutor.hasFailedCleanup(delegate)` before checking `delegateClosed.get()`, guaranteeing non-blocking retry dispatch and truthful return status.

### 2.4 Issue 4: Concurrency Invariants & Admission Conservation (F05-04)
- **Invariants Maintained:**
  - $0 \le \text{activeResourceReservations} \le \text{cleanupQueueCapacity}$
  - $0 \le \text{pendingCleanupObligations} \le \text{cleanupQueueCapacity}$
  - $\text{active} + \text{pending} \le \text{cleanupQueueCapacity}$
  - Zero caller-thread native close on caller timeout or shutdown.
  - Exactly-once physical disposal via atomic CAS on channels and `markInFlight()` on retries.

---

## 3. Test Evidence Summary

| Suite / Test Target | Tests Run | Failures | Errors | Result | Log Artifact |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Full Backend Maven Test Suite** | 154 | 0 | 0 | **PASS** | `docs/reports/drive/GEMINI_FULL_BACKEND_TEST_RUN_F05.log` |
| **Drive Regression Suite** | 111 | 0 | 0 | **PASS** | `docs/reports/drive/GEMINI_DRIVE_REGRESSION_TEST_RUN_F05.log` |
| **Auth & Library Integration Suite** | 8 | 0 | 0 | **PASS** | `docs/reports/drive/GEMINI_AUTH_TEST_RUN_F05.log` |
| **Seed & Policy Verification Suite** | 8 | 0 | 0 | **PASS** | `docs/reports/drive/GEMINI_FULL_BACKEND_TEST_RUN_F05.log` |
| **Drive Tooling Comprehensive** | 28 | 0 | 0 | **PASS** | `scripts/drive/test_drive_tooling.ps1` |
| **Independent Code Audit (Agent E)** | 4 files | 0 | 0 | **PASS** | `docs/reports/drive/DRIVE_01_F05/CROSS_REVIEW.md` |
| **Real Drive E2E Chrome Playback** | 1 session | 0 | 0 | **PASS** | `docs/reports/drive/DRIVE_01_F05/real_drive_results.json` |
| **Fine-Tuned Qwen GPU Integration** | 2 tests | 0 | 0 | **PASS** | `backend/fastapi/tests/test_serving_integration.py` (Exit 0) |

---

## 4. Real Google Drive End-to-End Playback Evidence

### 4.1 Mount Configuration & Identity
- **Remote Target:** `cinema-drive,root_folder_id=1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ:`
- **Mount Point:** `X:`
- **Process ID:** `17024` (verified via `scripts/drive/status_drive.ps1`, status `MOUNTED`)
- **Flags:** `--read-only --vfs-cache-mode off --buffer-size 32M --vfs-read-chunk-size 8M --vfs-read-chunk-size-limit 32M --vfs-read-chunk-streams 0 --dir-cache-time 72h --poll-interval 15s --attr-timeout 1s`
- **Target File:** `X:\videoplayback.mp4` (exact size: 29,209,556 bytes)

### 4.2 Playback Results (`docs/reports/drive/DRIVE_01_F05/real_drive_results.json`)
- **HTTP HEAD:** Status 200, Content-Length 29,209,556, Accept-Ranges: bytes.
- **HTTP Range Requests:** 3 byte-range slices verified byte-for-byte against direct file reads (`status: 206`):
  - Slice 0: bytes 0–65535 (64 KiB)
  - Slice 1: bytes 14,604,778–14,670,313 (64 KiB, middle)
  - Slice 2: bytes 29,144,020–29,209,555 (64 KiB, end)
- **Decoded Playback:**
  - Width: 1920, Height: 1080 (1080p Full HD)
  - Duration: 445.8 seconds
  - Initial Decoded Playback: `presentedFrames = 35`
- **UI Timeline Seeks (HTML5 Timeline Slider Dispatch):**
  - **Seek 1 (25%):** Target 111.45s $\to$ Decoded mediaTime 111.57s, `presentedFrames = 35`
  - **Seek 2 (60%):** Target 267.48s $\to$ Decoded mediaTime 267.57s, `presentedFrames = 38`
  - **Seek 3 (94% near-end):** Target 419.05s $\to$ Decoded mediaTime 419.17s, `presentedFrames = 41`
- **Pause & Resume:** Verified via player button dispatch (`paused == true` then `paused == false`).
- **Mobile Responsive Viewport (375x667):** Touch targets for play/pause, volume, and fullscreen all verified $\ge 44 \times 44\text{ px}$.

### 4.3 Screenshots
- Desktop playback and near-end seek: `docs/reports/drive/DRIVE_01_F05/screenshots/01_actual_drive_playback.png`
- Mobile 375px responsive player: `docs/reports/drive/DRIVE_01_F05/screenshots/02_actual_drive_mobile.png`

---

## 5. Fine-Tuned Qwen Model Serving Evidence

### 5.1 Artifact Identity & Model Configuration
- **Base Model:** `Qwen/Qwen3-4B` (cached in `$env:USERPROFILE\.cache\huggingface\hub\models--Qwen--Qwen3-4B`)
- **LoRA Checkpoint:** `ai/models/qwen3-4b-phase23-lora`
  - `adapter_config.json`: PEFT version 0.20.0, r=16, alpha=32, target modules: q, k, v, o, gate, up, down.
  - `adapter_model.safetensors`: 132,187,888 bytes
  - `system_prompt_v2_2.txt`: StructuredDiscoveryIntent v1 prompt
- **Serving Environment:** `dippie-qwen` conda environment
  - Python 3.12 / PyTorch 2.6.0+cu124
  - Transformers 5.16.1 / PEFT 0.20.0 / BitsAndBytes 0.50.2
- **Hardware Placement:** NVIDIA GeForce RTX 3050 6GB Laptop GPU
  - Quantization: 4bit-nf4 with double quantization and float16 compute
  - VRAM Consumption: ~2.8 GB / 6.44 GB total VRAM

### 5.2 Live GPU Verification (`test_serving_integration.py`)
- **Health Endpoint:** status `"healthy"`, `modelLoaded: true`, `phase23AdapterLoaded: true`, `servingMode: "full"`, `quantization: "4bit-nf4"`.
- **Readiness Endpoint:** `ready: true`, HTTP 200, status `"ready"`.
- **Live Intent Generation Test:** Query `"Gợi ý cho tôi phim hoạt hình phiêu lưu trước năm 2010 không có kinh dị"`:
  - `intent_type`: `"DISCOVERY"`
  - `year_max`: `2009`
  - `include_genres`: `["Animation"]`
  - `exclude_genres`: `["Horror"]`
- Result: **2/2 tests PASS in 105.3s on CUDA (Exit 0)**.

---

## 6. How to Run the Production Snapshot

### 6.1 Prerequisites
- Windows 10/11 x64 with Java 25 / JDK 17+
- Node.js 18+
- Python 3.12 with `dippie-qwen` conda environment
- Rclone 1.75+ and WinFsp 2.1+

### 6.2 Service Launch Order
1. **Mount Google Drive (Read-Only):**
   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/drive/mount_drive.ps1 `
     -Remote "cinema-drive,root_folder_id=1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ:" `
     -RemoteSubpath "" `
     -MountPoint "X:" `
     -Execute
   ```
2. **Start Spring Boot Backend:**
   ```powershell
   cd backend/springboot
   $env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"
   .\mvnw.cmd spring-boot:run "-Dspring-boot.run.arguments=--server.port=8080 --app.media.drive-mount=X: --app.media.drive-metadata-timeout-ms=15000 --app.media.drive-read-timeout-ms=15000"
   ```
3. **Start FastAPI Qwen AI Gateway:**
   ```powershell
   cd backend/fastapi
   & "C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```
4. **Start Frontend Next.js Application:**
   ```powershell
   cd frontend
   npm run dev -- -p 3000
   ```
5. Open browser at `http://localhost:3000` to browse movies and stream video from Google Drive!
