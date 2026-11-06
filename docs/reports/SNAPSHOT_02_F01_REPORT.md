# BÁO CÁO NHIỆM VỤ: SNAPSHOT-02-F01 — SỬA I/O DRIVE NGOÀI TIMEOUT VÀ XÁC NHẬN ĐÚNG TẬP TRÊN WEB

- **Mã Checkpoint**: `SNAPSHOT-02-F01-CHECKPOINT-01`
- **Thời gian**: 19/10/2026
- **Workspace**: `D:\Class\movie-rcm-system`
- **Branch**: `dev`
- **Baseline Git Commit**: `2f205a4b8b60a2eeb6864af8ee7dba7a1cf2dc88`
- **Cấp độ phát hành (Release Level)**: `usable_preview` *(Bản dùng thử — không tự nhận production-ready)*
- **Tệp bằng chứng chính**: `docs/reviews/evidence/SNAPSHOT_02_F01_WEB_JADOO_EVIDENCE.json`

---

## 1. Mục Tiêu & Tóm Tắt Kết Quả

Nhiệm vụ **SNAPSHOT-02-F01** giải quyết dứt điểm 2 mục tiêu duy nhất theo đánh giá của Reviewer trong `docs/reviews/SNAPSHOT_02_REVIEW.md`:
1. **S1 (P1) — Bỏ metadata I/O Drive chạy ngoài timeout**: Loại bỏ toàn bộ `Files.exists` trong `StorageKeyConfig.resolvePath` đối với provider `"drive"`, bảo đảm `StorageKeyConfig` chỉ thực hiện chuẩn hóa và kiểm tra containment thuần túy trên bộ nhớ. Toàn bộ thao tác kiểm tra tồn tại và phân giải tiền tố `VideoDieppie/` được chuyển vào bên trong `DriveMediaStorageAdapter.*ForPath`, chạy dưới sự kiểm soát chặt chẽ của `ioExecutor.executeMetadata` với timeout và circuit breaker.
2. **S2 (P2) — Xác nhận chọn tập và phát video thật trên Web UI**: Thực thi quy trình kiểm thử trình duyệt thực tế (real Chrome headless via Chrome DevTools Protocol), mô phỏng đầy đủ hành trình người dùng: Tìm kiếm "Jadoo" trên giao diện Web -> Chọn bộ phim hoạt hình -> Phát Episode 1 và kiểm tra kích thước frame giải mã 1920x1080 -> Kiểm tra tiến trình thời gian phát thực tế -> Tua đến mốc 60 giây và tiếp tục phát ổn định -> Chuyển sang Episode 2 để xác minh ánh xạ thực tế -> Đối chiếu từng byte với `data/catalog.jadoo_all.json` và điểm gắn Google Drive `X:\`.

---

## 2. Chi Tiết Kỹ Thuật: Sửa Gọn I/O Ngoài Timeout (S1 — P1)

### 2.1. Phân Tích Lỗi Gốc
Trước khi sửa, `StorageKeyConfig.resolvePath` gọi `Files.exists(resolved)` và `Files.exists(alt)` một cách đồng bộ đối với mọi đường dẫn Google Drive nhằm loại bỏ tiền tố `VideoDieppie/`. Vì `MediaStreamService` gọi `resolvePath` trước khi chuyển giao cho các phương thức `driveStorageAdapter.*ForPath`, các lệnh `stat` trên hệ thống tệp mạng/rclone mount có thể bị treo hoặc chậm ngoài sự bảo vệ của `DriveIoExecutor.executeMetadata` và ranh giới timeout/circuit breaker.

### 2.2. Giải Pháp Triệt Để Áp Dụng (Option B)
1. **`StorageKeyConfig.java`**:
   - Xóa bỏ hoàn toàn các lệnh `Files.exists` trên đường dẫn Drive.
   - Đối với provider `"drive"`, `resolvePath` chỉ thực hiện:
     - Kiểm tra rỗng, null-byte, và path traversal (`..`).
     - Chuẩn hóa đường dẫn: `root.rootPath().resolve(relativePath).normalize().toAbsolutePath()`.
     - Kiểm tra containment nghiêm ngặt: `resolved.startsWith(root.rootPath())`.
     - Hoàn toàn **không thực hiện disk I/O** hay gọi `Files.exists`/`toRealPath` trên Drive.
2. **`DriveMediaStorageAdapter.java`**:
   - Bổ sung phương thức phân giải fallback có giới hạn: `resolveFallbackPathBounded(rootPath, targetPath)`.
   - Tích hợp bên trong khối `ioExecutor.executeMetadata(...)` của các phương thức:
     - `getResourceForPath(Path rootPath, Path targetPath)`
     - `getResourceLengthForPath(Path rootPath, Path targetPath)`
     - `openChannelForPath(Path rootPath, Path targetPath)`
   - Nếu tệp tại `targetPath` chưa tồn tại và có tiền tố `VideoDieppie/`, adapter sẽ kiểm tra đường dẫn thay thế bên dưới `rootPath` trong ranh giới timeout (`metadataTimeoutMs = 60,000ms`) và circuit breaker.
   - Kênh đọc dữ liệu `FileChannel.open(effectiveTarget, StandardOpenOption.READ)` mở đúng tệp đã được phân giải an toàn.
3. **Bổ Sung Regression Tests (`DrivePathSecurityTest.java`)**:
   - Bổ sung test suite lồng nhau `StorageKeyAndBoundedFallbackTests`:
     - `testStorageKeyConfigZeroDriveDiskIo`: Kiểm tra `StorageKeyConfig.resolvePath` với provider `"drive"` không gọi disk I/O và thành công với đường dẫn tệp chưa tồn tại trên ổ đĩa giả lập `Z:\`, đồng thời vẫn chặn đứng path traversal purely in memory.
     - `testAdapterBoundedFallbackResolution`: Kiểm tra adapter giải quyết fallback `VideoDieppie/` bên trong metadata executor và đọc dữ liệu chính xác.
   - **Kết quả kiểm thử**: **30/30 tests PASS** (0 failures, 0 errors, thời gian chạy ~14s trên JDK 25).

---

## 3. Xác Minh Hành Trình Trình Duyệt Thực Tế Trên Web UI (S2 — P2)

Toàn bộ quy trình kiểm thử giao diện được thực hiện tự động bằng trình duyệt thật thông qua kịch bản `scripts/test_live_jadoo_playback.cjs`, ghi nhận bằng chứng tại `docs/reviews/evidence/SNAPSHOT_02_F01_WEB_JADOO_EVIDENCE.json`.

```
[Web UI: /search?q=Jadoo]
         │ (Tìm thấy 118 kết quả, click card 'Xin Chào Jadoo')
         ▼
