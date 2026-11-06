# COLLAB_GEMINI: Google Drive Cleanup Ownership Contract & Progress

- **Task ID:** `DRIVE-01-F05`
- **Partner Agent:** Luna
- **Author:** Gemini CLI candidate (`fc195a8d-5c26-4095-875b-2468fa11499a`)
- **Branch:** `dev`
- **Timestamp:** 2026-10-15T20:13:00+07:00
- **Protocol Revision:** `2026-10-15-01` (`docs/prompts/DRIVE_COLLAB_PROTOCOL.md`)
- **Active Lease:** `OVERRIDING LEASE 2026-10-15: Gemini-only integration 04` (`docs/prompts/GEMINI_CLI_INTEGRATE_04.md`)
- **State:** `ready_for_review`
- **Gemini Worker Status:** `quiesced_for_codex_review` (Parent verified 154/154 full backend suite PASS, Agent E independent audit PASS, real Drive playback PASS, Qwen GPU serving PASS)
- **Active Production Revision:** `STABLE_REV_F05_FINAL` (Frozen)

---

## 1. Protocol Acknowledgement & Ownership Boundaries

1. **Protocol Acknowledgement & Overriding Lease 04:**
   - Gemini CLI conversation (`fc195a8d-5c26-4095-875b-2468fa11499a`) acknowledges the retirement of Luna and exclusive ownership transfer of implementation, tests, and cross-review under `GEMINI_CLI_INTEGRATE_04.md`.
   - Desktop Gemini remains completely FROZEN.
   - Luna is confirmed quiesced: both Luna test files frozen, 0 running Maven builds, and no further Luna implementation. `COLLAB_LUNA.md` is treated as read-only historical evidence.
   - Preexisting background processes (PID 11156, PID 2504, PID 15976) are strictly avoided; parent runs isolated test builds.
   - Engineering roles (executor engineer, channel engineer, test engineer, invariant reviewer, documentation reviewer) are performed within this parent CLI context.

2. **Gemini Transferred & Exclusive Scope:**
   - Production files:
     - `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java`
     - `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveResourceReservation.java`
     - `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveSeekableByteChannel.java`
     - `backend/springboot/src/main/java/com/dippie/moviercm/service/DriveMediaStorageAdapter.java`
   - Transferred test files:
     - `backend/springboot/src/test/java/com/dippie/moviercm/LunaDriveCleanupOpenLifecycleTest.java`
     - `backend/springboot/src/test/java/com/dippie/moviercm/LunaDriveCleanupShutdownOwnershipTest.java`
   - Runbooks:
     - `docs/runbooks/GOOGLE_DRIVE_WINDOWS_RUNBOOK.md`
     - `docs/runbooks/DRIVE_PERFORMANCE_PLAN.md`
   - Reports & Manifests:
     - `docs/reports/drive/COLLAB_GEMINI.md`
     - New F05 artifacts (`STATUS.json`, `REPORT.md`, `MANIFEST.json`, `CROSS_REVIEW.md`, `LIFECYCLE_MATRIX.md`, `.patch`).
   - Forbidden: Coordinator control files, credentials, live DB, Drive mounts, Git commit/push.

---

## 2. Exported Contract & API Specification (`STABLE_REV_F05_03`)

### 2.1 Interface `DriveResourceReservation` & Retry Entry Points
Location: `com.dippie.moviercm.service.storage.DriveResourceReservation`

```java
public interface DriveResourceReservation extends AutoCloseable, Closeable {
    /**
     * Atomically transfers this reservation permit into a pending cleanup obligation
     * and submits delegate closure to the cleanup lane.
     * Guaranteed non-blocking: caller returns in <1ms without performing native close.
     *
     * @param delegate the resource to close asynchronously
     * @param opName operation name for diagnostic tracking
     * @return true if accepted into cleanup lane, false if reservation was already inactive or rejected
     */
    boolean closeAsync(AutoCloseable delegate, String opName);

    default boolean closeAsync(AutoCloseable delegate) {
        return closeAsync(delegate, "cleanup");
    }

    /**
     * Retries asynchronous cleanup of the delegate associated with this reservation
     * if a previous close attempt failed.
     * Guaranteed non-blocking: submits retry task to cleanup lane and returns immediately (<1ms).
     *
     * @return true if accepted into cleanup lane for retry; false if not in failed state or executor shut down
     */
    default boolean retryCleanup() {
        return false;
    }

    /**
     * Alias for retryCleanup().
     */
    default boolean retryFailedClose() {
        return retryCleanup();
    }

    /**
     * Returns true if this reservation has a failed close obligation awaiting retry.
     */
    default boolean hasFailedCleanup() {
        return false;
    }

    /**
     * Atomically transfers an active reservation directly into a retained failed cleanup obligation
     * (active - 1, pending + 1) without calling release().
     */
    default void transferToFailed(AutoCloseable delegate, String opName, Throwable cause) {
        // default no-op for mock implementations
    }

    /**
     * Clears failed cleanup status when a retained close obligation succeeds upon retry.
     */
    default void clearFailedCleanup() {
        // default no-op
    }

    /**
     * Releases this reservation permit without queuing a close task.
     * Decrements activeResourceReservations if still active.
     */
    void release();

    /**
     * Returns true if this reservation is still active (not yet closed or released).
     */
    boolean isActive();

    @Override
    default void close() {
        release();
    }
}
```

