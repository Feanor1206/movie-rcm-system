# BÁO CÁO NHIỆM VỤ: SNAPSHOT-02 — SỬA JS BUDGET VÀ DÙNG CATALOG/VIDEO THẬT TRÊN DRIVE

- **Mã Checkpoint**: `SNAPSHOT-02-CHECKPOINT-01`
- **Thời gian**: 18/10/2026
- **Workspace**: `D:\Class\movie-rcm-system`
- **Branch**: `dev`
- **Baseline Git Commit**: `2f205a4b8b60a2eeb6864af8ee7dba7a1cf2dc88`
- **Cấp độ phát hành (Release Level)**: `usable_preview` *(Bản dùng thử — không tự nhận production-ready)*
- **Tệp bằng chứng đầy đủ**: `docs/reports/evidence/SNAPSHOT_02_evidence.json`

---

## 1. Kết Quả Sửa JS Budget Đạt Dư Địa An Toàn $\ge 2$ KiB

### 1.1. So Sánh Số Byte Trước và Sau
Ngưỡng ngân sách CI: **$\le$ 143,360 gzip bytes (140 KiB)**. Đo lường chính xác bằng `scripts/compute_build_bytes.cjs` (giữ nguyên logic và ngưỡng) trên môi trường **Node.js 20 LTS** (`v20.20.2`).

| Route | GitHub CI Run trước | Đo lường Local hiện tại (gzip) | Raw bytes | Trạng thái | Dư địa dự phòng (Margin) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`/movies/[id]`** | **143,378 B** *(Vượt +18 B)* | **141,307 B** *(138.00 KiB)* | 494,710 B | **PASS** | **+2,053 bytes (+2.00 KiB)** |
| `/` | - | 139,308 B *(136.04 KiB)* | 491,552 B | **PASS** | +4,052 bytes (+3.96 KiB) |
| `/search` | - | 139,682 B *(136.41 KiB)* | 488,641 B | **PASS** | +3,678 bytes (+3.59 KiB) |
| `/profile` | - | 139,808 B *(136.53 KiB)* | 502,482 B | **PASS** | +3,552 bytes (+3.47 KiB) |

- **Node.js thực tế sử dụng**: Node.js **`v20.20.2`** (đúng phiên bản runtime CI).
- **Dư địa dự phòng an toàn**: Tuyến `/movies/[id]` đạt **2,053 bytes** ($> 2.00$ KiB), bảo đảm GitHub CI không bị dao động hoặc vượt ngưỡng khi nén trên các runner khác nhau.
- **Frontend Unit Tests**: **83/83 test passed** (100% pass trên 7 test suites, 0 regression).
- **TypeScript Typecheck**: `npx tsc --noEmit` hoàn tất với **0 lỗi**.
- **Bảo toàn tính năng**: Giữ nguyên toàn bộ logic playback, grant token, descriptor error recovery, retry button và các thuộc tính trợ năng Accessibility (ARIA).

### 1.2. Các Tinh Chỉnh Được Áp Dụng
1. `frontend/components/layout/Footer.tsx`:
   - Tinh giản cấu trúc cột lồng nhau sang thanh liên kết phẳng hiện đại.
   - Loại bỏ các chuỗi văn bản tĩnh lặp lại không cần thiết trong bundle client.
2. `frontend/features/movies/components/MovieDetail.tsx`:
   - Rút gọn các biểu thức ternary aria string lặp lại (`wlAria`, `favAria`).
   - Inline rail danh sách phim tương tự, loại bỏ component trung gian không cần tải sớm.
   - Tinh gọn các glyph SVG hỗ trợ hiển thị.
3. `frontend/app/movies/[id]/page.tsx`:
   - Dọn dẹp import icon không dùng trong khối fallback 404.

---

## 2. Tìm và Xác Thực Catalog JSON & Video Thật Trên Google Drive

