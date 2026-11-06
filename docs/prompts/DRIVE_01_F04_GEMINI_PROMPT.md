# DRIVE-01-F04 — One remaining cleanup ownership finding

taskId: DRIVE-01-F04
promptVersion: 7
reviewedCheckpoint: DRIVE-01-F03-CHECKPOINT-01
branch: dev; manual handoff; automation paused

Read docs/reviews/DRIVE_01_F03_REVIEW.md. Only R1 cleanup saturation/shutdown ownership remains. Prior seek/size timeout, late-open, identity, argv, PS5.1 encoding, mapping and fresh-root fixes must be preserved. Do not recreate those tasks or add features. G1 remains unaccepted until this narrow issue closes.

User update: fix cleanup comprehensively in this assignment with mandatory cross-agent review, rather than sending another implementation that passes only the last repro. Version7 adds an internal review/fix/retest gate and full lifecycle matrix. If version6 agents already started, preserve their owners and work; add the review gates in place, do not restart agents or create competing writers. Parent must relay this update to every active agent.

## Required outcome

cleanupExecutor's DiscardOldestPolicy currently loses close obligations when its256-entry queue fills. Reviewer DRIVE_F03_cleanup_pressure.java demonstrates300 submitted closes,258 completed and42 actual handles left open after recovery. Swallowing submission failures or marking delegateClosed before accepted ownership also loses resources. A bounded queue alone is not a bounded resource lifecycle.

No accepted resource may become ownerless on cleanup saturation, rejection or shutdown. Close each exactly once, or retain explicit bounded ownership until physical close succeeds/completes. Define admission before open/ownership transfer: a system at capacity must fail fast before accepting more resource obligations, not silently discard already accepted closes. Include returned channels, late-open resources and canceled metadata operations in the lifecycle. Preserve caller deadlines and local-provider isolation. No synchronous caller close fallback, unlimited cleanup threads/queues, increased arbitrary queue cap or silent rejection.

Track all lanes separately and accurately: active main IO, physical cleanup workers, queued close obligations, open resource/cleanup reservations. Do not label main-worker count as all physical resources. A blocked close may remain blocked at OS level; its ownership/capacity must remain retained, preventing unbounded new obligations. Circuit/backpressure can reject new work while existing resources remain safely owned. Document actual shutdown behavior; shutdownNow must not simply abandon queued owned resources.

Choose a coherent contract in the first coordination pass, then implement narrowly. Public standalone cleanup API must have explicit acceptance/ownership semantics; callers must honor them. Do not merely throw on rejection while channel wrapper catches and forgets the resource. Tests must cover actual callers and full lifecycle, not just submit-count internals.

## Parallel ownership — up to six useful agents, no overlap

| Agent | Scope |
| --- | --- |
| A | DriveIoExecutor.java and new cleanup admission/ownership helpers. Publish acceptance/lease/counter contract immediately. No channel/adapter files owned by B. |
| B | DriveSeekableByteChannel.java and DriveMediaStorageAdapter.java only if reservation/transfer integration requires it. Match A contract; never abandon delegate on failed submission. No executor/test edits. |
| C | New DriveCleanupQueueSaturationTest.java: exceed cleanup capacity, slow/blocked close, exactly-once/conservation after recovery; production API/callers. No production edits. |
| D | New DriveCleanupShutdownOwnershipTest.java: rejection, shutdown race, timeout/open handoff and accepted pending obligations; finite waits and actual capacity assertions. No production edits. |
| E | Read-only independent lifecycle audit of A/B changes; prepare an independent test/repro under tests with a new uniquely named file if a gap is found. Send findings early; do not compete with A/B/C/D writers or rerun full builds. |
| F | Current contract/runbook corrections and F04 evidence preparation. Audit metric labels and shutdown limitations. Parent delegates single post-integration browser smoke to F if needed; no change to passing harness just to create work. |

Parent owns coordination and final artifacts, and assigns exact new helper/test paths before dispatch. Use actual available slots/IDs honestly; no fake delegation. Agent A/B agree resource transfer contract early, C/D/E work independently on test design. Shared Maven/Next output has one writer; no redundant builds. User wants speed plus quality, not quota savings. Maintain disk bounds and small fixtures.

## Mandatory cross-review: do not hand off before this gate closes

Before implementation, A/B and parent write the lifecycle/state-transition contract: owner of each resource, admission reservation point, ownership transfer, timeout winner, who owns eventual physical close, when each permit is released. Include queued/running/open/closing/quarantined/shutdown states, not only Future completion. Reviewers challenge the contract before coding proceeds; C/D can prepare adversarial cases immediately in parallel.

Cross-review assignments are read-only outside each agent's owned files:

- C reviews B's channel/adapter ownership and all call sites against the lifecycle contract.
- D reviews A's executor/admission/disposal/shutdown paths, including rejected tasks and returned queues.
- E independently audits the complete integrated lifecycle and tries to break conservation/capacity with a separate production-path stress test. New file ownership must be named before writing.
- F reviews C/D/E test assertions and evidence: do they exercise production code, would discard/leak/early permit-release actually fail them, and are runner/metric claims accurate?
- After handoff, A reviews B and B reviews A for contract compatibility. Parent resolves every disagreement and integrates; nobody may self-approve their own production files.

Publish a findings ledger in docs/reports/drive/DRIVE_01_F04/CROSS_REVIEW.md: reviewer, reviewed files/revision hashes, concrete scenario/repro, priority, owner, fix, regression evidence, re-review result. A verbal "looks good" is insufficient. Changes after approval invalidate the approval of affected paths and require the relevant reviewer to check again. Tests from before the final edits are not final evidence.

