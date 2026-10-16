# Drive cleanup — single coordinator / disjoint writers

Coordination revision: 2026-10-15-01. User explicitly requests Luna and Gemini work concurrently with Codex coordinating. This supersedes the earlier Codex-implementation/stop handoff and the Luna full-implementation handoff.

## Exclusive owners

| Owner | Writable paths | Forbidden |
| --- | --- | --- |
| Gemini | Production DriveIoExecutor.java, DriveResourceReservation.java, DriveSeekableByteChannel.java, DriveMediaStorageAdapter.java; new uniquely named production helper paths declared before editing; docs/reports/drive/COLLAB_GEMINI.md; new Gemini F05 artifacts | Luna tests/log; coordinator controls/protocol; old frozen artifacts; Maven/build |
| Luna (thread Tiếp tục Luna Drive cleanup) | New LunaDriveCleanupShutdownOwnershipTest.java, LunaDriveCleanupOpenLifecycleTest.java; COLLAB_LUNA.md; new Luna evidence/review reports | All production files; existing tests; Gemini artifacts; coordinator controls/protocol |
| Codex coordinator (thread Đọc dự án) | This protocol, current task/control, reviewer repro/review/evidence | Production/tests while Gemini/Luna own them |

Three original coordinator subagents are interrupted. Do not resume them or create additional production writers from Luna. Preserve earlier partial diffs; no reset/revert/stash/clean. Luna's earlier instrumentation of an existing test is declared in COLLAB_LUNA.md: leave it in place and report it; request coordinator reassignment before changing that path again.

Existing tests have no writer under this allocation. If compatibility requires changing them, publish exact paths and justification in the owner's collaboration log; coordinator grants a new disjoint assignment before writes. New helper/test paths must be declared to avoid namespace collisions.

## Acknowledgement and bounded handoff

Each owner writes only their OWN collaboration log, acknowledging this revision, writable paths and actual agent IDs/owners. Do not manufacture the other party's ACK or claim a message was read without evidence. Missing COLLAB_GEMINI.md means no ACK yet, not proof the agent ended.

Gemini can implement while Luna prepares tests/read-only review. Gemini reads COLLAB_LUNA.md findings and fixes production; Luna reads COLLAB_GEMINI.md contract and results. No approval questions need the user to relay between owners; write questions/findings to own log for coordinator to read.

To authorize tests, Gemini publishes state=stable_for_test with all production path SHA256, contract/API, known limitations and actual worker-quiesced acknowledgement. All Gemini production subagents stop writes for that revision. Luna acknowledges hashes and publishes state=testing. Luna parent alone runs targeted tests then full isolated H2 suite if targeted checks pass; no subagent launches build, Maven, browser server or other shared-output writer. Hash production and owned test inputs before and after; changed inputs invalidate certification.

After Luna publishes state=test_complete/findings with revision hashes, Gemini may resume work only after explicit coordination handoff to state=working; do not write during testing. Failed tests require concrete repro and owner fix, never weakening assertions just to pass. Repeat only for changed revisions or new failures. Do not use polling timers or duplicate builds.

## Acceptance

Read F04 independent review and F05 prompt for technical requirements. Close caller must return while native-close latch remains held; bounded ownership remains counted until disposal, including shutdown/rejection/late-open/close-errors. No synchronous caller disposal, silent owner loss, unlimited threads or arbitrary cap increase. Final cross-review names exact final hashes.

G1 requires Codex independent review after integrated source freeze. G2/G3 real read-only mount/video tests follow G1; rclone/WinFsp/OAuth/upload already complete. No owner accesses credentials, mounts, live DB, AI/GPU, OS settings, commit/push/reset/deploy. Preserve backend/fastapi/.env.example and all frozen historical artifacts.

This file is cooperative coordination, not an OS-enforced lock. Codex can message Luna directly. Computer Use can target the existing Antigravity conversation when a follow-up is needed; do not start an additional Gemini writer via CLI. File updates cannot start a stopped Gemini process.

## Confirmed handoff

Gemini has now acknowledged revision2026-10-15-01 in its own COLLAB_GEMINI.md, state=stable_for_test, production workers quiesced, revision STABLE_REV_F05_01. Coordinator independently checked all four published file hashes and byte sizes: four matches, zero mismatches. Luna has been messaged directly to validate the snapshot, acknowledge testing and run its exclusive test lane. This is acknowledgement of coordination, not technical acceptance of production correctness.

## CLI transport prepared, no write lease yet

User requests CLI to reduce Computer Use overhead. Installed agy CLI cannot directly resume desktop conversation db189d79-d1b7-4d60-85ec-ab667d40a8a8 (trajectory not found). A separate READ-ONLY Gemini CLI candidate using gemini-3.8-flash-high successfully read this protocol and acknowledged the frozen state: conversation fc195a8d-5c26-4095-875b-2468fa11499a. It has NO production write lease and its single print-mode process has exited. Desktop remains frozen. After Luna's testing ends, coordinator may grant this CLI session exclusive Gemini production ownership by a new explicit protocol lease, keeping desktop frozen and notifying Luna. Never dispatch both writers.

