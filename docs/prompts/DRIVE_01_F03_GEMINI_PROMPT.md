# DRIVE-01-F03 — Two residual lifecycle/identity cases, six parallel agents

taskId: DRIVE-01-F03
promptVersion: 5
reviewedCheckpoint: DRIVE-01-F02-CHECKPOINT-01
branch: dev; manual handoff; automation paused

Read docs/reviews/DRIVE_01_F02_REVIEW.md. Fix ONLY R1/R2, residual cases of F1/F2. F3 and existing successful browser/argv/mapping fixes are closed: preserve them. G1 not accepted; G2/G3 external blocked. No feature expansion or architecture rewrite for unrelated concerns.

User wants speed plus quality; ample quota/RAM/CPU, limited disk. Dispatch six independent agents if slots permit; record actual slots/IDs and queue honestly if fewer. Parent announces contracts immediately, integrates after handoffs, coordinates a single shared build/test round. No overlapping writers or redundant full builds. Do not pad runtime or wait for unrelated agents before starting independent work.

| Agent | Exclusive scope |
| --- | --- |
| A | Production DriveSeekableByteChannel/DriveIoExecutor and adapter only as needed. R1: all outstanding operation ownership, bounded cleanup admission and disposal under timeout/interruption races; no direct native close on caller fallback. |
| B | scripts/drive stop/status/mount and shared ownership verifier if appropriate. R2: exact creation identity and trustworthy live invocation/owned-handle verification, same fail-closed policy in all termination paths. Preserve working formatter/readiness. |
| C | New DriveMetadataCleanupLifecycleTest.java. Production position/size blocked then timeout then try-with-resources; verify caller exits promptly, worker occupancy retained until release/close and exactly-once cleanup. No production edits. |
| D | New DriveCleanupAdmissionRaceTest.java. Saturated cleanup with no active read, late open/completion/interruption races, physical cleanup that ignores interrupts; bounded actual capacity, no leaks and timely-open usability. No production edits. |
| E | scripts/drive-tests security/toolkit regression files and test helpers. Near-time PID reuse (200ms mismatch), exact-time but wrong invocation, missing/unreadable live identity, valid helper-created process, launcher cleanup and status consistency. Mock every process signal; exact -File PS5.1/7 runners, preserve encoding fixes. No production script edits. |
| F | New evidence/docs under DRIVE_01_F03; targeted independent checks and the single browser smoke delegated by parent after compilation. Document resource/identity contract limits truthfully. No edit to passing harness just to create work; never overwrite frozen outputs. |

Parent owns artifacts and any integration cross-file changes after owner handoff. Java files use current backend src/main/java or src/test/java packages. Agent B publishes identity test seams early to E; A publishes lifecycle contract to C/D immediately. Files from old agents are frozen before reassignment. Do not kill or restart user/Gemini processes.

## R1 acceptance

activeWorkerReads is insufficient: a blocked position/size occupies a worker too. After its caller deadline, cleanup must not reject into synchronous delegate.close on the caller. Zero active reads does not prove close is safe. Own every in-flight channel operation and reserve/account bounded cleanup capacity until physical completion. Do not spawn unlimited cleanup threads, drop close requests, decrement early or wait forever on the request thread. Preserve successful-stream throughput and existing read timeout behavior.

Audit executeOpen and generic AutoCloseable-returning task timeout/interruption races: caller-side disposal must not block the caller after a deadline. Late physical close must occur exactly once, within bounded ownership/accounting; resources delivered normally stay open for their caller. Native WinFsp hard cancellation is not guaranteed; enforce caller/resource bounds and document actual limitations.

Use deterministic latches and production wrappers/controller for tests, not executor-only simulations. Reviewer DRIVE_F02_position_close.java reproduces current failure; leave reviewer code untouched and add corrected regression expectations. Always release test latches/join owned workers, cover metadata/no-read close and occupied pool, repeat canceled cycles to prove no leaked channel/worker capacity.

## R2 acceptance

Use exact process creation identity from the recorded handle/source with preserved precision; no tolerance that permits a different process. Compare intended mount invocation to trustworthy live identity (or use a verifiably retained owned-process handle strategy). Nine nonempty fields alone do not establish ownership. A process running another remote/mount must never be signaled even if name/path/session match. Any unavailable identity fails closed, preserves state and explains the blocker. Shared policy across stop/status/mount cleanup avoids drift. Account for PID reuse between validation and signal; prefer signaling a validated retained process handle rather than resolving an unchecked PID again.

No real rclone launch/kill or mount/install/OAuth in tests. Native argv recorder may be a harmless owned child; all termination tests must intercept every possible signal. Confirm legitimate helper-created state is stoppable, not only negative tests that make all stop calls reject. Exact PowerShell5.1/7 -File invocations and runner-specific evidence.

## Finish / verification

Current109 Maven pass and PS5/7 comprehensive28/security30 pass are baseline, not proof these residual repros are fixed. Run targeted C/D/E checks first, then one backend full test-profile suite and one fresh-root browser smoke if streaming source changes. Frontend/mapping remain prior evidence unless changed; don't repeat unrelated builds. F03 evidence only, isolated H2/temp roots/free ports, finite waits. Don't alter reviewers to obtain green output; old bug detectors may fail their old assertions after a fix and must be interpreted honestly.

Artifacts docs/reports/DRIVE_01_F03_REPORT.md, DRIVE_01_F03_STATUS.json, DRIVE_01_F03.patch, DRIVE_01_F03_MANIFEST.json; evidence docs/reports/drive/DRIVE_01_F03/. New run/checkpointId, promptVersion5, state ready_for_review, sourceFrozen=true, truthful gates. Actual pre-edit baseline snapshot; Git-generated patch/reverse check, finalize before SHA256/bytes. Parent finalizes after all writers hand off, then freeze/end turn for Codex review.

No Codex-owned prompts/control/reviews/repros edits; preserve frozen old artifacts and unrelated backend/fastapi/.env.example. No commit/push/reset/branch/deploy, live DB, AI/FastAPI/Qwen/GPU/model, OS settings, install/OAuth/real mount, polling/monitor. G2/G3 setup follows only after G1 closes independently.
