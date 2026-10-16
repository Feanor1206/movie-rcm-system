# DRIVE-01-F07 Usable Snapshot Runbook

**Environment:** Windows 11 (AMD64), JDK 25.0.3, Python 3.10+ (conda `dippie-qwen`), Node.js v20+ / v26.1+  
**Architecture:** Next.js (:3000) $\leftrightarrow$ Spring Boot (:8080) $\leftrightarrow$ FastAPI (:8000) $\leftrightarrow$ Google Drive Mount (X:)

---

## 1. Prerequisites Verification

Before starting services, ensure required ports and drive letters are free:
```powershell
# 1. Verify ports 3000, 8000, 8080 are free
Get-NetTCPConnection -LocalPort 3000, 8000, 8080 -ErrorAction SilentlyContinue

# 2. Verify drive letter X: is unmounted
Get-PSDrive -Name X -ErrorAction SilentlyContinue

# 3. Preflight Google Drive tooling check
pwsh -File scripts/drive/preflight_drive.ps1
```

---

## 2. Service Startup Sequence

### Step 1: Mount Google Drive (Read-Only)
Mount the verified remote folder (`1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ`) containing `videoplayback.mp4`:
```powershell
pwsh -File scripts/drive/mount_drive.ps1 `
    -Remote "cinema-drive,root_folder_id=1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ:" `
    -RemoteSubpath "" `
    -MountPoint "X:" `
    -Execute
```
*Verification:*
```powershell
Get-Item X:\videoplayback.mp4 | Select-Object Name, Length
# Expected: videoplayback.mp4, 29209556 bytes
```

### Step 2: Start Spring Boot Backend (:8080)
Start Spring Boot with the isolated snapshot profile (`--spring.profiles.active=snapshot`, datasource `./data/snapshot/moviercm_snapshot_db`) bound to loopback `127.0.0.1:8080`:
```powershell
# From workspace root (script auto-builds missing classes/classpath and writes PID tracking)
pwsh -File scripts/start_backend_dev.ps1
```
*Health check:*
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/movies/drive-videoplayback/media-descriptor"
# Expected: hasFeature: true, streamUrl: "/api/media/stream/ast-drive-videoplayback"
```

### Step 3: Start FastAPI AI Gateway with Qwen LoRA (:8000)
Start the AI service using the conda environment with RTX 3050 CUDA support:
```powershell
cd backend/fastapi
& "C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
```
*Health check:*
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/readiness"
# Expected: ready: true, servingMode: "full", activeInferenceBackend: "qwen3-4b-peft-lora-4bit-nf4"
```

### Step 4: Start Next.js Frontend (:3000)
Start the frontend web application:
```powershell
cd frontend
npm run dev
```
*Web Access:* Navigate browser to `http://localhost:3000` (or `http://127.0.0.1:3000`).

---

## 3. Playback & AI Usage Instructions

1. **Watch Google Drive Movie:**
   - Open browser at `http://localhost:3000/movies/drive-videoplayback`.
   - Click "Phát Phim Chính" (`[data-testid='play-feature-btn']`).
   - Notice: The video stream starts playing within ~11–19s (Google Drive WAN fetch over rclone VFS).
   - Seek forward/backward: Seeking buffers in ~11–14s.
   - Note on Audio: Container is confirmed video-only DASH stream (H.264 without audio track). This is normal and expected for this file.

2. **Chat with Qwen Recommendation AI:**
   - Click the CineBot AI icon in the bottom-right corner.
   - Enter a query, e.g.: "Tôi muốn tìm một bộ phim hoạt hình phiêu lưu hài hước vui nhộn".
   - The query passes through Next.js $\rightarrow$ FastAPI $\rightarrow$ GPU LoRA inference, returning ranked recommendations and cinema reasoning.

---

## 4. Service Shutdown Sequence

When finished testing, shut down services cleanly:

### Option A: Foreground Terminals (Recommended)
Press `Ctrl+C` in each owned foreground terminal (Next.js, FastAPI, Spring Boot).

### Option B: Verified Process Identity Scripts
```powershell
# 1. Stop Spring Boot Backend (verifies exact recorded PID, ProcessName 'java', and StartTime)
pwsh -File scripts/stop_backend_dev.ps1

# 2. Stop Google Drive Mount safely (verifies exact rclone PID, StartTime, and arguments)
pwsh -File scripts/drive/stop_drive.ps1

# 3. Stop Next.js and FastAPI by pressing Ctrl+C in their owned foreground windows

# 4. Verify drive X: and ports are completely released
Get-PSDrive -Name X -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 3000, 8000, 8080 -ErrorAction SilentlyContinue
```
*(No broad `Stop-Process` or regex name-matching is ever used, ensuring other processes and services remain untouched).*