### 2.1. Kết Quả Định Vị Trên Google Drive
- **Remote rclone**: `cinema-drive:`
- **Thư mục gốc giới hạn**: `--drive-root-folder-id 1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ`
- **Tệp Catalog tìm thấy**: `catalog.jadoo_all.json` (tại thư mục `Dippie-Catalog-v1/`)
- **Tên Package**: `pkg_dippie_jadoo_all` (Package Revision: 2)
- **Hợp đồng dữ liệu**: `dippie.catalog.v1` (5 tệp schema trong `docs/contracts/animation-catalog-v1/` được **giữ nguyên từng byte**, không sửa đổi).

### 2.2. Kiểm Tra Cú Pháp & Liên Kết Thực Thể
- **Kiểm tra Schema**: Chạy `python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.jadoo_all.json`.
  - **Kết quả**: `VALID: structure and internal references/timestamps pass; media and factual truth were not verified.` (0 lỗi cú pháp, 0 lỗi quan hệ tham chiếu).
- **Thống kê thực thể trong Catalog**:
  - **1** Bộ phim hoạt hình (`ser_jadoo`: "Xin Chào Jadoo")
  - **4** Mùa/Phần (`sea_jadoo_s01`, `sea_jadoo_s03`, `sea_jadoo_s04`, `sea_jadoo_s06`)
  - **99** Tập phim hoạt hình (thời lượng 900s–1300s mỗi tập)
  - **20** Phân đoạn / mẩu chuyện (`segments`)
  - **198** Tài nguyên Media (`media_assets`: 99 video MP4 1080p và 99 audio trích xuất)
  - **9** Nhân vật chính (`characters`: Choi Jadoo, Lee Yunhee, Kim Minji, Choi Mimi, Choi Seungi, v.v.)
  - **3** Nguồn xuất xứ (`sources`)

### 2.3. Ánh Xạ Đường Dẫn & Video Thực Tế Trên Điểm Gắn `X:`
- Tệp catalog khai báo `storage_key: "cinema-drive"` và `relative_path: "VideoDieppie/jadooss1/...mp4"`.
- Điểm gắn rclone ánh xạ root folder ID `1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ` trực tiếp vào `X:\` (bên trong `VideoDieppie`).
- **Thích ứng Backend**: Bổ sung xử lý fallback tự động loại bỏ tiền tố `VideoDieppie/` nếu tệp nằm trực tiếp tại `X:\jadooss1\...` trong cả:
  - `backend/springboot/src/main/java/com/dippie/moviercm/config/StorageKeyConfig.java` (cho phép `cinema-drive` và `cinema_drive`).
  - `backend/springboot/src/main/java/com/dippie/moviercm/service/DriveMediaStorageAdapter.java`.
- **Kiểm tra tệp video thực tế**:
  - Đường dẫn: `X:\jadooss1\Anh sẽ mua cho em tất cả những gì em muốn ăn. ⧸ Xin Chào Jadoo [2ykw6ZxTb8o].mp4`
  - Kích thước: **339,074,277 bytes (~323.36 MiB)**
  - Tồn tại thực tế: **Có (`True`)**, đọc được ngay lập tức qua WinFsp.

---

## 3. Bản Dùng Thử Hoạt Động Thật Với Dữ Liệu Catalog & Video

### 3.1. Khởi Động Bản Dùng Thử & Trạng Thái Cụm Dịch Vụ
Lệnh khởi chạy:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_preview_stack.ps1 -MountDrive
```
Cả 3 dịch vụ và điểm gắn Drive đều HEALTHY (200 OK):
- **Drive Mount**: Gắn thành công vào `X:` (PID 2076, rclone WinFsp read-only).
- **FastAPI AI Engine**: Cổng **8000** (PID 20500) -> HTTP 200 OK (`/health`, `/api/readiness`).
- **Spring Boot Backend**: Cổng **8080** (PID 19644) -> HTTP 200 OK (`/api/health`).
- **Next.js Frontend**: Cổng **3000** (PID 9656) -> HTTP 200 OK (`/`).

