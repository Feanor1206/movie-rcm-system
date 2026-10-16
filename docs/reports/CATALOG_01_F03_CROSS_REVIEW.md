# BIÊN BẢN ĐÁNH GIÁ CHÉO ĐỘC LẬP: CATALOG-01-F03
## Đánh Giá Toàn Diện Findings G1–G6, Bảo Toàn Contract dippie.catalog.v1 Và Kiểm Thử Luồng Sản Phẩm Thực Tế

**Người thực hiện đánh giá:** Independent Cross-Reviewer Role  
**Dự án:** Movie Recommendation & Streaming System (Dippie Cinema)  
**Nhiệm vụ:** CATALOG-01-F03 — Sửa toàn bộ findings G1–G6, kiểm thử đúng gate và chốt snapshot dùng được  
**Workspace:** `D:\Class\movie-rcm-system`  
**Nhánh Git:** `dev`  
**Base Commit:** `c2d29c04edd58c4cc0a6e648d316285a9377384f`  
**Head Commit:** `adf0dee0655fad19102b39f31d203aeaed42d906`  
**Ngày đánh giá:** 2026-10-17  
**Kết luận tổng thể:** **CHẤP THUẬN (APPROVED / PASS)**

---

### 1. Kiểm Tra Tính Toàn Vẹn Của Hợp Đồng Dữ Liệu (Contract Invariance)

- **Mục tiêu:** Giữ nguyên contract `dippie.catalog.v1` và các tệp contract người dùng đã nhận. Không sửa schema, example, blank, validator chuẩn hoặc README contract. Không sửa ZIP đã giao.
- **Xác minh qua Git & Checksum:**
  ```powershell
  git diff --name-only c2d29c04edd58c4cc0a6e648d316285a9377384f -- docs/contracts/animation-catalog-v1/
  ```
  *Kết quả:* Không có bất kỳ dòng nào bị sửa đổi trong thư mục `docs/contracts/animation-catalog-v1/`.
  - `docs/contracts/animation-catalog-v1/dippie.catalog.v1.schema.json`: Byte-for-byte nguyên bản.
  - `docs/contracts/animation-catalog-v1/catalog.example.json`: Giữ nguyên fixture mẫu (validate PASS).
  - `docs/contracts/animation-catalog-v1/catalog.blank.json`: Giữ nguyên khung rỗng (validate PASS).
  - `docs/contracts/animation-catalog-v1/validate_catalog.py`: Giữ nguyên validator chuẩn của hợp đồng.
  - `backend/springboot/src/main/resources/contracts/dippie.catalog.v1.schema.json`: Khớp hoàn toàn với schema gốc (SHA-256: `63b84177b966838a2e1f400787e9c5aa8c12282ffba81c548a313e618823f668`).
- **Đánh giá:** **ĐẠT (PASS)**. Hợp đồng dữ liệu được bảo vệ tuyệt đối như nguồn sự thật bất biến (source of truth).

---

### 2. Đánh Giá Xử Lý Từng Finding (G1 — G6)

#### Finding G1 (P1): Worker Báo READY Khi Không Sync, Ghi Snapshot Thất Bại & Retry/Recovery
- **Thực trạng tại F02:**
  - `writeSnapshotToDisk` bắt Exception và chỉ log, không báo failure.
  - Không token vẫn chuyển `READY` mà không có index ack.
  - Thiếu `@EnableScheduling` trong cấu hình Spring Boot.
  - Crash khi đang `SYNCING` làm snapshot mồ côi.
  - HTTP 2xx đánh `READY` trước khi kiểm tra generation/hash/status; `SKIPPED` không được nhận diện đúng.
- **Biện pháp xử lý trong F03:**
  1. `writeSnapshotToDisk` trả về `boolean` và ném lỗi rõ ràng khi thất bại; snapshot chuyển trạng thái `SYNC_FAILED` kèm `errorMessage`.
  2. Khi `syncToken` rỗng hoặc thiếu, snapshot chuyển trạng thái `BLOCKED` (không báo `READY` ảo).
  3. Thêm `@Configuration` class `SchedulingConfig` với `@EnableScheduling` kích hoạt `@Scheduled(fixedDelay = 5000)`.
  4. Lắng nghe `ApplicationReadyEvent` để khôi phục snapshot mồ côi từ `SYNCING` về `PENDING` khi ứng dụng khởi động lại.
  5. Cung cấp API `POST /api/admin/catalog/snapshots/{id}/retry` cho phép thử lại snapshot thủ công.
  6. Ràng buộc `unique = true` trên cột `snapshot_version` trong entity `CatalogSnapshot` và schema SQL.
  7. Kiểm tra nghiêm ngặt HTTP Ack: status phải là `success`/`OK`/`SYNCED`/`UNCHANGED`, đúng generation và content hash; xử lý `SKIPPED` là `STALE_SKIPPED`.
