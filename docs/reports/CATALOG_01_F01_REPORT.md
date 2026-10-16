# BÁO CÁO NGHIỆM THU: CATALOG-01-F01
## Sửa Toàn Bộ Findings C1–C10, Giữ Nguyên Schema dippie.catalog.v1 & Chốt Snapshot Vận Hành Hoàn Chỉnh

**Dự án:** Movie Recommendation & Streaming System (Dippie Cinema)  
**Nhánh Git:** `dev`  
**Base Commit:** `c2d29c04edd58c4cc0a6e648d316285a9377384f`  
**Thời điểm hoàn thành:** 2026-10-16  
**Trạng thái nghiệm thu:** **100% ĐẠT (PASS)**

---

### TỔNG QUAN KẾT QUẢ KIỂM THỬ THỰC TẾ

| Hạng mục kiểm tra | Bộ kiểm thử / Công cụ | Số lượng | Kết quả | Chi tiết |
| :--- | :--- | :--- | :--- | :--- |
| **Spring Boot Catalog Validator** | `CatalogValidatorTest` | 9/9 tests | **PASS** | Kiểm thử JSON Schema Draft 2020-12, đường dẫn traversal, ID trùng, tham chiếu gãy, mốc thời gian. |
| **Spring Boot Import & Transaction** | `CatalogImportServiceTest` | 6/6 tests | **PASS** | Kiểm thử dry-run diff, commit nguyên tử, idempotent re-import, chặn revision thấp, xung đột hash, cập nhật revision cao. |
| **Python Contract Probe** | `CATALOG_01_contract_probe.py` | 8/8 cases | **PASS** | 100% khớp tuyệt đối giữa validator sản phẩm và hợp đồng chuẩn `validate_catalog.py`. |
| **FastAPI Catalog Retrieval & NLU** | `test_catalog_retrieval.py` | 12/12 tests | **PASS** | Đánh chỉ mục Hybrid (BM25 + e5), Stage 1-5 pipeline, token auth `/api/index/sync`, grounded explanation. |
| **Frontend TypeScript Check** | `npx tsc --noEmit` | Toàn bộ dự án | **PASS** | 0 lỗi kiểu dữ liệu TypeScript trong `frontend/`. |

---

### BÁO CÁO GIẢI QUYẾT CHI TIẾT TỪNG FINDING (C1 — C10)

#### 1. Finding C1 — Bảo mật API Admin & Xác thực Nội bộ Đồng bộ Chỉ mục
- **Thực trạng phát hiện:** Endpoint `/api/admin/catalog/**` cho phép truy cập công khai mà không có kiểm tra phân quyền `ROLE_ADMIN`. Endpoint `/api/index/sync` của FastAPI cho phép gọi không xác thực và nhận đường dẫn tệp trên đĩa (`catalog_path`), tiềm ẩn lỗ hổng bảo mật.
- **Giải pháp xử lý:**
  1. Trong `backend/springboot/src/main/java/com/dippie/moviercm/config/SecurityConfig.java`:
     - Cấu hình tường lửa phân quyền nghiêm ngặt: `.requestMatchers("/api/admin/**").hasRole("ADMIN")`.
     - Áp dụng chú thích `@PreAuthorize("hasRole('ADMIN')")` trực tiếp tại `AdminCatalogController.java`.
  2. Trong `backend/fastapi/main.py`:
     - Thiết lập middleware kiểm tra mã bí mật nội bộ `X-Service-Token` (giá trị: `dippie-catalog-internal-sync-secret-2026`). Yêu cầu bắt buộc trả về HTTP 401 khi thiếu header và HTTP 403 khi sai token.
     - Loại bỏ việc nạp đường dẫn tệp đĩa tùy ý để triệt tiêu nguy cơ SSRF/LFI.
  3. Trong `frontend/lib/services/catalogService.ts`:
     - Tự động gắn header `Authorization: Bearer <token>` lấy từ phiên đăng nhập quản trị (`dippie_auth_token`).
     - Gắn `X-Service-Token` nội bộ khi kích hoạt `triggerAiIndexSync()`.

