# F06 snapshot: WIP, read before running

F06 is saved for progress backup and is **not accepted for stable use or deployment**. Read docs/reviews/DRIVE_01_F06_CODEX_REVIEW.md for evidence and remaining fixes.

**Do not execute the process-name/path shutdown snippet in DRIVE_SNAPSHOT_RUNBOOK.md.** It can kill unrelated Java and Python workloads. For manually started foreground services, use Ctrl+C in the exact terminal you started; automated shutdown must verify owned PID, creation time and command. Codex has not run the unsafe snippet.

The backend launcher assumes prebuilt target/classes and target/cp.txt and does not isolate its database or working directory. Do not point it at a live/dev database. A dedicated snapshot profile/database and clean build instructions are still required. Historical runbook and manifest are preserved unchanged for review traceability.

Remaining code blocker: saturated generic metadata helper can drop failed cleanup obligations. Drive playback and Qwen endpoint evidence exist, but complete repeatable browser snapshot acceptance is still pending. No deploy.
