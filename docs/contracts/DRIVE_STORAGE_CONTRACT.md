# Google Drive Storage Contract — DRIVE-01

**Milestone:** DRIVE-01  
**Target:** Spring Boot Media Storage & Stream Delivery via Windows Mount  
**Version:** 1.2.0 (Updated: 2026-10-15 — Checkpoint DRIVE-01-F03)  
**Status:** APPROVED TECHNICAL CONTRACT  
**Author:** Platform Orchestration & Agent F (Integration Evidence & Docs)  

---

## 1. Storage Provider Architecture & Abstraction

### 1.1 `MediaStorageAdapter` Interface
The `MediaStorageAdapter` interface is extended to support random-access channel opening (`SeekableByteChannel` / `FileChannel`) in addition to existing `Resource` methods:

```java
package com.dippie.moviercm.service;

import org.springframework.core.io.Resource;
import java.io.IOException;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.Path;

public interface MediaStorageAdapter {

    String getProviderName();

    boolean isAvailable();

    Path resolveValidatedPath(String relativePath);

    Resource getResource(String relativePath);

    long getResourceLength(String relativePath);

    SeekableByteChannel openChannel(String relativePath) throws IOException;
}
```

### 1.2 Configuration Properties
Configured in `application.yml` and overridable via environment variables:
- `app.media.root`: `${APP_MEDIA_ROOT:./media}` (Local storage root)
- `app.media.drive-mount`: `${APP_MEDIA_DRIVE_MOUNT:}` (Google Drive Windows mount path, e.g. `M:\DippieMedia` or empty string if disabled)
- `app.media.max-concurrent-streams`: `${APP_MEDIA_MAX_CONCURRENT_STREAMS:10}` (Bounded concurrency permits)

---

## 2. Security & Path Boundary Invariants (Storage Boundary - Agent A)

`DriveMediaStorageAdapter` must enforce strict validation on any input `relativePath`:
1. **Explicit Root:**
   - Root is taken strictly from `app.media.drive-mount`.
   - If empty or whitespace: adapter is marked unavailable (`isAvailable() == false`).
   - If configured path does not exist, is not a directory, or is not readable: throws `MediaUnavailableException` (HTTP 503).
   - Never falls back to parent directory, local media root, or application working directory.
   - Read-only: Never creates directories (`mkdir`/`createDirectories`) or files.