### 3.2. Nhập Dữ Liệu & Đồng Bộ Outbox Worker Sang FastAPI
1. **Đăng nhập Quản trị viên**: `POST http://localhost:8080/api/auth/login` với tài khoản `admin` / `password123` -> Nhận JWT Bearer Token.
2. **Kiểm tra Dry-run API**: `POST http://localhost:8080/api/admin/catalog/validate` với tệp `catalog.jadoo_all.json` -> Trả về `valid: true`, `toUpdate: 342`, `conflicts: 0`.
3. **Nhập Catalog vào Cơ sở Dữ liệu**: `POST http://localhost:8080/api/admin/catalog/import`
   - Ghi nhận thành công 342 thực thể vào bảng H2.
   - Sinh Outbox Snapshot `snap_1792319788700_pkg_dippie_jadoo_all_g2` (Generation 2).
4. **Tiến trình Đồng bộ Outbox Worker**:
   - `CatalogSyncWorker` ghi committed snapshot ra đĩa: `committed_catalog_snapshot.json`.
   - Gửi yêu cầu HTTP POST sang FastAPI `http://127.0.0.1:8000/api/index/sync` với token bảo mật.
   - FastAPI nạp 120 mục tìm kiếm (1 series, 99 tập, 20 phân đoạn), tính toán BM25 và nạp Dense Encoder (`multilingual-e5-small`).
   - FastAPI phản hồi HTTP 200 OK (`status: "success"`).
   - Snapshot chuyển trạng thái chính thức: **`READY`** (Content Hash: `056a51d233cab913126dfd36a6d1460fa1cfa241b24146cc4272cf99efb05bab`).

---

## 4. Kiểm Thử Tìm Kiếm, AI Chat & Phát Video Thực Tế

### 4.1. Tìm Kiếm & AI Chat Thông Minh
- **Tra cứu Series Công Khai**: `GET http://localhost:8080/api/catalog/series` -> Trả về `ser_jadoo` ("Xin Chào Jadoo").
- **Tìm kiếm Từ khóa**: `GET http://localhost:8080/api/catalog/search?q=Jadoo` -> Trả về **118 kết quả** bao gồm series và các tập phim hoạt hình tương ứng.
- **Trợ lý AI CineBot**: `POST http://localhost:8000/api/chat` với câu hỏi *"Tìm phim hoạt hình Xin Chào Jadoo"*:
  - Mô hình nhận diện đúng bối cảnh phim và đề xuất đoạn trích: *"Nữ Hướng Đạo Sinh và màn giải cứu Eunhee trong rừng"* (thời lượng 11:10–22:06) cùng thông tin chi tiết về các nhân vật Choi Jadoo, Lee Yunhee.

### 4.2. Phát Video & Telemetry Chuyển Tiếp Frame Liên Tiếp
Kiểm thử trực tiếp trên endpoint phát video chuẩn của hệ thống:
`http://localhost:8080/api/media/stream/asset_jadoo_s01_v0001`

1. **Kiểm tra Header (HTTP HEAD)**:
   - `HTTP/1.1 200 OK`
   - `Content-Type: video/mp4`
   - `Content-Length: 339074277` (339 MB)
   - `Accept-Ranges: bytes`

2. **Yêu cầu Đoạn phát Đầu tiên (HTTP Range 0-1023)**:
   - `HTTP/1.1 206 Partial Content`
   - `Content-Range: bytes 0-1023/339074277`
   - Kích thước nhận: 1,024 bytes
   - Magic bytes nhận diện container MP4: `ftyp` (hợp lệ tuyệt đối).

3. **Yêu cầu Tua / Seek (HTTP Range 10485760-10486783)**:
   - Tua tới offset 10 MB: `HTTP/1.1 206 Partial Content`
   - `Content-Range: bytes 10485760-10486783/339074277`
   - Kích thước nhận: 1,024 bytes đúng vị trí.

