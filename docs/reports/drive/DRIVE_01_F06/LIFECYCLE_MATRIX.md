# DRIVE-01-F06 Lifecycle State Transition & Concurrency Matrix

## 1. Lifecycle State Definitions

| State / Variable | Type | Allowed Values / Range | Invariant / Semantic Guarantee |
| :--- | :--- | :--- | :--- |
| `active` | Atomic Integer | `0 <= active <= cleanupQueueCapacity` | Number of currently admitted, actively held resource reservation permits. |
| `pending` | Atomic Integer | `0 <= pending <= cleanupQueueCapacity` | Number of cleanup obligations currently pending execution or retained as failed cleanups. |
| `total` | Composite Sum | `0 <= active + pending <= cleanupQueueCapacity` | Total resource obligations under management. Never exceeds `cleanupQueueCapacity`. |
| `shutdown` | Boolean | `false` -> `true` (monotonic) | When true, new reservations and non-internal opens are strictly rejected. |
| `disposalState` | Atomic Integer | `0` to `5` (monotonic transitions) | Handshake state arbitrating worker vs. caller cleanup ownership. |

### Disposal State Enumeration
- `0 (UNCLAIMED)`: Resource newly created by worker, no disposal action initiated.
- `1 (CALLER_DISPATCHING)`: Caller thread timed out or was interrupted and is attempting to submit cleanup task. Worker must spin-wait.
- `2 (DISPATCH_ACCEPTED)`: Caller successfully submitted cleanup to `cleanupExecutor` or reservation queue. Worker skips disposal.
- `3 (DISPATCH_FAILED)`: Caller cleanup submission was rejected (e.g. queue saturation). Worker must claim and execute native closure.
- `4 (WORKER_CLAIMED)`: Worker claimed closure duty; executes `resource.close()` on background worker thread.
- `5 (DISPOSAL_RETAINED)`: Worker completed before caller could dispatch; caller retains failed cleanup obligation on-budget.

---

## 2. State Transition Matrix

| Trigger Event | Initial State | Guard / Condition | Next State | Action / Accounting |
| :--- | :--- | :--- | :--- | :--- |
| **`acquireReservation()`** | `(active, pending)` | `total < capacity && !shutdown` | `(active + 1, pending)` | Admission granted fail-fast. |
| **`acquireReservation()`** | `(active, pending)` | `total >= capacity` | `(active, pending)` | Admission rejected; throws `MediaUnavailableException`. |
| **`acquireReservation()`** | `(active, pending)` | `shutdown == true` | `(active, pending)` | Admission rejected; throws `MediaUnavailableException`. |
| **`executeOpen(task)` (Unreserved)** | `(active, pending)` | `total < capacity && !shutdown` | `(active + 1, pending)` | Pre-admission permit acquired internally before task dispatch. |
| **`executeOpen(task)` (Unreserved)** | `(active, pending)` | `total >= capacity` | `(active, pending)` | Admission rejected fail-fast; task is NEVER dispatched. |
| **Normal Open Success (Unreserved)** | `(active, pending)` | Caller claims handle | `(active - 1, pending)` | Caller assumes ownership; internal permit released immediately. |
| **Caller Timeout (Unreserved Open)** | `(active, pending)` | Worker in-flight | `(active, pending)` | Caller retains `effectiveReservation`; initiates handshake. |
| **Worker Closes Late Handle** | `(active, pending)` | `close()` succeeds | `(active - 1, pending)` | Handle closed natively on worker thread; permit released. |
| **Worker Close Throws** | `(active, pending)` | `close()` throws | `(active - 1, pending + 1)` | Handle retained in `retainedFailedCleanups`; `chargesPending=true`. |
| **Caller Dispatches Late Handle** | `(active, pending)` | `closeAsync` accepted | `(active - 1, pending + 1)` | Task queued in `cleanupExecutor`; permit transferred to pending. |
| **Caller Dispatch Rejected** | `(active, pending)` | Worker completed | `(active - 1, pending + 1)` | `reservation.transferToFailed`; registered with `chargesPending=true`. |
| **`closeAsync(resource)` (Reserved)** | `(active, pending)` | Task accepted | `(active - 1, pending + 1)` | Active permit transfers atomically to pending cleanup obligation. |
| **`closeAsync(resource)` (Reserved)** | `(active, pending)` | Submission rejected | `(active - 1, pending + 1)` | `reservation.transferToFailed`; registered with `chargesPending=true`. |
| **Physical Close Success (Async)** | `(active, pending)` | `resource.close()` OK | `(active, pending - 1)` | Pending obligation cleared; decrements pending, checks shutdown. |
| **Physical Close Fails (Async)** | `(active, pending)` | `resource.close()` throws | `(active, pending)` | Retained in `retainedFailedCleanups`; pending count is preserved. |
| **`retryFailedCleanups()`** | `(active, pending)` | In-flight CAS OK | `(active, pending)` | Tasks re-submitted to `cleanupExecutor` without changing budget. |
| **Retry Physical Close OK** | `(active, pending)` | `resource.close()` OK | `(active, pending - 1)` | Record removed; pending decremented; triggers shutdown if pending=0. |
| **`shutdown()`** | `(active, pending, false)` | `total > 0` | `(active, pending, true)` | `executor.shutdownNow()`; `cleanupExecutor` kept alive to drain. |
| **`shutdown()` Drain Complete** | `(0, 0, true)` | `total == 0` | `(0, 0, true)` | `cleanupExecutor.shutdown()` executed cleanly. |

---

## 3. Strict Concurrency Guarantees

1. **No Handle Leakage Under Saturation:**
   Because all opens (reserved and unreserved) require pre-admission, when `active + pending == capacity`, new opens fail fast. No native handles are opened without a corresponding budget permit.

2. **Strict Counter Nonnegativity:**
   `active` and `pending` are decremented via CAS loops that clamp with `Math.max(0, val - 1)`. Underflow to negative values is mathematically impossible.

3. **Strict Bounded Retention:**
   Every retained failed cleanup unconditionally charges pending. Thus:
   $$\text{retainedFailedCleanups.size()} \le \text{pendingCleanupObligations} \le \text{cleanupQueueCapacity}$$

4. **Zero Caller-Thread Native I/O Blocking:**
   All `resource.close()` calls execute exclusively on background worker or cleanup threads. Callers never block or execute synchronous native close on timeout or shutdown.