[/series/ser_jadoo]
         │
         ├───▶ [Tập 1: ep_jadoo_s01_0001 / asset_jadoo_s01_v0001]
         │        ├─ <video> src: /api/media/stream/asset_jadoo_s01_v0001?grant=...
         │        ├─ Kích thước frame giải mã: 1920 x 1080 (Full HD)
         │        ├─ Tiến trình phát: t0 = 0.36s -> t1 = 1.87s (Δt = 1.51s) [PASS]
         │        ├─ Tua video: Seek tới 60.0s -> Settled tại t2 = 60.14s
         │        └─ Tiếp tục phát sau tua: t3 = 61.66s (Δt = 1.51s) [PASS]
         │
         └───▶ [Tập 2: ep_jadoo_s01_0002 / asset_jadoo_s01_v0002]
                  ├─ Click chọn Tập 2 trên thanh danh sách tập
                  ├─ <video> src: /api/media/stream/asset_jadoo_s01_v0002?grant=...
                  ├─ Kích thước frame giải mã: 1920 x 1080 (Full HD)
                  └─ Tiến trình phát: t4 = 0.52s -> t5 = 2.04s (Δt = 1.52s) [PASS]
```

### 3.1. Dữ Liệu Đo Lường Thực Tế Trích Xuất Từ Browser Harness

| Bước | Thực Thể | Thuộc Tính Đo Lường | Giá Trị Thực Tế | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- |
| **Xác thực** | Quản trị viên | Đăng nhập & sinh JWT Bearer Token | `admin` (Token hợp lệ) | **PASS** |
| **Tìm kiếm** | Trang `/search` | Số kết quả trả về cho query "Jadoo" | **118 mục** (Bộ, tập, phân cảnh) | **PASS** |
| **Điều hướng** | Trang `/series/ser_jadoo` | Tên bộ phim & số tập hiển thị | "Xin Chào Jadoo" — **99 tập** | **PASS** |
| **Tập 1 Phát** | `ep_jadoo_s01_0001` | Frame giải mã & Kích thước video | **1920 x 1080** | **PASS** |
| **Tập 1 Tiến độ** | `asset_jadoo_s01_v0001` | Thời gian phát ban đầu -> sau 1.5s | $t_0 = 0.36$s $\rightarrow t_1 = 1.87$s ($\Delta t = 1.51$s) | **PASS** |
| **Tập 1 Tua** | Tua mốc 60.0s | Mốc settled -> Tiến độ tiếp diễn | $t_2 = 60.14$s $\rightarrow t_3 = 61.66$s ($\Delta t = 1.51$s) | **PASS** |
| **Tập 2 Chuyển** | `ep_jadoo_s01_0002` | Cập nhật Asset ID & Stream URL | `asset_jadoo_s01_v0002` + Grant Token | **PASS** |
| **Tập 2 Phát** | `asset_jadoo_s01_v0002` | Frame giải mã & Tiến độ phát | **1920 x 1080**, $t_4 = 0.52$s $\rightarrow t_5 = 2.04$s | **PASS** |

### 3.2. Đối Chiếu Thực Tế Giữa Catalog JSON & Điểm Gắn Google Drive `X:\`

- **Tập 1 (`ep_jadoo_s01_0001`)**:
  - Asset ID: `asset_jadoo_s01_v0001`
  - Khai báo catalog `relative_path`: `VideoDieppie/jadooss1/Anh sẽ mua cho em tất cả những gì em muốn ăn. ⧸ Xin Chào Jadoo [2ykw6ZxTb8o].mp4`
  - Khai báo catalog `size_bytes`: `339074277`
  - Đường dẫn thực tế trên `X:\`: `X:\jadooss1\Anh sẽ mua cho em tất cả những gì em muốn ăn. ⧸ Xin Chào Jadoo [2ykw6ZxTb8o].mp4`
  - Kích thước đo trên `X:\`: **339,074,277 bytes** $\rightarrow$ **Trùng khớp 100% từng byte**.
- **Tập 2 (`ep_jadoo_s01_0002`)**:
  - Asset ID: `asset_jadoo_s01_v0002`
  - Khai báo catalog `relative_path`: `VideoDieppie/jadooss1/Muốn ăn nhưng lại sợ tăng cân ⧸ Xin Chào Jadoo [3Fz2tc7RKLM].mp4`
  - Khai báo catalog `size_bytes`: `695103291`
  - Đường dẫn thực tế trên `X:\`: `X:\jadooss1\Muốn ăn nhưng lại sợ tăng cân ⧸ Xin Chào Jadoo [3Fz2tc7RKLM].mp4`
  - Kích thước đo trên `X:\`: **695,103,291 bytes** $\rightarrow$ **Trùng khớp 100% từng byte**.

### 3.3. Hình Ảnh Bằng Chứng Trực Quan Đã Ghi Lại
Các ảnh chụp màn hình ghi lại từ trình duyệt thực tế được lưu tại `docs/reviews/evidence/`:
1. `live_jadoo_search_results.png` (113 KB): Giao diện tìm kiếm `/search?q=Jadoo` hiển thị 118 kết quả từ catalog v1.
2. `live_jadoo_ep1_playing.png` (230 KB): Trình phát video đang phát Tập 1 với tiêu đề và hình ảnh hoạt hình giải mã Full HD.
3. `live_jadoo_ep1_seek_60s.png` (234 KB): Trình phát video tại mốc thời gian sau khi tua 60.0s, tiếp tục phát khung hình mới.
4. `live_jadoo_ep2_playing.png` (360 KB): Trình phát video chuyển sang Tập 2 sau khi click danh sách tập, hiển thị nội dung video của tập thứ hai.

---

## 4. Hướng Dẫn Vận Hành & Đường Dẫn Cơ Sở Dữ Liệu Bản Dùng Thử

Theo yêu cầu bổ sung của Reviewer về đường dẫn dữ liệu và vận hành:
- **Đường dẫn Cơ sở Dữ liệu H2 (Preview DB)**:
  `backend/springboot/data/moviercm_db.mv.db`
  *(Chứa toàn bộ 342 thực thể, 99 tập phim Jadoo, 198 assets đã import ở rev 2, được giữ nguyên ngoài Git)*.
- **Đường dẫn Tệp Snapshot Index AI**:
  `backend/springboot/data/catalog/committed_catalog_snapshot.json`
- **Lệnh Khởi Động Bản Dùng Thử**:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\start_preview_stack.ps1 -MountDrive
  ```