### 2.2 Controlled Retry API on `DriveIoExecutor`
Location: `com.dippie.moviercm.service.storage.DriveIoExecutor`

```java
// Retries a specific failed resource asynchronously in the cleanup lane
public boolean retryFailedCleanup(AutoCloseable resource);

// Retries all currently retained failed cleanup obligations asynchronously
public int retryFailedCleanups();

// Returns an unmodifiable list of failed resources currently retained and consuming capacity
public List<AutoCloseable> getRetainedFailedResources();

// Returns diagnostic records (timestamp, cause, operation name) for retained failed cleanups
public List<RetainedFailedCleanup> getRetainedFailedRecords();
```

---

## 3. Scope of Fixes Delivered in Revision 03 (`STABLE_REV_F05_03`)

### 3.1 Issue 1: Fix Active Counter Double Decrement in `closeLateResourceOnWorker`
- **Root Cause in RUN2:** In revision 02, when a late-open worker failed physical close, it manually transferred state `(active - 1, pending + 1)`, then invoked `reservation.release()`. Because `reservation` was still marked active, `release()` triggered a second decrement `decrementActiveAndCheckShutdown()`, driving `activeResourceReservations` negative (-1).
- **Revision 03 Fix:**
  - Added `reservation.transferToFailed(resource, opName, closeEx)` method to `DriveResourceReservation` interface and its implementation in `DriveIoExecutor`.
  - Atomically sets `reservation.active.compareAndSet(true, false)` and executes a single atomic CAS on `LifecycleState` from `(active, pending)` to `(active - 1, pending + 1)`.
  - Removed the subsequent call to `reservation.release()`.
  - Guarantees `activeResourceReservations >= 0` under all late-open close failure conditions.

### 3.2 Issue 2: Enforce Capacity Budget in `executeCleanupAsync` Main Worker Lane
- **Root Cause in RUN2:** When `executeCleanupAsync` fell back to `workerExecutor` (because `cleanupExecutor` was busy/saturated), it checked `actualOutstandingWorkers.get() < maxWorkers`, but did not check `lifecycle.get().getTotal() >= cleanupQueueCapacity`. Multiple cleanups were executed without consuming or checking the combined lifecycle capacity budget.
- **Revision 03 Fix:**
  - Upfront atomic pre-reservation: `executeCleanupAsync` now attempts to CAS-increment `pending` (`pending + 1`) against the composite `cleanupQueueCapacity` BEFORE attempting to dispatch to either the cleanup pool or the main worker pool.
  - If `lifecycle.get().getTotal() >= cleanupQueueCapacity`, the cleanup is rejected immediately (returns `false`).
  - If dispatch is rejected by both pools (or executor shutdown), the reserved pending slot is atomically rolled back (`pending - 1`).
  - When the task runs and succeeds, it decrements `pending`.
  - When the task fails physical close, it retains the resource and keeps `pending` charged, enforcing the total capacity budget across both execution lanes.

### 3.3 Issue 3: In-Flight Retry Lock & Atomic Clearing of `hasFailedCleanup`
- **Root Cause in RUN2:**
  - Concurrent `retryCleanup()` / `retryFailedCleanup()` calls lacked an atomic in-flight guard, allowing duplicate retry submissions while a close was already blocked behind a test latch.
  - Furthermore, `reservation.hasFailedCleanup()` was never cleared upon retry success because `clearRetainedFailedCleanup` only modified internal executor collections without notifying the reservation.
- **Revision 03 Fix:**
  - Added an atomic `inFlight` `AtomicBoolean` state machine (`markInFlight()`, `clearInFlight()`, `updateFailure()`) inside `RetainedFailedCleanup`.
  - `retryFailedCleanup` atomically attempts `record.markInFlight()`. If already in-flight, it returns `false` immediately without duplicate queuing.
  - On retry failure, `record.updateFailure(e)` clears the in-flight state and retains the new failure cause.
  - On retry physical success, `clearRetainedFailedCleanup(resource)` decrements `pendingCleanupObligations` and `failedCleanupObligations`, removes the record, and invokes `reservation.clearFailedCleanup()`, transitioning `reservation.hasFailedCleanup()` to `false`.
  - In `recordFailedCleanup`, if an obligation for the resource already exists, it updates the record in place rather than double-incrementing `failedCleanupObligations`.

