# DRIVE-01 — Independent review

2026-10-15. **REQUEST CHANGES — G1 not accepted.** G2/G3 remain BLOCKED_EXTERNAL_INPUT, correctly distinguished from the local filesystem fixture. M4 local acceptance remains valid. No install, OAuth, real mount, live DB or application edit was performed by Codex.

Checkpoint DRIVE-01-CHECKPOINT-01 / promptVersion2 is explicitly ready_for_review and frozen. All37 manifest entries match SHA256/length before and after review; reverse patch check passes. Gemini artifacts remain untouched. Six-agent execution is self-reported, not independently audited through Gemini conversations.

## Independent verification

- Exact Spring test-profile Maven command: **92/92 pass**, isolated H2, local JDK25.0.3 targeting17. Bare Maven and remote CI were not rerun by Codex at this checkpoint.
- Frontend **83/83 pass on Node26 and Node20.20.2**; tsc exit0. Frontend source is unchanged; dynamic guard against the existing production build passes at143264/143360bytes for detail. This is not a newly executed build claim.
- Windows PowerShell5.1 tooling: **14 +24 +14 pass**, with evidence paths redirected outside frozen artifacts. Mapping suite **7/7 pass** on current Node. These tests do not establish actual native launch argument preservation, mount readiness or full process ownership validation.
- Actual Spring provider=drive with a temporary local directory and production Chrome: descriptor offline/retry, decoded playback/time progression, three seeks, pause/resume, player retry, mobile controls44px/no collisions and HTTP benchmark stages succeeded. **Whole walkthrough exits1** on a fresh fixture, as explained in D5. This is fixture evidence, not real Drive playback.
- Additional production-path repros demonstrate D1–D4/D6 below. No real rclone process was launched or killed; mocked process operations and a harmless Node argv recorder were used for Windows execution tests.

## D1 — P1: blocked Drive IO is unbounded and consumes local stream capacity

DriveMediaStorageAdapter.java:34–40,83–162 performs synchronous Files metadata/open calls; MediaStreamController.java:46–105 performs metadata and channel reads on the request path. There is no configured metadata/open/read deadline, bounded IO worker/queue isolation or circuit breaker. The existing shared permit cap is insufficient: stalled Drive GETs retain all permits and healthy local GETs return429. Descriptor and HEAD metadata calls do not even acquire those permits and can occupy further servlet workers.

Reviewer DRIVE_01_IoRepro.java injects a deterministic blocking storage read into the production controller/service. With the configurable cap set to1, the Drive request remains pending and a healthy local request returns429. The latch is released by the reviewer to clean up. This is controlled fault injection, not an observation of actual WinFsp hanging, and500ms is not a proposed timeout threshold. Source inspection confirms no internal deadline at any duration.

Implement bounded Drive work/deadlines/circuit and provider isolation, including metadata/HEAD/descriptor. Do not release actual worker capacity merely because a caller times out; Future.cancel does not guarantee filesystem cancellation. Test a reader that ignores interruption, repeated timeout pressure, recovery and healthy local traffic. Current DriveFaultIsolationTest manually acquires/releases permits in several cases and tests immediate exceptions/concurrency, not these requirements. Also classify unreadable/disconnected source errors accurately; do not expose configured host paths through public exception messages.

## D2 — P1: stop does not verify the recorded executable and tolerates mismatched process starts

scripts/drive/stop_drive.ps1:98–131 never compares state.executablePath with proc.Path. It accepts a start time difference up to5seconds; an empty timestamp also defaults to a match. status_drive.ps1 uses similarly incomplete identity checks. Recorded executable/session/mount identity are not enforced.

Reviewer DRIVE_01_stop_identity.ps1 executes the actual stop script with process operations mocked. State says C:\Expected\rclone.exe, the live process says C:\Different\rclone.exe and starts3seconds later. The script requests termination and reports STOPPED. No process is actually killed. Require complete, trustworthy identity fields and fail closed on missing/mismatch/unreadable values; compare normalized executable, exact start identity, owner/session and mount invocation as appropriate before any signal. Add negative tests for two same-name rclone processes, not only rclone versus powershell.

