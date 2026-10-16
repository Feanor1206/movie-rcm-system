# DRIVE-01-F04 Evidence & Verification Repository

**Checkpoint:** DRIVE-01-F04  
**Task ID:** DRIVE-01-F04  
**Timestamp:** 2026-10-15  
**Maintainer:** Agent F (Documentation, Contract Audit, and F04 Evidence Preparation)  

---

## 1. Directory Structure & Evidence Ownership

This directory houses the authoritative verification evidence, lifecycle contract specifications, cross-review ledgers, and audit reports for checkpoint `DRIVE-01-F04`, resolving the R1 cleanup saturation and shutdown ownership finding identified in `docs/reviews/DRIVE_01_F03_REVIEW.md`.

```text
docs/reports/drive/DRIVE_01_F04/
├── README.md                          # Evidence index, manifest, and environment declaration
├── CLEANUP_ADMISSION_CONTRACT.md      # Authoritative cleanup admission & lifecycle contract specification
├── CROSS_REVIEW.md                    # Mandatory cross-agent review findings ledger
├── LIFECYCLE_MATRIX.md                # 12-row complete lifecycle acceptance matrix with evidence mappings
├── agent-c/                           # Agent C: DriveCleanupQueueSaturationTest outputs & logs
├── agent-d/                           # Agent D: DriveCleanupShutdownOwnershipTest outputs & logs
├── agent-e/                           # Agent E: Independent lifecycle audit reports & repro evidence
└── screenshots/                       # Browser playback & UI evidence screenshots (post-integration smoke)
```

---

## 2. Core Problem & F04 Architectural Resolution

### 2.1 The R1 Finding (DRIVE_01_F03_REVIEW.md)
In F03, `DriveIoExecutor.java` configured its fallback cleanup thread pool with a bounded queue (`LinkedBlockingQueue(256)`) and `ThreadPoolExecutor.DiscardOldestPolicy`.
When cleanup backed up under sustained pressure:
1. Submitting additional close tasks silently discarded existing queued close tasks without physical execution.
2. `actualOutstandingWorkers` only tracked active main IO threads, remaining blind to queued and physical cleanup operations.
3. Callers caught and swallowed submission failures or marked delegates closed before ownership was successfully accepted.
4. On `shutdown()`, unexecuted close obligations were dropped without drain.
5. Reviewer repro `DRIVE_F03_cleanup_pressure.java` demonstrated that 300 submitted closes resulted in 42 leaked open file handles on a saturated executor.

### 2.2 The F04 Cleanup Admission Contract
F04 replaces silent discard and unbounded queue pressure with a strict, ownership-preserving lifecycle bounded by four architectural pillars:

1. **Explicit Admission Gate (`acquireReservation()`):**
   - Resource acquisition (channel opening, metadata streams) requires an explicit admission reservation upfront.
   - If total capacity (main workers + cleanup queue capacity) is exhausted, the system fails fast immediately (`MediaUnavailableException`) *before* native file handles are acquired.
   - No resource obligation is ever accepted without guaranteed disposal capacity.

2. **Four Distinct Metric Lanes:**
   - **Lane 1: Active Main IO Workers (`activeMainWorkers`):** Physical background worker threads executing active read, position, or size operations.
   - **Lane 2: Active Physical Cleanup Workers (`activeCleanupWorkers`):** Physical background threads actively executing native `close()` on delegates.
   - **Lane 3: Queued Close Obligations (`queuedCleanupObligations`):** Accepted close tasks waiting in the cleanup queue for worker execution.
   - **Lane 4: Active Resource Reservations (`activeReservations`):** Total outstanding resource obligations (caller-held + operation-active + queued-cleanup).
   Main worker count is never conflated with total physical resource consumption.

3. **Drain on `shutdown()`:**
   - Both graceful `shutdown()` and abrupt `shutdownNow()` drain, preserve, and physically close all accepted queued obligations.
   - Tasks returned from `shutdownNow()` are processed to completion so no accepted handle is abandoned or leaked.
   - New admission requests during or after shutdown are immediately rejected.

