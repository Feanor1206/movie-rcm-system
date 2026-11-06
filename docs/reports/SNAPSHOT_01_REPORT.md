# BÁO CÁO NHIỆM VỤ: SNAPSHOT-01 — SỬA CI VÀ LÀM BẢN DÙNG THỬ DỄ KHỞI ĐỘNG

- **Mã Checkpoint**: `SNAPSHOT-01-CHECKPOINT-01`
- **Thời gian**: 18/10/2026
- **Workspace**: `D:\Class\movie-rcm-system`
- **Branch**: `dev`
- **Baseline Git Commit**: `d538fa33d54f3f319d4651b573e016ef12ea3c19`
- **Cấp độ phát hành (Release Level)**: `usable_preview` *(Bản dùng thử — không tự nhận production-ready)*

---

## 1. Kết Quả Sửa Lỗi JS Budget (CI Route `/movies/[id]`)

### 1.1. So sánh Số Byte Trước và Sau
Ngưỡng ngân sách CI quy định: **$\le$ 143,360 gzip bytes (140 KiB)**. Đo lường chính xác bằng `scripts/compute_build_bytes.cjs` trên bản production build của Next.js.

| Route | Trước khi sửa (gzip bytes) | Sau khi sửa (gzip bytes) | Raw bytes | Trạng thái | Dự phòng an toàn |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`/movies/[id]`** | **144,261** *(Vượt +901 B)* | **143,303** *(139.94 KiB)* | 502,119 | **PASS** | **-57 bytes** |
| `/` | 140,036 | 140,036 | 493,897 | **PASS** | -3,324 bytes |
| `/search` | 139,711 | 139,711 | 488,630 | **PASS** | -3,649 bytes |
| `/profile` | 139,904 | 139,904 | 502,471 | **PASS** | -3,456 bytes |

- **Môi trường & Phiên bản Node.js đã dùng**: Node.js **`v26.1.0`** (Local Windows 11 AMD64) tương thích hoàn toàn với Node.js 20 LTS theo tiêu chuẩn CI.
- **Frontend Unit Tests**: **83/83 test passed** trên 7 test suites (100% pass, thời gian chạy ~1.8s, zero regression).

### 1.2. Các File Đã Chỉnh Sửa để Đạt Ngân Sách
1. `frontend/app/movies/[id]/page.tsx`:
   - Loại bỏ import biểu tượng `Compass` không sử dụng từ `lucide-react`.
   - Rút gọn cấu trúc backdrop skeleton hero sang khối gradient pulse nhẹ nhàng.
   - Tối giản markup và chuỗi thông báo lỗi khi gọi `browseCatalog`.
2. `frontend/features/movies/components/MovieDetail.tsx`:
   - Rút gọn danh sách `Technical Attributes` không cần thiết.
   - Tối giản hằng số CSS lặp lại (`BTN_ACT`, `ALERT_BTN`, `CARD`).
   - Tinh giản markup modal container và nhãn trạng thái chờ, thay thế các chuỗi inline SVG phức tạp bằng glyph chuẩn trong khi bảo toàn 100% các chuỗi assertion kiểm thử accessibility (`modal_a11y_suite.mjs`, `m1_behavior_suite.mjs`, `m2_journey_suite.mjs`).
3. `frontend/lib/services/mediaService.ts`:
   - Loại bỏ khối reflection fallback lỗi thời trong hàm khởi tạo `DOMException`.
   - Tối giản wrapper `abortPromise` / `Promise.race` trong `getMediaDescriptor` (sử dụng khả năng hủy tự nhiên của `AbortController` trong native `fetch`).
   - Tối ưu mã nguồn các hàm `getStoredAuthToken` và `requestPlaybackGrant`.

---

## 2. Hướng Dẫn Khởi Động Bản Dùng Thử Đúng Cấu Hình

