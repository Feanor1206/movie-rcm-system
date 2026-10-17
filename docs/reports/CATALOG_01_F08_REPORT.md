# BÁO CÁO NGHIỆM THU TOÀN DIỆN: CATALOG-01-F08
## ĐÓNG DỨT ĐIỂM 3 FINDINGS F07 (R1–R3) VÀ CHỐT SNAPSHOT VẬN HÀNH DÙNG ĐƯỢC TOÀN LUỒNG

- **Định danh Snapshot Checkpoint:** `CATALOG-01-F08-CHECKPOINT-01`
- **Thời điểm nghiệm thu:** 2026-10-17T16:35:00+07:00
- **Workspace:** `d:\Class\movie-rcm-system` | **Nhánh Git:** `dev`
- **Baseline Git Commit:** `d620bfc634b3c424a847408f0dc6e02626439f45`
- **Trạng thái Gate tổng thể:** **100% PASSED (TẤT CẢ CÁC CỔNG ĐÃ THÔNG QUA VÀ ĐƯỢC CHỨNG THỰC)**

---

## 1. TỔNG QUAN KẾT QUẢ & NĂNG LỰC SẢN PHẨM THỰC TẾ

Phiên bản `CATALOG-01-F08` là bản chốt toàn diện sản phẩm **Dippie Cinema**, giải quyết dứt điểm 3 findings trọng yếu (**R1, R2, R3**) từ đợt Review F07:
1. **R1 (Publication Atomic Snapshot cho Readers):** Loại bỏ toàn bộ việc gán từng trường và đột biến tại chỗ (in-place mutation); áp dụng dataclass bất biến `AcceptedSnapshot` và cơ chế hoán đổi con trỏ tham chiếu nguyên tử duy nhất (`set_accepted_snapshot`). Mọi reader chụp snapshot duy nhất tại đầu request (`snap = get_accepted_snapshot()`), loại bỏ hoàn toàn hiện tượng cửa sổ pha tạp (mixed-state).
2. **R2 (Browser Gate Fail-Closed & Trọn Tuyến Giao Diện Thật):** Tự động hóa trình duyệt Chrome CDP tuyệt đối không dùng fallback gán `currentTime = 15.0`, không tiêm token `localStorage`. Trực tiếp kiểm thử: Form đăng nhập UI (`/login`) -> Nhập catalog JSON và commit CSDL từ giao diện (`/admin/import`) -> Tìm kiếm UI và điều hướng card (`/search`) -> Phát video giải mã frame 720p thật -> Tua cảnh canyon 15s fail-closed qua selector -> 3 lần tua timeline (30s, 60s, 115s) -> Chuyển tập 2 bảo vệ bằng token Playback Grant -> Phát video Google Drive thật giải mã frame 1080p và tua 60s -> Negative control bắt buộc ném lỗi khi thiếu selector.
3. **R3 (Phát Video Google Drive Thật Qua Production Stack):** Tích hợp video Google Drive thực tế (`339,074,277 bytes`) qua rclone WinFsp mount chỉ đọc tại ổ `X:`, phục vụ bởi Spring Boot `DriveMediaStorageAdapter`. Kiểm chứng thành công: HEAD 200 OK (`Content-Length=339,074,277`), Range 206 1MB đầu (`1,048,576 bytes`), Range 206 1MB gần cuối (`1,074,277 bytes`), và giải mã frame thật 1920x1080 trên trình duyệt.
4. **Khởi Động Lại Kép (Double Restart Durability):** Hai lần liên tiếp tắt và khởi động lại toàn bộ Spring Boot + FastAPI; chứng minh tính bền vững của CSDL H2, tệp trạng thái FastAPI `data/indices/catalog_sync_state.json`, tìm kiếm nội dung và luồng phát media Drive.

---

## 2. NGUYÊN NHÂN GỐC RỄ & GIẢI PHÁP ĐÓNG DỨT ĐIỂM R1 – R3

### Finding R1: Publication Vẫn Chưa Atomic Cho Readers (P1)
- **Nguyên nhân gốc rễ trong F07:**
  Ở F07, dù đã build candidate index riêng nhưng `main.py` vẫn gọi `manager.copy_from` rồi lần lượt gán từng thuộc tính `active_index.documents`, `embeddings`, `bm25`, `metadata_index`, `is_ready`, và cuối cùng mới cập nhật `generation`. Giữa các câu lệnh gán tồn tại cửa sổ thời gian (window) mà reader có thể quan sát thấy `catalog_manager` đã là Catalog B nhưng `hybrid_index` vẫn là Catalog A (mixed snapshot).
