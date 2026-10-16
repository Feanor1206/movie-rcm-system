# BIÊN BẢN NGHIỆM THU SẢN PHẨM: CATALOG-01-F03
## Nghiệm Thu Toàn Diện Luồng Sản Phẩm Thực Tế & Đóng Findings G1–G6

**Dự án:** Movie Recommendation & Streaming System (Dippie Cinema)  
**Workspace:** `D:\Class\movie-rcm-system`  
**Nhánh:** `dev`  
**Base Commit:** `c2d29c04edd58c4cc0a6e648d316285a9377384f`  
**Head Commit:** `adf0dee0655fad19102b39f31d203aeaed42d906`  
**Thời điểm nghiệm thu:** 2026-10-17  
**Kết quả nghiệm thu:** **ĐẠT TIÊU CHUẨN SẢN PHẨM (PRODUCT ACCEPTANCE PASS)**

---

### I. ĐÁNH GIÁ CÁC LÁT CẮT SẢN PHẨM THỰC TẾ (P1 – P4)

#### P1. Quản Trị Nhập Dữ Liệu & Giám Sát Hàng Đợi Outbox (Admin Import & Outbox Monitoring)
- **Đăng nhập quản trị viên:** Hệ thống yêu cầu xác thực JWT Bearer với thẩm quyền `ROLE_ADMIN` để truy cập các endpoint quản trị `/api/admin/catalog/**`.
- **Tải lên & Soạn thảo JSON:** Hỗ trợ tải tệp JSON từ máy tính hoặc dán trực tiếp chuỗi JSON vào ô nhập liệu.
- **Xác thực & Xem trước khác biệt (Dry-run Preview):**
  - Kiểm tra cú pháp theo JSON Schema `dippie.catalog.v1` và ngữ nghĩa quan hệ.
  - Hiển thị bảng tổng hợp khác biệt: số lượng thực thể tạo mới (`toCreate`), cập nhật (`toUpdate`), giữ nguyên (`unchanged`), xung đột (`conflicts`).
  - Nếu có lỗi, hiển thị bảng chi tiết kèm vị trí chính xác theo chuẩn **JSON Pointer**.
- **Ràng buộc Preview với Hash Dữ Liệu:** Bất kỳ thao tác chỉnh sửa nội dung trong textarea đều tự động hủy trạng thái preview trước đó và yêu cầu kiểm tra lại trước khi cho phép nhập, ngăn chặn việc preview một dữ liệu nhưng lại nhập dữ liệu khác.
- **Giao dịch nhập nguyên tử (Atomic Commit):** Nhập đồng thời vào 12 bảng thực thể CSDL có quản trị khóa lạc quan (`@Version`).
- **Hàng đợi Outbox & Giám sát trạng thái:**
  - Bảng "Hàng đợi Outbox & Đồng bộ Chỉ mục AI" hiển thị trực quan các snapshot kèm số thế hệ (`generation`), mã SHA-256 và số lượng mục.
  - Các huy hiệu trạng thái chuẩn:
    - `READY`: Xanh lá (Chỉ mục AI đã nạp và sẵn sàng).
    - `SYNCING`: Xanh dương kèm biểu tượng xoay (Đang ghi đĩa và gửi ack).
    - `PENDING`: Vàng (Chờ worker xử lý).
    - `BLOCKED`: Cam (Dừng an toàn do thiếu token cấu hình).
    - `SYNC_FAILED`: Đỏ (Lỗi I/O hoặc mạng kèm thông báo chi tiết).
  - Nút "Thử lại": Cho phép quản trị viên kích hoạt lại snapshot bị lỗi (`SYNC_FAILED`) hoặc bị chặn (`BLOCKED`) qua `POST /api/admin/catalog/snapshots/{id}/retry`.

---

#### P2. Trải Nghiệm Duyệt Catalog & Phát / Tua Video (Player & Playback Readiness)
- **Danh mục Web:** Người dùng có thể duyệt danh sách các bộ hoạt hình đã xuất bản tại `/series/{id}`, xem danh sách mùa, tập, phân đoạn truyện ngắn và phân cảnh.
- **Triệt tiêu Race Condition khi đổi tập:** Khi người dùng chuyển tập, component lập tức xóa sạch trạng thái tập cũ và hủy bỏ yêu cầu mạng đang dang dở bằng `AbortController`.
- **Trình phát video HTML5 qua Media Service:** Phát trực tiếp video từ Google Drive thông qua backend streaming có hỗ trợ Byte Range (`HTTP 206 Partial Content`).
- **Bộ Bốn Định Danh & Thế Hệ Tua Video (Seek Identity & Generation Tuple):**
  - Cấu trúc `PendingSeekIdentity(seriesId, episodeId, assetId, sceneId, targetSec, generation)` bảo vệ tuyệt đối việc tua video.
  - Khi người xem nhấp tua phân cảnh, trình phát chỉ áp dụng mốc thời gian khi video phát sinh sự kiện `onLoadedMetadata`/`onCanPlay` và xác nhận khớp đúng cả 4 tiêu chí định danh.
  - Reset `pendingSeekRef.current = null` ngay khi chuyển tập hoặc unmount component.
- **Chống tua nhầm khi phân cảnh trỏ asset không tồn tại:**
  - Nếu phân cảnh thuộc `mediaAssetId` khác, hệ thống chuyển sang asset đó. Nếu asset không có trong tập, hệ thống phát cảnh báo rõ ràng trên giao diện và **tuyệt đối không tua video trên asset hiện tại**, bảo toàn trạng thái phát.