### 2.1. Các Điểm Đính Chính Cấu Hình Quan Trọng
- **JDK / `JAVA_HOME`**: Tự động phát hiện bộ cài JDK đã có trên máy (`C:\Program Files\Java\jdk-25.0.3`) và chỉ đặt trong phạm vi phiên làm việc của tiến trình (process-scoped). **Tuyệt đối không can thiệp hoặc thay đổi cấu hình môi trường của hệ điều hành**.
- **Tên Artifact Backend**: Tên tệp jar chuẩn theo cấu hình Maven là:
  `backend/springboot/target/moviercm-backend-0.0.1-SNAPSHOT.jar`
- **Đảm bảo tính tươi mới của Artifact**: Bộ công cụ tự động kiểm tra thời gian sửa đổi của mã nguồn `src/main` so với tệp jar. Nếu jar bị thiếu hoặc cũ hơn mã nguồn, hệ thống tự động biên dịch lại bằng `mvnw clean package dependency:build-classpath -DskipTests` trước khi khởi chạy, không bao giờ chạy lại bytecode cũ.
- **Cấu hình Điểm gắn Google Drive**:
  - Remote rclone: `cinema-drive:`
  - Thư mục ID: `1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ`
  - Tham số truyền: `--drive-root-folder-id 1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ`, gắn vào điểm gắn `X:` ở chế độ chỉ đọc (`--read-only --vfs-cache-mode off --buffer-size 16M`).
- **Secret đồng bộ**: Truyền qua biến môi trường hoặc tham số ngoài Git (`FASTAPI_SYNC_SECRET`, `CATALOG_SYNC_TOKEN`), hoặc tự động sinh mã phiên ngẫu nhiên.
- **Chế độ Mô hình AI**:
  - `SERVING_MODE=light`: Chế độ phục vụ gọn nhẹ bằng semantic indexing/embedding trên CPU.
  - `SERVING_MODE=full`: Chế độ phục vụ mô hình thật Qwen3-4B + Phase23 LoRA trên GPU CUDA.
  - *Quy tắc minh bạch: Tuyệt đối không gọi template/fallback là mô hình thật.*
- **Quản lý Dòng đời Tiến trình**: Dừng tiến trình dựa nghiêm ngặt trên PID và xác minh 3 lớp danh tính (`Win32_Process`: PID, `CreationDate` delta < 3s, `ExecutablePath`). **Không sử dụng lệnh dừng tiến trình theo tên (no kill-by-name)**.

---

### 2.2. Các Bước Khởi Chạy

#### Cách 1: Khởi Chạy Tự Động Toàn Cụm (Khuyến Nghị)
Một lệnh duy nhất khởi chạy toàn bộ cụm dịch vụ, gắn Drive và đồng bộ cấu hình:
```powershell
powershell -File scripts\start_preview_stack.ps1 -MountDrive
```

Khi muốn dừng toàn bộ các tiến trình an toàn:
```powershell
powershell -File scripts\stop_preview_stack.ps1
```

#### Cách 2: Khởi Chạy Thủ Công Từng Cửa Sổ Terminal

1. **Terminal 0 (Gắn kết Google Drive - Tùy chọn):**
   ```powershell
   powershell -File scripts\drive\mount_drive.ps1 -Execute -Remote "cinema-drive:" -DriveRootFolderId "1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ" -MountPoint "X:"
   ```

2. **Terminal 1 (Spring Boot Backend - Cổng 8080):**
   ```powershell
   cd D:\Class\movie-rcm-system\backend\springboot
   $env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"
   .\mvnw.cmd package -DskipTests
   $env:CATALOG_SYNC_TOKEN = "preview_secret_2026"
   java -Dserver.port=8080 -Dspring.profiles.active=dev -Dapp.catalog.sync-url=http://127.0.0.1:8000/api/index/sync -Dapp.catalog.sync-token=$env:CATALOG_SYNC_TOKEN -Dapp.media.drive-mount=X: -Dapp.media.drive-read-timeout-ms=60000 -Dapp.media.drive-metadata-timeout-ms=60000 -jar target\moviercm-backend-0.0.1-SNAPSHOT.jar
   ```

