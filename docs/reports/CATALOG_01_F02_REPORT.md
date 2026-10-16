# BÁO CÁO NGHIỆM THU: CATALOG-01-F02
## Sửa Toàn Bộ Findings F1–F8, Kiểm Thử Đúng Gate Và Chốt Snapshot Vận Hành Hoàn Chỉnh

**Dự án:** Movie Recommendation & Streaming System (Dippie Cinema)  
**Workspace:** `D:\Class\movie-rcm-system`  
**Nhánh Git:** `dev`  
**Base Commit:** `c2d29c04edd58c4cc0a6e648d316285a9377384f`  
**Head Commit:** `adf0dee0655fad19102b39f31d203aeaed42d906`  
**Thời điểm hoàn thành:** 2026-10-16  
**Trạng thái nghiệm thu:** **100% ĐẠT (PASS)**

---

### I. TỔNG QUAN NHIỆM VỤ & CAM KẾT HỢP ĐỒNG

Nhiệm vụ **CATALOG-01-F02** tập trung giải quyết triệt để 8 thiếu sót và rủi ro vận hành (F1–F8) được chỉ ra trong đợt rà soát độc lập `CATALOG_01_F01_REVIEW.md`. Luồng dữ liệu hoàn chỉnh đạt chuẩn:

$$\text{JSON dippie.catalog.v1} \longrightarrow \text{Validate \& Dry-run} \longrightarrow \text{Import Transaction (Outbox)} \longrightarrow \text{DB Persistence} \longrightarrow \text{Web Catalog} \longrightarrow \text{Search \& Chatbot} \longrightarrow \text{Video Playback}$$

#### Nguyên Tắc Bất Di Bất Dịch:
1. **Bảo toàn Contract Schema:** Tuyệt đối không thay đổi schema `dippie.catalog.v1.schema.json`, các file example, blank, validator gốc và file ZIP đã bàn giao cho người dùng.
2. **Không nới lỏng Validation:** Không hạ thấp tiêu chuẩn kiểm tra để làm cho dữ liệu sai được import.
3. **An toàn Hệ thống:** Không ghi vào live DB, không can thiệp/rename/xóa tài nguyên Google Drive, không tạo tiến trình nền ngoài luồng.
4. **Không tùy tiện Git:** Không thực hiện `git commit`, `git push`, `git reset`, hay `git revert`. Bàn giao dưới dạng bản vá tái lập sạch (`CATALOG_01_F02.patch`) kèm manifest kiểm chứng.

---

### II. BẢNG TỔNG HỢP KẾT QUẢ CÁC GATE KIỂM THỬ

| Nhóm Kiểm Thử / Gate | Bộ Kiểm Thử / Công Cụ | Số Lượng Ca | Kết Quả Thực Tế | Trạng Thái Gate |
| :--- | :--- | :--- | :--- | :--- |
| **Contract Invariance** | SHA-256 đối chiếu 5 tệp hợp đồng | 5 files | 100% byte-for-byte nguyên bản | **PASS** |
| **Reviewer Probe 1** | `CATALOG_01_F01_logic_probe.py` | 3 ca logic & export | 0 contract errors, UNCHANGED, CONFLICT | **PASS** |
| **Reviewer Probe 2** | `CATALOG_01_F01_probe.py` | 3 ca schema + runtime pub | 3/3 lỗi contract khớp, 0 draft/private indexed | **PASS** |
| **Reviewer Probe 3** | `CATALOG_01_contract_probe.py` | 8 ca đối chiếu validator | 8/8 kịch bản khớp tuyệt đối | **PASS** |
| **Spring Boot Validator** | `CatalogValidatorTest` | 9 unit tests | 9/9 PASS (0 failures, 0 errors) | **PASS** |
| **Spring Boot Import/Outbox** | `CatalogImportServiceTest` | 6 service tests | 6/6 PASS (0 failures, 0 errors) | **PASS** |
| **FastAPI Hybrid & Pipeline** | `test_catalog_retrieval.py` | 12 integration tests | 12/12 PASS (0 failures, 0 errors) | **PASS** |
| **Frontend TypeScript** | `npx tsc --noEmit` | Toàn bộ dự án `frontend/` | 0 errors (Exit code: 0) | **PASS** |
| **Patch Applicability** | `git apply --check -R docs/reports/CATALOG_01_F02.patch` | 66 files manifest | Khớp hoàn toàn (Exit code: 0) | **PASS** |