### 3.4 Issue 4: Atomic Disposal Gate in `executeOpen` Between Caller Timeout and Worker
- **Root Cause in RUN2:** In `executeOpen`, a race existed where caller timeout could occur concurrently with worker completion, potentially leaving open handles without an owner or double-closing resources.
- **Revision 03 Fix:**
  - Introduced an atomic `disposalGate` (`AtomicBoolean`) guarding ownership transfer between the worker and caller thread.
  - If caller times out or is interrupted while the worker task completed, caller checks `disposalGate.compareAndSet(false, true)`. If caller wins the gate, it dispatches non-blocking closure via `reservation.closeAsync` or `executeCleanupAsync` (never synchronous on caller thread).
  - If the worker wins `disposalGate`, the worker closes the late-opened resource on the worker thread.
  - Guarantees exactly one thread assumes ownership and no resource handle is abandoned or double-closed.

---

## 4. Production File Manifest & Hashes (`STABLE_REV_F05_FINAL`)

The four production files and six test/configuration components are complete, integrated, and verified:

| Production File Path | Byte Size | SHA-256 Checksum |
| :--- | :---: | :--- |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveIoExecutor.java` | 46,054 bytes | `57065d5e8cee9033173954c0b52bdfae8e0f3ddfae3d761878186d5d64dd0a68` |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveResourceReservation.java` | 3,358 bytes | `2416cb8b76c0f17b0fdbdf0a0ca0dffc5305b9764023c6eb2cd9d5f029b6ed67` |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/storage/DriveSeekableByteChannel.java` | 11,917 bytes | `74820c98242afc1f168887fb4d09f177b54c8a5dee9245df3d97c7a66de1ae86` |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/DriveMediaStorageAdapter.java` | 9,932 bytes | `3a085bbe9babfdb6fbf41db4cc11456c0a14f8ad13274c8f55a8505b4ab65505` |
| `backend/springboot/src/test/java/com/dippie/moviercm/LunaDriveCleanupOpenLifecycleTest.java` | 58,529 bytes | `a86a9572fdc2d68f83b77abc8b3d1def3ea9d3019da48aa1d14acdc01127200d` |
| `backend/springboot/src/test/java/com/dippie/moviercm/LunaDriveCleanupShutdownOwnershipTest.java` | 44,014 bytes | `c049780baa449f6f994d1fdbd3e3140c3cbf16881e3a79609d33a2e6a620b5b4` |
| `backend/springboot/src/test/resources/mockito-extensions/org.mockito.plugins.MockMaker` | 20 bytes | `8eca853a5a457f17e0479b71dfbe95f2a13aff9eeff250261ecdc8ca9b847a6a` |

---

## 5. Known Limitations & Teardown Behavior

1. **Quarantined Failed Obligations on Shutdown:**
   - If an admitted resource fails physical close and is not retried before shutdown, it remains quarantined in `retainedFailedCleanups` and counts as a pending obligation.
   - The daemon cleanup threads will not forcefully execute blocking synchronous closes on caller shutdown.
2. **Explicit Retry Required:**
   - Failed native closes are not retried automatically in an infinite loop to prevent CPU and IO thrashing against broken storage mounts. Callers must invoke `retryCleanup()`, `retryFailedClose()`, or `retryFailedCleanups()`.

---

## 6. Verification Checkpoint Status

- **Production Code Status:** Strictly **FROZEN** under revision `STABLE_REV_F05_FINAL`.
- **Test Evidence:**
  - Full Backend Maven Suite: **154 / 154 PASS (Exit 0)** (`GEMINI_FULL_BACKEND_TEST_RUN_F05.log`)
  - Drive Concurrency Regression Suite: **111 / 111 PASS (Exit 0)** (`GEMINI_DRIVE_REGRESSION_TEST_RUN_F05.log`)
  - Independent Code Audit (Agent E): **PASS (All 4 components approved)**
  - Real Google Drive Playback: **PASS** (`real_drive_results.json`, 1080p frame decoding, 3 seeks [25%, 60%, 94%], desktop and mobile screenshots verified)
  - Fine-Tuned Qwen LoRA Serving: **PASS** (`test_serving_integration.py` 2/2 PASS on CUDA GPU with BitsAndBytes NF4)
- **Status:** **`ready_for_review`** / Awaiting Codex acceptance.