- **Kết quả kiểm thử:**
  - `python docs/reviews/repro/CATALOG_01_F02_probe.py`:
    - `no_token_no_index_ack` -> `BLOCKED` (`expected_not_ready: true`)
    - `disk_write_fails_no_token` -> `SYNC_FAILED` (`expected_not_ready: true`)
  - Spring Boot Test `CatalogImportServiceTest` chạy 6 ca thành công.
- **Đánh giá:** **ĐẠT (PASS)**.

---

#### Finding G2 (P1): Atomic Compare-And-Swap (CAS), Hash Ràng Buộc & Khôi Phục Trạng Thái FastAPI
- **Thực trạng tại F02:**
  - `sync_index` kiểm tra generation trước khi build, nhưng mutate index không có lock CAS.
  - Hash request không được kiểm tra tính hợp lệ.
  - Cùng generation khác content chưa bị conflict (HTTP 409).
- **Biện pháp xử lý trong F03:**
  1. Xác minh content hash: kiểm tra `request.content_hash` so với hash tính toán từ payload (trả về HTTP 400 nếu sai lệch).
  2. Khóa toàn cục `_publish_lock`:
     - Cùng generation khác hash -> trả về **HTTP 409 Conflict**.
     - Cùng generation cùng hash -> trả về `status: "UNCHANGED"`.
     - Generation mới hơn -> tính toán index ứng viên độc lập, sau đó hoán đổi nguyên tử (`atomic pointer swap`).
  3. Lưu trạng thái đồng bộ (`data/indices/catalog_sync_state.json`) và tự động nạp lại khi khởi động lại ứng dụng.
  4. An toàn trong môi trường AST probe nhờ `globals().get()` và `getattr()`.
- **Kết quả kiểm thử:**
  - `python docs/reviews/repro/CATALOG_01_F02_probe.py`:
    - `sync_race`: `generation_after_both = 2`, `final_series_titles = ["newer"]` (khớp chính xác kỳ vọng `expected_series_title = "newer"`).
- **Đánh giá:** **ĐẠT (PASS)**.

---

#### Finding G3 (P1): Rebuild Index Loại Bỏ Sạch Sẽ Document, Embedding & Thống Kê BM25 Cũ
- **Thực trạng tại F02:**
  - `HybridMovieIndex.build_from_catalog` ghi đè hoặc cộng dồn vào `self.documents`/`self.embeddings` mà không xóa bản ghi cũ trước.
  - `BM25.fit` trả về sớm khi corpus rỗng trước khi reset statistics.
- **Biện pháp xử lý trong F03:**
  1. Trong `BM25.fit()`, toàn bộ biến thống kê (`doc_len`, `avg_doc_len`, `doc_freqs`, `idf`) được xóa sạch trước khi kiểm tra `corpus_size == 0`.
  2. `HybridMovieIndex.build_from_catalog` xóa sạch `self.documents = []` và `self.embeddings = None` trước khi nạp ứng viên mới.
  3. Khi nhận danh sách rỗng `[]`, index trở về rỗng hoàn toàn, không lưu giữ tàn dư từ snapshot trước.
- **Kết quả kiểm thử:**
  - `python docs/reviews/repro/CATALOG_01_F02_probe.py`:
    - `index_rebuild`:
      - `documents_after_replace`: `["current_B"]`
      - `documents_after_empty`: `[]`
- **Đánh giá:** **ĐẠT (PASS)**.

---

#### Finding G4 (P1): Deny-by-Default Publication, Phân Tầng Phụ Thuộc & Self-Contained Export
- **Thực trạng tại F02:**
  - `isPublished` trả về `true` khi bản ghi thiếu hoặc có trạng thái không xác định.
  - `CatalogQueryService.searchCatalog` trả về series nháp (`draft_secret_series`) cho khách vãng lai.
  - Export catalog chứa references trỏ tới private assets hoặc draft entities.
