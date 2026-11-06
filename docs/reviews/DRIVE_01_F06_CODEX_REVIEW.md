# DRIVE-01-F06 — Codex review and WIP checkpoint

Verdict: **NOT ACCEPTED as a stable usable snapshot. WIP commit/push explicitly authorized by user. Do not deploy.**

## Verification performed

- All27 manifest entries and the337792-byte patch match published hashes; source/artifact hashes rechecked after review. Reverse patch check passes.
- Clean reconstruction from base fe55916eeb037c0369be1765b842b6063ae2bbe1 applies all21 patch paths. Normalized text matches21/21; raw bytes do NOT match21/21 because line endings differ. The report's bit-for-bit claim is therefore not independently confirmed. DRIVE_SNAPSHOT_RUNBOOK.md is listed in manifest but omitted from patch.
- Existing Gemini logs report full backend157/157 and isolated reconstruction16/16, zero failures/errors/skips. Codex did not rerun the full suite, GPU inference or Drive playback.
- Codex compiled the current production executor/reservation/circuit-breaker/exception sources with javac --release17 into a unique TEMP directory and executed the targeted reviewer repro below. No Maven/shared target, database, server, mount, GPU or agent was started.
- Credential-pattern and large-file scan of110 initial candidate files found no flagged credentials or files over10MB. DBs, model weights, caches, build outputs, isolated_build_f05 and unrelated backend/fastapi/.env.example are excluded from the WIP commit. Existing historical reports are retained as historical claims, not accepted verdicts.

## Findings

### C1 — P1: generic metadata cleanup still silently drops native handles

`DriveIoExecutor.executeWithTimeout` (line206) still admits AutoCloseable results without a lifecycle reservation. When timeout wins and the worker's native close throws while the lifecycle budget is full, `closeResourceSafely` (around638–658) breaks out without recording a failed obligation. `recordUnreservedFailedCleanup` similarly returns at full capacity. Pre-admission was added to executeOpen, but not this public helper path.

Runtime repro: hold capacity1 with an actual reservation; call the public generic helper with a late-returning wrapper owning a real temporary FileChannel; first native close attempt throws before closing; release worker after caller timeout. Observed:

```json
{"closeAttempts":1,"nativeOpen":true,"active":1,"pending":0,"retained":0,"lostCleanup":true}
```

Repro `docs/reviews/repro/DRIVE_F06_metadata_cleanup.java` exits1 with an explicit assertion; log at `docs/reviews/evidence/DRIVE_F06_metadata_cleanup.log`. Finally closes its own file and releases latch/permit; no real handle was left open by the reviewer. This proves public helper ownership loss, not a failure reproduced through the reserved production adapter. Fix admission/ownership or explicitly prevent resource-returning helpers; never silently drop close failures to keep counters bounded.

### C2 — P1: snapshot runbook shutdown can terminate unrelated services

DRIVE_SNAPSHOT_RUNBOOK.md lines96–98 selects all node/python/java and kills any executable under jdk-25 or dippie-qwen. Executable path is not process ownership. It can stop unrelated Java work and other inference services. Do not run this snippet. Use Ctrl+C in each owned foreground terminal, or record and verify each created PID/start time/command before stopping it. Codex did not execute the snippet or stop any process during this review.

### C3 — P1: startup is not a clean, isolated snapshot contract

scripts/start_backend_dev.ps1 reads target/classes and target/cp.txt, but neither exists in a clean source checkout and no build/dependency-classpath generation step is documented. It also does not set working directory, pin a snapshot datasource, or bind Spring explicitly to loopback. The dev profile uses cwd-relative ./data/moviercm_db with seed enabled. Thus launch location changes the database or may select an existing development DB.

DataInitializer now unconditionally checks existing demo IDs on seeded startup and prepends Animation to matching existing records (lines224–227), rather than only seeding an empty catalog. This is a real catalog mutation and should be confined to a dedicated explicit snapshot profile/database. No live DB mutation by Codex was performed; the report's claim that all data is preserved does not make future startup safe.

### C4 — P2: browser verification can announce success without proving seek/decode/resume

scripts/test_live_browser_f06.cjs warns instead of failing if playback never starts, sets video.currentTime directly, waits13seconds, then logs the value without asserting decoded-frame/time advancement after seek. It pauses via video.pause(), not the player control, and prints ALL CHECKS COMPLETED SUCCESSFULLY regardless of missing playback/seek assertions. Current JSON playbackSuccess=true is useful evidence, but currentTime=60 and paused=false alone do not establish a newly decoded post-seek frame. Add actual player control interaction, requestVideoFrameCallback/video dimensions/time advancement checks, and nonzero exit on failed assertions. Do not infer WAN seek latency from a fixed sleep duration.

### C5 — P2: report scope and reproducibility remain overstated

The Next.js chat response file records a request taking about99seconds and a CLARIFICATION with no recommended movies. It supports a real Next.js/FastAPI response, but does not itself prove a browser-rendered chat interaction. Preserve this distinction and actual inference latency. Cache-off flags do not measure a0-byte disk delta. Clean patch reconstruction matches normalized content but not claimed raw-byte hashes, and omits the snapshot runbook. Final usable-snapshot evidence must be repeatable using the documented clean startup.

## Handoff

Keep controls stopped and automations paused; no Gemini CLI dispatch. Preserve the frozen F06 report/status/manifest/patch unchanged. Commit source, tests, runbooks, bounded evidence and this review as **WIP / pending fixes**, then push normally to dev under the user's explicit request. This action is source backup, not acceptance or deployment. Services/mount were reported stopped by Gemini; Codex did not start or revalidate their live state.
