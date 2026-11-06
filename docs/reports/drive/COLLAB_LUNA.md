# Luna collaboration log — Drive cleanup

Date: 2026-10-15 (Asia/Bangkok)  
Branch: `dev`

## Ownership and coordination

- Gemini is the sole editor of production cleanup code.
- Luna owns new tests named `LunaDriveCleanup*`, this collaboration log, and new Luna test/review reports. Luna must not edit existing tests or Gemini files.
- Only the parent Luna agent may run Maven/build. RUN1 was executed on `STABLE_REV_F05_01`; RUN2 is gated on the current cross-review of Luna's revised tests and a fresh pre-run hash check.
- `docs/reports/drive/COLLAB_GEMINI.md` has since published `stable_for_test`, revision `STABLE_REV_F05_02`, with Gemini production workers quiesced. Luna independently rechecked all four listed SHA256 values and byte sizes; they match. This newer checkpoint supersedes F05_01 for the next verification run.

## Baseline finding from F04 review

The independent F04 review reported that closing a reservation after shutdown or cleanup submission rejection could run native `close()` on the caller, consume ownership before physical disposal, and report zero reservations/pending cleanup while the handle remained open. Shutdown could also drain dropped cleanup runnables inline. The reviewer repro uses a real temporary `FileChannel` and a controlled close latch; with the latch held, its recorded output was:

```text
callerBlocked=true closeThread=pool-1-thread-1 handleOpen=true reservations=0 pending=0 cleanupWorkers=0
accepted=true closedAfterRelease=true
```

It exited 1 because the caller remained blocked. This is lifecycle simulation evidence, not a real Drive stall. Treat it as historical F04 evidence; it does not describe or certify Gemini's current in-progress production source.

## Preliminary findings from the pre-stable workspace snapshot

The read-only Luna reviewer found these additional risks in the current unverified production diff. They must be reproduced against Gemini's stable revision before they are treated as current findings:

- `DriveMediaStorageAdapter.openChannel`: the reservation is released when `executeOpen` times out, even though the open worker may still be running and can later return a live handle. Repro: gate the open callable, let the caller time out, then release the callable to return a real temporary `FileChannel`; assert capacity/ownership remains charged until late-handle cleanup physically completes.
- `DriveResourceReservation.closeAsync`: reservation state is consumed before disposal, and cleanup failure is swallowed while pending accounting is decremented. Repro: use a closeable that throws before closing its underlying temporary handle; assert the caller returns while the close gate is held, the handle remains open and the bounded obligation stays visible, then invoke the documented retry path and assert one physical disposal and baseline accounting.
- Admission, active-to-pending transfer, and shutdown use separate counters/operations in the observed diff, so the total budget and lane shutdown decision are not one atomic transition. Repro: race reservation admission, close transfer, and shutdown at latches; assert total owned resources never exceeds configured capacity, and every pre-issued reservation can still hand off cleanup after shutdown.
- One existing saturation test lacks `finally` release for a blocking latch, and an existing shutdown-race test includes caller-thread close as a recovery fallback. These existing tests are outside Luna's current ownership; Luna will not modify them. New Luna tests will use unconditional `finally` release and fail if native close runs on the caller.

These findings came from the unverified source snapshot seen during test preparation. Recheck them against the stable revision below before treating them as reproduced. Luna makes no production changes; Gemini owns production fixes.

## Stable revision read-only review

Stable revision `STABLE_REV_F05_01` was rehashed and size-checked against Gemini's manifest on 2026-10-15. All four values match:

| Production source | Bytes | SHA256 |
| --- | ---: | --- |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java` | 25,225 | `bc8f8147280b332e2e87a2ecc47f0a593f27de680c91f08ef432e8508d156cb0` |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveResourceReservation.java` | 1,761 | `ebbbc0f9051bd8b6d78e693bb61dfa804506a46819104782eb483da12de087dc` |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveSeekableByteChannel.java` | 11,047 | `da59023731055b84bf12b52d331dd6ec44acd70c63a1b111128d3602cb2c47ed` |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/DriveMediaStorageAdapter.java` | 9,798 | `67c23cf547f5ebda9b4d010bb230b505a64ef2c67d6328aab2c02eb2b346172e` |

The following are source-review findings against that stable snapshot. They are not yet test-reproduced. Targeted adversarial tests are now cross-reviewed and will be run against this exact snapshot:

