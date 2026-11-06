# DRIVE-01-F08 Concurrency & Lifecycle Invariant Matrix

| Operation / Path | Admission Invariant | Active Permit Accounting | Pending Permit Accounting | Saturated Capacity Behavior | Shutdown & Recovery Drain |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Caller-Reserved `executeOpen`** | Requires `reservation.isActive() == true` | Charged 1 active permit upon reservation acquisition | Uncharged (active path) | Rejected at initial reservation acquisition if `cur.getTotal() >= capacity` | If timeout + close fails, transfers to pending failed obligation (`chargesPending=true`) |
| **Unreserved `executeOpen`** | Requires internal reservation permit (`acquireReservation()`) | Charged 1 active permit internally | Uncharged (active path) | Rejected fail-fast before opening native handle (`cur.getTotal() >= capacity`) | If timeout + close fails, transfers to pending failed obligation (`chargesPending=true`) |
| **Scalar `executeMetadata` / `executeRead`** | Pure scalar lane: strictly forbids `AutoCloseable` results (throws `IllegalArgumentException` and closes if violated). Bounded by `actualOutstandingWorkers <= maxWorkers` | 0 (no lifecycle permits consumed) | 0 (no lifecycle permits consumed) | Rejects fail-fast when `actualOutstandingWorkers >= maxWorkers` | No native resources produced; workers join cleanly during shutdown |
| **Resource-Producing `executeWithTimeout` (AutoCloseable)** | Requires lifecycle pre-admission via internal reservation (`acquireReservation()`). Bounded by `cur.getTotal() < capacity` and `actualOutstandingWorkers <= maxWorkers` | Charged 1 active permit internally | Uncharged (active path) | Rejected fail-fast before worker thread spawn or native handle opening (`cur.getTotal() >= capacity`) | If timeout + close fails, transfers to pending failed obligation (`chargesPending=true`), bounded by queue capacity |
| **Direct `executeCleanupAsync`** | Bounded cleanup pool gate | None (cleanup lane) | Dynamically acquires 1 pending permit in `lifecycle` | Returns `false` fail-fast when `cur.getTotal() >= capacity` | Retained in `retainedFailedCleanups`, retried across shutdown |
| **`retryFailedCleanup` / `retryFailedCleanups`** | Enforces single in-flight retry per resource via `markInFlight()` | None | Permit already charged on retention (`chargesPending=true`) | Safely executes bounded close retry | Drains across shutdown; `cleanupExecutor.shutdown()` fires only when `cur.getTotal() == 0 && retainedFailedCleanups.isEmpty()` |
| **`shutdown()`** | CAS `isShutdown = true` | Prevents new admissions | Allows existing active/pending to drain | Closes main worker pool immediately (`shutdownNow`) | `cleanupExecutor` remains active until all active/pending and all retained failed cleanups are drained |

---

## Strict Concurrency Invariants Enforced in F08 (Finding R1 Resolution)

1. **Strict Resource Boundedness & Non-Negative Permits**:
   $$\text{retainedFailedCleanups.size()} \le \text{pendingCleanupObligations} \le \text{cleanupQueueCapacity}$$
   $$\text{activeResourceReservations} \ge 0, \quad \text{pendingCleanupObligations} \ge 0$$
   $$\text{activeResourceReservations} + \text{pendingCleanupObligations} \le \text{cleanupQueueCapacity}$$
   Guaranteed by atomic compare-and-swap on `LifecycleState` and strict decrement guards.
   Completely eliminated `chargesPending=false` and unreserved quarantine leaks.

2. **Strict Scalar vs Resource-Producing Boundary**:
   - Scalar operations (`executeMetadata`, `executeRead`) NEVER consume lifecycle permits and NEVER return or retain `AutoCloseable` resources.
   - Resource-producing operations (`executeOpen`, `executeWithTimeout`) ALWAYS acquire lifecycle permits prior to opening native handles.

3. **Zero Native Handle Leaks Under Capacity Saturation**:
   Pre-admission checks (`cur.getTotal() >= capacity`) reject execution BEFORE opening native resources, eliminating both unbounded handle growth and unreserved retention.

4. **Quiescent Recovery & Safe Shutdown Drain**:
   $$\text{cleanupExecutor.isShutdown()} \iff \text{lifecycle.isShutdown()} \land \text{total} == 0 \land \text{retainedFailedCleanups.isEmpty()}$$
   Guarantees that retry tasks can recover retained handles even after shutdown is requested.