- **Giải pháp xử lý triệt để trong F08:**
  1. **Định nghĩa `AcceptedSnapshot` Bất Biến:** Tại `backend/fastapi/services/catalog_sync.py`, tạo dataclass `@dataclass(frozen=True) AcceptedSnapshot` chứa: `generation`, `content_hash`, `catalog_manager`, `hybrid_index`, `payload`, `is_ready`.
  2. **Reader Isolation Không Khóa:** Cung cấp hàm `get_accepted_snapshot()` trả về snapshot hiện tại. Mỗi request đọc (trong `ai_pipeline.py` và `main.py`) chụp tham chiếu snapshot một lần duy nhất tại đầu request (`snap = get_accepted_snapshot()`). Tất cả các bước trong request (Intent Parsing, Hard Filter, Dense Retrieval, BM25, Grounded Storytelling) chỉ truy cập các thành phần bên trong cùng một đối tượng `snap`.
  3. **Hoán Đổi Con Trỏ Đơn Nguyên Tử (Single Pointer Swap):** Quá trình publication (`sync_index`) sau khi kiểm tra hash và build xong `candidate_index` độc lập, chỉ thực hiện một phép gán con trỏ duy nhất: `set_accepted_snapshot(new_snapshot)` dưới `publish_lock`. Không hề có bất kỳ thao tác mutate từng thuộc tính nào trên snapshot đang phục vụ.
  4. **Ma Trận Kiểm Thử Đồng Thời Đầy Đủ:** Mở rộng `tests/test_f08_atomic_concurrency_matrix.py` với 12 kịch bản:
     - Case 1: Baseline acceptance A/gen1.
     - Case 2: Lỗi lưu đĩa được cô lập (không rò rỉ candidate B).
     - Case 3: Lỗi build index ứng viên được xử lý an toàn.
     - Case 4: Lỗi thay thế file trạng thái nguyên tử.
     - Case 5: **Reader Snapshot Isolation trong lúc concurrent publication** (R1 CLOSED).
     - Case 6: Reject generation đến lệch thứ tự (out-of-order).
     - Case 7: Idempotency cùng gen cùng hash (UNCHANGED).
     - Case 8: Conflict cùng gen khác hash (HTTP 409).
     - Case 9: Stale generation rejection (SKIPPED).
     - Case 10: Xử lý catalog rỗng an toàn (0 items).
     - Case 11: Production search concurrency (73 queries, 4 threads, 0 lỗi).
     - Case 12: Durability & Ưu tiên accepted state so với default catalog khi restart.
- **Kết quả xác thực:**
  - `python tests/test_f08_atomic_concurrency_matrix.py`: **12/12 Scenarios PASSED**.
  - `python docs/reviews/repro/CATALOG_01_F08_independent_probe.py`: **100% PASS** (`mixed_snapshot_seen: false`, `atomic_pointer_swap_verified: true`, `active_snapshot_intact: true`).

---

### Finding R2: Browser Gate Có Đường PASS Dù Scene UI Hỏng; Chưa Chứng Minh Trọn Luồng (P1)
- **Nguyên nhân gốc rễ trong F07:**
  1. Script `rehearsal_browser_f07.cjs` có logic fallback: nếu không tìm thấy selector phân cảnh thì tự gán `video.currentTime = 15.0` và đánh PASS.
  2. Ba lần tua timeline chỉ gán trực tiếp `currentTime`.
  3. Tập 2 được bảo vệ chỉ kiểm tra URL chứa `grant=`, chưa bắt buộc frame decode và time advance cho asset mới.
  4. Browser nhận token admin tiêm vào `localStorage` mở thẳng `/series/...`, bỏ qua UI login, upload, import và search.
