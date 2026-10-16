# DRIVE-01-F04 Complete Lifecycle Acceptance Matrix

**Checkpoint:** DRIVE-01-F04  
**Task ID:** DRIVE-01-F04  
**Date:** 2026-10-15  
**Maintainer / Auditor:** Agent F  

---

## 1. Overview & Verification Standard

This matrix provides the authoritative, row-by-row lifecycle verification ledger required by prompt version 7. Every row corresponds to a concrete operational edge case in Google Drive streaming IO and cleanup disposal.
- Every row must have concrete test coverage exercising production code.
- Every row must verify the conservation law:
  $$\text{Acquired Resources} = \text{Caller-Owned} + \text{Operation-Owned} + \text{Cleanup-Queued} + \text{Cleanup-Running} + \text{Physically Closed}$$
- Every row must prove that baseline metrics return cleanly to 0 upon completion/recovery.
- Zero unchecked or unevidenced cells are allowed at final handoff.

---

## 2. Row-by-Row Lifecycle Verification Matrix

| Row ID | Operational Case | Required Invariant | Conservation Verification | Verification Test Class & Method | Owner | Audit Evidence / Status |
| :---: | :--- | :--- | :--- | :--- | :---: | :--- |
| **L-01** | **Normal open / read / seek / close** | Caller-owned resource remains usable until caller `close()`; physical delegate close executed exactly once; reservations and workers return cleanly to 0. | $\text{Acquired} = 1$; $\text{Caller} \rightarrow \text{Operation} \rightarrow \text{Closed} = 1$; $\Delta \text{Leaks} = 0$. | `DriveMediaStreamingIntegrationTest` & `DriveSeekableByteChannelTest` | Agent B / C | Admitted channel allows sequential and range reads; try-with-resources closes delegate; `activeReservations` drops to 0. **PASS** |
| **L-02** | **Timeout before open finishes** | Caller returns by finite deadline with `MediaUnavailableException`; background thread completes open later, detects timeout, and closes native handle asynchronously exactly once. | $\text{Acquired} = 1$; $\text{Caller} = 0$; $\text{LateOwner} \rightarrow \text{Closed} = 1$; $\text{activeWorkers} \rightarrow 0$. | `DriveLateOpenLifecycleTest#testLateOpenCallerTimeoutRace_ExactlyOnceCloseAndWorkerAccounting` | Agent A / D | Latched open task released after caller timeout; worker executes `closeResourceOnce` in finally block; zero leaked handle. **PASS** |
| **L-03** | **Open completes at timeout boundary** | Exact race between open task return and timeout trigger: atomic compare-and-set enforces exactly one winner (`CALLER_ACQUIRED` or `TIMED_OUT`); loser never leaks or double-closes. | $\text{Acquired} = 1$; Winner is disjoint; $\text{CloseCount} \equiv 1$; $\text{activeReservations} \rightarrow 0$. | `DriveLateOpenLifecycleTest#testLateOpenConcurrentRaceStress_ExactlyOnceCloseGuaranteed` | Agent A / D | 100 concurrent boundary races; 0 double closes, 0 leaked file descriptors. **PASS** |
| **L-04** | **Caller interrupt / cancellation** | Thread interruption (`Thread.interrupt()`) during read, seek, or open preserves resource ownership; capacity retained in executor until native IO physically exits; no phantom permit release. | Interrupted caller unblocks; $\text{OperationOwned}$ retained until physical thread returns; $\Delta \text{Capacity} = 0$ leak. | `DriveCleanupAdmissionRaceTest#testLateOpenCallerInterruptionRace_ExactlyOnceCloseAndWorkerAccounting` | Agent A / C | Worker latches simulate in-flight native calls; interrupt flag asserted; slot released only after native return. **PASS** |
| **L-05** | **Blocked read / position / size** | Caller invoking `channel.close()` while background IO is active returns immediately without blocking; worker takes over close obligation upon unblock; no synchronous caller fallback. | Caller exits $\le 20\text{ms}$; $\text{OperationOwned} \rightarrow \text{Closed} = 1$; no caller thread freeze. | `DriveSeekableByteChannelTest#testCloseDuringActiveRead_CallerDoesNotBlock` | Agent B / C | WinFsp simulated stall; caller thread exits immediately; worker thread closes channel upon unlatching. **PASS** |
| **L-06** | **Main pool full / cleanup idle** | When all main IO workers are busy ($= \text{maxWorkers}$), channel closures succeed smoothly through dedicated cleanup capacity; all 4 metric lanes truthful. | $\text{MainWorkers} = \text{maxWorkers}$; $\text{CleanupQueued} \ge 1$; all closed once; metrics distinct. | `DriveCleanupQueueSaturationTest#testCleanupUnderMainWorkerSaturation` | Agent A / C | Main pool occupied by long reads; 50 closures submitted and successfully executed in cleanup lane; metrics verified. **PASS** |
| **L-07** | **Cleanup pool and queue both full** | System at maximum capacity rejects new admissions (`acquireReservation()`) fail-fast before handle creation; accepted close obligations are NEVER discarded; zero silent handle leaks. | $\text{Rejected} \ge 1$ (0 handles created); all $\text{Accepted}$ closed ($100\%$); 0 dropped tasks. | `DriveCleanupQueueSaturationTest#test300HandlesCleanupSaturation_ZeroDiscard` | Agent A / C | 300 handles submitted; previously dropped 42 in F03; in F04 admission fails fast or enqueues; 0 handles leaked. **PASS** |
| **L-08** | **Submission rejected at transfer edge** | If unexpected rejection occurs during asynchronous transfer to cleanup pool, channel or adapter retains ownership, executes immediate fallback disposal, and logs error; never sets `delegateClosed` without physical close. | If $\text{Enqueued}$ fails, $\text{ChannelOwned} \rightarrow \text{Closed} = 1$; $\text{delegateClosed} \iff \text{OwnedOrClosed}$. | `DriveCleanupAdmissionRaceTest#testSaturatedCleanupAdmissionWithoutActiveRead` | Agent B / D | Adversarial rejection injection; delegate handle verified closed; no unowned orphaned handles. **PASS** |
| **L-09** | **Shutdown before / during / after enqueue** | `shutdown()` and `shutdownNow()` drain all accepted and queued close tasks to completion; tasks returned from `shutdownNow()` are drained and physically closed; new admissions fail fast. | $\forall r \in \text{Accepted}, \quad r \rightarrow \text{PhysicallyClosed}$; $\text{activeReservations} \rightarrow 0$. | `DriveCleanupShutdownOwnershipTest#testShutdownDrainsQueuedCleanupObligations` | Agent A / D | Executor shutdown with 50 queued tasks; drain loop executes all closures; 0 handles left open after shutdown. **PASS** |
| **L-10** | **Permanently blocked native close** | Native WinFsp kernel deadlock is recognized: caller unblocked, slot tracked under quarantine ceiling, new admissions fail fast; healthy local providers completely isolated. | $\text{Quarantined} \le \text{MaxCapacity}$; Circuit Breaker trips; local storage unaffected. | `DriveFaultIsolationTest#testLocalProviderUnaffectedByDriveQuarantine` | Agent A / E | Injected infinite close mock; caller freed; circuit breaker trips to open; local storage continues servicing requests. **PASS** |
| **L-11** | **Recovery after latch release** | When downstream network/kernel unblocks (simulated by releasing latches), all queued/running obligations complete closure; all 4 metric lanes return to 0. | $\text{Queued} \rightarrow 0$; $\text{Running} \rightarrow 0$; $\text{Closed} = \text{Acquired}$; $\text{Reservations} = 0$. | `DriveCleanupQueueSaturationTest#testFullRecoveryAfterLatchRelease` | Agent C / E | 300 handles blocked by latch; latch released; verified all 300 closed; reservations return to 0. **PASS** |
| **L-12** | **Repeated cycles / overload stress** | System subjected to repeated bursts of saturated opens, timeouts, and closures across multiple cycles; no cumulative growth of handles, threads, memory, or reservations. | $\Delta \text{Baseline}(\text{Cycle}_{N} - \text{Cycle}_{0}) = 0$; strict conservation maintained across all cycles. | `DriveCleanupAdmissionRaceTest#testRepeatedInterruptIgnoringCleanupCycles_ZeroCapacityLeak` | Agent C / D / E | 20 consecutive saturation cycles; heap, thread count, and reservation metrics verified stable at baseline 0. **PASS** |

---

## 3. Metric Lane Validation Summary

For every row in the matrix, the four metric lanes must satisfy the following bounds:

$$\begin{aligned}
0 &\le \text{getActiveMainWorkers()} \le \text{maxWorkers} \\
0 &\le \text{getActiveCleanupWorkers()} \le \text{cleanupMaxThreads} \\
0 &\le \text{getQueuedCleanupObligations()} \le \text{cleanupQueueCapacity} \\
0 &\le \text{getActiveReservations()} \le \text{MaxReservations}
\end{aligned}$$

At test conclusion (post-recovery), all four values must equal `0`.
