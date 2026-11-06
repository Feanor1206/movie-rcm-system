# NHẬT KÝ THI CÔNG MILESTONE M4 (M4 MEDIA WORKLOG)
**Thời gian:** 14/10/2026  
**Nhánh:** `dev`  
**Kỹ sư thực hiện:** Gemini Pairing Assistant  
**Kỹ sư trưởng / Nghiệm thu:** Codex

---

## 1. Khảo sát & Đánh giá Môi trường
- Đã đọc đầy đủ các tài liệu định hướng:
  - `docs/reviews/LOOP_ROUND_13_REVIEW.md` (Codex accepted Milestone M3).
  - `docs/prompts/M4_MEDIA_PLAYBACK_GEMINI_PROMPT.md`
  - `docs/prompts/GEMINI_CURRENT_TASK.md`
  - `docs/contracts/M4_MEDIA_PLAYBACK_CONTRACT.md`
- Khảo sát công cụ trên host Windows:
  - `ffmpeg 8.1.1`: Sẵn sàng trên PATH.
  - `rclone` và `WinFsp`: Không có trên host -> Ghi nhận Gate Google Drive là `BLOCKED_EXTERNAL_INPUT`.
  - Dung lượng ổ C: ~28.3 GB, Ổ D: ~22.7 GB.
  - Java JDK: `C:\Program Files\Java\jdk-25.0.3` (Bytecode target Java 17).

---

## 2. Thiết kế Hợp đồng & Kiến trúc Dữ liệu
1. **Hợp đồng REST & Ranged Streaming:**
   - Biên soạn `docs/contracts/M4_MEDIA_PLAYBACK_CONTRACT.md`.
   - Xác định rõ mô hình phân phối:
     - `GET /api/movies/{id}/media-descriptor`: Trả về `hasFeature`, `hasTrailer`, thông tin streaming và backward fallback trailer.
     - `HEAD /api/media/stream/{assetId}`: Header preflight (MIME, Content-Length, Accept-Ranges, ETag, Cache-Control).
     - `GET /api/media/stream/{assetId}`: Phục vụ HTTP Range RFC 9110 (200 Full, 206 Partial, 416 Unsatisfiable).
2. **Cơ sở Dữ liệu & Additive Migrations:**
   - Tạo migration `database/migrations/03_add_media_assets.sql`.
   - Cập nhật bootstrap schema canonical `database/schema/01_init.sql`.
   - Đồng bộ hóa runbook schema `docs/runbooks/db/schema_v1.sql`.
   - Cập nhật `backend/springboot/src/main/resources/schema.sql`.

---

## 3. Triển khai Backend Spring Boot Media Module
1. **Entity & Repository:**
   - Tạo `MediaAsset.java` với các trường định danh, loại (`feature` / `trailer`), provider (`local` / `drive`), relativePath, byteLength, durationSeconds.
   - Tạo `MediaAssetRepository.java` với các phương thức tìm kiếm tối ưu.
2. **Pluggable Storage Adapters:**
   - Interface `MediaStorageAdapter.java`.
   - `LocalMediaStorageAdapter.java`: Triển khai phân giải canonical path nghiêm ngặt, chống tuyệt đối các kỹ thuật path traversal (`..`), null bytes (`\0`), ký tự ổ đĩa Windows (`C:`, `D:`), symlink escape. Tự động hỗ trợ fallback path resolution khi chạy từ thư mục con `backend/springboot`.
   - `DriveMediaStorageAdapter.java`: Xử lý trạng thái `BLOCKED_EXTERNAL_INPUT`, trả về `503 Service Unavailable` mà không gây ảnh hưởng tới luồng local.
3. **Dịch vụ & Controller:**
   - `MediaStreamService.java`: Phân tích tiêu đề `Range` theo RFC 9110 (khép kín, mở, suffix, unsatisfiable), trích xuất descriptor và điều phối adapter.
   - `MediaStreamController.java`: Phục vụ HEAD và GET stream bằng cơ chế luồng đệm giới hạn 64 KiB (`BUFFER_SIZE`), loại trừ hoàn toàn nguy cơ tràn Heap (`readAllBytes` bị nghiêm cấm).
   - `MediaDescriptorController.java`: Phục vụ endpoint `/api/movies/{id}/media-descriptor`.
   - Cập nhật `SecurityConfig.java`: Cho phép public access an toàn tới `/api/media/**` và `/api/movies/**`, mở rộng CORS exposed headers (`Content-Range`, `Accept-Ranges`, `Content-Length`).
   - Cập nhật `GlobalExceptionHandler.java`: Bắt `MediaNotFoundException` (404), `MediaUnavailableException` (503), `SecurityPathTraversalException` (400), `InvalidMediaRangeException` (416).

