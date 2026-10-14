# Google Drive Storage Contract — DRIVE-01

**Milestone:** DRIVE-01  
**Target:** Spring Boot Media Storage & Stream Delivery via Windows Mount  
**Status:** DRAFT / APPROVED FOR AGENT IMPLEMENTATION  
**Author:** Parent Orchestrator  

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

---

## 4. Windows Operations Toolkit Semantics (Windows Operations - Agent B)

1. **Preflight Script (`scripts/drive/preflight_drive.ps1`):**
   - Read-only inspection of Windows OS, `rclone.exe`, WinFsp installation, mount drive collision, account session visibility, and free RAM/disk.
   - Never outputs credentials, tokens, or confidential configuration.
2. **Mount Script (`scripts/drive/mount_drive.ps1`):**
   - Parameters: `Remote`, `RemoteSubpath`, `MountPoint`, `ConfigPath`, `WhatIf`, `Execute`.
   - Default mode is dry-run (`-WhatIf`). Mounting requires explicit `-Execute`.
   - Mount baseline flags:
     `--read-only --vfs-cache-mode off --buffer-size 32M --vfs-read-chunk-size 8M --vfs-read-chunk-size-limit 32M --vfs-read-chunk-streams 0`
   - Background launch via `Start-Process -WindowStyle Hidden` recording PID, start timestamp, executable path, and mount target in a local state JSON file outside git.
3. **Status & Stop Scripts (`scripts/drive/status_drive.ps1`, `scripts/drive/stop_drive.ps1`):**
   - `status_drive.ps1`: Verifies process vitality and filesystem readability without secret leaks.
   - `stop_drive.ps1`: Validates recorded PID against executable path and start time to prevent accidental killing of reused PIDs; terminates only helper-owned processes. Never kills arbitrary `rclone.exe` or user processes.

---

## 5. Verification & Gate Definitions (Verification - Agent C)

- **G1 (IMPLEMENTATION):** Production code compiles, unit tests pass, isolated tests pass with local temporary mock mount directory. Status: **PASS**.
- **G2 (MOUNTED_DRIVE):** Real rclone + WinFsp mount on Windows with real user credentials. Status: **BLOCKED_EXTERNAL_INPUT** (requires interactive user setup outside automated coding scope).
- **G3 (BROWSER_DRIVE):** Real end-to-end browser playback against live Google Drive. Status: **BLOCKED_EXTERNAL_INPUT** (depends on G2).