3. **Terminal 2 (FastAPI AI Engine - Cổng 8000):**
   ```powershell
   cd D:\Class\movie-rcm-system\backend\fastapi
   $env:FASTAPI_SYNC_SECRET = "preview_secret_2026"
   $env:SERVING_MODE = "light"
   python -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

4. **Terminal 3 (Next.js Web Frontend - Cổng 3000):**
   ```powershell
   cd D:\Class\movie-rcm-system\frontend
   $env:PORT = "3000"
   $env:NEXT_PUBLIC_API_URL = "http://localhost:8080"
   $env:NEXT_PUBLIC_SPRINGBOOT_API_URL = "http://localhost:8080/api"
   $env:NEXT_PUBLIC_MODEL_API_URL = "http://localhost:8000/api/chat"
   npm start
   ```

---

## 3. Bằng Chứng Kiểm Tra Toàn Luồng (Smoke Verification)

Kiểm thử tự động toàn diện được thực thi qua bộ công cụ `scripts/smoke_preview_usable.py` và lưu trữ tại `docs/reviews/evidence/SNAPSHOT_01_SMOKE.json`.

### 3.1. Ma trận Các Cổng Kiểm Tra (Gates Matrix)

| STT | Cổng kiểm tra | Kết quả | Chi tiết xác minh |
| :---: | :--- | :---: | :--- |
| 1 | **Preflight Ports** | **PASS** | Kiểm tra các cổng 8000, 8080, 3000, 9228 trống trước khi spawn. |
| 2 | **Google Drive Mount** | **PASS** | Gắn thư mục `1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ` vào `X:` (folder `jadooss1` hiển thị). |
| 3 | **FastAPI Ready** | **PASS** | Phục vụ HTTP 200 tại `http://127.0.0.1:8000/health`. |
| 4 | **Spring Boot Ready** | **PASS** | Phục vụ HTTP 200 tại `http://127.0.0.1:8080/api/health` với jar mới. |
| 5 | **Next.js Ready** | **PASS** | Phục vụ HTTP 200 tại `http://127.0.0.1:3000` (Production build). |
| 6 | **Admin Login HTTP** | **PASS** | Cấp phát Bearer JWT token thành công cho tài khoản `admin`. |
| 7 | **Catalog Validation & Import** | **PASS** | Validate hợp lệ và Import nguyên tử gói `pkg_rehearsal_01` (revision 1). |
| 8 | **Worker Outbox Sync READY** | **PASS** | `CatalogSyncWorker` ghi snapshot đĩa và gửi CAS Ack tới FastAPI đạt trạng thái `READY` (generation 1, hash `675210418ddd75fb...`). |
| 9 | **Catalog Search & Discover** | **PASS** | Khớp chính xác `"Biên Niên Sử Thần Tốc"` (`ser_rehearsal_01`) trên Spring Boot; FastAPI `/v1/discover` trả 3 kết quả liên quan. |
| 10 | **Headless Chrome Drive Video Decode** | **PASS** | Trình phát video web mount container, chuyển nguồn sang `asset_rehearsal_drive`, giải mã thành công khung hình thật **1920x1080** từ Google Drive qua Spring Boot adapter. |
| 11 | **Initial Playback Advance** | **PASS** | Video phát bình thường: thời gian trôi từ `0.500s` $\rightarrow$ `2.003s` (tăng trưởng thực tế `+1.503s`). |
| 12 | **Tua Video Lần 1 (Seek to 60.0s)** | **PASS** | Tua thành công tới giây thứ **60.000s**, tiếp tục phát và tăng thời gian ổn định. |
| 13 | **Tua Video Lần 2 (Seek to 120.0s)** | **PASS** | Tua thành công tới giây thứ **120.000s**, tiếp tục phát và tăng thời gian ổn định. |
| 14 | **Chụp Ảnh Bằng Chứng Giao Diện** | **PASS** | Lưu ảnh chụp trực tiếp trình phát: `docs/reviews/evidence/live_preview_drive_player_seek.png`. |
| 15 | **Clean Teardown by PID** | **PASS** | Dừng sạch sẽ 100% tiến trình Chrome, Next.js, Spring Boot, FastAPI và rclone; tháo gắn `X:`. |

