# DRIVE-01-F04 independent review

Checkpoint DRIVE-01-F04-CHECKPOINT-01 / promptVersion7: **REQUEST CHANGES**. G1 not accepted; real mount/playback not run. All25 manifest SHA256/bytes match at entry; reverse patch check passes. No application code or frozen Gemini artifact changed by Codex.

## R1 — P1: shutdown/rejected cleanup blocks caller and loses accounting

DriveIoExecutor.acquireReservation().closeAsync(), around lines365–395, consumes the reservation before disposal. On shutdown it invokes delegate.close() directly on caller; cleanup submission catch does likewise. Both swallow failure and return true. DriveSeekableByteChannel.closeDelegateAsync calls this boundary directly. Thus the E-01 fix explicitly approved in CROSS_REVIEW reintroduces the prohibited synchronous caller close. shutdown() also runs returned cleanup Runnables inline, allowing a blocked queued close to hold shutdown indefinitely.

Independent repro docs/reviews/repro/DRIVE_F04_shutdown_close.java compiles production sources to a temporary directory, acquires a production reservation, opens one real read-only FileChannel on a tiny temporary file, shuts down, then invokes closeAsync with a controlled native-close latch. While latch is held, after200ms:

    callerBlocked=true closeThread=pool-1-thread-1 handleOpen=true reservations=0 pending=0 cleanupWorkers=0
    accepted=true closedAfterRelease=true

Exit1: AssertionError Caller performs native close synchronously after shutdown. Finally releases latch, joins owned caller, closes/deletes temporary file. This is deterministic lifecycle simulation using a real handle and production reservation API, not real Drive stall evidence.

Retain bounded ownership/capacity until physical close finishes without running native close on caller. Cover shutdown-before-close, rejection during transfer, blocked queued shutdown and close errors. Assert caller completion WHILE close latch remains held; assert truthful ownership counters and exactly-once disposal after recovery. No larger queue/unlimited threads/silent catch substitute.

## Cross-review evidence

E-01 and matrix L-08 approve immediate fallback disposal, contrary to the required invariant. CROSS_REVIEW lacks reviewed revision hashes. Re-review final integrated revisions with actual hashes and targeted evidence; suite pass counts cannot establish missing lifecycle invariants.

G2/G3 pending G1 acceptance, not missing external inputs: installation/OAuth/upload complete. F05 prompt scopes only R1 and truthful cross-review evidence. A checkpoint commit is not acceptance or deployment.