---

### III. BÁO CÁO CHI TIẾT GIẢI QUYẾT TOÀN BỘ FINDINGS F1 – F8

```
+-------------------------------------------------------------------------------------------------------+
|                               DANH SÁCH FINDINGS ĐÃ KHẮC PHỤC TRIỆT ĐỂ                                |
+----+----+---------------------------------------------------------------------------------+-----------+
| ID | Mức| Tiêu đề tóm tắt                                                                 | Trạng thái|
+----+----+---------------------------------------------------------------------------------+-----------+
| F1 | P1 | Service credential công khai trong frontend, auth sync bị bypass                | CLOSED    |
| F2 | P1 | Snapshot ghi đĩa/sync trước commit, thiếu outbox worker và retry                | CLOSED    |
| F3 | P1 | Runtime index dữ liệu draft/private, API public rò rỉ metadata và raw JSON       | CLOSED    |
| F4 | P1 | Revision entity bị package revision nâng giả; thứ tự key gây xung đột giả       | CLOSED    |
| F5 | P1 | storage_key chưa nối vào streaming; nhiều edition bị đụng unique constraint     | CLOSED    |
| F6 | P1 | Seek can thiệp video cũ khi đổi asset; timer deep link không có identity guard   | CLOSED    |
| F7 | P2 | Validation thiếu format date/uri/exclusiveMinimum; export sai cấu trúc contract  | CLOSED    |
| F8 | P2 | Manifest chưa bao trọn 31 files phụ thuộc; thiếu bằng chứng nghiệm thu gate     | CLOSED    |
+----+----+---------------------------------------------------------------------------------+-----------+
```

---

#### 1. Finding F1 (P1) — Bảo Mật Service Credential & Đồng Bộ Chỉ Mục Fail-Closed
- **Nguyên nhân tại F01:**
  Chuỗi mã bí mật nội bộ `dippie-catalog-internal-sync-secret-2026` bị hardcode trực tiếp trong `frontend/lib/services/catalogService.ts`, đồng thời được dùng làm giá trị mặc định (fallback) trong `FastAPI` và `CatalogImportService.java`. Bất kỳ ai kiểm tra client bundle đều lấy được credential này để ghi đè chỉ mục toàn hệ thống.
- **Giải pháp triển khai trong F02:**
  1. **Xóa hoàn toàn khỏi Frontend:** Loại bỏ phương thức `triggerAiIndexSync()` và chuỗi bí mật khỏi `frontend/lib/services/catalogService.ts` và component `CatalogImportModal.tsx`. Giao diện web người dùng không còn quyền trực tiếp gọi sang FastAPI AI index sync.
  2. **FastAPI Fail-Closed:** Trong `backend/fastapi/main.py`:
     ```python
     FASTAPI_SYNC_SECRET = os.environ.get("CATALOG_SYNC_TOKEN", os.environ.get("FASTAPI_SYNC_SECRET", "")).strip()
     ```
     Nếu không có biến môi trường nào được thiết lập, endpoint `/api/index/sync` trả về ngay lập tức mã `HTTP 503 Service Unavailable` ("Catalog sync secret is not configured on server (fail-closed)").
  3. **Backend-to-Backend Sync:** `CatalogSyncWorker.java` và `CatalogImportService.java` đọc token từ biến môi trường của tiến trình máy chủ, bảo vệ tuyệt đối không rò rỉ vào Git hay client.
  4. **Kiểm tra phân quyền hai lớp:** Frontend chỉ tương tác với Spring Boot thông qua JWT của phiên người dùng có thẩm quyền `ROLE_ADMIN`.
- **Bằng chứng xác minh:**
  - `npx tsc --noEmit` đạt 0 lỗi.
  - Test case `test_12_fastapi_endpoints_sync_and_serve_real_catalog` xác nhận cơ chế xác thực hoạt động chuẩn xác: thiếu header trả về 401, sai token trả về 403, cấu hình chuẩn trả về 200.

---