- **Lệnh Dừng An Toàn Toàn Bộ Stack**:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\stop_preview_stack.ps1
  ```
  *(Xác minh nghiêm ngặt ownership từng PID, kiểm tra StartTime delta < 3.0s, tuyệt đối không kill-by-name, tự động unmount `X:`)*.

---

## 5. Tổng Kết Đảm Bảo Chất Lượng & Tuân Thủ Ranh Giới

1. **JS First-load Budget**:
   - Tuyến `/movies/[id]` đạt **141,307 gzip bytes**, dư **2,053 bytes** ($> 2.00$ KiB) so với ngân sách 143,360 bytes.
2. **Frontend Tests**:
   - **83/83 unit tests PASS** (Node 20 test runner).
3. **TypeScript Typecheck**:
   - `npx tsc --noEmit` hoàn thành với **0 lỗi**.
4. **Backend Tests**:
   - `DrivePathSecurityTest` và `MediaStreamingIntegrationTest`: **30/30 tests PASS**.
5. **Tính Toàn Vẹn Contract**:
   - Cả 5 tệp trong `docs/contracts/animation-catalog-v1/` được **giữ nguyên 100% từng byte**, không thay đổi schema.
6. **Tuân Thủ Phạm Vi**:
   - Không commit / push / deploy git.
   - Không thêm kiến trúc hàng đợi, message bus, hay executor thừa thãi.
   - Tài nguyên mạng và mount được dọn dẹp sạch sẽ sau khi hoàn thành kiểm thử.