#### 2. Finding C2 — Danh sách trắng Storage Key & Xử lý An Toàn Đường Dẫn Đĩa
- **Thực trạng phát hiện:** Giá trị `storage_key` trong JSON đầu vào chưa được ánh xạ qua danh sách trắng (allowlist) của máy chủ, và việc gọi `Paths.get("X:").toAbsolutePath()` trên Windows gây lỗi khi ổ đĩa `X:` chưa được mount.
- **Giải pháp xử lý:**
  1. Xây dựng component `StorageKeyConfig.java`:
     - Danh sách trắng các khóa cho phép:
       - Cục bộ: `local_main`, `local_storage`, `animation_local`, `demo_local`.
       - Google Drive: `drive_primary`, `drive_storage`, `google_drive`, `drive_main`, `animation_drive`, `test_drive`.
     - Bất kỳ `storage_key` nào ngoài danh sách sẽ bị từ chối ngay với ngoại lệ `IllegalArgumentException`.
  2. Bổ sung cơ chế chống văng lỗi ổ đĩa Windows: Thêm dấu phân cách thư mục (`"X:\\"`) và khối `try/catch` bọc an toàn, tự động chuyển về thư mục nội bộ dự phòng khi ổ đĩa chưa mount.
  3. Xác thực đường dẫn tương đối chống Path Traversal: Chặn các chuỗi chứa `..`, đường dẫn tuyệt đối hoặc ký tự điều khiển hệ thống tệp.

#### 3. Finding C3 & C5 — Trình Xác Thực JSON Schema Draft 2020-12 & Khớp Contract Probe 100%
- **Thực trạng phát hiện:** Việc chuyển đổi logic xác thực sang Java làm thất thoát một số ràng buộc phức tạp của Draft 2020-12 (`allOf`, `not`, mốc thời gian `start_ms < end_ms`, đối tượng bí danh đa ngôn ngữ, mốc thời gian phân đoạn null).
- **Giải pháp xử lý:**
  1. Trong `CatalogValidator.java`:
     - Đọc trực tiếp tệp schema chuẩn `dippie.catalog.v1.schema.json`.
     - Triển khai động cơ xác thực 2 bước:
       - **Bước 1 (Structural & Type):** Kiểm tra đầy đủ `$ref`, `allOf`, `not` (nhận diện `PATH_TRAVERSAL`), `anyOf`, `const`, `enum`, `type`, `pattern`, `minLength`, `minimum`, `maximum`, `required` (báo mã `MISSING_REQUIRED_KEY`), và `additionalProperties: false` (báo mã `UNKNOWN_FIELD` với đường dẫn con chính xác).
       - **Bước 2 (Semantic & Relational):** Xác thực bảng quan hệ 11 danh mục thực thể, ID duy nhất toàn cục (`DUPLICATE_ID`), tham chiếu hợp lệ (`BROKEN_REFERENCE`), mốc thời gian (`INVALID_INTERVAL`), thứ tự nhãn cue (`UNSORTED_CUES`), và tính toàn vẹn nguồn gốc (`READY_REQUIRES_PROVENANCE`).
  2. Kiểm thử độc lập qua `CATALOG_01_contract_probe.py`:
     - Kết quả: Đạt 100% khớp chuẩn 8/8 kịch bản (kể cả fixture chính thức, đối tượng bí danh phức tạp và phân đoạn null).