#### 2. Finding F2 (P1) — Kiến Trúc Outbox Worker Thật, Tách Rời Giao Dịch & Chống Stale Generation
- **Nguyên nhân tại F01:**
  Phương thức `importPackage` được đánh dấu `@Transactional` nhưng lại thực hiện thao tác ghi đĩa (`writeSnapshotToDisk`) và gửi HTTP request sang FastAPI ngay bên trong phương thức trước khi giao dịch DB commit. Khi commit DB thất bại, chỉ mục AI vẫn bị cập nhật sai (ghost data). Tệp snapshot chỉ chứa package vừa nhập thay vì toàn bộ catalog hiện có.
- **Giải pháp triển khai trong F02:**
  1. **Tách biệt hoàn toàn Giao Dịch & I/O:**
     - Loại bỏ mọi thao tác ghi đĩa và gọi HTTP ra khỏi `CatalogImportService.importPackage`.
     - Sinh số thứ tự đơn điệu toàn cục `generation = max(generation) + 1`.
     - Lưu bản ghi trạng thái `CatalogSnapshot` vào CSDL với trạng thái ban đầu là `PENDING`.
  2. **Đồng bộ Bất Đồng Bộ Sau Commit (`afterCommit`):**
     - Đăng ký trình lắng nghe đồng bộ giao dịch Spring (`TransactionSynchronizationManager.registerSynchronization`) để kích hoạt xử lý snapshot sau khi giao dịch cơ sở dữ liệu đã commit thành công (`afterCommit`).
  3. **Chuyên Biệt Hóa Background Worker (`CatalogSyncWorker`):**
     - Thiết lập `@Scheduled(fixedDelay = 5000)` để quét định kỳ các snapshot có trạng thái `PENDING`.
     - Đăng ký `@EventListener(ApplicationReadyEvent.class)` để tự động phục hồi và tiếp tục xử lý các snapshot còn tồn đọng khi ứng dụng khởi động lại.
     - Hàm `exportEligibleSnapshot()` truy vấn toàn bộ các bản ghi catalog hợp lệ (published) từ CSDL trên tất cả các package đã nạp, cấu trúc thành snapshot JSON hoàn chỉnh và ghi ra đĩa nguyên tử (`Files.move` với `ATOMIC_MOVE` và `REPLACE_EXISTING`).
     - Gửi yêu cầu đồng bộ sang FastAPI kèm mã băm `content_hash` và số `generation`.
  4. **Chống Stale Generation tại FastAPI:**
     - Khi nhận yêu cầu đồng bộ, FastAPI so sánh `request.generation` với `_current_sync_generation`. Nếu thế hệ yêu cầu nhỏ hơn thế hệ hiện tại (`generation < _current_sync_generation`), FastAPI trả về `HTTP 200` kèm `status="SKIPPED"` mà không đè lên chỉ mục mới hơn.
  5. **Idempotent Re-import Chính Xác:**
     - Khi nạp lại một package trùng lặp hoàn toàn nội dung và revision, hệ thống tìm kiếm snapshot gần nhất của package đó trong CSDL và trả về đúng trạng thái thực tế (`PENDING`, `SYNCED`, `FAILED`).
- **Bằng chứng xác minh:**
  - `CatalogImportServiceTest.testImportCommitSuccess`: Tạo snapshot `PENDING` thành công.
  - `CatalogImportServiceTest.testIdempotentReimport`: Đọc đúng bản ghi snapshot đã có trong CSDL.
  - `test_catalog_retrieval.py`: FastAPI xử lý mượt mà payload snapshot đồng bộ có generation.

---

#### 3. Finding F3 (P1) — Chính Sách Phát Hành Phân Tầng & Lọc Dữ Liệu Công Khai
- **Nguyên nhân tại F01:**
  Các cờ `include_draft` và `include_private` trong `catalog_sync.py` mặc định là `True`, dẫn đến việc các nội dung nháp hoặc tệp riêng tư vẫn bị lập chỉ mục tìm kiếm và chatbot. Các API đọc công khai của Spring Boot trả về toàn bộ metadata và raw JSON không kiểm soát quyền hạn.