## D3 — P2: native mount arguments lose spaces

scripts/drive/mount_drive.ps1:229 passes an array directly to Start-Process -ArgumentList. In supported Windows PowerShell this becomes a joined command line without preserving each argument's boundaries. Existing tests inspect the dry-run plan, not argv received by a child.

Reviewer DRIVE_01_mount_execute.ps1 captures production launch arguments and passes them through the same native launcher to a harmless Node recorder. Remote fixture:Animation Films becomes two arguments; the config path ending in secret config.conf also splits. Both preservation checks are false. Implement quoting/argument handling that works on the explicitly supported PowerShell5.1/7 versions; verify actual child argv for space/Unicode/quotes/backslashes without launching a mount.

## D4 — P2: launcher reports MOUNTED before checking mount readiness

mount_drive.ps1:233–269 waits1second, checks only HasExited, then reports Success=true/Status=MOUNTED. A process can be alive while mount initialization is blocked or the target is absent. The same reviewer execution seam, with a live-looking process and nonexistent target, reports MOUNTED. Add bounded readiness checks and truthful STARTING/FAILED/TIMEOUT states; inspect backend-compatible filesystem readability and handle failure without losing ownership of the spawned process. Do not advertise process survival as a healthy mounted source. Reconcile directory-mode preflight with actual rclone Windows requirements; do not assume an existing empty directory is a valid target merely because it has no files.

## D5 — P2: walkthrough fails clean startup and does not assert content integrity

scripts/run_drive_media_walkthrough.cjs:530 snapshots the root before DriveWalkthroughServer creates/copies the fixture. On a new root the baseline is0files and the final root has1file, so line1163 fails. A prepopulated directory hides this dependency. Reviewer wrapper changes only output locations and the fixture root to unique temp paths; original UI/network assertions are unchanged. It reaches all playback/benchmark steps and exits1 at0!==1. Output: C:\Users\Admin\AppData\Local\Temp\codex-drive01-browser-BpoL15.

Move fixture preparation before the measured read-only baseline and assert the complete relative-path/size/SHA256 snapshot. Current assertion checks only counts, although the report exposes hashes; a same-count content mutation can pass. Add a negative check that a same-count byte mutation fails. Preserve original artifacts and write follow-up evidence separately.

Correct handoff documentation: DRIVE_PERFORMANCE_PLAN.md claims unchanged free space/0 OS writes, universal optimality/no risk of SSD exhaustion, and gives stop_drive -MountPoint even though that parameter does not exist. Cache-off does not eliminate OS/browser/config/log writes. FileChannel.position removes application byte-discard seeking but does not prove O(1) remote cloud latency. Keep measurement provenance and limits explicit; use actual CLI parameters and state-file paths.

## D6 — P2: mapping preview verifies files outside the mount through junctions

scripts/preview_drive_media_mapping.cjs:204–225 checks lexical containment then statSync follows reparse points. Reviewer DRIVE_01_mapping_boundary.cjs creates a Windows junction inside a temporary root pointing to an outside directory: the outside file is reported verified. The validator also accepts clip.mp4:secret, inconsistent with the required Windows ADS boundary. This affects the administrative preview, not a demonstrated escape of the production adapter's real-path check.

Require canonical root/target containment before verification, reject ADS/device paths consistently and test real junction escape. Keep preview read-only and do not silently accept unsafe records as verified. Tests should compare repeated validation without claiming database reconciliation: current idempotency test only repeats the same preview.

## Evidence and next step

Independent logs and final hash verification are in docs/reviews/evidence/DRIVE_01. Reviewer helpers are docs/reviews/repro/DRIVE_01_*. No frozen manifest/status/report was rewritten. The browser whole-run failure and mocked process provenance are retained, not labeled full passes.

Follow-up: DRIVE-01-F01, six agents with independent ownership, scoped to D1–D6 and affected regression checks. No need to repeat accepted M4 UI work or add features. G2/G3 stay blocked pending reviewed setup and user OAuth/folder input. Automation remains paused/manual. A direct-dev checkpoint commit/push, if made, is not acceptance or deployment.
