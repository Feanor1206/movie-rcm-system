# DRIVE-01-F09 Concurrency & Lifecycle Invariant Matrix

| Operation / Path | Admission Invariant | Active Permit Accounting | Pending Permit Accounting | Saturated Capacity Behavior | Shutdown & Recovery Drain |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Caller-Reserved `executeOpen`** | Requires `reservation.isActive() == true` | Charged 1 active permit upon reservation acquisition | Uncharged (active path) | Rejected at initial reservation acquisition if `cur.getTotal() >= capacity` | If timeout + close fails, transfers to pending failed obligation (`chargesPending=true`) |
| **Unreserved `executeOpen`** | Requires internal reservation permit (`acquireReservation()`) | Charged 1 active permit internally | Uncharged (active path) | Rejected fail-fast before opening native handle (`cur.getTotal() >= capacity`) | If timeout + close fails, transfers to pending failed obligation (`chargesPending=true`) |
| **Scalar `executeMetadata` / `executeRead`** | Pure scalar lane: strictly forbids `AutoCloseable` results. Bounded by `actualOutstandingWorkers <= maxWorkers` | 0 (no lifecycle permits consumed) | 0 (no lifecycle permits consumed) | Rejects fail-fast when `actualOutstandingWorkers >= maxWorkers` | No native resources produced; workers join cleanly during shutdown |
| **Forbidden `AutoCloseable` in `executeScalar`** | Detected after execution: attempts immediate close. If close throws, records into `retainedFailedCleanups` | 0 | Dynamically charges 1 pending permit if `cur.pendingCleanupObligations < capacity` (`chargesPending=true`), else `false` | Retained bounded by capacity; chained into thrown `IllegalArgumentException` | Drainable via `retryFailedCleanups()`; permit decremented in `clearRetainedFailedCleanup` only if `chargesPending=true` |
| **Resource-Producing `executeWithTimeout` (AutoCloseable)** | Requires lifecycle pre-admission via internal reservation (`acquireReservation()`). Bounded by `cur.getTotal() < capacity` | Charged 1 active permit internally | Uncharged (active path) | Rejected fail-fast before worker thread spawn or native handle opening (`cur.getTotal() >= capacity`) | If timeout + close fails, transfers to pending failed obligation (`chargesPending=true`), bounded by queue capacity |
| **Direct `executeCleanupAsync`** | Bounded cleanup pool gate | None (cleanup lane) | Dynamically acquires 1 pending permit in `lifecycle` | Returns `false` fail-fast when `cur.getTotal() >= capacity` | Retained in `retainedFailedCleanups`, retried across shutdown |
| **`retryFailedCleanup` / `retryFailedCleanups`** | Enforces single in-flight retry per resource via `markInFlight()` | None | Permit charged only if `chargesPending=true` | Safely executes bounded close retry | Drains across shutdown; `cleanupExecutor.shutdown()` fires only when `cur.getTotal() == 0 && retainedFailedCleanups.isEmpty()` |
| **`shutdown()`** | CAS `isShutdown = true` | Prevents new admissions | Allows existing active/pending to drain | Closes main worker pool immediately (`shutdownNow`) | `cleanupExecutor` remains active until all active/pending and all retained failed cleanups are drained |

---

## Strict Concurrency Invariants Enforced in F09

1. **Strict Resource Boundedness & Non-Negative Permits**:
   $$\text{retainedFailedCleanups.size()} \le \text{cleanupQueueCapacity}$$
   $$\text{activeResourceReservations} \ge 0, \quad \text{pendingCleanupObligations} \ge 0$$
   $$\text{activeResourceReservations} + \text{pendingCleanupObligations} \le \text{cleanupQueueCapacity}$$
   Guaranteed by atomic compare-and-swap on `LifecycleState` and conditional decrements governed by `chargesPending`.

2. **Strict Scalar Rejection & Exception Chaining**:
   - Scalar lane never accepts `AutoCloseable`.
   - If returned, close is attempted immediately.
   - If close fails, the close exception is chained into `IllegalArgumentException` and retained with dynamic pending accounting, eliminating silent resource drops.

3. **Strict Process Identity & Fail-Closed Termination**:
   - Process stopping validates complete state schema (`PID`, `StartTime`, `ExecutablePath`, `CommandLine`, `CreationDate`).
   - Live process must match canonical path, `java.exe`, snapshot profile argument, and creation time within 3 seconds.
   - State file is only unlinked after verified termination.