- **Giải pháp triển khai trong F02:**
  1. **Đổi mặc định an toàn tại FastAPI:**
     - Đặt `include_draft=False` và `include_private=False` làm giá trị mặc định cho toàn bộ luồng đồng bộ chỉ mục của `catalog_sync.py`.
  2. **Lan truyền chính sách phát hành phân tầng (Parent Publication Cascade):**
     - Nếu một bộ phim (`series`) có trạng thái `draft` hoặc `archived`, toàn bộ các phần (`seasons`), tập (`episodes`), phân đoạn (`segments`) và cảnh (`scenes`) trực thuộc sẽ bị loại bỏ hoàn toàn khỏi chỉ mục tìm kiếm và ngữ cảnh chatbot.
     - Nếu một tập phim (`episode`) có trạng thái `draft` hoặc `archived`, toàn bộ các phân đoạn và cảnh của tập đó bị loại bỏ.
     - Nếu một tài nguyên video (`media_asset`) có chính sách `private`, các cảnh tham chiếu đến video đó sẽ bị loại khỏi chỉ mục công khai.
  3. **Lọc API Đọc Công Khai (`CatalogQueryService.java`):**
     - Các endpoint `/api/catalog/series` và `/api/catalog/episodes/*` tự động áp dụng bộ lọc chỉ trả về các thực thể có `status == "published"` đối với người dùng thông thường hoặc khách truy cập ẩn danh.
     - Chuyển endpoint xuất danh mục `/api/catalog/export` vào phạm vi quản trị `/api/admin/catalog/export` yêu cầu quyền `ROLE_ADMIN`, bảo vệ toàn diện các trường nhạy cảm (`raw_json`, storage provenance).
- **Bằng chứng xác minh:**
  - Chạy `python docs/reviews/repro/CATALOG_01_F01_probe.py`: Đoạn kiểm tra `runtime_default_publication` xác nhận chính xác:
    - 0 series, 0 episodes, 0 segments, 0 scenes (0/4 items) được lập chỉ mục khi dùng runtime defaults.

---

#### 4. Finding F4 (P1) — Độc Lập Revision Thực Thể & Mã Băm Chuẩn Hóa Khóa JSON
- **Nguyên nhân tại F01:**
  Hàm `extractRevision` sử dụng `Math.max(record.revision, packageRevision)`, làm cho thực thể có revision thấp trong một package có revision cao bị nâng revision giả tạo. Hàm tính mã băm SHA-256 sử dụng chuỗi JSON thô không sắp xếp khóa, gây xung đột giả (`CONFLICT`) khi cùng một đối tượng chỉ đổi thứ tự thuộc tính.
- **Giải pháp triển khai trong F02:**
  1. **Bảo tồn Revision Thực Thể Độc Lập:**
     - Sửa phương thức `extractRevision` trong `CatalogImportService.java` chỉ trích xuất giá trị `record.revision` của chính thực thể.
     - Xử lý xung đột chuẩn xác: Khi thực thể trong package có revision nhỏ hơn thực thể đã lưu trong CSDL, hệ thống ném `CatalogConflictException` (báo `CONFLICT`).
  2. **Chuẩn Hóa Khóa Đối Tượng JSON (`computeCanonicalSha256`):**
     - Đệ quy chuyển đổi cấu trúc JSON sang `TreeMap<String, Object>`, tự động sắp xếp toàn bộ các thuộc tính của Object theo thứ tự từ điển A–Z.
     - Duy trì nguyên vẹn thứ tự tuần tự của các phần tử trong Array.
     - Hai tệp JSON có cùng thuộc tính nhưng khác thứ tự khai báo key luôn tạo ra mã băm SHA-256 giống hệt nhau, báo `UNCHANGED`.
  3. **Cập Nhật Thực Thể Được Quản Lý (Managed Entities):**
     - Trong `importPackage`, tái sử dụng thực thể đã được EntityManager tải từ CSDL để cập nhật dữ liệu thay vì khởi tạo đối tượng mới với `opt_lock_version = 0`, bảo toàn tính toàn vẹn của cơ chế khóa lạc quan `@Version`.
- **Bằng chứng xác minh:**
  - `python docs/reviews/repro/CATALOG_01_F01_logic_probe.py`:
    - `reordered_identical_object`: Kết quả `UNCHANGED` (khớp hoàn toàn kỳ vọng).
    - `lower_entity_revision_in_higher_package`: Kết quả `CONFLICT` (khớp hoàn toàn kỳ vọng).
  - `CatalogImportServiceTest.testHigherRevisionUpdate`: Cập nhật thành công khi revision tăng hợp lệ.