- **Late-open close failure can lose ownership.** When the opener is still running after timeout, the worker directly closes the late handle while `actualOutstandingWorkers` and the active reservation remain charged, then releases the reservation even if `close()` throws (around lines 267-285). When the caller timeout path already sees `resourceRef`, it submits a generic cleanup action and releases the reservation immediately without checking whether `executeCleanupAsync` accepted it (around lines 317-325). The published contract permits the still-running worker/active-reservation lanes to account for a blocked late close; RUN1's pending-lane assertion was too strict and has been corrected. The close-throws and ignored-rejection paths still need direct adversarial coverage.
- **Failed close ownership is dropped.** `DriveResourceReservation.closeAsync` marks its permit inactive before submitting. Its cleanup `finally` decrements pending obligations regardless of close success (around lines 402-444 in `DriveIoExecutor.java`). The exported `DriveResourceReservation` API has no retry method or retained-failure state (`DriveResourceReservation.java`); therefore the stated failed-obligation retention/retry contract is not represented by this revision.
- **Admission and handoff are not one atomic capacity transition.** `acquireReservation` reads pending and active independently, then CAS-increments only active (around lines 386-396). `closeAsync` decrements active and later increments pending (around lines 415-416). Concurrent admissions and handoffs can observe an undercount window; the 320-attempt test covers saturation, while a handoff/admission race needs a separate deterministic test before strict linearizability can be claimed.
- **Worker-finally channel close bypasses the cleanup lane.** `DriveSeekableByteChannel.closeDelegateSilently` invokes `delegate.close()` directly and releases its reservation in `finally` (around lines 284-297). A throwing close is swallowed and ownership is released; a blocked close remains outside cleanup-worker/pending accounting. This path is reached after an active channel operation completes while wrapper closure has already been requested.
- `DriveIoExecutor.shutdown()` itself calls `shutdownNow()` for the IO pool and only shuts the cleanup executor when both ownership counters are zero (lines 593-599); it does not visibly drain dropped tasks inline. The bounded shutdown and queued-task lifecycle still require the new Luna test to provide runtime evidence.

The reviewer has been asked to independently inspect these findings and the latest open-lifecycle test. Concrete repro output and final disposition will be added after the targeted tests run against a verified source snapshot.

## Earlier Luna-session change to an existing test

Before the current ownership boundary was given, a Luna agent added teardown/latch instrumentation to the already-uncommitted `backend/springboot/src/test/java/com/dippie/moviercm/DriveCleanupShutdownOwnershipTest.java` (the diff grew from 661 to 692 added lines). The agent identified the additions as a managed-latch list with teardown release, plus `TrackedFileChannel` close-completion and close-thread instrumentation. This file is outside Luna's current ownership and has been left untouched since the boundary changed. No production file was edited by Luna.

## Luna test plan

New tests are being prepared in separate files:

- `backend/springboot/src/test/java/com/dippie/moviercm/LunaDriveCleanupShutdownOwnershipTest.java`
- `backend/springboot/src/test/java/com/dippie/moviercm/LunaDriveCleanupOpenLifecycleTest.java`

They will assert, with bounded fixtures and timeout/finally/join cleanup:

1. Shutdown-before-close returns to the caller while the native-close latch is still held; the live handle and its capacity remain truthfully owned, then physical disposal occurs once after release.
2. Cleanup rejection preserves an acquired reservation and its capacity so the owner can retry; no caller-thread close occurs.
3. Shutdown does not run or wait for a blocked queued close inline.
4. A close exception retains a bounded failed obligation and does not report disposal; an explicit controlled retry can dispose it and restore counters.
5. Open timeout and caller interruption preserve ownership while the open worker can still return a late handle; the late handle is disposed through cleanup.
6. Accounting stays bounded across at least 300 admission attempts. A rejected-before-acquisition attempt is distinguished from an acquired handle.

Tests will be adapted only to Gemini's published stable API. A caller-return assertion is evaluated before releasing the close latch.

## Luna subagent and file status

