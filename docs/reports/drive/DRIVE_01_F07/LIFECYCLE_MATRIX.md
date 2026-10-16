# DRIVE-01-F07 Concurrency & Lifecycle Invariant Matrix

| Operation / Path | Admission Invariant | Active Permit Accounting | Pending Permit Accounting | Saturated Capacity Behavior | Shutdown & Recovery Drain |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Caller-Reserved `executeOpen`** | Requires `reservation.isActive() == true` | Charged 1 active permit upon reservation acquisition | Uncharged (active path) | Rejected at initial reservation acquisition if `total >= capacity` | If timeout + close fails, transfers to pending failed obligation (`chargesPending=true`) |
| **Unreserved `executeOpen`** | Requires internal reservation permit (`acquireReservation()`) | Charged 1 active permit internally | Uncharged (active path) | Rejected fail-fast before opening native handle (`cur.getTotal() >= capacity`) | If timeout + close fails, transfers to pending failed obligation (`chargesPending=true`) |
| **Generic `executeWithTimeout` (AutoCloseable)** | Bounded worker pool gate (`actualOutstandingWorkers <= maxWorkers`) | None (unreserved metadata helper) | None on admission | Admitted up to `maxWorkers` | If timeout + close fails, recorded in `retainedFailedCleanups` (`chargesPending=false`). Dynamically acquires pending permit on retry once capacity frees up |
| **Direct `executeCleanupAsync`** | Bounded cleanup pool gate | None (cleanup lane) | Dynamically acquires 1 pending permit in `lifecycle` | Returns `false` fail-fast when `cur.getTotal() >= capacity` | Retained in `retainedFailedCleanups`, retried across shutdown |
| **`retryFailedCleanup` / `retryFailedCleanups`** | Enforces single in-flight retry per resource via `markInFlight()` | None | If `!chargesPending`, dynamically reserves 1 pending permit in `lifecycle` | Rejects retry if queue is saturated (`cur.getTotal() >= capacity`), keeping handle retained | Drains across shutdown; `cleanupExecutor.shutdown()` fires only when `cur.getTotal() == 0 && retainedFailedCleanups.isEmpty()` |
| **`shutdown()`** | CAS `isShutdown = true` | Prevents new admissions | Allows existing active/pending to drain | Closes main worker pool immediately (`shutdownNow`) | `cleanupExecutor` remains active until all active/pending and all retained failed cleanups are drained |

---

## Strict Concurrency Invariants Enforced in F07

1. **Non-Negative Permits**:
   $$\text{activeResourceReservations} \ge 0, \quad \text{pendingCleanupObligations} \ge 0$$
   Guaranteed by atomic compare-and-swap on `LifecycleState` and strict decrement guards.

2. **In-Flight Queue Budget**:
   $$\text{activeResourceReservations} + \text{pendingCleanupObligations} \le \text{cleanupQueueCapacity}$$
   Guaranteed by atomic pre-admission checks before every permit increment.

3. **Zero Native Handle Drops**:
   Every opened native handle whose close throws is registered in `retainedFailedCleanups`. It is never silently discarded to maintain artificial counter ceilings.

4. **Safe Shutdown Drain**:
   $$\text{cleanupExecutor.isShutdown()} \iff \text{lifecycle.isShutdown()} \land \text{total} == 0 \land \text{retainedFailedCleanups.isEmpty()}$$
   Guarantees that retry tasks can recover retained handles even after shutdown is requested.