---

#### 5. Finding F5 (P1) — Phân Giải storage_key Cho Phát Video & Triệt Tiêu Xung Đột Nhiều Ấn Bản
- **Nguyên nhân tại F01:**
  `StorageKeyConfig` không được liên kết vào luồng phát video của `MediaStreamService`. Phương thức phát video mở trực tiếp từ thư mục mặc định của provider mà không kiểm tra tính bao chứa của `storage_key`. Ngoài ra, phương thức `syncToLegacyMediaAsset` luôn gán phiên bản cố định `version = "v1"`, dẫn đến vi phạm ràng buộc duy nhất `unique(movie_id, kind, version)` khi một tập có nhiều ấn bản video (multi-editions).
- **Giải pháp triển khai trong F02:**
  1. **Tích hợp `StorageKeyConfig` Vào `MediaStreamService`:**
     - Tiêm `StorageKeyConfig` và `CatalogMediaAssetRepository` vào `MediaStreamService.java`.
     - Trong `getMediaResource`, `getResourceLength`, và `openMediaChannel`: Kiểm tra `storage_key` của tài nguyên, gọi `storageKeyConfig.resolvePath(storageKey, relativePath)` để phân giải đường dẫn tuyệt đối và xác thực an toàn tính bao chứa thư mục (Path Containment), ngăn chặn tấn công leo thang thư mục.
  2. **Chính Sách Phát Video Phân Quyền:**
     - Cho phép phát các tài nguyên có `access_policy == "authenticated"` đối với người dùng đã đăng nhập có token hợp lệ.
     - Giới hạn quyền phát tài nguyên có `access_policy == "private"` chỉ dành riêng cho tài khoản quản trị `ROLE_ADMIN`.
  3. **Phiên Bản Động Cho Nhiều Ấn Bản (`syncToLegacyMediaAsset`):**
     - Đặt chuỗi phiên bản duy nhất: `"v1_" + aid`, bảo đảm mọi ấn bản của cùng một tập phim đều có khóa định danh riêng biệt, loại bỏ hoàn toàn lỗi đụng độ ràng buộc duy nhất trên bảng legacy.
     - Lan truyền chính xác trường `storage_key` sang bảng `media_assets`.
- **Bằng chứng xác minh:**
  - Nạp danh mục có nhiều ấn bản video thành công, không phát sinh lỗi CSDL.
  - Đảm bảo an toàn kiểm tra phân giải đường dẫn đối với cả ổ đĩa cục bộ và Drive.

---

#### 6. Finding F6 (P1) — Tuple Định Danh Playback & Vòng Đời Trình Phát Video Vững Chắc
- **Nguyên nhân tại F01:**
  Khi người dùng nhấp vào một cảnh thuộc asset khác, hàm `handleSeekScene` gọi `setSelectedAsset` rồi lập tức gán `currentTime` và `play()` lên phần tử video cũ. Đoạn mã xử lý deep-link sử dụng `setTimeout(300ms)` tùy tiện, không có cơ chế hủy và không có bộ bảo vệ thế hệ, gây ra hiện tượng tua sai thời điểm hoặc giật hình khi người dùng chuyển tập nhanh.
- **Giải pháp triển khai trong F02:**
  1. **Loại Bỏ `setTimeout` Tùy Tiện:**
     - Xóa bỏ toàn bộ các hàm `setTimeout` giả định độ trễ mạng trong `frontend/app/series/[id]/page.tsx`.
  2. **Định Nghĩa Tuple Định Danh Tua Hình (`PendingSeekIdentity`):**
     ```typescript
     interface PendingSeekIdentity {
       seriesId: string;
       episodeId: string;
       assetId: string;
       sceneId: string;
       targetSec: number;
       generation: number;
     }
     ```
  3. **Đồng Bộ Dựa Trên Sự Kiện Sẵn Sàng Của Trình Phát (`onLoadedMetadata`, `onCanPlay`):**
     - Khi chuyển asset, hệ thống chỉ lưu `PendingSeekIdentity` vào trạng thái chờ mà không can thiệp vào trình phát video cũ.
     - Khi trình phát phát ra sự kiện `onLoadedMetadata` hoặc `onCanPlay`, hệ thống đối chiếu chặt chẽ:
       ```typescript
       if (
         pendingSeek.seriesId === currentSeriesId &&
         pendingSeek.episodeId === currentEpisodeId &&
         pendingSeek.assetId === selectedAsset?.id &&
         pendingSeek.generation === episodeGenRef.current
       ) {
         // Thực hiện tua an toàn trong khoảng thời lượng video
         videoRef.current.currentTime = clampedSec;
         setPendingSeek(null);
       }
       ```
  4. **Triệt Tiêu Hoàn Toàn Race Condition Khi Tải Dữ Liệu:**
     - Tích hợp `AbortController` và bộ đếm thế hệ `episodeGenRef` cho cả hai hiệu ứng tải thông tin bộ phim (`series`) và chi tiết tập phim (`episode`).
     - Hủy ngay lập tức các yêu cầu mạng trước đó khi người dùng đổi tập hoặc đổi bộ phim.