- `executor_owner` and `channel_owner`, which previously had production-source ownership in the earlier orchestration, were interrupted after the user clarified Gemini's exclusive production ownership. No Luna agent is currently editing production.
- `channel_owner` had created the allowed new `LunaDriveCleanupOpenLifecycleTest.java` before interruption; the parent now owns that file and has not run it.
- `executor_owner` was interrupted before creating its allowed shutdown-ownership test file. A fresh `luna_shutdown_tests` agent now owns only `LunaDriveCleanupShutdownOwnershipTest.java` and has no production/existing-test ownership.
- `adversarial_test_owner` completed a read-only cross-review of both new test files; it has no write permission for the current task. It previously disclosed the exact earlier edits to the existing `DriveCleanupShutdownOwnershipTest.java`, recorded above; no further edits to that file are being made.
- Reviewer feedback on `LunaDriveCleanupOpenLifecycleTest.java` asked for explicit proof that the opener latch remains held at caller return, concurrent rather than sequential 320-attempt admission, teardown that closes admission before releasing permits, and a mixed active-plus-pending capacity check. The parent incorporated those changes; the reviewer confirmed the final opener/worker teardown and bounded admission-pool cleanup.
- The current open-lifecycle test asserts timeout/interruption caller return while the open latch is held, late-close caller return while the physical close latch is held, and 320 concurrent admissions against a mixed active-plus-pending budget. Parent fixed the opener publication/close-latch teardown race and made the admission pool teardown bounded and unconditional; the reviewer confirmed those fixes.
- The shutdown-ownership test runs shutdown, rejection, and retry callers on bounded separate threads; it checks blocked queued cleanup and a failed close. It expects the failed close to remain pending and documents that the current interface has no retry/reconciliation API. The reviewer found no compile-level API mismatch and identified the failed-close ownership/accounting defect. The bounded-wait teardown fix was then checked by the parent.

`COLLAB_GEMINI.md` is present and declares `STABLE_REV_F05_01`; its source manifest matches the workspace. Gemini's published stable state is a test gate, not evidence that cleanup acceptance criteria pass.

## Stable revision and test evidence

- Gemini stable production revision: `STABLE_REV_F05_01` (manifest verified; source review and adversarial tests not yet passed).
- Targeted test command (parent Luna only): `backend/springboot/mvnw.cmd -Dtest=LunaDriveCleanupOpenLifecycleTest,LunaDriveCleanupShutdownOwnershipTest -Dspring.profiles.active=test test`, run from `backend/springboot`.
- Production source SHA256 immediately before test run:
  - `DriveIoExecutor.java`: `bc8f8147280b332e2e87a2ecc47f0a593f27de680c91f08ef432e8508d156cb0`
  - `DriveResourceReservation.java`: `ebbbc0f9051bd8b6d78e693bb61dfa804506a46819104782eb483da12de087dc`
  - `DriveSeekableByteChannel.java`: `da59023731055b84bf12b52d331dd6ec44acd70c63a1b111128d3602cb2c47ed`
  - `DriveMediaStorageAdapter.java`: `67c23cf547f5ebda9b4d010bb230b505a64ef2c67d6328aab2c02eb2b346172e`
- Production byte sizes immediately before run, in the same order: `25,225`, `1,761`, `11,047`, `9,798`.
- Maven output log path: `docs/reports/drive/LUNA_DRIVE_CLEANUP_TARGETED_20261015_RUN1.log`. An initial invocation from the repository root used a nonexistent wrapper path and did not launch Maven; its shell diagnostic was saved separately and is not counted as a test run.
- The project targets Java 17; this host exposes Java 25.0.3 and initially had no `JAVA_HOME`. Luna set `JAVA_HOME` only in the Maven process to `C:\Program Files\Java\jdk-25.0.3`; compilation used `release 17`.
- Production source SHA256 immediately after targeted test run:
  - `DriveIoExecutor.java`: `bc8f8147280b332e2e87a2ecc47f0a593f27de680c91f08ef432e8508d156cb0`
  - `DriveResourceReservation.java`: `ebbbc0f9051bd8b6d78e693bb61dfa804506a46819104782eb483da12de087dc`
  - `DriveSeekableByteChannel.java`: `da59023731055b84bf12b52d331dd6ec44acd70c63a1b111128d3602cb2c47ed`
  - `DriveMediaStorageAdapter.java`: `67c23cf547f5ebda9b4d010bb230b505a64ef2c67d6328aab2c02eb2b346172e`