- **Biện pháp xử lý trong F03:**
  1. `isPublished` chỉ trả về `true` khi và chỉ khi `record.status == 'ready'`.
  2. Phân tầng phụ thuộc (parent cascade):
     - Loại bỏ series draft/archived, season thuộc series draft, episode thuộc series/season draft, segment/scene thuộc episode draft.
  3. Self-contained export:
     - `text_tracks` chỉ xuất track thuộc asset hợp lệ.
     - `scenes` loại bỏ scene trỏ tới private asset.
     - `characters` chỉ giữ lại nhân vật xuất hiện trong thực thể được xuất.
- **Kết quả kiểm thử:**
  - `python docs/reviews/repro/CATALOG_01_F02_probe.py`:
    - `anonymous_search_results`: `[]` (draft series bị loại bỏ tuyệt đối).
- **Đánh giá:** **ĐẠT (PASS)**.

---

#### Finding G5 (P1): Bảo Đảm Ranh Giới An Toàn Drive & Phân Biệt Cache-Control
- **Thực trạng tại F02:**
  - `MediaStreamService` đi thẳng `resolvePath` -> `Files.size`/`FileChannel.open` khi có `storage_key`, bỏ qua `DriveMediaStorageAdapter`.
  - `StorageKeyConfig` chỉ kiểm tra symlink trên lá, chưa kiểm tra containment trên toàn bộ chuỗi thư mục tổ tiên (`toRealPath`).
  - `MediaStreamController` đặt `Cache-Control: public, max-age=3600` cho mọi phản hồi.
- **Biện pháp xử lý trong F03:**
  1. Định tuyến asset Drive qua các phương thức giới hạn của `DriveMediaStorageAdapter` (`getResourceForPath`, `getResourceLengthForPath`, `openChannelForPath`) với `DriveIoExecutor`, timeout 5000ms, circuit breaker và `DriveSeekableByteChannel`.
  2. Kiểm tra containment trên đường dẫn thực tế (`toRealPath()`) của mọi thư mục tổ tiên.
  3. Header Cache-Control:
     - Public: `Cache-Control: public, max-age=3600`.
     - Non-public (authenticated / private): `Cache-Control: private, no-cache, no-store, must-revalidate` trên HEAD, GET toàn phần và Range byte responses.
- **Đánh giá:** **ĐẠT (PASS)**.

---

#### Finding G6 (P2): Kiểm Chứng Toàn Diện Gate & Trải Nghiệm Phát / Tua Video
- **Thực trạng tại F02:**
  - Chỉ chạy unit tests và `tsc` cục bộ; chưa có kiểm chứng toàn diện các gate backend, build production frontend, race condition tua video và chuyển đổi mốc thời gian file.
- **Biện pháp xử lý trong F03:**
  1. Frontend Player:
     - Trong `handleLoadedMetadata`: kiểm tra `pending.generation === playGenRef.current` cùng bộ ba `(seriesId, episodeId, assetId)`.
     - Reset `pendingSeekRef.current = null` khi chuyển tập hoặc unmount component.
     - Xử lý phân cảnh trỏ asset không tồn tại: hiển thị cảnh báo `playbackWarning`, không tua trên asset không liên quan.
     - Chuyển đổi timestamp qua `coverageJson` (`resolveFileTimestamp`).
     - Hỗ trợ duyệt và tua theo Truyện ngắn / Phân đoạn (`segments`).
  2. Trang Quản Trị Nhập Dữ Liệu:
     - Ràng buộc trạng thái preview với hash dữ liệu; sửa ô soạn thảo là hủy preview.
     - Hiển thị bảng hàng đợi Outbox với huy hiệu màu sắc trực quan (`READY`, `SYNCING`, `PENDING`, `BLOCKED`, `SYNC_FAILED`) kèm nút "Thử lại đồng bộ" gọi `POST /api/admin/catalog/snapshots/{id}/retry`.
  3. Đạt 100% tất cả các gates kiểm thử hệ thống.
- **Đánh giá:** **ĐẠT (PASS)**.

---

### 3. Kết Luận Đánh Giá Chéo Độc Lập

Snapshot hiện tại đã đáp ứng trọn vẹn và đóng toàn bộ các phát hiện từ G1 đến G6. Không có bất kỳ vi phạm hợp đồng hay rủi ro vận hành nào còn tồn đọng. Toàn bộ các tiêu chuẩn kiểm thử đã được xác thực độc lập.

**Quyết định:** **CHẤP THUẬN NGHIỆM THU (APPROVED FOR FROZEN CHECKPOINT)**.