## Active lease: CLI repair revision 02

Luna RUN1 has finished: nine tests, three failures, no source drift; exact outputs are in COLLAB_LUNA.md and LUNA_DRIVE_CLEANUP_TARGETED_20261015_RUN1.log. Coordinator now grants ONLY Gemini CLI conversation fc195a8d-5c26-4095-875b-2468fa11499a the exclusive production lease for STABLE_REV_F05_02 repair. Desktop Gemini remains FROZEN and must not resume editing. Luna owns tests and must not run builds during this working revision. CLI may edit the four assigned production files and declared new production helpers, plus COLLAB_GEMINI.md. It must not edit Luna tests or existing tests and must not run Maven/build. It publishes working then stable_for_test with final hashes, contract, failure/retry semantics and quiesced state before returning. No reviewer acceptance implied.

Repair02 lease is now RELEASED: CLI final turn explicitly completed; state=stable_for_test, zero writers/background tasks. Coordinator verified four manifest hashes/bytes match. Luna owns RUN2 test/build lane; all Gemini production writers remain frozen until coordinator explicitly grants next repair lease. RUN1 late-open lane assertions were corrected by Luna after contract review; failed-close owner loss was the confirmed production defect. RUN2 must test retry recovery/dedup and bounded failed ownership before G1 acceptance.

RUN2 has finished:11 tests/3 failures (negative late-open accounting, unreserved cleanup capacity bypass, duplicate retry/stale failure flag). Sole production lease03 is now granted to the SAME Gemini CLI conversation under GEMINI_CLI_REPAIR_03.md; desktop stays frozen, Luna stops builds and freezes tests until stable03. No other production writer may run. Technical acceptance still pending.

Repair03 lease RELEASED after explicit final CLI result and stable_for_test/quiesced checkpoint STABLE_REV_F05_03. Four hashes/bytes independently match. Luna now owns RUN3 targeted test/build lane, then full backend if targeted passes. Both Gemini CLI and desktop are FROZEN with zero production writers. No further production work until coordinator grants a new lease for concrete findings.

## OVERRIDING LEASE 2026-10-15: Gemini-only integration 04

User explicitly retires Luna and assigns all implementation, tests and heavy cross-review to Gemini; Codex only assigns and checks final handoffs. This section supersedes earlier owner/build restrictions. Luna has acknowledged no owned Maven running and frozen both Luna test files; its final evidence-only handoff may still append COLLAB_LUNA.md. No further Luna implementation or test work is authorized. Old coordinator subagents remain interrupted.

Exclusive owner: SAME Gemini CLI conversation fc195a8d-5c26-4095-875b-2468fa11499a. Desktop Gemini stays frozen. Gemini now owns the four production files, declared Drive helpers, Drive cleanup tests INCLUDING LunaDriveCleanupOpenLifecycleTest.java and LunaDriveCleanupShutdownOwnershipTest.java, current GOOGLE_DRIVE_WINDOWS_RUNBOOK.md and DRIVE_PERFORMANCE_PLAN.md, its own collaboration log and NEW F05 artifacts. COLLAB_LUNA.md remains historical Luna-owned evidence. Coordinator retains controls/protocol/reviewer repro/evidence. Exact per-subagent file ownership must be published before edits. One parent build runner only, frozen source during certification. Use isolated build workspace while preexisting Maven processes remain of unknown ownership. Never kill those processes.

Execute GEMINI_CLI_INTEGRATE_04.md. Maximize useful parallel agents only if runtime supports them; truthfully report actual capability and identities. Full repair/test/cross-review cycle is Gemini's responsibility, followed by explicit FROZEN checkpoint and hash-consistent evidence. No mount/live DB/credentials/deploy. G1 remains pending Codex checking; G2/G3 separate. Automation remains PAUSED. Computer Use stays off. No per-step user updates.

## Additional Gemini read-only review lanes

Coordinator may launch separate Gemini CLI conversations ONLY as read-only reviewers. These are not production parents/writers: no edits anywhere, no builds/tests/servers/process signals or credentials. Their response text is captured outside Git by coordinator. Roles: (1) cleanup source invariants/rejection/cancellation audit, final path hashes required; (2) test-hang and fixture review, no process execution. Production parent fc195a8d-5c26-4095-875b-2468fa11499a remains the sole writer/build owner. Review reports with drift are advisory and must be rechecked against final freeze. Actual independent review conversations/IDs recorded after dispatch; no fictional native subagents.

## Isolated environment verification lane

Coordinator additionally grants one Gemini environment verifier permission to execute H2-only backend tests in its OWN unique TEMP snapshot (not shared target, not isolated_build_f05). This supersedes sole-build restriction ONLY for fully disjoint temporary output/workspaces. It cannot edit repository files or production sources, signal other processes, access credentials/Drive/liveDB, install dependencies or change OS. It may experiment with test-process mocking flags/config in the disposable snapshot and reports exact working configuration/logs/hashes to coordinator. Parent remains sole repository writer; source-changing tests certify only captured snapshot. Bound every test process and retain identity. No simultaneous builds in the same directory.