- Maven result: **exit 1**; 9 tests run, 6 passed, 3 failed, 0 errors. Test compilation succeeded using Java 25.0.3 with `release 17`; the project targets Java 17, and this host has no Java 17 runtime configured.
- Source hashes and byte sizes were unchanged across the run (`25,225`, `1,761`, `11,047`, `9,798` bytes), so this run applies to `STABLE_REV_F05_01`.
- RUN1 reported 3 assertion failures. Cross-review against Gemini's published late-open contract showed the first two failures were test expectation errors: late-open disposal may remain charged to `actualOutstandingWorkers=1` and `activeResourceReservations=1`, with `pendingCleanupObligations=0`, while the open worker itself performs the blocked close. Those assertions are corrected in the Luna test file and will be rerun against the same source hash.
- Confirmed runtime finding on `STABLE_REV_F05_01`: `LunaDriveCleanupShutdownOwnershipTest.failedPhysicalCloseRemainsOwnedAndAccounted` injected a close exception before the underlying temporary file was closed. `failedCleanupObligations` reached `1` and the file handle remained open, but `pendingCleanupObligations` was `0` instead of `1` (RUN1 failed at line 704). The interface also offers no retry/reconciliation API. This violates the bounded ownership/retry requirement; Gemini must fix it.
- The other six RUN1 cases passed, including shutdown-before-close, blocked queued shutdown, bounded rejection/retry, and 320 admission attempts. The backend-wide test suite has not been run; focused retest is pending after the corrected assertions.
- RUN2 was not started. Gemini has resumed the exclusive production repair under a new coordination lease, so Luna has frozen both test files and stopped builds until Gemini publishes a new stable manifest. The corrected late-open assertions have not yet been rerun.

## Coordination checkpoint after RUN1

- Luna-owned files changed in this work: `backend/springboot/src/test/java/com/dippie/moviercm/LunaDriveCleanupOpenLifecycleTest.java`, `backend/springboot/src/test/java/com/dippie/moviercm/LunaDriveCleanupShutdownOwnershipTest.java`, and this log. The earlier-session change to existing `DriveCleanupShutdownOwnershipTest.java` remains untouched and is recorded above.
- The two late-open test assertions were corrected to the published ownership lanes: while the open worker is blocked closing a late handle, expect `actualOutstandingWorkers=1`, `activeResourceReservations=1`, and `pendingCleanupObligations=0`. The handle remains bounded by its worker and active reservation. This correction has not been run yet.
- The close-throws case remains a confirmed safety finding: while the failed handle is still open, the stable implementation records one failure but releases the pending obligation and provides no retry/reconciliation method.
- Current Luna test files are frozen during Gemini's production repair. No further Maven/build will run until Gemini publishes a new `stable_for_test` revision with a fresh four-file manifest. At that point Luna will record fresh pre/post hashes and run the focused suite first; if any production hash changes during testing, the run will not certify the new revision.
- Source hash equality across the targeted run: **confirmed**. If source changes, this run does not certify the new revision.
- Cross-reviewer findings and fixture fixes: **recorded above**. The suite is frozen while Gemini repairs production; fresh cross-review and test evidence will be recorded for the next stable revision.

No Drive mount, real video playback test, commit, or push has been performed.

## STABLE_REV_F05_02 verification preparation

Gemini published `stable_for_test` for `STABLE_REV_F05_02` with production writers/builds quiesced. Luna independently verified this manifest before continuing:

| Production source | Bytes | SHA256 |
| --- | ---: | --- |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java` | 34,735 | `409125a060bc2045ca4ff6cbc40954e7721516497689c829a4bf34ec180c19c2` |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveResourceReservation.java` | 2,707 | `f1622f544465063eab3bc8032375093e658e3265f2585e7e438a52227a5a52e4` |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveSeekableByteChannel.java` | 11,415 | `f188b20ded4b72ed54f1542e52f684fd57f64db8888bb9d0b6e31f3fa3f4c419` |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/DriveMediaStorageAdapter.java` | 9,932 | `3a085bbe9babfdb6fbf41db4cc11456c0a14f8ad13274c8f55a8505b4ab65505` |

The Luna tests were updated only in the two `LunaDriveCleanup*` files. They now exercise the F05_02 retry API, keep the physical close latch held until the retry caller returns, check that a second retry cannot enqueue a duplicate physical close, and check that a successful retry restores failure and capacity accounting. The 320-attempt admission case now releases active-to-pending reservation transfers and all 320 admission attempts through one start gate, then holds the physical cleanup workers while asserting no transient capacity gap. A small capacity-1 case covers repeated throwing unreserved cleanup submissions and requires rejection to preserve caller ownership once one failed obligation fills the budget.