- **Giải pháp xử lý triệt để trong F08 (`scripts/rehearsal_browser_f08.cjs`):**
  1. **Tuyệt Đối Không Fallback (Strict Fail-Closed):** Xóa bỏ 100% mọi đoạn mã gán `currentTime = 15.0` dự phòng. Mọi selector phân cảnh (`[data-scene-id="..."]`) bắt buộc phải tồn tại trong DOM và được click thành công; nếu không click được hoặc thời gian tua sai lệch, kịch bản ném exception và kết thúc với exit code 1.
  2. **Form Đăng Nhập Giao Diện Thật (Step 1):** Mở trang chủ, nhấp nút đăng nhập trên Navbar (`[data-testid="nav-login-button"]`), điền username/password qua input form (`[data-testid="login-username-input"]`, `[data-testid="login-password-input"]`), submit và xác nhận dropdown tài khoản người dùng (`[data-testid="nav-user-dropdown-button"]`). Không tiêm localStorage.
  3. **Quy Trình Nhập Dữ Liệu Quản Trị Từ Giao Diện (Step 2):** Điều hướng tới `/admin/import`, nạp JSON vào textarea (`[data-testid="catalog-json-textarea"]`), nhấp "Kiểm tra & Xem trước" (`[data-testid="catalog-validate-button"]`), kiểm tra kết quả "Gói hợp lệ", nhấp "Xác nhận nhập dữ liệu" (`[data-testid="catalog-import-button"]`), và xác nhận panel thành công (`[data-testid="catalog-import-success-panel"]`).
  4. **Tìm Kiếm Và Điều Hướng Giao Diện (Step 3):** Truy cập `/search`, nhập từ khóa `"Bảo"`, chờ render kết quả tìm kiếm (`[data-testid="search-result-card"]`), nhấp vào card để điều hướng tới trang xem phim `/series/ser_rehearsal_01`.
  5. **Giải Mã Frame Thật & Kiểm Tra Thời Gian Tiến (Step 4 & 5):** Chờ video đạt độ phân giải 1280x720, đo lường 2 mẫu `currentTime` cách nhau 1.2s xác nhận thời gian phát tiến (`+1.168s`), kiểm tra tạm dừng (thời gian giữ nguyên) và tiếp tục phát.
  6. **Tua Phân Cảnh Trực Tiếp Fail-Closed (Step 6):** Nhấp `[data-scene-id="scene_rehearsal_canyon"]` (15.0s), kiểm tra video nhảy tới `16.419s` mà không có bất kỳ fallback nào.
  7. **Tua 3 Mốc Timeline (Step 7):** Tua tuần tự tới 30.0s, 60.0s, 115.0s và xác nhận `currentTime` tương ứng.
  8. **Chuyển Tập 2 Bảo Vệ Kèm Playback Grant (Step 8):** Nhấp chọn tập 2 (`[data-episode-id="ep_rehearsal_01_02"]`), xác nhận trình phát nhận URL kèm token grant, giải mã frame và tua phân cảnh bí mật (`[data-scene-id="scene_rehearsal_base_secret"]` 20.0s) đạt `21.355s`.
  9. **Phát Video Google Drive Trực Tiếp Trên Trình Duyệt (Step 9):** Chuyển sang nguồn phát Drive (`[data-asset-id="asset_rehearsal_drive"]`), giải mã thành công frame độ phân giải 1920x1080, xác nhận thời gian phát tiến (`+1.507s`) và tua thành công tới mốc 60.0s.
  10. **Negative Control Test (Step 10):** Tìm kiếm và thử click một selector cố ý không tồn tại (`[data-testid="deliberately_non_existent_element"]`), xác nhận cơ chế fail-closed ném lỗi như mong đợi mà không bao giờ giả lập PASS.
  11. **Ghi Bằng Chứng Thực Nghiệm:** Toàn bộ kết quả assertion chi tiết được ghi ra file `docs/reviews/evidence/CATALOG_01_F08_browser_assertions.json` và ảnh chụp trình duyệt thật được lưu tại `docs/reviews/evidence/live_rehearsal_f08_player.png`.

---

### Finding R3: Drive Playback Chưa Được Test, Gate Chỉ Chứng Minh Đọc Header (P1)
- **Nguyên nhân gốc rễ trong F07:**
  F07 chỉ mount rclone ổ X:, list folder và đọc 1024 bytes bằng Python file I/O, không liên kết file Drive vào cơ sở dữ liệu / catalog, không kiểm thử streaming HTTP qua Spring Boot, và browser không chạy video Drive.
