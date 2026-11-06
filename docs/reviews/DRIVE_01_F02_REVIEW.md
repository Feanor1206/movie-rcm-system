# DRIVE-01-F02 — Independent review

2026-10-15. **REQUEST CHANGES: two residual P1 cases in F1/F2.** F3 is closed. G1 remains unaccepted; G2/G3 remain BLOCKED_EXTERNAL_INPUT. M4 local acceptance is unaffected. Codex changed only review/repro/prompt/control material; no actual Drive, install/OAuth/mount, live DB or application edits.

Checkpoint DRIVE-01-F02-CHECKPOINT-01, promptVersion4, explicitly frozen/ready_for_review. All29 manifest entries match hash/byte length before and after verification; reverse patch check passes. Frozen original/F01/F02 artifacts are preserved.

## Independently passed

- Exact Spring test-profile Maven: **109/109 pass**, exit0, isolated H2, local JDK25 targeting17. No remote CI/bare Maven claim.
- Comprehensive **28/28**, security **30/30** on each of Windows PowerShell5.1 and PowerShell7 using actual -File invocations. The5.1 parsing finding is closed; baseline14-pass is previous evidence, not a newly repeated run.
- Unchanged late-open reviewer repro: lateOpenChannelStillOpen=false, actualWorkers=0. Missing-identity repro: terminationRequestedWithMissingIdentityFields=false. These specific bugs are fixed.
- Handed fresh-root Spring/Chrome walkthrough: **exit0**, with only evidence/root locations redirected. Descriptor offline/recovery, decoded playback, seek, pause/retry, mobile controls, HTTP benchmarks and full snapshot parity pass. Fixture provider=drive is still a local directory, not real Drive. Output: C:\Users\Admin\AppData\Local\Temp\codex-drive-f02-browser-* (exact path in browser.log).
- Unchanged frontend and mapping were not rerun; prior evidence remains labeled prior.

## R1 — P1: non-read IO timeout can still fall back to blocking caller close

DriveSeekableByteChannel.java:198–214 defers cleanup only while activeWorkerReads>0. position(newPosition) and size run on the same bounded IO executor but are not counted in activeWorkerReads. If a position operation stalls, its metadata deadline expires with the worker still busy. try-with-resources then calls close; the cleanup pool is full, so closeDelegateAsyncOrDirect catches rejection and calls delegate.close directly on the request thread. Native close may wait for that outstanding operation, undoing the caller deadline and retaining the stream permit.

Reviewer DRIVE_F02_position_close.java uses the production channel/executor and deterministic FileChannel position/close operations waiting on a test latch. Output: positionDeadlineFired=true, callerStillBlockedInClose=true, ioWorkers=1. It releases the latch and joins all test-owned work. This is controlled native-IO fault simulation, not a claim that actual WinFsp was disconnected. It is the same F1 lifecycle requirement, not a new feature.

Fix ownership for all outstanding channel operations and cleanup admission pressure; no direct caller close fallback merely because no read is active. Preserve actual occupancy until IO and physical cleanup finish, without unbounded close threads/queues. Audit analogous caller-side closeResourceOnce/AutoCloseable-disposal paths in DriveIoExecutor timeout/interruption handling: cleanup must not move blocking IO back to the caller in a completion race. Add production-path seek/size/close and saturated-cleanup tests; preserve timely-open usability and exactly-once disposal.

## R2 — P1: process creation mismatch still accepted; invocation fields only checked for presence

stop_drive.ps1:406–413 accepts a creation-time difference below500ms. Requiring nine fields prevents missing-state bypass but mountPoint/remoteTarget/arguments are not compared to the live invocation. The same permissive start comparison is in launch-time cleanup (mount_drive.ps1:425). This still contradicts F2's exact process identity and consistent mount ownership requirements.

Reviewer DRIVE_F02_stop_reused_identity.ps1 provides all nine fields. The mocked live process has the same name/path/session/PID, but starts200ms later and runs unrelated:other onY: instead of expected:media onZ:. Production stop requests termination and reports STOPPED. Process signals are mocked; no actual process is killed. The mocked live command line is available, but the script never checks it.

Use exact recorded process creation identity, preserving actual timestamp precision, and a trustworthy invocation/owned-handle check instead of merely nonempty fields. Verification failure or unreadable live identity must retain state and refuse signals. Reuse one policy for stop/status and launch cleanup, including failure/race handling. Test near-time PID reuse, mismatched mount invocation and legitimate helper-created processes; don't replace500ms with another mismatch tolerance.

## Evidence / next assignment

docs/reviews/evidence/DRIVE_01_F02 contains independent Maven/PS5/PS7/browser logs, old repro outputs, new residual repros and final manifest verification. Reviewer helper files under docs/reviews/repro/DRIVE_F02_* are diagnostic detectors, not tests to edit for a green exit.

DRIVE-01-F03 is scoped only to R1/R2. Preserve F3, native argv, missing-state rejection, fresh-root evidence and mapping fixes. Six agents can parallelize the two implementations and their independent tests; no need to redo unrelated work or rerun unchanged frontend builds. Manual handoff, automation paused. A checkpoint push to dev is not acceptance or deployment.
