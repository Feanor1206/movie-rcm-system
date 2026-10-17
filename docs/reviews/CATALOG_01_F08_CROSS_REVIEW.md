# BÁO CÁO CROSS-REVIEW ĐỘC LẬP: CATALOG-01-F08
## THẨM ĐỊNH CHÉO ĐỘC LẬP VỀ VIỆC ĐÓNG CÁC FINDINGS R1 – R3 TẠI F07 REVIEW

- **Mục tiêu đánh giá:** Thẩm định chéo độc lập snapshot `CATALOG-01-F08-CHECKPOINT-01` đối chiếu với 3 findings trọng yếu (**R1, R2, R3**) từ báo cáo Review F07 (`docs/reviews/CATALOG_01_F07_REVIEW.md`).
- **Baseline Git Commit:** `d620bfc634b3c424a847408f0dc6e02626439f45`
- **Workspace:** `d:\Class\movie-rcm-system` | **Branch:** `dev`
- **Kết luận chung:** **TẤT CẢ 3 FINDINGS R1–R3 ĐÃ ĐƯỢC XỬ LÝ TRIỆT ĐỂ, CHỨNG MINH THỰC NGHIỆM ĐẦY ĐỦ VÀ ĐỦ ĐIỀU KIỆN ĐÓNG TOÀN DIỆN.**

---

## 1. THẨM ĐỊNH CHI TIẾT TỪNG FINDING

### 1.1. Thẩm Định Finding R1: Publication Atomic Snapshot Cho Readers (P1)
- **Vấn đề tại F07 Review:**
  F07 Reviewer chỉ ra: Sau durable save, `main.py` vẫn gọi `manager.copy_from` rồi lần lượt gán `active_index.documents`, `embeddings`, `bm25`, `metadata_index`, `is_ready`, và cuối cùng mới cập nhật `generation`/`hash`. Probe F07 đặt scheduling barrier sau `manager.copy_from` và trước `active_index assignments`; một reader đồng thời đọc phải snapshot bị pha tạp (`manager`: next-B, `index`: accepted-A).
- **Kiểm tra mã nguồn giải pháp trong F08:**
  1. `backend/fastapi/services/catalog_sync.py`:
     - Tạo dataclass `@dataclass(frozen=True) AcceptedSnapshot` chứa toàn bộ trạng thái phiên bản: `generation`, `content_hash`, `catalog_manager`, `hybrid_index`, `payload`, `is_ready`.
     - Cung cấp `get_accepted_snapshot()` và `set_accepted_snapshot(snapshot)`.
  2. `backend/fastapi/services/ai_pipeline.py`:
     - Readers gọi `snap = get_accepted_snapshot()` một lần duy nhất tại điểm bắt đầu request.
     - Các giai đoạn trong request (NLU Intent, Hard Filters, Vector Retrieval, BM25, Grounded Storytelling) chỉ sử dụng các thành phần bên trong cùng `snap`.
  3. `backend/fastapi/main.py`:
     - Publication không mutate in-place snapshot đang phục vụ.
     - Hoán đổi con trỏ tham chiếu nguyên tử duy nhất: `set_accepted_snapshot(new_snapshot)` dưới `publish_lock`.
- **Kiểm chứng thực nghiệm:**
  - `python tests/test_f08_atomic_concurrency_matrix.py`: **12/12 Scenarios PASSED**.
  - `python docs/reviews/repro/CATALOG_01_F08_independent_probe.py`:
    - Đặt barrier trước hoán đổi con trỏ tham chiếu.
    - Reader trước swap: Đọc 100% catalog A (`pre_swap_mixed_snapshot_seen: false`).
    - Reader sau swap: Đọc 100% catalog B (`post_swap_pure_b_seen: true`).
    - `atomic_pointer_swap_verified: true`, `rejected_candidate_leaked: false`.
- **Đánh giá Cross-Review:** **CLOSED - ĐẠT CHUẨN BẤT BIẾN VÀ CÔ LẬP TUYỆT ĐỐI CHO READERS.**

---

### 1.2. Thẩm Định Finding R2: Browser Gate Fail-Closed & Trọn Tuyến Giao Diện Thật (P1)
- **Vấn đề tại F07 Review:**
  1. Kịch bản browser F07 tự đặt `currentTime = 15/20` nếu không tìm thấy scene button, dẫn tới scene UI hỏng nhưng test vẫn PASS.
  2. Ba lần tua timeline chỉ gán trực tiếp `currentTime`.
  3. Tập 2 được bảo vệ chỉ kiểm tra URL chứa `grant=`, chưa bắt buộc frame decode và time advance cho asset mới.
  4. Trình duyệt nhận token admin tiêm vào `localStorage` mở thẳng `/series/...`, bỏ qua UI login, upload, import và search.