- **Quy đổi thời gian thực tế qua Coverage JSON (`resolveFileTimestamp`):**
  - Đọc thông số `source_in_ms` và `episode_in_ms` trong `coverageJson` để chuyển đổi thời gian logic của tập sang thời gian thực của tệp video: `fileTimestamp = (source_in_ms + (logicalMs - episode_in_ms)) / 1000`.
  - Hỗ trợ xem danh sách và tua video theo Truyện ngắn / Phân đoạn (`CatalogSegment`).

---

#### P3. Tìm Kiếm Đa Cấp Độ & Trợ Lý Ảo CineBot (Search & Grounded AI Discovery)
- **Đường ray tìm kiếm hoạt hình tại `/search`:**
  - Khi tìm kiếm từ khóa, kết quả trả về phân tách rõ ràng các bộ (`series`), tập (`episodes`), truyện ngắn (`segments`) và phân cảnh (`scenes`).
  - Hỗ trợ deep-link đầy đủ tham số: `/series/{seriesId}?episode={episodeId}&scene={sceneId}&asset={assetId}&t={startMs}`. Khi mở liên kết, hệ thống chọn đúng tập, đúng asset và tua đúng mốc thời gian.
- **Chính sách xuất bản phân cấp (Publication Cascading):**
  - Mặc định deny-by-default: chỉ các bản ghi có `record.status == 'ready'` mới được hiển thị cho người dùng thông thường.
  - Tự động loại bỏ các phần tử con nếu phần tử cha (series/season/episode) là draft hoặc archived.
- **Trợ lý CineBot AI:**
  - CineBot tự động sử dụng chỉ mục Hybrid Retrieval đã cập nhật từ catalog thực để đưa ra các gợi ý và giải thích có căn cứ (grounded explanations) thay vì dữ liệu tĩnh cũ.

---

#### P4. Tính Ổn Định Khi Khởi Động Lại & Bảo Đảm Thế Hệ (Restart Persistence & Concurrency)
- **Tự động phục hồi snapshot mồ côi:**
  - Khi khởi động lại Spring Boot, listener `ApplicationReadyEvent` trong `CatalogSyncWorker` tự động phát hiện các snapshot còn kẹt ở trạng thái `SYNCING` và chuyển về `PENDING` để worker tiếp tục xử lý.
- **Bảo tồn trạng thái tại FastAPI:**
  - FastAPI lưu giữ thế hệ và hash đồng bộ tại `data/indices/catalog_sync_state.json`. Khi khởi động lại, hệ thống phục hồi chính xác thế hệ hiện hành mà không bị reset về 0.
- **Ngăn chặn xung đột thế hệ:**
  - Ràng buộc `UNIQUE` trên `snapshot_version` trong cơ sở dữ liệu ngăn chặn hoàn toàn hai giao dịch đồng thời tạo ra cùng một số thế hệ.
  - Cơ chế CAS có khóa luồng `_publish_lock` tại FastAPI ngăn chặn việc snapshot cũ ghi đè lên snapshot mới.

---

### II. BẢNG TỔNG HỢP KIỂM CHỨNG CÁC GATES KỸ THUẬT

| STT | Gate Kiểm Thử | Lệnh Thực Hiện | Kết Quả Thực Tế | Trạng Thái |
| :---: | :--- | :--- | :--- | :---: |
| 1 | **Contract Invariance** | `git diff -- docs/contracts/animation-catalog-v1/` | 0 dòng khác biệt, SHA-256 khớp tuyệt đối | **PASS** |
| 2 | **Contract Validator** | `python docs/contracts/animation-catalog-v1/validate_catalog.py docs/contracts/animation-catalog-v1/catalog.example.json` | `VALID` | **PASS** |
| 3 | **Reviewer Repro Probe** | `python docs/reviews/repro/CATALOG_01_F02_probe.py` | 100% các khối worker, search, sync_race, index_rebuild đều PASS | **PASS** |
| 4 | **Spring Boot Unit & Integration** | `.\mvnw.cmd test "-Dtest=CatalogValidatorTest,CatalogImportServiceTest"` | Tests run: 15, Failures: 0, Errors: 0, Skipped: 0 | **PASS** |
| 5 | **FastAPI AI Integration** | `python -m unittest backend/fastapi/tests/test_catalog_retrieval.py` | Ran 12 tests in 141.361s, OK | **PASS** |
| 6 | **Frontend Typecheck** | `npx tsc --noEmit` (trong thư mục `frontend/`) | Exit code: 0, 0 compilation errors | **PASS** |
| 7 | **Frontend Production Build** | `npm run build` (trong thư mục `frontend/`) | 8/8 static/dynamic routes compiled thành công | **PASS** |
| 8 | **Reverse Patch Applicability** | `git apply --check -R docs/reports/CATALOG_01_F03.patch` | Clean applicability, không có drift hay xung đột | **PASS** |

---

### III. KẾT LUẬN NGHIỆM THU

Lát cắt sản phẩm **CATALOG-01-F03** đã hoàn thành trọn vẹn mọi yêu cầu chức năng, phi chức năng và đóng toàn bộ các phát hiện kỹ thuật **G1 – G6**. Hệ thống sẵn sàng vận hành ổn định và bàn giao checkpoint an toàn.