Run the internal cycle review -> fix by owning agent -> targeted regression -> independent re-review until no open P1/P2 cleanup finding remains and the matrix below passes. Do not make Codex the first person to review integrated queue overflow/shutdown behavior. Preserve honest limits: if genuinely blocked, report incomplete with evidence; do not claim completed/ready-for-acceptance or hide a failed cell to meet a time target. No polling or endless repeated builds; each cycle must resolve a named finding.

## Lifecycle acceptance matrix (each row needs evidence)

| Case | Required invariant |
| --- | --- |
| Normal open/read/seek/close | Caller-owned resource stays usable until close; physical close exactly once. |
| Timeout before open finishes | Caller returns by deadline; late result has a retained owner and is closed exactly once. |
| Open completes at timeout boundary | One ownership winner, no premature close of delivered resource and no leaked late result. |
| Caller interrupt / cancellation | Every acquired resource remains owned; actual worker/cleanup capacity retained until physical completion. |
| Blocked read / position getter / position setter / size | Caller exits promptly, including try-with-resources cleanup; no synchronous fallback under pressure. |
| Main pool full / cleanup idle | Cleanup succeeds through explicit bounded reserved capacity, with truthful metrics. |
| Cleanup pool and queue both full | Reject before accepting an unowned resource, or retain existing ownership; no discarded accepted close and no cap increase as a substitute. |
| Submission rejected at each transfer edge | Original or new owner is explicit; channel cannot mark delegate closed while nobody owns physical close. |
| Shutdown before / during / after enqueue | Queued and running accepted obligations are drained or explicitly retained; shutdownNow return values/canceled tasks cannot be ignored. |
| Permanently blocked native close | Finite tracked/quarantined resources; new admission fails fast; healthy local traffic unaffected; no claim that Java can force kernel completion. |
| Recovery after latch release | All accepted resources closed once, all releasable counters/reservations return to baseline. |
| Repeated cycles / overload stress | No cumulative handle, lease, queued-task, worker or thread growth; conservation holds under repeated interleavings. |

Use the conservation equation at every stage: acquired resources = caller-owned + operation-owned + cleanup-owned + physically closed (disjoint ownership, no duplicate accounting). Separately count admissions rejected before acquisition. A cleared Future or a zero main-worker counter does not establish release. Define how reservations bound all still-owned resources, including the fallback cleanup lane.

Stress must exceed the actual configured capacity (small configurable capacities are acceptable), cover at least 300 cleanup attempts/reproduction scale, and repeat independently seeded/controlled interleavings. Avoid random sleep-only tests; use latches/barriers to force the races. Make tests fail if one close is dropped, duplicated or released early. If API changes reject before open, prove the rejected acquisition created no handle and the accepted set all closed; do not simply reduce attempts or count rejected resources as cleaned up.

## Verification

Test production paths with tiny temporary files/real FileChannel handles or deterministic tracked handles and interruption-ignoring close latches. Validate all accepted resources accounted for before release; after recovery, every accepted handle closed exactly once and capacities return to baseline. Exceed the real configured cleanup capacity without generating huge files. Always release/join test-owned workers and close test-owned fallback handles. Add negative test proving dropped cleanup would fail the suite. Do not edit Codex reviewer files; the current detector's old assertions may change outcome after the implementation contract changes, so interpret it honestly and write proper new regression expectations.

Run targeted C/D tests early, one final backend test-profile suite after integration, existing lifecycle regression and one affected browser smoke. PS/frontend/mapping unchanged means prior evidence; do not waste time redoing accepted work. Rerun only checks affected by actual changes/failures. Separate logs/evidence F04, isolated H2/ports/temp roots. No actual Drive mount/rename/write/disconnect in the coding check.

## Real environment and handoff

User and Codex already installed rclone1.75.1/WinFsp2.1 and completed cinema-drive OAuth read-only. Folder VideoDieppie is selected and readable (folder ID 1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ). User has now uploaded videoplayback.mp4, and Codex verified its metadata: 29209556 bytes, top-level file. This is metadata verification only; codec/decode/seek have not been checked on that file. Do not ask user to redo upload, OAuth or install. Do not read/copy credentials or put tokens/config into artifacts.

No actual mount has been started. G2 is pending reviewed mount execution, not missing installation/OAuth. G3 is pending real mounted playback verification, not missing media. Do not claim either gate from local fixtures, and do not run the fixture harness against the real Drive root because it creates/renames files. Codex will perform the operational read-only mount and real-file test after G1 independent review. Keep the coding checkpoint isolated.

Artifacts docs/reports/DRIVE_01_F04_REPORT.md, DRIVE_01_F04_STATUS.json, DRIVE_01_F04.patch, DRIVE_01_F04_MANIFEST.json; evidence docs/reports/drive/DRIVE_01_F04/ including CROSS_REVIEW.md and a row-by-row LIFECYCLE_MATRIX.md. New checkpoint/runId, promptVersion7, ready_for_review/sourceFrozen=true only after internal review gate finishes. Status includes crossReviewComplete, openCleanupFindings, matrix results and actual reviewer IDs; report an honest incomplete state if not closed. Actual pre-edit baseline snapshot; Git-generated patch/reverse check, final SHA256/bytes after writers stop. Preserve frozen artifacts and unrelated backend/fastapi/.env.example. Codex-owned prompts/control/reviews/repros read-only.

No commit/push/reset/branch/deploy, live DB, AI/FastAPI/Qwen/GPU/model, OS settings, install/OAuth/real mount or automatic polling. Finish coherent checkpoint, freeze and end turn for manual independent Codex review.