4. **Bằng Chứng Giải Mã Frame & Bước Nhảy Thời Gian Liên Tiếp (FFprobe qua HTTP Stream)**:
   Thực thi lệnh `ffprobe` trỏ trực tiếp vào luồng stream HTTP của Spring Boot đọc từ mounted Drive `X:`:

   - **Mốc thời gian ban đầu (0.00s)**:
     ```json
     [
       {"pkt_dts_time": "0.000000", "width": 1920, "height": 1080, "pict_type": "I", "key_frame": 1},
       {"pkt_dts_time": "0.040000", "width": 1920, "height": 1080, "pict_type": "P", "key_frame": 0},
       {"pkt_dts_time": "0.080000", "width": 1920, "height": 1080, "pict_type": "I", "key_frame": 1}
     ]
     ```
     -> **Frame advance**: Tiến trình phát diễn ra đều đặn mỗi +0.040s (+40ms, chuẩn 25fps), độ phân giải Full HD 1920x1080.

   - **Mốc thời gian sau khi tua 60 giây (`60s`)**:
     ```json
     [
       {"pkt_dts_time": "58.800000", "width": 1920, "height": 1080, "pict_type": "I", "key_frame": 1},
       {"pkt_dts_time": "58.840000", "width": 1920, "height": 1080, "pict_type": "P", "key_frame": 0},
       {"pkt_dts_time": "58.880000", "width": 1920, "height": 1080, "pict_type": "P", "key_frame": 0}
     ]
     ```
     -> **Seek advance**: Video tua mượt mà tới vị trí I-frame gần nhất (58.80s) và tiếp tục phát các frame tiếp theo (+40ms mỗi frame).

   - **Mốc thời gian sau khi tua 120 giây (`120s`)**:
     ```json
     [
       {"pkt_dts_time": "118.440000", "width": 1920, "height": 1080, "pict_type": "I", "key_frame": 1},
       {"pkt_dts_time": "118.480000", "width": 1920, "height": 1080, "pict_type": "P", "key_frame": 0}
     ]
     ```
     -> Chứng minh video thực sự phát được liên tục từ file video thực tế trên Google Drive, không phải header rỗng.

---

## 5. Danh Mục Thay Đổi Mã Nguồn

| File | Thành phần | Nội dung thay đổi |
| :--- | :--- | :--- |
| `frontend/components/layout/Footer.tsx` | Frontend | Tinh giản layout liên kết phẳng, giảm kích thước First-load JS cho tất cả các route. |
| `frontend/features/movies/components/MovieDetail.tsx` | Frontend | Rút gọn chuỗi ternary lặp, inline rail phim liên quan, giảm First-load JS của `/movies/[id]` xuống 141,307 B. |
| `frontend/app/movies/[id]/page.tsx` | Frontend | Dọn dẹp import icon không dùng trong khối 404 fallback. |
| `backend/fastapi/services/hybrid_retrieval.py` | FastAPI | Tối ưu `DenseEncoder.load()` ưu tiên nạp từ cache local (`local_files_only=True`) trước khi tải mạng, tránh tắc nghẽn startup. |
| `backend/springboot/src/main/java/com/dippie/moviercm/config/StorageKeyConfig.java` | Spring Boot | Bổ sung `cinema-drive` và `cinema_drive` vào allowlist khóa lưu trữ. |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/DriveMediaStorageAdapter.java` | Spring Boot | Bổ sung fallback tự động loại bỏ tiền tố `VideoDieppie/` khi điểm gắn `X:` nằm trực tiếp bên trong thư mục này. |
| `scripts/start_preview_stack.ps1` | Launcher | Tăng timeout kiểm tra readiness lên 90 giây; hỗ trợ UTF-8 BOM cho PowerShell 5.1; tối ưu hóa tiến trình khởi động. |

*(Lưu ý: Không thực hiện commit, push, revert; không sửa 5 file contract trong `docs/contracts/animation-catalog-v1/`; không sửa ngưỡng hay cách tính của `compute_build_bytes.cjs`).*
