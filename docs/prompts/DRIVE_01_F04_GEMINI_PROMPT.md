# DRIVE-01-F04 — One remaining cleanup ownership finding

taskId: DRIVE-01-F04
promptVersion: 6
reviewedCheckpoint: DRIVE-01-F03-CHECKPOINT-01
branch: dev; manual handoff; automation paused

Read docs/reviews/DRIVE_01_F03_REVIEW.md. Only R1 cleanup saturation/shutdown ownership remains. Prior seek/size timeout, late-open, identity, argv, PS5.1 encoding, mapping and fresh-root fixes must be preserved. Do not recreate those tasks or add features. G1 remains unaccepted until this narrow issue closes.

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

## Verification

Test production paths with tiny temporary files/real FileChannel handles or deterministic tracked handles and interruption-ignoring close latches. Validate all accepted resources accounted for before release; after recovery, every accepted handle closed exactly once and capacities return to baseline. Exceed the real configured cleanup capacity without generating huge files. Always release/join test-owned workers and close test-owned fallback handles. Add negative test proving dropped cleanup would fail the suite. Do not edit Codex reviewer files; the current detector's old assertions may change outcome after the implementation contract changes, so interpret it honestly and write proper new regression expectations.

Run targeted C/D tests early, one final backend test-profile suite after integration, existing lifecycle regression and one affected browser smoke. PS/frontend/mapping unchanged means prior evidence; do not waste time redoing accepted work. Rerun only checks affected by actual changes/failures. Separate logs/evidence F04, isolated H2/ports/temp roots. No actual Drive mount/rename/write/disconnect in the coding check.

## Real environment and handoff

User and Codex already installed rclone1.75.1/WinFsp2.1 and completed cinema-drive OAuth read-only. Folder VideoDieppie is selected and readable; currently no test MP4. Do not ask user to redo OAuth or install, do not read or copy credentials, and do not use those facts to claim mounted playback. No mount has been started. G2 awaits reviewed mount; G3 awaits uploaded test media and actual browser evidence.

Artifacts docs/reports/DRIVE_01_F04_REPORT.md, DRIVE_01_F04_STATUS.json, DRIVE_01_F04.patch, DRIVE_01_F04_MANIFEST.json; evidence docs/reports/drive/DRIVE_01_F04/. New checkpoint/runId, promptVersion6, ready_for_review/sourceFrozen=true. Actual pre-edit baseline snapshot; Git-generated patch/reverse check, final SHA256/bytes after writers stop. Preserve frozen artifacts and unrelated backend/fastapi/.env.example. Codex-owned prompts/control/reviews/repros read-only.

No commit/push/reset/branch/deploy, live DB, AI/FastAPI/Qwen/GPU/model, OS settings, install/OAuth/real mount or automatic polling. Finish coherent checkpoint, freeze and end turn for manual independent Codex review.
