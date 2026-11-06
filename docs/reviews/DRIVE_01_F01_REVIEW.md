# DRIVE-01-F01 — Independent review

2026-10-15. **REQUEST CHANGES: three remaining scoped groups F1–F3.** G1 is not accepted. G2/G3 remain BLOCKED_EXTERNAL_INPUT; no actual Drive/OAuth/mount was exercised. M4 local acceptance remains unchanged. Codex made no application edits.

Checkpoint DRIVE-01-F01-CHECKPOINT-01 / promptVersion3 is explicitly frozen/ready_for_review. All35 manifest entries match SHA256 and bytes before/after verification; reverse patch check passes. Frozen Gemini artifacts are preserved.

## Independently closed or improved

- Backend exact Spring test-profile Maven: **101/101 pass**, exit0, isolated H2, local JDK25 targeting17. Bare Maven and remote CI not rerun this review.
- D1 provider admission is now separate; generic IO tasks have bounded physical-worker accounting/deadlines and a circuit breaker. These are substantial fixes, but resource ownership after timeout remains incomplete (F1).
- D2 rejects wrong executable, missing executable/start and session mismatch. Missing session/invocation fields still bypass verification (F2).
- D3 native argv tests pass on PowerShell7; D4 missing-target/premature-exit tests pass there. No actual rclone launch/mount is claimed.
- D5 fresh-root browser walkthrough **exit0** through the handed production assertions, with output/root redirection only. Actual Spring provider=drive reads a temporary local filesystem fixture; Chrome decodes frames, advances time, seeks, pauses/resumes/retries and passes mobile controls. Full path/size/hash snapshot comparison and mutation negative check pass. Output: C:\Users\Admin\AppData\Local\Temp\codex-drive-f01-browser-kS9JHP.
- D6 mapping **9/9 pass**; unchanged reviewer Windows-junction/ADS repro now reports outsideRootReportedVerified=false and adsPathAccepted=false.
- PowerShell7 comprehensive **28/28** and security **20/20** pass. Windows PowerShell5.1 baseline **14/14** and security **20/20** pass, but comprehensive fails to parse (F3). Distinguish runners instead of claiming62/62 on both.
- Frontend source/build configuration unchanged; previous83-pass and JS-budget results remain prior evidence. Codex did not repeat unaffected frontend suites/build in this review.

## F1 — P1: IO deadlines do not own late resources or bound request cleanup

DriveIoExecutor.executeWithTimeout cancels its Future on timeout, then discards the eventual return value. DriveMediaStorageAdapter.openChannel returns a raw FileChannel from that executor. If an uninterruptible open completes after the caller timed out, the Future is canceled, the caller never receives the channel, and nothing closes it. The worker count correctly returns to0 while the file handle remains open. Repeated slow opens can accumulate leaked handles despite a bounded worker count.

Reviewer DRIVE_F01_late_open.java uses the actual production executor and a deterministic delayed FileChannel.open. Output: caller=MediaUnavailableException; lateOpenChannelStillOpen=true; actualWorkers=0. The probe closes its handle afterward; this is controlled fault injection, not actual WinFsp evidence.

DriveSeekableByteChannel.close directly calls delegate.close on the request thread. The production controller closes it via try-with-resources after read failure. A native read that ignores interruption can make close wait for that read, so the read deadline fires but the request/stream permit does not finish. position/size likewise bypass the IO policy and need an explicit bounded-or-justified lifecycle strategy.

Reviewer DRIVE_F01_channel_close.java wraps a deterministic FileChannel whose read/close wait for an explicit latch. The production wrapper raises its40ms read timeout, but the caller is still blocked in close after250ms: readDeadlineFired=true, callerStillBlockedInClose=true, ioWorkers=1. Cleanup releases the latch and joins the workers. The short timings are test budgets, not proposed deployment values.

Fix resource ownership across timeout/completion races: a late successfully opened channel must be closed exactly once; timely returned channels must remain usable. Ensure cleanup cannot re-block the request indefinitely. Track actual pending cleanup/open/read capacity until real completion, including an interruption-ignoring delegate; do not solve this with unbounded background close threads or premature capacity release. Existing executor-only tests do not cover these production channel lifecycle cases.

## F2 — P1: stop still signals a process with incomplete ownership identity

scripts/drive/stop_drive.ps1 extracts sessionId/mountPoint/remoteTarget/arguments/status but does not require them. Its session check runs only when sessionId is non-null; invocation/mount data is returned in diagnostics without checking it against a live process. Missing processName defaults to rclone. A500ms start window remains a tolerance, not exact identity.

Reviewer DRIVE_F01_stop_missing_identity.ps1 executes the production script with process operations mocked: matching PID/name/path/start, but no sessionId, mountPoint, remoteTarget, arguments or status. It requests termination and reports STOPPED with null mount identity. No real process is killed. This contradicts the assigned fail-closed schema.

Require complete state and consistent invocation/mount ownership before signaling; unreadable identity must reject and preserve state. Apply the same verifier to stop/status and mount launch-failure cleanup. The launcher cleanup still uses only name and up-to2s start-time tolerance. Test missing fields individually, same-name executable/start/session mismatch and different mount invocation; tests must intercept every possible termination path. Avoid optional checks that silently preserve old unsafe behavior.

## F3 — P2: the claimed PowerShell5.1 comprehensive result is not reproducible

Exact command: powershell.exe -NoProfile -File scripts/drive-tests/test_drive_toolkit_comprehensive.ps1 -EvidencePath <temporary-output>. It fails at line144 before any test executes: UTF-8 CJK literal is decoded incorrectly and produces UnexpectedToken / missing Catch-or-Finally parser errors. The same file runs28/28 on PowerShell7. Baseline/security suites do execute successfully on5.1.

Make source encoding/literals compatible with the declared5.1/7 support and rerun the exact -File commands with separate evidence. Do not claim a runner passed from results produced under another runner or a specially decoded ScriptBlock. Preserve frozen reports and publish corrections in new artifacts.

## Evidence and follow-up

Independent logs, browser metrics and hash verification: docs/reviews/evidence/DRIVE_01_F01. Reviewer helpers: docs/reviews/repro/DRIVE_F01_*. These are repro detectors, not all regression tests with expected exit0 after a fix. Their outputs/provenance must be interpreted, not edited to pass.

Next prompt DRIVE-01-F02 addresses only F1–F3, with six agents on independent implementation/test/evidence tasks. Do not redo D3–D6 implementations or add features. Keep real Drive gates separate and monitoring paused. A direct-dev checkpoint push is not acceptance or deployment.
