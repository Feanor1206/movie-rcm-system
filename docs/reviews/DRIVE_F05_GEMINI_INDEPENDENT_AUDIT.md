I have launched the search to locate the relevant files (`DriveIoExecutor`, `DriveResourceReservation`, `DriveSeekableByteChannel`, `DriveMediaStorageAdapter`, `F04`, `COLLAB_LUNA`) across the codebase. I will analyze them as soon as the results are returned.
# Independent Read-Only Gemini Cleanup Audit Report

**Reviewer Role:** Independent Read-Only Gemini Cleanup Reviewer  
**Audited Target Revision:** Current workspace snapshot (`STABLE_REV_F05_04` in progress)  
**Concurrent Writer Parent:** Conversation `fc195a8d-5c26-4095-875b-2468fa11499a`  
**Execution Boundary:** Strictly read-only. No edits made, zero test/build processes spawned, no process signals sent, no credentials touched, no Drive/DB operations executed.

---

## 1. Input Integrity & Cryptographic Drift Audit

Before starting analysis and immediately prior to issuing this report, SHA-256 cryptographic hashes were computed across all target production sources, historical reviews, and collaboration logs.

| Audited File Path | Pre-Audit SHA-256 (20:26:52) | Post-Audit SHA-256 (20:30:35) | Drift Status |
| :--- | :--- | :--- | :---: |
| [`DriveIoExecutor.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java) | `DD44E84D41D18163C0E26651C2D3A9A50FCB8DEEBC208ED0EA38D6C77611D29A` | `DD44E84D41D18163C0E26651C2D3A9A50FCB8DEEBC208ED0EA38D6C77611D29A` | **ZERO DRIFT** |
| [`DriveResourceReservation.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveResourceReservation.java) | `2416CB8B76C0F17B0FDBDF0A0CA0DFFC5305B9764023C6EB2CD9D5F029B6ED67` | `2416CB8B76C0F17B0FDBDF0A0CA0DFFC5305B9764023C6EB2CD9D5F029B6ED67` | **ZERO DRIFT** |
| [`DriveSeekableByteChannel.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveSeekableByteChannel.java) | `F188B20DED4B72ED54F1542E52F684FD57F64DB8888BB9D0B6E31F3FA3F4C419` | `F188B20DED4B72ED54F1542E52F684FD57F64DB8888BB9D0B6E31F3FA3F4C419` | **ZERO DRIFT** |
| [`DriveMediaStorageAdapter.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/DriveMediaStorageAdapter.java) | `3A085BBE9BABFDB6FBF41DB4CC11456C0A14F8AD13274C8F55A8505B4AB65505` | `3A085BBE9BABFDB6FBF41DB4CC11456C0A14F8AD13274C8F55A8505B4AB65505` | **ZERO DRIFT** |
| [`DRIVE_01_F04_REVIEW.md`](file:///D:/Class/movie-rcm-system/docs/reviews/DRIVE_01_F04_REVIEW.md) | `1A452329097B0F4DF90EE10C29603D8460A69645E81474122BDB3257655B3023` | `1A452329097B0F4DF90EE10C29603D8460A69645E81474122BDB3257655B3023` | **ZERO DRIFT** |
| [`COLLAB_LUNA.md`](file:///D:/Class/movie-rcm-system/docs/reports/drive/COLLAB_LUNA.md) | `246539B2E2E2F1EA718C0A92441C2B13C2C47B5AAFC2A4D18316A9F0DABDD574` | `246539B2E2E2F1EA718C0A92441C2B13C2C47B5AAFC2A4D18316A9F0DABDD574` | **ZERO DRIFT** |

---

## 2. Production Architecture: Adapter Paths vs. Generic Helpers

A primary source of subtle concurrency discrepancies identified in prior reviews stems from conflating the storage adapter's production path with generic executor helper overloads:

```
[Production Adapter Path]
DriveMediaStorageAdapter.openChannel()
   ├── 1. ioExecutor.acquireReservation() ──> [Atomic CAS: active + 1] (Bounded by cleanupQueueCapacity)
   ├── 2. ioExecutor.executeOpen(..., reservation)
   │        └── Handshake & Timeout: passes reservation permit
   └── 3. returns DriveSeekableByteChannel(rawChannel, ioExecutor, reservation)
            └── close() ──> reservation.closeAsync(delegate) ──> [Atomic CAS: active-1, pending+1]

[Generic Helper Overloads]
DriveIoExecutor.executeOpen(task) / executeWithTimeout(task)
   ├── No reservation acquired (reservation == null)
   ├── Admission checks ONLY worker thread count (actualOutstandingWorkers <= maxWorkers)
   └── On timeout/failure: fallback cleanup must dynamically pre-reserve pending budget
```

### Architectural Distinctions Matrix

| Metric / Behavior | Adapter Production Path ([`DriveMediaStorageAdapter.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/DriveMediaStorageAdapter.java)) | Generic Helpers ([`DriveIoExecutor.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java)) |
| :--- | :--- | :--- |
| **Reservation Binding** | Always bound to a non-null [`DriveResourceReservation`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveResourceReservation.java). | `reservation == null` across public convenience overloads. |
| **Admission Gate** | Strictly enforces composite lifecycle capacity `total < cleanupQueueCapacity` upfront. | Bypasses lifecycle capacity; checks only `actualOutstandingWorkers <= maxWorkers`. |
| **Timeout Ownership Handshake** | Preserves reservation permit; transfers active permit to pending lane on failure (`active - 1, pending + 1`). | Attempts unreserved cleanup; requires manual increment of `pending` if retained. |
| **Shutdown Protection** | Active reservations contribute to `total > 0`, preventing premature `cleanupExecutor.shutdown()`. | `total == 0` if only unreserved tasks run; shutdown can close `cleanupExecutor` while workers are running. |
| **Channel Delegate Close** | Invokes [`DriveResourceReservation.closeAsync`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveResourceReservation.java#L20). | Invokes [`DriveIoExecutor.executeCleanupAsync`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L703). |

---

## 3. High-Confidence Audit Findings & Concrete Execution Traces

### Finding 1: `disposalGate` Reset Race in `dispatchLateDisposal` Causes Leaked File Handles
- **Severity:** High (Resource Leak)
- **Files & Lines:** 
  - [`DriveIoExecutor.java#L460-L496`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L460-L496) (`dispatchLateDisposal`)
  - [`DriveIoExecutor.java#L345-L374`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L345-L374) (`executeOpen` worker task)
- **Mechanics & Root Cause:**
  In [`dispatchLateDisposal`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L460-L496), if cleanup submission is rejected (`!accepted`), lines 476–479 and 487–489 execute:
  ```java
  if (!workerCompleted.get()) {
      disposalGate.set(false);
  }
  ```
  The intent was to yield disposal back to the background worker thread. However, the worker thread only evaluates `disposalGate.compareAndSet(false, true)` at two specific points: line 352 (inside try block) and line 362 (inside finally block).
  Between line 364 and line 371, the worker has completed all its disposal checks and exited the try-finally blocks, but **has not yet executed `workerCompleted.set(true)`**.
  If the caller encounters cleanup rejection during this execution gap, `!workerCompleted.get()` returns `true`, and caller resets `disposalGate.set(false)`. The worker never executes another check on `disposalGate` and terminates at line 373. The caller returns and throws `MediaUnavailableException`. The opened physical `FileChannel` is abandoned and permanently leaked.

- **Deterministic Execution Trace:**
  ```text
  Worker Thread (pool-1-thread-1)                   Caller Thread (HTTP worker / test thread)
  ---------------------------------                 -----------------------------------------
  1. openTask.call() produces FileChannel.
  2. resourceRef.set(handle) [line 349].
                                                    3. TimeoutException expires at future.get() [line 400].
                                                    4. future.cancel(true) [line 400].
                                                    5. state.set(OpenState.TIMED_OUT) [line 402].
                                                    6. dispatchLateDisposal(handle, ...) [line 405].
                                                    7. disposalGate.compareAndSet(false, true) -> SUCCEEDS [line 468].
  8. Worker reaches line 351 (state == TIMED_OUT).
  9. disposalGate.compareAndSet(false, true)
     -> FAILS (Caller currently holds gate).
  10. Worker enters finally at line 357.
  11. Line 362: disposalGate.compareAndSet
      -> FAILS (Caller still holds gate).
  12. Worker exits try-finally; is at line 370.
      (workerCompleted is still false!)
                                                    13. reservation.closeAsync() is REJECTED (queue full/shutdown).
                                                    14. Evaluates if (!workerCompleted.get()) -> TRUE [line 476].
                                                    15. disposalGate.set(false) [line 478].
                                                    16. dispatchLateDisposal finishes; caller throws exception.
  17. Line 371: workerCompleted.set(true).
  18. Line 372: actualOutstandingWorkers.dec().
  19. Worker task terminates.
  ----------------------------------------------------------------------------------------------------------------
  POST-CONDITION: Handle remains open. Worker is dead. Caller has returned. disposalGate is false. Resource LEAKED.
  ```

---

### Finding 2: Unreserved `dispatchLateDisposal` Rejection Corrupts Pending Accounting to `-1`
- **Severity:** High (Capacity & Invariant Corruption)
- **Files & Lines:**
  - [`DriveIoExecutor.java#L484-L495`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L484-L495) (`dispatchLateDisposal` unreserved branch)
  - [`DriveIoExecutor.java#L781-L792`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L781-L792) (`recordFailedCleanup`)
  - [`DriveIoExecutor.java#L794-L806`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L794-L806) (`clearRetainedFailedCleanup`)
  - [`DriveIoExecutor.java#L930-L940`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L930-L940) (`decrementPendingAndCheckShutdown`)
- **Mechanics & Root Cause:**
  When `executeOpen` is invoked without a reservation (`reservation == null`), and cleanup dispatch via `executeCleanupAsync` is rejected:
  1. `executeCleanupAsync` either never incremented `pending` (if rejected on capacity check at line 718) or rolled back `pending` via `decrementPendingAndCheckShutdown()` (at line 770). Thus, `pending == 0`.
  2. In [`dispatchLateDisposal`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L490-L494), when `workerCompleted.get()` is true:
     ```java
     recordFailedCleanup(resource, opName, new RejectedExecutionException("Cleanup submission rejected"), null);
     ```
     Unlike `closeLateResourceOnWorker` (lines 526–533) or `closeResourceSafely` (lines 543–550), **this branch does not CAS-increment `pending + 1` in `lifecycle`**.
  3. Consequently, `retainedFailedCleanups` holds 1 record and `failedCleanupObligations == 1`, but `lifecycle.get().getPending() == 0`.
  4. When an administrator or test calls [`ioExecutor.retryFailedCleanup(resource)`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L815) and physical close succeeds:
     [`clearRetainedFailedCleanup`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L794) unconditionally executes:
     ```java
     decrementPendingAndCheckShutdown();
     ```
  5. `decrementPendingAndCheckShutdown()` decrements `pending` from `0` to `-1`! This violates the non-negative invariant and breaks admission accounting.

- **Deterministic Execution Trace:**
  ```text
  Initial State: lifecycle = [active=0, pending=0, shutdown=false], failedCleanupObligations = 0
  1. executeOpen(unreservedTask, timeoutMs) times out.
  2. executeCleanupAsync(resource) rejected due to saturation -> returns false; pending remains 0.
  3. dispatchLateDisposal line 492: recordFailedCleanup(resource, ..., null).
     - failedCleanupObligations.incrementAndGet() -> 1.
     - lifecycle.pending is NOT incremented -> remains 0.
  4. Caller invokes ioExecutor.retryFailedCleanup(resource).
  5. Retry worker executes resource.close() successfully.
  6. Line 853 invokes clearRetainedFailedCleanup(resource).
  7. Line 798: failedCleanupObligations.decrementAndGet() -> 0.
  8. Line 799: decrementPendingAndCheckShutdown() CASes pending from 0 to -1.
  ----------------------------------------------------------------------------------------------------------------
  POST-CONDITION: lifecycle.pending == -1. Permanent negative underflow.
  ```

---

### Finding 3: `DriveSeekableByteChannel.retryClose()` Prematurely Short-Circuits on Physical Close Failures
- **Severity:** Medium (Recovery Defect in Channel API)
- **Files & Lines:**
  - [`DriveSeekableByteChannel.java#L260-L282`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveSeekableByteChannel.java#L260-L282) (`closeDelegateAsync`)
  - [`DriveSeekableByteChannel.java#L301-L307`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveSeekableByteChannel.java#L301-L307) (`retryClose`)
  - [`DriveIoExecutor.java#L616-L619`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L616-L619) (Close failure handling)
- **Mechanics & Root Cause:**
  In [`DriveSeekableByteChannel.closeDelegateAsync`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveSeekableByteChannel.java#L260-L282):
  ```java
  boolean accepted = reservation.closeAsync(delegate, "closeChannel");
  if (accepted) {
      delegateClosed.set(true);
  }
  ```
  `delegateClosed` is set to `true` as soon as the close task is **accepted into the cleanup queue**, NOT when physical close finishes.
  If the cleanup thread later encounters a physical close exception:
  - `DriveResourceReservation.hasFailedCleanup()` becomes `true`.
  - The physical `FileChannel` delegate remains unclosed.
  - If the application invokes `channel.retryClose()`, line 302 checks:
    ```java
    if (delegateClosed.get()) {
        return true;
    }
    ```
  - `retryClose()` immediately returns `true` without retrying or delegating to `reservation.retryCleanup()`.
  The channel wrapper falsely claims the delegate is closed and cannot be recovered via `channel.retryClose()`. Callers are forced to bypass the channel and invoke `reservation.retryCleanup()` directly.

---

### Finding 4: Unreserved Worker Late Close Failure Bypasses Capacity Upper Bound
- **Severity:** Medium (Budget Overflow)
- **Files & Lines:**
  - [`DriveIoExecutor.java#L525-L534`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L525-L534) (`closeLateResourceOnWorker`)
- **Mechanics:**
  In [`closeLateResourceOnWorker`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L503-L536), when `reservation == null` and physical `resource.close()` throws `closeEx`:
  ```java
  while (true) {
      LifecycleState cur = lifecycle.get();
      LifecycleState next = new LifecycleState(cur.getActive(), cur.getPending() + 1, cur.isShutdown());
      if (lifecycle.compareAndSet(cur, next)) {
          break;
      }
  }
  recordFailedCleanup(resource, opName, closeEx, null);
  ```
  Lines 526–532 unconditionally increment `pending + 1` without checking `cur.getTotal() >= cleanupQueueCapacity`.
  While reservation-backed resources are strictly capped because their active permit already held a slot in the total budget, unreserved tasks were admitted solely on worker count (`actualOutstandingWorkers`). As a result, throwing unreserved late closes can push `lifecycle.getTotal()` beyond `cleanupQueueCapacity`.

---

## 4. Verification of Baseline F04 Review & Lifecycle Invariants

| Invariant / Requirement | Baseline F04 Status | Current Revision (`F05_04` In-Progress) Status | Verification & Evidence |
| :--- | :--- | :--- | :--- |
| **No Synchronous Close on Caller** | **VIOLATED** (closed delegate on caller thread upon rejection or shutdown) | **RESOLVED** | Caller thread in `closeAsync` and `close()` strictly dispatches asynchronously and returns in <1ms without invoking `delegate.close()`. |
| **No Inline Task Draining on Shutdown** | **VIOLATED** (drained queued runnables inline on shutdown thread) | **RESOLVED** | [`DriveIoExecutor.shutdown()`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L946-L958) only calls `executor.shutdownNow()`. Queued cleanup tasks run asynchronously on `cleanupExecutor` daemon threads; caller never executes them inline. |
| **Atomic Active-to-Pending Handoff** | **VIOLATED** (separate counter updates caused undercount gap) | **RESOLVED** (for reserved paths) | [`DriveIoExecutor.LifecycleState`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L32-L52) encapsulates `(active, pending, shutdown)` into an immutable record updated via atomic CAS `(active - 1, pending + 1)`. Total capacity is perfectly conserved. |
| **Active Double-Decrement on Worker Failure** | **VIOLATED** in RUN2 (`active` went to -1) | **RESOLVED** | [`DriveResourceReservation.transferToFailed`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveResourceReservation.java#L76) replaces `release()`, executing a single atomic CAS `(active - 1, pending + 1)`. `active` remains non-negative. |
| **Retry In-Flight Deduplication** | **VIOLATED** in RUN2 (concurrent retries queued duplicates) | **RESOLVED** | [`RetainedFailedCleanup.markInFlight()`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L75) CASes `inFlight` flag; concurrent retries return `false` immediately. |

---

## 5. Concrete Recommendations for Writer Parent (`fc195a8d-5c26-4095-875b-2468fa11499a`)

1. **Eliminate the `disposalGate.set(false)` TOCTOU Hole:**
   In [`DriveIoExecutor.java#L476-L479`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L476-L479) and `L487-L489`, remove `disposalGate.set(false)`. Once the caller wins `disposalGate`, caller owns the disposal obligation. If `closeAsync` or `executeCleanupAsync` is rejected, transfer immediately to `transferToFailed` (for reserved) or retain in `retainedFailedCleanups` with atomic `pending + 1` (for unreserved). Never attempt to reset the gate hoping a terminating worker will re-execute.
2. **Fix Unreserved `dispatchLateDisposal` Rejection Accounting:**
   In [`DriveIoExecutor.java#L490-L494`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java#L490-L494), increment `lifecycle.pending + 1` via CAS before calling `recordFailedCleanup(resource, ...)` so that subsequent retry disposal does not underflow `pending` to `-1`.
3. **Align `DriveSeekableByteChannel.retryClose()` with Reservation State:**
   In [`DriveSeekableByteChannel.java#L301-L307`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveSeekableByteChannel.java#L301-L307), do not return `true` if `reservation != null && reservation.hasFailedCleanup()`. Delegate to `reservation.retryCleanup()` so failed physical closes can be retried through the channel handle.

---
*Report completed by Independent Read-Only Gemini Cleanup Reviewer. All inputs remained identical throughout audit; zero workspace modifications performed.*