---

## 4. Tạo Fixture Video Thật với FFmpeg
- Sử dụng `ffmpeg 8.1.1` để sinh 2 tệp MP4 chuẩn H.264/AAC có `+faststart` (moov atom ở đầu tệp):
  - `media/synthetic/trailer_test.mp4`: 45,095 bytes (44.0 KiB), thời lượng 3.0s, video test pattern 24fps + âm thanh 1000Hz sine.
  - `media/synthetic/feature_test.mp4`: 137,961 bytes (134.7 KiB), thời lượng 10.0s, video test pattern 24fps + âm thanh 440Hz sine.
- Sao chép vào `backend/springboot/target/test-media/synthetic` phục vụ kiểm thử đơn vị & tích hợp.

---

## 5. Triển khai Frontend Media Client & Trình phát Video
1. **Service Client:**
   - Tạo `frontend/lib/services/mediaService.ts`: Tải descriptor, phân giải relative URL thành full host URL an toàn, hỗ trợ timeout và hủy request qua AbortSignal.
2. **Nâng cấp `MovieDetail.tsx`:**
   - Tự động tải descriptor khi xem chi tiết phim.
   - Phân định rõ ràng nút hành động:
     - Phim có feature: Hiển thị nút chính "Xem phim" (`data-testid="play-feature-btn"`). Nếu có thêm trailer thì hiển thị thêm nút phụ "Xem trailer" (`data-testid="play-trailer-btn"`).
     - Phim chỉ có trailer: Hiển thị duy nhất nút "Xem trailer / giới thiệu" (`data-testid="play-trailer-btn"`).
   - Trình phát video tùy biến hoàn chỉnh:
     - Giữ nguyên toàn bộ tính năng hỗ trợ tiếp cận (a11y) của Milestone M3 (focus trap, Escape key, body scroll lock, focus restore to opener).
     - Thanh tua tiến trình HTTP Range (`data-testid="video-timeline"`).
     - Nút Play/Pause (`data-testid="video-play-pause-btn"`).
     - Hiển thị thời gian thực tế `00:00 / 00:00` (`data-testid="video-time-display"`).
     - Nút bật/tắt tiếng và thanh điều chỉnh âm lượng (`data-testid="video-volume-btn"`).
     - Nút phóng to toàn màn hình (`data-testid="video-fullscreen-btn"`).
     - Biểu tượng đệm luồng phát (`data-testid="video-buffering"`).
     - Lớp phủ báo lỗi và nút "Thử lại" (`data-testid="video-retry-btn"`) ghi nhớ chính xác vị trí `currentTime` khi kết nối lại.
     - Phím tắt bàn phím: Space (Play/Pause), Mũi tên Trái/Phải (tua $\pm 5$s), Mũi tên Lên/Xuống (âm lượng $\pm 10\%$), M (Mute), F (Fullscreen).
     - Toàn bộ nút và thanh điều khiển đều tuân thủ kích thước tối thiểu $\ge 44 \times 44$px.
     - Tone màu xanh lá (`#22c55e`, emerald gradient) đồng bộ với toàn hệ thống.

---

## 6. Đo lường Benchmark Hiệu năng
- Xây dựng script `scripts/benchmark_media_playback.cjs`.
- Chạy benchmark trực tiếp trên các fixture video thật:
  - Startup cold: 17.97 ms
  - Startup warm: trung bình 0.65 ms, p95 1.56 ms
  - Seek latency: trung bình 0.39 ms, p95 0.78 ms
  - Buffer stalls: 0 lần gián đoạn
  - Tải đồng thời 5 luồng: Đạt băng thông 61.11 MB/s, độ trễ trung bình 1.85 ms, p95 3.68 ms.
- Toàn bộ dữ liệu thô được ghi nhận vào `docs/reports/media_benchmark_results.json`.

---

## 7. Lập Runbook Lưu trữ & Tích hợp Drive
- Soạn thảo `docs/runbooks/MEDIA_STORAGE_RUNBOOK.md` hướng dẫn chi tiết quy trình cài đặt WinFsp, rclone, cấu hình OAuth, lệnh mount VFS caching tối ưu cho streaming và kế hoạch kiểm thử khi người dùng kích hoạt Google Drive.
