# F07 checkpoint review

Verdict: **WIP / not accepted as a stable usable snapshot.** User authorized a temporary commit and normal push to dev despite remaining issues. No deployment.

## Checks performed

- Frozen manifest30/30 byte counts and SHA256 match; patch hash matches and reverse application check passes.
- From declared base fe55916, the23 patch paths apply and match normalized working-tree text. However the two runbooks DRIVE_PERFORMANCE_PLAN.md and GOOGLE_DRIVE_WINDOWS_RUNBOOK.md are omitted from patch and do not match manifest in the reconstruction. Thus this is a valid23-path patch, not complete30-file reproducibility.
- Node20.20.2: TypeScript noEmit passes; production Next build passes; route budget passes all4 routes. Measured /movies/[id]=143100 gzip bytes,260 bytes below143360. Tiny margin remains; this is local Windows verification with existing dependencies/.env.local, not an observed Linux CI result.
- Frontend83/83 tests pass under Node20.20.2 (also passed under host Node). Browser script syntax and both PowerShell script parsers pass.
- Direct compilation of current production executor/reservation/circuit-breaker and exception sources with javac --release17 followed by the bounded repro below confirms a capacity defect. No Maven/shared backend output, DB, network, Drive mount, browser server or GPU was started by this review.
- Backend159/159 and116 targeted passes are reported in the handoff; no new F07 raw backend logs or executed F07 browser/Qwen artifacts were supplied under the F07 evidence directory. These claims were not independently rerun/certified here. A script being present is not proof it executed successfully.

## Remaining findings

### R1 — P1: off-budget failed resource retention is reintroduced

DriveIoExecutor.executeWithTimeout still has no lifecycle pre-admission. At capacity, lines586/628/649 retain failures with chargesPending=false. This fixes the single lostCleanup assertion but reintroduces the earlier unbounded retained map: the resource remains real and open even though active+pending ignores it. Worker concurrency does not bound cumulative retained resources; later metadata requests remain admissible.

Fresh production-source repro: docs/reviews/repro/DRIVE_F07_metadata_budget.java holds the capacity1 reservation, runs3 sequential timed-out generic calls with distinct real temporary FileChannels, and injects close exceptions. Result:

```json
{"capacity":1,"active":1,"pending":0,"retained":3,"nativeOpen":3}
```

Exit1 asserts retained obligations exceed capacity; log at docs/reviews/evidence/DRIVE_F07_metadata_budget.log. Fixture finally closes all owned files, joins callers and releases permit. This is a public generic-helper finding, not evidence that the reserved adapter path failed. Fix with bounded ownership admission or a safe enforceable API boundary, not lost handles or off-budget quarantine. Tests must assert actual retained resource limits, not just nonnegative counters or a single retained handle.

### R2 — P1: launcher can silently start stale bytecode

scripts/start_backend_dev.ps1 lines16–32 builds only if classes/cp.txt are missing. Once both exist, Java source changes are never compiled; only application.yml resources may be copied. After pulling the next fix, the script can run the previous executor while presenting the new snapshot. Invoke incremental compilation on every start or validate a reproducible input hash/build artifact before reuse. Check readiness with a finite timeout rather than reporting success after500ms.

### R3 — P2: stop script records identity but does not validate it fully

stop_backend_dev.ps1 checks process name java and StartTime within2seconds, ignoring recorded ExecutablePath/CommandLine/Profile. Get-Process then Stop-Process by numeric PID also leaves a reuse race. Use exact creation identity plus canonical executable/expected application arguments and a retained process handle; reject mismatches without signaling. Broad name-based killing is removed, which is a genuine improvement; fail-closed ownership is not fully established yet. No stop script was executed by this review.

### R4 — P2: browser proof still bypasses the timeline and lacks final evidence

test_live_browser_f07.cjs line172 unconditionally sets video.currentTime after slider dispatch, so broken slider behavior can pass. It tests one60-second seek, not3 including near-end; no requestVideoFrameCallback/presented-frame evidence is captured. Dimensions/time advancement and UI pause/resume checks are improvements, but do not close the requested verification contract. Use only actual timeline interactions, assert3 target-near decoded frames and continued time advancement, stable paused time, and resume progress. Use a unique owned browser profile and available CDP port. Supply executed JSON/log/screenshots; the expected browser_verification_f07.json was absent at review time.

### R5 — P2: reproducibility/evidence remains partial

The23-path reconstruction omits two manifest runbooks changed since declared fe55916 base. Export full base-relative runtime/runbook patch or declare d572c63 as base with a correct incremental patch. Preserve frozen F07 artifacts and issue corrected follow-up artifacts. Local frontend gate now passes; retain the pending remote CI distinction. Qwen browser discovery/recommendation verification remains unproven by F07 handoff; no new inference was started by reviewer.

## Improvements acknowledged

Frontend budget regression is resolved locally under Node20; existing movie genre mutation is removed; snapshot profile has a separate persistent H2 path; launcher now pins cwd/loopback; broad process-name shutdown command is removed. Snapshot services/mount were reported stopped by the author; not live-verified here.

## Commit handling

Commit source/tests/docs/evidence as WIP and push normally to dev as requested. Commit title/body contain technical changes only, no model attribution or co-author trailer. Exclude backend/fastapi/.env.example, isolated_build_f05, DB/model/cache/build output and credentials. No application fixes were made by reviewer; only review/repro/evidence/control notes. No agent CLI or automation was started.
