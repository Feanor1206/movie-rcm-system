# DRIVE-01-F03 — Independent review

2026-10-15. **REQUEST CHANGES: one remaining P1 cleanup-admission/lifetime finding.** The prior seek timeout and process identity repros are closed. G1 is not yet accepted. M4 local remains accepted; real mount/playback gates are separate.

Checkpoint DRIVE-01-F03-CHECKPOINT-01 / promptVersion5 is explicit frozen/ready_for_review. All26 manifest entries match SHA256/bytes before and after verification; reverse patch check passes. No frozen Gemini artifacts or application code were changed by Codex.

## Verified progress

- Exact Spring test-profile Maven: **123/123 pass**, isolated H2, local JDK25 targeting17; remote CI/bare Maven not rerun.
- Windows PowerShell5.1 comprehensive **28/28**, security **35/35**; PowerShell7 security **35/35**, actual -File executions with separate outputs. Unaffected baseline/frontend/mapping are prior evidence, not fresh runs.
- Old production seek/close detector now prints positionDeadlineFired=true, callerStillBlockedInClose=false, ioWorkers=1. Its old bug-presence assertion exits1 because the stall is fixed, not because the application failed. Late-open detector reports no leaked handle and workers0.
- Old mocked process reuse detector now reports terminationRequestedDespiteCreationAndInvocationMismatch=false. Schema-required fields and live command-line checks are present; this closes the two concrete prior identity repros. No actual user/rclone process was killed. Real helper-created mount/stop still needs operational validation.
- Reviewer fresh-root browser run uses the handed production assertions, redirecting only evidence and fixture paths. Exit0: decoded playback/seek/retry, mobile controls, HTTP checks and snapshot parity pass. Fixture playback is distinct from real Drive.

## R1 — P1: bounded cleanup queue silently discards resource ownership

DriveIoExecutor.java creates cleanupExecutor with LinkedBlockingQueue(256) and **DiscardOldestPolicy**. When the main IO pool is occupied and fallback cleanup backs up, submitting another close silently removes a previously queued close task. executeCleanupAsync also returns without retaining resources on shutdown and swallows submission failures. DriveSeekableByteChannel marks delegateClosed before submission, so a discarded resource has no owner left to retry closing it.

The queue bounds memory, but dropping cleanup is not safe disposal. The fallback lane is also absent from actualOutstandingWorkers, which therefore cannot be interpreted as total pending physical IO/cleanup or proof all resources are released.

Reviewer DRIVE_F03_cleanup_pressure.java uses the production executor and300 actual read-only FileChannel handles on one tiny temporary file. It occupies the main worker, temporarily blocks cleanup, submits300 closes, then releases cleanup. Output:

    submittedCleanup=300 trackedMainWorkers=1
    closedAfterRelease=258 leakedOpenHandles=42

The reviewer closes all remaining handles and releases/joins owned work afterward. This is controlled cleanup-pressure injection through the actual production API, not a claim that300 real Drive viewers were run. It demonstrates ownership loss precisely in the admission-pressure requirement from F1/R1. Current tests cover one fallback close, not queue overflow.

Replace silent discard with an ownership-preserving bounded lifecycle. Reserve cleanup capacity/resource ownership before accepting opens where necessary; full admission must reject before taking unowned resources, not discard accepted close obligations. Caller must still return promptly, without synchronous kernel close fallback or unlimited thread/queue growth. Account for physical cleanup, queued obligations and resource permits until actual close completes. Shutdown/rejection paths must explicitly preserve or drain accepted ownership; do not solve this by raising256 or swallowing rejection. Add stress tests above capacity and conservation checks (accepted resources = closed resources + explicitly still-owned resources).

## Real Drive readiness update

The frozen Gemini status still says installation/OAuth/folder are missing. Those prerequisites have since been completed outside coding: rclone1.75.1, WinFsp2.1 installed, cinema-drive authenticated with drive.readonly, target folder VideoDieppie metadata verified. No mount has been started. Folder was empty; the requested YouTube download returned403, so no uploaded test video exists yet. G2 is pending reviewed mount execution; G3 additionally needs a test MP4 and real playback evidence. Never copy token/config into reports/Git or claim these gates from fixture success.

## Evidence / next

docs/reviews/evidence/DRIVE_01_F03 contains independent Maven/PowerShell/browser/repro logs, metrics and final hash verification. Reviewer helpers under docs/reviews/repro remain read-only to Gemini. No OS/GPU/live DB or credentials were changed during this code review.

DRIVE-01-F04 is scoped only to cleanup saturation/shutdown ownership. Preserve previous fixes and avoid unrelated rewrites. Automation stays paused/manual; checkpoint push is not acceptance or deployment.