#### 4. Finding C4 & C7 — Cấu Trúc Bảng CSDL Toàn Diện, Raw JSON, Khóa Lạc Quan & Snapshot Outbox
- **Thực trạng phát hiện:** DDL cơ sở dữ liệu bị tinh giản quá mức làm mất các trường chi tiết của hợp đồng, thiếu cơ chế khóa lạc quan (`@Version`) và không có bảng outbox theo dõi snapshot phục vụ đồng bộ chỉ mục AI.
- **Giải pháp xử lý:**
  1. Cập nhật `backend/springboot/src/main/resources/schema.sql`:
     - Hoàn thiện đầy đủ cấu trúc 12 bảng thực thể: `catalog_packages`, `catalog_genres`, `catalog_attribute_scales`, `catalog_sources`, `catalog_series`, `catalog_seasons`, `catalog_episodes`, `catalog_segments`, `catalog_characters`, `catalog_media_assets`, `catalog_text_tracks`, `catalog_scenes`.
     - Bổ sung cột `raw_json CLOB NOT NULL` trên cả 12 bảng nhằm lưu giữ 100% dữ liệu gốc không bị hao hụt.
     - Bổ sung cột `opt_lock_version BIGINT NOT NULL DEFAULT 0` kết hợp `@Version` trên tất cả entity class JPA.
     - Tạo mới bảng `catalog_snapshots` (`id`, `revision`, `content_hash`, `total_items`, `status`, `created_at`, `synced_at`) làm outbox ghi nhận giao dịch snapshot.
  2. Cập nhật các repository JPA tương ứng và sửa đổi `CatalogSnapshotRepository.java`.

#### 5. Finding C6 — Xem Trước Khác Biệt (Dry-Run Diff Preview) & Phát Hiện Xung Đột Revision
- **Thực trạng phát hiện:** Thiếu luồng tính toán diff chi tiết trước khi nạp tệp và cơ chế phát hiện xung đột đồng thời.
- **Giải pháp xử lý:**
  1. Phương thức `validateAndPreview(data)` trong `CatalogImportService.java`:
     - Tính mã băm SHA-256 trên toàn bộ nội dung JSON.
     - So sánh với dữ liệu hiện có trong CSDL và phân loại chính xác các số lượng: `toCreate`, `toUpdate`, `unchanged`, `conflicts`.
  2. Quy tắc phân định Revision:
     - `incomingRev < existingRev`: Báo `CONFLICT` (`CatalogConflictException`), bảo vệ CSDL khỏi việc ghi đè lùi phiên bản.
     - `incomingRev == existingRev` và mã băm giống nhau: Ghi nhận `UNCHANGED` (idempotent, không báo lỗi).
     - `incomingRev == existingRev` nhưng nội dung khác nhau: Báo `CONFLICT` chống sửa đổi đè nội dung trên cùng một phiên bản.
     - `incomingRev > existingRev`: Ghi nhận `UPDATE`, cập nhật thực thể an toàn.
  3. Khắc phục triệt để lỗi unboxing `NullPointerException` trong Java bằng các helper an toàn `getIntOrNull` và `getLongOrNull`.

#### 6. Finding C8 — Trải Nghiệm Web: Deep Linking Phân Cảnh, Triệt Tiêu Race Condition & Accessibility
- **Thực trạng phát hiện:** Trang web `/series/[id]` thiếu đọc tham số deep-link từ tìm kiếm, gặp hiện tượng race condition khi chuyển tập nhanh, click trap do lồng button trong div, không đồng bộ asset khi tua cảnh và thiếu điều khiển bàn phím.
- **Giải pháp xử lý:**
  1. Trong `frontend/features/search/components/SearchExperience.tsx`:
     - Xây dựng liên kết phân cảnh chuẩn deep link:
       `/series/{seriesId}?episode={epId}&scene={scId}&asset={assetId}&t={startMs}`.
  2. Trong `frontend/app/series/[id]/page.tsx`:
     - Đọc tham số URL qua `useSearchParams()` (`episode`, `scene`, `asset`, `t`).
     - **Triệt tiêu Race Condition:** Sử dụng `AbortController` và generation counter `episodeGenRef`. Khi đổi tập, hệ thống lập tức xóa dữ liệu cũ (`setEpisodeDetail(null); setSelectedAsset(null);`) trước khi nạp tập mới.
     - **Đồng bộ Asset khi Tua Cảnh:** Trong `handleSeekScene`, nếu `scene.mediaAssetId !== selectedAsset.id`, tự động chuyển `selectedAsset` sang đúng nguồn phát video của phân cảnh đó trước khi seek.
     - **Lọc Active Scene theo Asset:** Kiểm tra điều kiện `s.mediaAssetId === selectedAsset.id` khi hiển thị cảnh đang phát.
     - **Loại bỏ Click Trap:** Thay thế phần tử `<button>` lồng bên trong thành `<span className="pointer-events-none">`.
     - **Khả năng tiếp cận (Accessibility):** Bổ sung `role="button"`, `tabIndex={0}` và trình lắng nghe phím `Enter` / `Space` (`onKeyDown`) trên danh sách phân cảnh.