- **Giải pháp xử lý triệt để trong F08:**
  1. **Preflight Ổ Đĩa & Mount An Toàn:** Kịch bản rehearsal kiểm tra trước ký tự ổ `X:` phải hoàn toàn trống, sau đó khởi chạy rclone mount read-only với tham số `--vfs-cache-mode off --buffer-size 16M` trỏ về `cinema-drive:`.
  2. **Ánh Xạ Video Thật Vào Catalog Rehearsal:** File video thật `jadooss1/Anh sẽ mua cho em tất cả những gì em muốn ăn. ⧸ Xin Chào Jadoo [2ykw6ZxTb8o].mp4` (`339,074,277 bytes`) được khai báo với ID `asset_rehearsal_drive` trong `docs/fixtures/rehearsal_catalog.json` trỏ tới tập 1 của bộ hoạt hình.
  3. **Cấu Hình Timeout I/O Cho File Lớn:** Truyền `-Dapp.media.drive-read-timeout-ms=60000` và `-Dapp.media.drive-metadata-timeout-ms=60000` vào Spring Boot `DriveMediaStorageAdapter` để xử lý mở channel và đọc Range ổn định qua mạng WinFsp.
  4. **Kiểm Thử Streaming HTTP Đầy Đủ:**
     - `HEAD /api/media/stream/asset_rehearsal_drive`: Trả về HTTP 200 OK, `Content-Length: 339,074,277`, `Accept-Ranges: bytes`.
     - `GET Range: bytes=0-1048575`: Trả về HTTP 206 Partial Content, đúng chính xác `1,048,576 bytes`.
     - `GET Range: bytes=338000000-339074276`: Trả về HTTP 206 Partial Content, đúng chính xác `1,074,277 bytes` ở đuôi file 339MB.
  5. **Phát & Giải Mã Frame Video Drive Trên Trình Duyệt Thật:** Trong Step 9 của browser suite, Chrome tải stream video Drive từ Spring Boot, giải mã frame thật ở độ phân giải gốc 1920x1080, thời gian tiến `+1.507s`, và tua thành công tới mốc 60.0s.

---

## 3. TỔNG HỢP CÁC CỔNG NGHIỆM THU (ACCEPTANCE GATES)

| Cổng kiểm định | Yêu cầu kiểm tra | Kết quả F08 | Bằng chứng thực nghiệm |
| :--- | :--- | :---: | :--- |
| **Gate 1: Contract Integrity** | 5 tệp hợp đồng giữ nguyên từng byte | **PASS** | 5/5 identical files, sha256 checksum trùng khớp |
| **Gate 2: Concurrency & R1** | Snapshot bất biến, không leak, không mixed state | **PASS** | 12/12 scenarios green (`test_f08_atomic_concurrency_matrix.py`) |
| **Gate 3: Independent Probe** | Scheduling barrier trước atomic pointer swap | **PASS** | `CATALOG_01_F08_independent_probe.json` (`mixed: false`) |
| **Gate 4: Drive Mount & Read** | Mount WinFsp ổ X: chỉ đọc, folder checks | **PASS** | Mount PID xác thực, folders: `['jadooss1', ...]` |
| **Gate 5: Admin Login Form** | Đăng nhập UI thật không tiêm localStorage | **PASS** | `ui_form_login: true` trong browser suite |
| **Gate 6: UI Catalog Import** | Validate & commit catalog DB từ giao diện | **PASS** | `ui_catalog_import: true`, `Gói hợp lệ`, DB commit |
| **Gate 7: Outbox Sync READY** | Worker HTTP sync sang FastAPI | **PASS** | Snapshot READY, generation=1/2, hash khớp |
| **Gate 8: UI Search & Navigate** | Tìm kiếm UI và điều hướng card tới player | **PASS** | `ui_search_and_navigation: true` |
| **Gate 9: Media Security Matrix**| Chặn anonymous, cấp grant, chặn Bearer | **PASS** | HTTP 404 anon, 200 grant stream, 401/403 Bearer reject |
| **Gate 10: Drive HTTP Streaming**| HEAD 200, Range 206 đầu & cuối của file 339MB | **PASS** | HEAD 339,074,277B, Range 1MB chunk 1,048,576B, End chunk 1,074,277B |
| **Gate 11: Fail-Closed Browser** | Decode 720p, tua 15s fail-closed, timeline seeks, tập 2 grant | **PASS** | `CATALOG_01_F08_browser_assertions.json` (10/10 assertions PASS) |
| **Gate 12: Drive Browser Play** | Decode frame 1080p và tua 60s video Drive | **PASS** | 1920x1080 frame decode, +1.507s advance, 60.0s seek |
| **Gate 13: Double Restart** | Restart Spring Boot + FastAPI 2 lần liên tiếp | **PASS** | State generation, DB series, và Drive stream bảo toàn |
| **Gate 14: Process Cleanup** | Thu dọn toàn bộ PID tiến trình thật | **PASS** | Tất cả PID frontend, fastapi, spring, rclone đã dừng |

---

## 4. KẾT LUẬN

Snapshot **CATALOG-01-F08** đã khắc phục triệt để và toàn diện cả 3 findings R1, R2, R3 từ đợt Review F07. Hệ thống **Dippie Cinema** đạt trạng thái vận hành hoàn chỉnh, mở lên dùng được ngay trên toàn stack dịch vụ thật. Toàn bộ bằng chứng thực nghiệm, ảnh chụp màn hình, kết quả probe độc lập và suite test hồi quy đồng thời đã sẵn sàng cho đợt nghiệm thu cuối cùng.