2. **Relative Path Sanitization:**
   - Empty or null: throws `SecurityPathTraversalException`.
   - Contains NUL character (`\0`): throws `SecurityPathTraversalException`.
   - Contains directory traversal (`..`): throws `SecurityPathTraversalException`.
   - Absolute or device paths (e.g. `C:\...`, `/...`, `\\server\share`, `\\.\`): throws `SecurityPathTraversalException`.
3. **Containment & Reparse Point Resolution:**
   - Resolved path `root.resolve(relativePath).normalize()` must satisfy `resolved.startsWith(root)`.
   - Real path check `resolved.toRealPath().startsWith(root.toRealPath())` must pass, preventing junction/symlink escape.
4. **File Availability & Error Mapping:**
   - If file does not exist or is not a regular file within a healthy mount root: throws `MediaNotFoundException` (HTTP 404).
   - If file is unreadable due to filesystem permissions / mount disconnection: throws `MediaUnavailableException` (HTTP 503).

---

## 3. Streaming & Random-Access Seek Semantics (Parent / Service / Controller)

1. **Random-Access Seek via `FileChannel`:**
   - Controller uses `SeekableByteChannel channel = mediaStreamService.openMediaChannel(asset)`.
   - On HTTP Range requests, `channel.position(range.getStart())` seeks directly at OS kernel level without discarding intermediate bytes ($O(1)$ application-level discard elimination).
   - Note on cloud latency: While application-level sequential discard is eliminated, remote cloud retrieval latency across network WAN still depends on network RTT and Google Drive API response times.
   - Streaming loop reads bounded 64 KiB chunks (`ByteBuffer.allocate(64 * 1024)`) until `contentLength` is exhausted.
2. **Availability Consistency & D1 Error Handling Contract:**
   - If a movie's feature asset specifies `storageProvider == "drive"` but `driveStorageAdapter.isAvailable() == false`, `getMediaDescriptor()` throws `MediaUnavailableException` (HTTP 503).
   - Strict D1 Invariant: Under no circumstances may an offline Drive mount cause the descriptor endpoint to return HTTP 200 with `hasFeature: false` (which would falsely report to the user that the film lacks media).
   - Client receives HTTP 503, rendering `<div role="alert">` and `<button data-testid="descriptor-retry-btn">`.
   - Once mount is restored, retry click recovers HTTP 200 descriptor and activates playback.
   - Provider Isolation: Failures or downtime on the Google Drive mount must NEVER impact local storage assets (`storageProvider == "local"`), which remain 100% available.
3. **Bulkhead Pattern & Bounded Concurrency Contract:**
   - Concurrency is strictly bounded by `app.media.max-concurrent-streams` (default 10, configurable).
   - Streaming traffic is isolated in its own bulkhead to prevent connection starvation on other business endpoints (recommendations, ratings, search).
   - Atomic permit accounting via `AtomicInteger activeStreamCount` and `AtomicLong totalRejectedCount`.
   - Overload handling: Exceeded permits immediately return HTTP 429 Too Many Requests with mandatory headers:
     - `Retry-After: 5`
     - `Cache-Control: no-store, no-cache, must-revalidate`
     - JSON body: `{"status":429,"error":"Too Many Requests","message":"Hệ thống đang phục vụ tối đa luồng phát media đồng thời. Vui lòng thử lại sau 5 giây."}`
   - Guaranteed permit recovery: Permits are unconditionally released in a `finally` block in `MediaStreamController` even on client abort (`ClientAbortException`), socket resets, or broken pipes.
4. **Timeout & Circuit Breaker Contract:**
   - Diagnostic test gate `awaitTestStreamGate` enforces a strict 5000ms deadline to prevent thread starvation.
   - Non-blocking availability checks: `DriveMediaStorageAdapter.isAvailable()` evaluates local mount point vitality synchronously without unbounded blocking.
   - Fast fail: When mount is missing or unreadable, adapter trips immediately to unavailable status, short-circuiting downstream I/O requests with HTTP 503.
   - Self-healing: As soon as the mount directory becomes readable again, requests succeed automatically without requiring application restart.
5. **Resource Lifecycle & Asynchronous Ownership Contract (F1 / R1):**
   - **Resource Ownership Handshake:**
     - Opening a storage channel on cloud-backed mounts involves asynchronous dispatch to a bounded worker pool (`DriveIoExecutor`).
     - To prevent resource orphaning across timeout or cancellation races, the worker and caller execute a strict ownership handshake:
       - State `PENDING`: Worker is executing `FileChannel.open(targetPath, StandardOpenOption.READ)`.
       - State `TRANSFERRED_TO_CALLER`: If worker completes before caller deadline, caller assumes exclusive ownership of the channel. The worker thread yields ownership and will NEVER close the channel.
       - State `DISOWNED_OR_TIMED_OUT`: If caller deadline expires before worker completes, caller marks the request as abandoned/timed out and returns `MediaUnavailableException` (HTTP 503).
   - **Comprehensive Worker Operation Tracking (`activeWorkerOperations`):**
     - Channel worker ownership is NOT restricted to read operations; it covers ALL in-flight operations on the channel: `read(ByteBuffer)`, `position(long)`, and `size()`.
     - In-flight worker operations are tracked collectively via `activeWorkerOperations` (superseding the narrow `activeWorkerReads`).
     - When `DriveSeekableByteChannel.close()` is invoked while `activeWorkerOperations > 0`, the caller thread exits immediately without blocking on kernel WinFsp IO.
     - The active worker thread running the operation assumes deferred ownership and performs `closeDelegateSilently()` once its operation physically completes, fails, or unblocks.
   - **Non-Blocking Caller Close Policy & Saturated Cleanup Handling:**
     - When the caller or Spring MVC `try-with-resources` terminates (e.g. client disconnect, broken pipe, request completion, or deadline abort), calling `DriveSeekableByteChannel.close()` must return promptly.
     - **Absolute Non-Blocking Guarantee:** The caller thread must not be held hostage or blocked indefinitely under ANY circumstance, even when an underlying kernel I/O is stalled or when the cleanup pool is saturated.
     - When `activeWorkerOperations == 0`, closure is dispatched to the bounded cleanup pool (`executeCleanupAsync`).
     - **No Synchronous Caller Fallback on Saturation:** Under NO circumstances may a cleanup executor rejection (saturated cleanup pool / thread queue full) cause the caller thread to fall back to a synchronous, blocking `delegate.close()` call. Direct caller close fallback is strictly prohibited because closing an underlying Windows kernel file handle / WinFsp channel can block indefinitely if an internal kernel I/O is held up.
     - Saturated cleanup must be handled via a non-blocking fallback (such as an asynchronous daemon cleanup queue or background executor) that preserves the caller's finite deadline, while ensuring physical worker accounting (`actualOutstandingWorkers`) remains held until physical closure completes.
     - **True Capacity Accounting:** The physical worker permit (`actualOutstandingWorkers`) is NOT decremented early when the caller exits; it remains accounted for until the underlying OS/kernel delegate close operation physically returns.
     - Unbounded thread spawning or unbounded background queues are strictly prohibited; cleanup occurs within bounded concurrency limits.
   - **Asynchronous AutoCloseable Disposal Without Caller Burden:**
     - In `DriveIoExecutor` (`executeOpen` and generic `executeWithTimeout` returning `AutoCloseable`), caller timeout or thread interruption must NEVER trigger a blocking `ac.close()` directly on the caller thread.
     - If the background task is still executing when the caller deadline expires, the worker thread itself executes late cleanup upon task completion (`state == TIMED_OUT`).
     - If the resource was already instantiated when timeout/interruption occurred, closing that resource is offloaded asynchronously to ensure the caller returns immediately within its finite deadline.
     - Exactly-once disposal is strictly guaranteed via atomic flag guards (`closedDueToTimeout`, `delegateClosed`).
     - Resources delivered timely to the caller (`TRANSFERRED_TO_CALLER`) remain open and protected from racing timeout handlers.
   - **Detailed Lifecycle Breakdown by Operation:**
     - `openChannel(relativePath)`: Asynchronous file open via bounded worker pool. Protected by metadata deadline (`metadataTimeoutMs`, default 3000ms). Handshake ensures either caller receives ownership or worker disposes of late handle asynchronously.
     - `read(ByteBuffer dst)`: Tracked in `activeWorkerOperations`. Bounded chunk read executed via `executeRead(readTimeoutMs)`. On kernel hang, caller receives timeout exception, circuit breaker records failure, and physical worker count remains held until kernel IO physically resolves.
     - `position()` / `position(long newPosition)`: Tracked in `activeWorkerOperations` when dispatched to executor. Protected by metadata deadline. On timeout, caller exits promptly, worker retains occupancy, and deferred close is triggered by worker upon completion if channel was closed.
     - `size()`: Tracked in `activeWorkerOperations`. Queried via metadata executor with strict deadline protection. On timeout, caller exits promptly and worker executes deferred close upon completion.
     - `close()`: Prompt caller exit under all conditions. Idempotent guard ensures `close()` executes once without caller stall.
   - **Hard Cancellation Limitations of WinFsp / Filesystem Kernel I/O:**
     - WinFsp and the Windows NT I/O subsystem do not support safe, mid-flight "hard cancellation" of blocking kernel-level I/O operations (such as `ReadFile`, `SetFilePointerEx`, or `CloseHandle` dispatched through FUSE mini-filter file system drivers).
     - Java thread interruption (`Thread.interrupt()`) sets an interrupt flag but cannot force-abort a native thread blocked inside a CGO/WinFsp kernel dispatch routine without risking OS deadlocks, process instability, or driver corruption.
     - Therefore, the system contract explicitly acknowledges this physical reality: hard cancellation is neither promised nor attempted. Instead, caller latency is guaranteed via finite deadlines, non-blocking caller close, and asynchronous disposal, while stalled kernel operations are safely isolated within a bounded worker pool governed by a circuit breaker to protect system stability.

---

## 4. Windows Operations Toolkit Semantics (Windows Operations - Agent B)

1. **Preflight Script (`scripts/drive/preflight_drive.ps1`):**
   - Read-only inspection of Windows OS, `rclone.exe`, WinFsp installation, mount drive collision, account session visibility, and free RAM/disk.
   - Never outputs credentials, tokens, or confidential configuration.
2. **Mount Script (`scripts/drive/mount_drive.ps1`):**
   - Parameters: `Remote`, `RemoteSubpath`, `MountPoint`, `ConfigPath`, `WhatIf`, `Execute`.
   - Default mode is dry-run (`-WhatIf`). Mounting requires explicit `-Execute`.
   - Mount baseline flags:
     `--read-only --vfs-cache-mode off --buffer-size 32M --vfs-read-chunk-size 8M --vfs-read-chunk-size-limit 32M --vfs-read-chunk-streams 0 --dir-cache-time 72h --poll-interval 15s --attr-timeout 1s`
   - Background launch via `Start-Process -WindowStyle Hidden` recording complete 9-field process identity into runtime state JSON.
3. **Status & Stop Scripts (`scripts/drive/status_drive.ps1`, `scripts/drive/stop_drive.ps1`):**
   - `status_drive.ps1`: Verifies process vitality and filesystem readability without secret leaks.
   - `stop_drive.ps1`: Validates complete process identity before signaling; terminates only helper-owned processes. Never kills arbitrary `rclone.exe` or user processes.
4. **Process Identity & Ownership Verification Contract (F2 / R2):**
   - **Mandatory 9-Field Schema State:**
     Every runtime state JSON file (default: `$env:TEMP\movie-rcm-drive-mount.json`) must contain all 9 required schema fields:
     1. `pid`: Positive integer identifying the specific process ID.
     2. `processName`: Exact process name (must strictly equal `"rclone"`).
     3. `executablePath`: Fully-qualified, normalized path to `rclone.exe`.
     4. `startTime`: Exact process creation timestamp (ISO 8601 formatted timestamp or exact `DateTimeOffset` string).
     5. `sessionId`: Windows Logon Session ID matching caller context.
     6. `mountPoint`: Validated Windows drive letter (`M:`) or directory mount point.
     7. `remoteTarget`: Exact remote name and subpath (`cinema-gdrive:DippieMedia`).
     8. `arguments`: Exact arguments array or string used during launch.
     9. `status`: Lifecycle status string (`"MOUNTING"` or `"RUNNING"`).
   - **Exact Process Creation Identity (Zero Loose Tolerance):**
     - Anti-PID reuse verification strictly compares the live process creation timestamp (`Process.StartTime` / `Win32_Process.CreationDate`) against the recorded state timestamp with exact precision.
     - Multi-second or multi-millisecond loose tolerances (such as 200ms or 500ms drift windows) are strictly prohibited.
     - Any near-time PID reuse (e.g., an unrelated process spawned 200ms later reusing the same PID) is detected and rejected with `PID_REUSE_REJECTED`.
   - **Mandatory Live Invocation & Mount Target Verification (`CommandLine` Match):**
     - The presence of 9 non-empty fields in the state file alone does NOT prove ownership of a live process.
     - Scripts MUST inspect the live process command line (`CommandLine` property via CIM/WMI `Win32_Process`) and confirm that it contains BOTH:
       1. The exact expected `remoteTarget` (e.g., `cinema-gdrive:DippieMedia`), AND
       2. The exact expected `mountPoint` (e.g., `M:`).
     - If a running process matches the PID, process name (`rclone`), executable path, and session ID, but its actual live command line was launched with a different remote or mount point (e.g., `unrelated:other` on `Y:`), it is NOT helper-owned. The script must NEVER signal or terminate it.
     - To eliminate Time-of-Check to Time-of-Use (TOCTOU) races between validation and signaling, scripts prefer validating and retaining an owned process handle directly rather than repeatedly querying unchecked PIDs.
   - **Strict Fail-Closed Policy on Missing, Corrupted, or Unreadable Identity:**
     - If ANY of the 9 required fields is missing, null, empty string, or invalid; OR if live process identity cannot be read (e.g., access denied, process exited during inspection, WMI query failure); OR if ANY attribute (PID, name, path, creation time, session, CommandLine target/mount) does NOT match:
     - The operation immediately **Fails Closed**:
       - No termination signal (`Stop-Process`, `taskkill`) is ever issued.
       - The state file is **strictly preserved on disk** untouched (never deleted, overwritten, or assumed dead) to ensure traceability, forensic auditability, and safety.
       - Returns explicit status: `VERIFICATION_FAILED`, `IDENTITY_MISMATCH`, or `LIVE_IDENTITY_UNREADABLE` with diagnostic details.
     - **No Permissive Defaults:** The system never defaults missing fields (e.g., missing `processName` is never defaulted to `"rclone"`; missing `sessionId` is never bypassed).
   - **Universal Enforcement:** This verification logic is enforced uniformly across `status_drive.ps1`, `stop_drive.ps1`, and launcher failure cleanup inside `mount_drive.ps1`.

---

## 5. Verification & Gate Definitions (Verification - Agent C)

- **G1 (IMPLEMENTATION):** Production code compiles, unit tests pass, isolated tests pass with local temporary mock mount directory. Status: **PASS**.
- **G2 (MOUNTED_DRIVE):** Real rclone + WinFsp mount on Windows with real user credentials. Status: **BLOCKED_EXTERNAL_INPUT** (requires interactive user setup outside automated coding scope).
- **G3 (BROWSER_DRIVE):** Real end-to-end browser playback against live Google Drive. Status: **BLOCKED_EXTERNAL_INPUT** (depends on G2).