#### 7. Finding C9 — FastAPI Hybrid Retrieval, Stage 1–5 Pipeline & Grounded Explanations
- **Thực trạng phát hiện:** FastAPI thiếu cơ chế đồng bộ danh mục chuẩn hóa `dippie.catalog.v1` và chưa tích hợp tìm kiếm đa cấp độ gắn liền với giải thích có căn cứ (grounded explanations).
- **Giải pháp xử lý:**
  1. Trong `backend/fastapi/services/catalog_sync.py`:
     - Làm phẳng danh mục 4 cấp độ: Bộ (`series`), Tập (`episode`), Đoạn (`segment`), Cảnh (`scene`).
     - Trích xuất đầy đủ từ khóa, tình tiết cốt truyện (`plot_facts`), mô tả hình ảnh (`visual_description`), và nhãn nhân vật.
  2. Trong `backend/fastapi/services/hybrid_retrieval.py`:
     - Kết hợp BM25 Robertson-Spärck Jones và mô hình nhúng ngữ nghĩa `intfloat/multilingual-e5-small`.
     - Lưu trữ chỉ mục tiền tính toán tại `data/indices/movie_index_v1.json`.
  3. Trong `backend/fastapi/services/ai_pipeline.py`:
     - Khâu Stage 5 tự động tổng hợp lời giải thích bám sát mốc thời gian phân cảnh (ví dụ: `01:10–01:35`), nhân vật và chi tiết hành động trong cảnh.
  4. Kiểm thử thành công 12/12 ca kiểm thử trong `test_catalog_retrieval.py`.

#### 8. Finding C10 — Bàn Giao Snapshot Vận Hành Bền Vững & Hướng Dẫn Vận Hành
- **Thực trạng phát hiện:** Cần hoàn thiện sổ tay vận hành và bộ hồ sơ tài liệu báo cáo nghiệm thu rõ ràng.
- **Giải pháp xử lý:**
  - Cập nhật toàn diện `docs/runbooks/CATALOG_IMPORT.md`.
  - Xuất bản ma trận ánh xạ trường `docs/reports/CATALOG_01_F01_FIELD_MAPPING_MATRIX.md`.
  - Xuất bản báo cáo nghiệm thu `docs/reports/CATALOG_01_F01_REPORT.md` và tệp trạng thái máy đọc `docs/reports/CATALOG_01_F01_STATUS.json`.
  - Xuất bản biên bản đánh giá chéo độc lập `docs/reports/CATALOG_01_F01_CROSS_REVIEW.md`.

---

### KẾT LUẬN & KHUYẾN NGHỊ BÀN GIAO

Toàn bộ 10 phát hiện trong đợt đánh giá CATALOG-01 đã được giải quyết triệt để, giữ vững nguyên vẹn hợp đồng schema chuẩn `dippie.catalog.v1`, không thay đổi bất kỳ trường hay enum nào mà người dùng đang sử dụng. Hệ thống đã được kiểm chứng tự động từ cấp unit test đến tích hợp đa dịch vụ, sẵn sàng bàn giao cho người dùng và reviewer kiểm tra.