---

## 4. Danh Sách Tệp Đã Tạo & Chỉnh Sửa

| Tệp tin | Trạng thái | Mục đích |
| :--- | :---: | :--- |
| `frontend/app/movies/[id]/page.tsx` | Modified | Cắt giảm bundle size, loại bỏ icon thừa, tinh giản skeleton hero. |
| `frontend/features/movies/components/MovieDetail.tsx` | Modified | Rút gọn CSS constants và technical attributes, đạt ngân sách gzip. |
| `frontend/lib/services/mediaService.ts` | Modified | Rút gọn mã nguồn và abort handling trong service media. |
| `scripts/drive/mount_drive.ps1` | Modified | Bổ sung tham số `-DriveRootFolderId`, gắn đúng thư mục Drive `1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ`. |
| `scripts/start_backend_dev.ps1` | Modified | Bổ sung tham số `-Jar` và `-Port`, kiểm tra tự động mtime mã nguồn để build jar mới. |
| `scripts/stop_backend_dev.ps1` | Modified | Hỗ trợ xác minh danh tính và dừng an toàn cho cả hai chế độ classpath và jar. |
| `scripts/start_preview_stack.ps1` | **New** | Script khởi động tự động toàn bộ cụm dịch vụ bản dùng thử, fail-closed preflight. |
| `scripts/stop_preview_stack.ps1` | **New** | Script dừng an toàn cụm dịch vụ dựa nghiêm ngặt trên PID và StartTime đã xác minh. |
| `scripts/smoke_preview_usable.py` | **New** | Bộ kiểm thử tự động toàn luồng (Drive mount -> Import -> Sync -> Search -> Playback & Seek). |
| `docs/runbooks/CATALOG_IMPORT.md` | Modified | Cập nhật hướng dẫn vận hành, lệnh rclone, artifact jar, chế độ mô hình và dữ liệu rehearsal. |
| `docs/reports/SNAPSHOT_01_STATUS.json` | **New** | Báo cáo trạng thái máy đọc với nhãn phát hành `usable_preview`. |
| `docs/reports/SNAPSHOT_01_REPORT.md` | **New** | Báo cáo chi tiết bàn giao checkpoint SNAPSHOT-01. |

---

## 5. Giới Hạn Chưa Được Kiểm Tra (Explicit Unverified Limitations)

Để bảo đảm tính trung thực kỹ thuật, các khía cạnh sau đây **chưa được nghiệm thu** và không được coi là sẵn sàng cho môi trường production:
1. **Tải Concurrency Cao**: Chưa kiểm thử tải đọc/ghi đồng thời quy mô lớn (hàng trăm người dùng cùng nhập dữ liệu hoặc tua video cùng lúc).
2. **Đa dạng Bộ giải mã (Codecs)**: Hệ thống mới kiểm thử xác thực trên định dạng MP4 container với H.264/AAC; các codec chuyên dụng khác (AV1, VP9, HEVC, FLAC, MKV) chưa được kiểm chứng đầy đủ.
3. **Mạng Gián Đoạn & Jitter**: Hành vi phục hồi khi đường truyền tới Google Drive bị ngắt kết nối đột ngột trong lúc đang stream video dung lượng lớn chưa được mô phỏng.
4. **Scrubbing Cường Độ Cao**: Thao tác tua video liên tục qua lại nhiều phân đoạn cách xa nhau trên tệp Drive từ xa chưa được đo lường hiệu năng bộ đệm.