- **Bằng chứng xác minh:**
  - `npx tsc --noEmit` đạt 0 lỗi.
  - Giao diện web hiển thị mượt mà, chuyển đổi linh hoạt giữa các ấn bản video và tua chính xác tới từng giây của phân cảnh.

---

#### 7. Finding F7 (P2) — Chuẩn Xác Hóa Trình Xác Thực Contract & Định Dạng Xuất Chuẩn
- **Nguyên nhân tại F01:**
  Trình xác thực `CatalogValidator` thiếu triển khai kiểm tra định dạng ngày tháng (`format: "date"`), URI (`format: "uri"`) và các cận độc quyền (`exclusiveMinimum: 0`). Phương thức xuất catalog `exportSearchableCatalog` tạo header chứa các trường không hợp lệ (`contract_version`, `version`) và thiếu `schema_version`.
- **Giải pháp triển khai trong F02:**
  1. **Bổ Sung Kiểm Tra Định Dạng Nghiêm Ngặt:**
     - `format: "date"`: Sử dụng `DateTimeFormatter.ISO_LOCAL_DATE` kết hợp `ResolverStyle.STRICT`, chặn đứng các ngày không tồn tại như `2026-99-99`.
     - `format: "uri"`: Sử dụng `java.net.URI` yêu cầu có scheme hợp lệ, từ chối các chuỗi không phải URI (`not a uri`).
     - `exclusiveMinimum` / `exclusiveMaximum`: Triển khai kiểm tra cận độc quyền chính xác cho số thực và số nguyên.
     - Triển khai nguyên tắc **Fail-Closed**: Ném ngoại lệ khi tệp schema không tải được từ classpath thay vì bỏ qua bước kiểm tra cấu trúc.
  2. **Chuẩn Hóa Cấu Trúc Xuất Catalog:**
     - Thiết lập thuộc tính gốc: `"schema_version": "dippie.catalog.v1"`.
     - Cấu trúc đối tượng `package` gồm đúng 7 trường chuẩn: `id`, `description`, `created_at`, `revision`, `default_language`, `import_mode`, `reference_scope`.
     - Loại bỏ mọi trường tự chế ngoài hợp đồng.
- **Bằng chứng xác minh:**
  - `python docs/reviews/repro/CATALOG_01_F01_probe.py`: 3/3 ca kiểm tra định dạng và cận số thực khớp chính xác với `validate_catalog.py`.
  - `python docs/reviews/repro/CATALOG_01_F01_logic_probe.py`: Trả về `export_contract_errors: []` (0 lỗi hợp đồng).
  - `python docs/reviews/repro/CATALOG_01_contract_probe.py`: 8/8 kịch bản kiểm thử đạt chuẩn.
  - `CatalogValidatorTest`: 9/9 tests hoàn thành thành công.

---

#### 8. Finding F8 (P2) — Toàn Diện Hóa Manifest, Bản Vá Độc Lập & Bằng Chứng Gate
- **Nguyên nhân tại F01:**
  Bản kê khai `CATALOG_01_F01_MANIFEST.json` chỉ bao gồm 28 tệp, bỏ sót 31 tệp mã nguồn JPA Entity, Repository, DTO và Resource Schema quan trọng.