- **Kiểm tra mã nguồn giải pháp trong F08 (`scripts/rehearsal_browser_f08.cjs`):**
  1. **Strictly Fail-Closed:** Xóa bỏ 100% mọi gán fallback `currentTime = 15.0`. Nếu phần tử thiếu hoặc không thể click, exception được ném ngay lập tức.
  2. **Trọn Tuyến Giao Diện Người Dùng:**
     - Step 1: Form Login UI thật (`/login`) qua modal Navbar và submit credentials.
     - Step 2: Form Import UI thật (`/admin/import`), nạp JSON, validate ("Gói hợp lệ"), nhấn Import và commit CSDL thành công.
     - Step 3: Tìm kiếm UI (`/search`), nhập query `"Bảo"`, render card kết quả và nhấp điều hướng tới `/series/ser_rehearsal_01`.
     - Step 4 & 5: Phát video 720p thật, giải mã frame thật, xác nhận thời gian phát tiến (+1.17s), thử nghiệm Pause/Resume giữ nguyên và tiến thời gian.
     - Step 6: Tua phân cảnh canyon (15.0s) fail-closed thuần túy qua selector click -> đạt 16.42s (PASS).
     - Step 7: 3 lần tua timeline tuần tự (30s, 60s, 115s) thành công.
     - Step 8: Chuyển Tập 2 (protected asset), nhận URL kèm playback grant, giải mã frame và tua phân cảnh bí mật 20.0s đạt 21.36s.
     - Step 9: Chuyển sang Google Drive video, giải mã frame 1920x1080 và tua 60.0s đạt 60.000s.
     - Step 10: Fail-closed negative control assert phần tử không tồn tại ném lỗi chuẩn xác.
- **Kiểm chứng thực nghiệm:**
  - `docs/reviews/evidence/CATALOG_01_F08_browser_assertions.json`: Toàn bộ 10/10 assertions đạt `true`.
  - `docs/reviews/evidence/live_rehearsal_f08_player.png`: Ảnh chụp màn hình player thời gian thực.
- **Đánh giá Cross-Review:** **CLOSED - 100% FAIL-CLOSED, TOÀN TUYẾN GIAO DIỆN THẬT.**

---

### 1.3. Thẩm Định Finding R3: Phát Video Google Drive Thật Qua Production Stack (P1)
- **Vấn đề tại F07 Review:**
  F07 rehearsal chỉ mount rclone X:, list folder rồi đọc 1024 bytes MP4 bằng Python, không mapping file vào catalog / Spring Boot media service, không HTTP Range hoặc browser decode/seek trên Drive video.
- **Kiểm tra mã nguồn & cấu hình trong F08:**
  1. Preflight kiểm tra ổ `X:` trống trước khi mount; rclone mount read-only remote `cinema-drive:` với `--vfs-cache-mode off --buffer-size 16M`.
  2. File video thật `jadooss1/Anh sẽ mua cho em tất cả những gì em muốn ăn. ⧸ Xin Chào Jadoo [2ykw6ZxTb8o].mp4` (339,074,277 bytes) được mapping vào catalog `asset_rehearsal_drive`.
  3. Cấu hình `-Dapp.media.drive-read-timeout-ms=60000` và `-Dapp.media.drive-metadata-timeout-ms=60000` cho `DriveMediaStorageAdapter`.
  4. Thực hiện các truy vấn HTTP thật:
     - `HEAD /api/media/stream/asset_rehearsal_drive`: Trả về 200 OK, Content-Length 339,074,277 bytes, Accept-Ranges: bytes.
     - `GET Range bytes=0-1048575`: Trả về 206 Partial Content (1,048,576 bytes).
     - `GET Range bytes=338000000-339074276`: Trả về 206 Partial Content (1,074,277 bytes) ở gần cuối file 339MB.
  5. Browser phát video Drive, giải mã frame 1920x1080 và tua 60s thành công.
- **Kiểm chứng thực nghiệm:**
  - `docs/reviews/evidence/CATALOG_01_F08_rehearsal.json`: Cổng `drive_media_streaming_http` và `browser_e2e_playback_and_seek` đều **PASS**.
- **Đánh giá Cross-Review:** **CLOSED - PHÁT VÀ TUA VIDEO GOOGLE DRIVE THẬT 100%.**

---

## 2. KẾT LUẬN THẨM ĐỊNH

Cả 3 findings R1, R2, R3 từ F07 Review đã được xử lý triệt để và chứng minh bằng thực nghiệm sống động trên Live Production Stack. Snapshot `CATALOG-01-F08-CHECKPOINT-01` đáp ứng đầy đủ mọi điều kiện chất lượng để chuyển sang trạng thái nghiệm thu toàn phần.