The new late-open close-failure case waits for timeout while the opener latch remains held, releases the opener, captures the real temporary file handle, then checks transfer into one retryable pending obligation and successful retry. This directly tests a suspected active-counter double decrement in `closeLateResourceOnWorker`; the expected test failure, if present, is a Gemini-owned production finding. An independent read-only review of the prior test version also identified an executeOpen completion-vs-timeout ownership race in the small interval after `Future.cancel(true)` and before the timeout state CAS. The current test forces timeout to win before the open callable returns and does not deterministically cover that interval; it remains a static source-review finding pending a deterministic repro or a Gemini source fix.

At this preparation checkpoint, no Maven/build had yet run against `STABLE_REV_F05_02`. RUN2 was later allowed after a read-only review of the revised tests, a fresh Gemini stable-state check, and a fresh four-file hash check. Source drift would invalidate that run for a changed production revision.

## RUN2 findings on STABLE_REV_F05_02

The parent-only focused command was run from `backend/springboot`:

```powershell
$env:JAVA_HOME = 'C:\Program Files\Java\jdk-25.0.3'
.\mvnw.cmd '-Dtest=LunaDriveCleanupOpenLifecycleTest,LunaDriveCleanupShutdownOwnershipTest' '-Dspring.profiles.active=test' test
```

Compilation succeeded with `--release 17`. Surefire ran 11 tests: 8 passed, 3 failed, 0 errors; Maven exited 1. The full output is in `docs/reports/drive/LUNA_DRIVE_CLEANUP_TARGETED_20261015_RUN2.log`. The four production sizes and SHA256 values immediately before and after RUN2 matched Gemini's `STABLE_REV_F05_02` manifest exactly; the run therefore applies to that production revision.

The three failing test methods provide these repros against F05_02:

1. **Late-open close failure double-decrements active ownership.** The test times out while the opener latch is held, verifies the caller returned, then lets the opener return a real temporary-file-backed handle whose first close throws. The observed accounting was `active=-1, pending=1, total=0` instead of `active=0, pending=1, total=1`. Explicit retry physically closed the file, but active stayed at `-1`. Source review points to `closeLateResourceOnWorker`: it CAS-transfers `(active-1,pending+1)` and then calls `reservation.release()`, which decrements active a second time.
2. **Main-worker cleanup bypasses the bounded failed-obligation capacity.** With capacity 1 and one retained close failure occupying that slot, a second `executeCleanupAsync` submission on the idle main worker returned `true` and ran `close()`. The expected result is rejection while preserving caller ownership. The main-worker branch submits before checking lifecycle total; unlike the cleanup-queue branch, it does not reserve/check a bounded slot first.
3. **Retries can enqueue duplicate physical closes, and reservation-local failure stays set after success.** The test blocks the first retry close behind a latch, observes its caller return while the latch is still held, then submits a second retry. F05_02 accepted it; both tasks reached `close()` (3 total attempts including the initial failure). After disposal, global pending/failure counts cleared, but `reservation.hasFailedCleanup()` remained true.

Other RUN2 cases passed, including shutdown-before-close, post-shutdown rejection, blocked queued shutdown, timeout/interruption caller return while the opener latch remained held, and 320 admission attempts concurrent with active-to-pending transfers. The admission test's final overlap instrumentation and the late-open failure teardown received minor reviewer-driven edits after RUN2; they have not been rerun on F05_02. Both test files are frozen now pending Gemini's next stable production checkpoint.

The independent reviewer also noted a narrow `executeOpen` completion-vs-timeout race: after `Future.cancel(true)` but before the caller CASes `TIMED_OUT`, the worker can finish its callable, observe `PENDING`, and leave without disposing a published handle. The current timeout tests deliberately keep the opener latch held through caller return and do not deterministically reproduce that interval. This remains a static source-review finding, not a runtime repro. It is included for Gemini's repair review.

No backend-wide suite, Drive mount, real video playback, commit, or push was performed. No production file was changed by Luna.

## Handoff freeze — STABLE_REV_F05_03

Per the latest coordinator handoff, Luna has stopped implementation, test changes, and builds. The two `LunaDriveCleanup*` test files are frozen for Gemini's takeover. No production source was edited by Luna. All Luna review agents are completed or errored; none is still running. The open-test editor agent hit its usage limit after making test-only changes; its final new test has not been independently reviewed or run.

### RUN3 result (before the final test-only edits)

Gemini's `COLLAB_GEMINI.md` declared `STABLE_REV_F05_03`, `stable_for_test`, with all production writers and builds quiesced. Luna independently verified the four-file manifest before and after the parent-only targeted Maven run. Sizes and SHA256 were identical before and after:

| Production source | Bytes | SHA256 |
| --- | ---: | --- |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java` | 38,090 | `7bbc87d36976d0c1740fc0365ab400e117afdfec1d554d03f4ae3ddfd2dd6025` |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveResourceReservation.java` | 3,358 | `2416cb8b76c0f17b0fdbdf0a0ca0dffc5305b9764023c6eb2cd9d5f029b6ed67` |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveSeekableByteChannel.java` | 11,415 | `f188b20ded4b72ed54f1542e52f684fd57f64db8888bb9d0b6e31f3fa3f4c419` |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/DriveMediaStorageAdapter.java` | 9,932 | `3a085bbe9babfdb6fbf41db4cc11456c0a14f8ad13274c8f55a8505b4ab65505` |

Command, from `backend/springboot`, using Java 25.0.3 with project compilation `--release 17`:

```powershell
$env:JAVA_HOME = 'C:\Program Files\Java\jdk-25.0.3'
.\mvnw.cmd '-Dtest=LunaDriveCleanupOpenLifecycleTest,LunaDriveCleanupShutdownOwnershipTest' '-Dspring.profiles.active=test' test
```

Maven exited 0: 11 tests, 0 failures, 0 errors, 0 skipped (5 open-lifecycle tests and 6 shutdown-ownership tests). The console output and the two Surefire summaries were observed in the parent session; no standalone RUN3 console log was captured. This result covers the test sources present at that run only. Subsequent test-only changes below were not rerun, so RUN3 does not certify the current frozen test files or establish acceptance.

### Cross-review status and remaining finding

- The read-only production reviewer says the three RUN2 runtime findings appear fixed in F05_03 source: late-close accounting transfers active to pending once; `executeCleanupAsync` checks common capacity before either lane; retry uses an in-flight guard and clears reservation-local failure on success. RUN3's 11 passing cases support those paths but do not replace the source review.
- The read-only reviewer identified an unreserved `executeOpen` timeout/interruption rejection path: after a late handle is visible, the caller can win `disposalGate`, ignore `executeCleanupAsync(...) == false` when the shared lifecycle capacity is full, and return. The worker then cannot win the already-set gate and may exit with the handle open. Current production `DriveMediaStorageAdapter.openChannel` passes a reservation; this finding concerns the public unreserved overloads and is not evidence against the adapter's reserved path. No runtime result for this path was obtained before freeze.
- The reviewer proposed a deterministic public-API repro that fills capacity with a held reservation and uses `executeOpen`'s external resource reference to force the late-handle publication window. A new test method named `unreservedOpenLeavesPublishedLateHandleOpenWhenCleanupIsRejected` is now present in `LunaDriveCleanupOpenLifecycleTest.java`, but it was added after RUN3, has not been reviewed, compiled, or run, and currently asserts the observed open-handle behavior as diagnostic evidence. Gemini should review/reframe it as a regression test before relying on it.
- The open-test file also received two `openStarted` preconditions and a bounded quiescence helper that checks `activeCleanupWorkers`; a read-only reviewer confirmed those specific changes. Those changes are after RUN3 and untested.
- A secondary source-review concern remains for public unreserved `executeWithTimeout` / `executeOpen` late-handle cleanup return values. The Gemini contract example also lists `transferToFailed` as `void`, while production declares it `boolean`; no Gemini document was changed by Luna.

### Process and ownership handoff

Luna's RUN3 Maven process has completed (exit 0); Luna has no build process running. A read-only process scan found these Java processes still present, but their owners could not be verified, so none was stopped:

- PID 11156: Maven wrapper `spring-boot:run -Dspring-boot.run.profiles=dev`.
- PID 12172: `MovieRcmApplication --spring.profiles.active=dev`.
- PID 2752: `M4WalkthroughServer`.
- PID 2504 and PID 22012: Maven/Surefire for `DriveIoDeadlineTest,DriveIoProviderIsolationTest`.
- PID 15976 and PID 5200: Maven/Surefire for `DriveCleanupDeadlineTest`.

The two frozen Luna files are `backend/springboot/src/test/java/com/dippie/moviercm/LunaDriveCleanupOpenLifecycleTest.java` and `backend/springboot/src/test/java/com/dippie/moviercm/LunaDriveCleanupShutdownOwnershipTest.java`. Gemini now owns the next implementation and test execution steps under coordinator control. No broad backend suite, Drive mount, real-video test, commit, or push was done by Luna.