- **Giải pháp triển khai trong F02:**
  1. **Mở rộng Manifest Lên 66 Tệp (`CATALOG_01_F02_MANIFEST.json`):**
     - Bao trọn toàn bộ 13 JPA Entities, 13 JPA Repositories, 7 DTOs, cấu hình bảo mật, storage config, các controller, services, tài nguyên schema JSON, kịch bản kiểm thử và các trang giao diện frontend.
     - Tính toán mã băm SHA-256 và dung lượng byte chính xác cho từng tệp.
  2. **Tạo Bản Vá Toàn Diện (`CATALOG_01_F02.patch`):**
     - Phản ánh đầy đủ các thay đổi mã nguồn so với baseline commit `c2d29c04edd58c4cc0a6e648d316285a9377384f`.
     - Xác minh tính khả thi áp dụng ngược (Reverse Applicability):
       ```powershell
       git apply --check -R docs/reports/CATALOG_01_F02.patch
       ```
       *Kết quả:* Mã thoát 0 (Exit code 0), xác nhận bản vá hoàn toàn sạch và không bị xung đột.
  3. **Hoàn Thiện Bộ Tài Liệu Nghiệm Thu:**
     - Biên bản đánh giá chéo độc lập: `docs/reports/CATALOG_01_F02_CROSS_REVIEW.md`.
     - Ma trận ánh xạ các trường dữ liệu: `docs/reports/CATALOG_01_F02_FIELD_MAPPING_MATRIX.md`.
     - Sổ tay hướng dẫn vận hành: `docs/runbooks/CATALOG_IMPORT.md`.
     - Tệp trạng thái máy đọc: `docs/reports/CATALOG_01_F02_STATUS.json`.
- **Bằng chứng xác minh:**
  - Lệnh kiểm tra `git apply --check -R` trả về mã 0.
  - 66/66 tệp có mã băm SHA-256 khớp tuyệt đối với dữ liệu thực tế trên đĩa.

---

### IV. HƯỚNG DẪN VẬN HÀNH & TRIỂN KHAI

Để triển khai hệ thống hoạt hình hoạt động hoàn chỉnh, người vận hành thực hiện các bước sau theo runbook `docs/runbooks/CATALOG_IMPORT.md`:

1. **Thiết lập Biến Môi Trường Bảo Mật:**
   ```powershell
   $env:CATALOG_SYNC_TOKEN = "your-secure-internal-sync-token-2026"
   $env:FASTAPI_SYNC_SECRET = "your-secure-internal-sync-token-2026"
   $env:LOCAL_STORAGE_ROOT = "D:\Class\movie-rcm-system\data\storage"
   ```

2. **Khởi Động Dịch Vụ Backend:**
   - **FastAPI AI Engine:**
     ```powershell
     cd D:\Class\movie-rcm-system
     python -m uvicorn backend.fastapi.main:app --host 127.0.0.1 --port 8000
     ```
   - **Spring Boot Core Backend:**
     ```powershell
     cd D:\Class\movie-rcm-system\backend\springboot
     .\mvnw.cmd spring-boot:run
     ```

3. **Khởi Động Giao Diện Web Frontend:**
   ```powershell
   cd D:\Class\movie-rcm-system\frontend
   npm run dev
   ```

4. **Nạp Dữ Liệu Hoạt Hình Qua Giao Diện Admin:**
   - Truy cập `http://localhost:3000/admin/import`.
   - Chọn tệp JSON đạt chuẩn `dippie.catalog.v1`.
   - Nhấn **Validate & Preview** để kiểm tra tính hợp lệ và xem trước diff (`toCreate`, `toUpdate`, `unchanged`, `conflicts`).
   - Nhấn **Import Package** để lưu vào cơ sở dữ liệu. Background Outbox Worker sẽ tự động đồng bộ sang FastAPI và cập nhật chỉ mục tìm kiếm AI.

---

### V. KẾT LUẬN NGHIỆM THU

Hệ thống đã hoàn thành 100% các yêu cầu của nhiệm vụ **CATALOG-01-F02**:
- Tất cả 8/8 findings (F1–F8) đã được giải quyết triệt để và chứng minh qua các probe kiểm thử độc lập.
- Contract `dippie.catalog.v1` được bảo toàn nguyên vẹn.
- Snapshot vận hành đạt trạng thái sẵn sàng cao nhất, đáp ứng đầy đủ tiêu chuẩn bảo mật, tính toàn vẹn giao dịch và trải nghiệm người dùng.
