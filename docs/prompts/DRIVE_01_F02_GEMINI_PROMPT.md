# DRIVE-01-F02 — Close three remaining review groups, fast parallel execution

taskId: DRIVE-01-F02
promptVersion: 4
reviewedCheckpoint: DRIVE-01-F01-CHECKPOINT-01
branch: dev; manual handoff; automation paused

Read docs/reviews/DRIVE_01_F01_REVIEW.md. G1 remains REQUEST CHANGES, G2/G3 external blocked. D3/D4 native launch checks on PS7, D5 fresh-root browser/hash evidence and D6 real-junction mapping now pass; preserve those fixes. Only F1 resource lifecycle, F2 complete ownership verification and F3 exact PS5.1 execution remain. No new features or repeated architecture rewrite.

User prioritizes speed AND quality, with ample quota/RAM/CPU but limited disk. Use six real agents if slots permit; state actual slots/IDs. Parent publishes resource ownership and process identity contracts immediately, dispatches independent tasks in parallel and integrates after handoffs. No file collisions or concurrent shared Maven/Next builds. Run targeted tests during work, then one necessary final regression round; rerun only when a new change/failure warrants it. Finish when verified, do not pad45–60minutes.

| Agent | Exclusive scope |
| --- | --- |
| A — IO ownership implementation | Production DriveIoExecutor.java, DriveSeekableByteChannel.java, DriveMediaStorageAdapter.java and new storage helpers; controller/service only when lifecycle integration requires it. Fix late-open disposal and nonblocking-to-caller cleanup with bounded actual resource occupancy. Announce API to C/D. No test files owned by C/D. |
| B — Windows ownership implementation | scripts/drive/stop_drive.ps1, status_drive.ps1, mount_drive.ps1 and shared verifier helper if warranted. Full required state, exact process identity and mount invocation, fail closed including every launch-time cleanup path. No tests owned by E. Do not rewrite working argv formatting/readiness logic unnecessarily. |
| C — late-resource regression tests | New DriveLateOpenLifecycleTest.java. Production executor/adapter paths: open finishes after timeout, exactly-once close, timely open stays usable, timeout/completion race, repeated cycles no leaked channel. Independent tests; no production edits. |
| D — stalled cleanup regression tests | New DriveCleanupDeadlineTest.java, affected existing DriveIoDeadlineTest.java if required. Interruption-ignoring FileChannel read and close, production wrapper/controller end-to-end caller deadline, true resource accounting and local isolation. Model all latches explicitly, always release/join owned test workers. No production edits. |
| E — Windows regressions and encoding | scripts/drive-tests/*, scripts/drive/test_drive_tooling.ps1. Fix exact powershell.exe -File5.1 parsing and verify real supported runners separately. Tests missing EACH required identity field, wrong mount/argv, same-name process, mismatched executable/start/session and launcher cleanup; mock all process signals. Native argv tests remain real harmless child recorder, never actual mount. No edits to B files. |
| F — integration evidence/docs | docs/contracts/DRIVE_STORAGE_CONTRACT.md, Google Drive runbooks/performance plan and new evidence under DRIVE_01_F02; parent delegates the one shared browser run to F after stable compilation. Audit claims against actual runners/current source, clearly label fixture vs Drive. Do not alter already passing harness or frozen artifacts just to create work. Report targeted evidence gaps early. |

Java files use existing backend/springboot src/main/java or src/test/java package paths. Parent owns final report/status/patch/manifest and coordinates any required package/config changes. Before changing ownership announce it and wait for prior writer handoff. No agent restarts or user/Gemini process kills.

## F1 required behavior

Timeout/cancellation must not orphan successfully acquired resources. Use an explicit ownership/disposal handshake around asynchronous open and timeout races. Late channel closure must execute exactly once; caller-owned successful channels must not be closed by a racing timeout path. Do not simply add Future.cancel or rely on GC.

Read timeout alone is insufficient when try-with-resources immediately blocks on delegate.close. Ensure requests can terminate promptly while actual kernel IO/cleanup remains bounded and accounted for until it really completes. Include position/size/close in the lifecycle analysis, document which can block and how caller latency/resource bounds are enforced. No unbounded per-close threads/queues, no early decrement while physical cleanup still runs. Keep successful streaming efficient and preserve seek/Range/private policy/local isolation. Hard cancellation of WinFsp is not guaranteed; document that limit rather than claiming it solved.

Use production classes in tests, with deterministic fake FileChannel/native IO that ignores interrupts. Reviewer DRIVE_F01_late_open.java and DRIVE_F01_channel_close.java show current bugs. Leave Codex reviewer files unchanged; add regression expectations for fixed behavior and explain old repro-detector outputs after fix. Test both success and cancellation/timeout races, and release all test-owned latches.

## F2/F3 required behavior

All state identity fields used by the declared ownership contract must be required before any Stop-Process. No missing-session bypass, default identity that turns partial state into ownership, or a permissive multi-millisecond/multi-second mismatch window instead of exact recorded process identity. Validate intended mount invocation against live process identity using a trustworthy source/owned-process handle strategy; unverifiable input fails closed with state retained. Apply shared validation consistently to launcher failure/timeout cleanup as well as stop/status. Same binary/path alone does not establish which mount was launched.

No real kill/mount/install/OAuth in tests. Use mocks for all termination paths. Preserve process state on rejection. Check native argv preservation regressions without redoing already passing formatter. Exact scripts must parse/run under powershell.exe5.1 and pwsh7 using -File, with distinct output evidence. Resolve encoding safely (e.g. appropriate script encoding or compatible literals); don't validate only a manually UTF8-decoded ScriptBlock. Artifacts must distinguish actual runner versions/pass counts/limitations.

## Integration and handoff

Backend101-pass, mapping9-pass, frontend83-pass and browser fresh-root success are baseline. Run backend full test profile once after source stabilizes; targeted lifecycle tests first. Frontend source/build unchanged means prior frontend evidence may be labeled prior; do not waste time repeating unaffected build/benchmark. Re-run mapping/native argv only as needed by changed files, and one fresh-root browser smoke if backend streaming changes. All outputs F02-specific, fixture/temp/H2/ports isolated, no overwrite of original or F01 evidence.

Artifacts docs/reports/DRIVE_01_F02_REPORT.md, DRIVE_01_F02_STATUS.json, DRIVE_01_F02.patch, DRIVE_01_F02_MANIFEST.json; evidence docs/reports/drive/DRIVE_01_F02/. Status new checkpoint/runId, promptVersion4, ready_for_review/sourceFrozen=true, gate provenance truthful. Generate patch from actual pre-edit source baseline and validate reverse; finalize before SHA256/bytes. Parent finalizes only after all writers stop. Codex-owned prompts/control/review/repros are read-only, excluded from implementation.

Preserve existing changes and backend/fastapi/.env.example. No live DB, AI/FastAPI/Qwen/GPU/model, OS changes, Drive installation/OAuth/mount, deployment or auto-monitor. No new branch/commit/push/reset. Freeze and end the turn for manual Codex review. Do not invite user to run unsafe setup scripts before G1 review closes.