4. **Resource Conservation Law:**
   At every instant in time:
   $$\text{Acquired Resources} = \text{Caller-Owned} + \text{Operation-Owned} + \text{Cleanup-Owned} + \text{Physically Closed}$$
   - Ownership sets are strictly disjoint.
   - Exactly-once disposal: every accepted handle is closed once and only once.
   - Admissions rejected prior to acquisition create zero handles and are tracked independently.
   - Upon latch release / system recovery, all accepted resources are physically closed, and all metric counters return strictly to baseline (zero).

---

## 3. Parallel Ownership Matrix

| Agent | Scope | Files Owned / Primary Deliverable |
| :--- | :--- | :--- |
| **Agent A** | Core Executor & Admission | `DriveIoExecutor.java` (admission gate, 4 metric lanes, drain on shutdown, non-discarding cleanup queue). |
| **Agent B** | Channel & Adapter Integration | `DriveSeekableByteChannel.java`, `DriveMediaStorageAdapter.java` (reservation handshake, transfer semantics, delegate closure ownership). |
| **Agent C** | Queue Saturation Test Suite | `DriveCleanupQueueSaturationTest.java` (tests exceeding cleanup capacity, slow/blocked close, recovery, conservation law). |
| **Agent D** | Shutdown Ownership Test Suite | `DriveCleanupShutdownOwnershipTest.java` (shutdown races, rejected executions, drain verification, timeout boundary handoffs). |
| **Agent E** | Independent Lifecycle Audit & Stress | Independent audit of A/B changes, adversarial edge-case verification, standalone repro test suite. |
| **Agent F** | Documentation, Runbooks & Cross-Review | Contract specifications (`CLEANUP_ADMISSION_CONTRACT.md`), `CROSS_REVIEW.md` ledger, `LIFECYCLE_MATRIX.md`, runbook updates, and evidence curation. |

---

## 4. Evidence Ingestion & Verification Checklist

| Item | File Path | Responsible Agent | Verification Criteria |
| :--- | :--- | :--- | :--- |
| **Cleanup Admission Contract** | `CLEANUP_ADMISSION_CONTRACT.md` | Agent F | Formal definition of state transitions, admission gate, 4 metric lanes, shutdown drain, and conservation proof. |
| **Cross-Review Ledger** | `CROSS_REVIEW.md` | Agent F | Multi-agent findings ledger (Reviewer, commit hash, scenario, priority, fix, regression evidence, re-review). |
| **Lifecycle Matrix** | `LIFECYCLE_MATRIX.md` | Agent F | 12/12 row lifecycle matrix detailing invariant, test class, and evidence mapping. |
| **Saturation Suite Log** | `agent-c/saturation_test.log` | Agent C | `DriveCleanupQueueSaturationTest` exit 0, $\ge 300$ handles tested, zero leaks, conservation verified. |
| **Shutdown Suite Log** | `agent-d/shutdown_test.log` | Agent D | `DriveCleanupShutdownOwnershipTest` exit 0, drain on shutdown verified, zero abandoned tasks. |
| **Lifecycle Audit Log** | `agent-e/audit_evidence.log` | Agent E | Independent lifecycle stress run, adversarial edge cases passing, zero invariant violations. |
| **Post-Integration Browser Smoke** | `screenshots/`, `walkthrough_results.json` | Agent F (if delegated) | Range request 206, playback, seek, mobile controls, and snapshot parity verified on fresh root. |

---

## 5. Environment & Execution Provenance

- **Operating System:** Windows 10 / Windows 11 x64 (NT Kernel)
- **JVM Runtime:** Java JDK 25 / target bytecode JDK 17
- **Test Harness:** Isolated temporary filesystem fixtures (`@TempDir`, `Files.createTempFile`) with real `FileChannel` native handles; isolated H2 database; zero cloud/live Drive mutation.
- **External Dependencies:** WinFsp 2.1, rclone 1.75.1 (OAuth `cinema-drive:VideoDieppie` verified read-only). Live mount execution remains segregated under manual Codex gates G2/G3.
