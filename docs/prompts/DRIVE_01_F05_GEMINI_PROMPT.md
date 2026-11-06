# DRIVE-01-F05 — Nonblocking cleanup ownership

taskId: DRIVE-01-F05
promptVersion: 8
reviewedCheckpoint: DRIVE-01-F04-CHECKPOINT-01
branch: dev

Read docs/reviews/DRIVE_01_F04_REVIEW.md and read-only reviewer repro DRIVE_F04_shutdown_close.java. Fix only R1 and the evidence gate, preserving prior changes. F04 is not accepted.

The E-01 fix calls delegate.close() synchronously after shutdown or submission rejection, consumes reservations before physical disposal and reports zero counters during blocked caller close. shutdown() runs dropped cleanup tasks inline too. Resolve all these ownership paths coherently. No synchronous caller close fallback, unlimited threads/queues, arbitrary queue increase, untracked disposal or swallowed failure declared success. Accepted resources remain explicitly owned and bounded until physical disposal. Document close-error/shutdown semantics honestly; retain deadlines and local-provider isolation.

Use six parallel agents with exclusive paths: A executor/reservation contract; B channel/adapter integration; C shutdown-before-close/rejection tests; D queued shutdown/blocked-close/close-error tests; E independent integrated adversarial audit; F assertion audit, runbook and evidence. Parent assigns paths, integrates, owns final artifacts. No competing writers or concurrent builds to shared output. Mandatory cross-review: C reviews B, D reviews A, E integrated lifecycle, F C/D/E assertions, A/B compatibility. No self-approval of production files. Each approval names exact FINAL SHA256/revisions; later edits invalidate approvals. Fix, regress, re-review until zero P1/P2.

Deterministic coverage: reservation acquired then shutdown then channel close; shutdown racing submission; rejected cleanup transfer after reservation consumption; blocked queued close during shutdown; permanently blocked close; close throws before actual disposal; caller interrupt; recovery. Assert caller RETURNS while close latch is STILL held and actual open handle retains bounded, truthful ownership/counters; after release close exactly once and return counters to baseline. Do not release latch first then claim nonblocking. Preserve full lifecycle matrix including >=300 admission attempts, read/position/size timeouts and late-open races. Rejected-before-acquisition is separate from acquired handles.

Correct E-01/L-08 claims in NEW evidence, preserve frozen F04. Publish docs/reports/DRIVE_01_F05_REPORT.md, STATUS.json, MANIFEST.json and patch; docs/reports/drive/DRIVE_01_F05/CROSS_REVIEW.md and LIFECYCLE_MATRIX.md with reviewer identities, final hashes, findings/fix/re-review and exact outputs. Freeze only when internally reviewed and coherent; promptVersion8, new run/checkpoint, ready_for_review/sourceFrozen.

Real prerequisites complete: rclone/WinFsp installed, cinema-drive OAuth read-only, VideoDieppie contains videoplayback.mp4 (29,209,556 bytes). G2/G3 await operational checks AFTER Codex G1 acceptance; never claim fixtures are real Drive. No real mount/install/OAuth/credentials, live DB, AI/GPU, OS settings, deployment, commit/push/reset or modification of Codex controls/prompts/repros/prior frozen artifacts. End turn after valid handoff; file does not auto-start an agent.
