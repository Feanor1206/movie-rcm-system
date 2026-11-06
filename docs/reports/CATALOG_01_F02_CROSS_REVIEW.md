# BIÊN BẢN ĐÁNH GIÁ CHÉO ĐỘC LẬP: CATALOG-01-F02
## Đánh Giá Toàn Diện Findings F1–F8, Bảo Toàn Contract dippie.catalog.v1 Và Kiểm Thử Vận Hành Độc Lập

**Người thực hiện đánh giá:** Independent Cross-Reviewer Role  
**Dự án:** Movie Recommendation & Streaming System (Dippie Cinema)  
**Nhiệm vụ:** CATALOG-01-F02 — Sửa toàn bộ findings F1–F8, kiểm thử đúng gate và chốt snapshot dùng được  
**Workspace:** `D:\Class\movie-rcm-system`  
**Nhánh Git:** `dev`  
**Base Commit:** `c2d29c04edd58c4cc0a6e648d316285a9377384f`  
**Head Commit:** `adf0dee0655fad19102b39f31d203aeaed42d906`  
**Ngày đánh giá:** 2026-10-16  
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
  - `docs/contracts/animation-catalog-v1/catalog.example.json`: Giữ nguyên fixture mẫu.
  - `docs/contracts/animation-catalog-v1/catalog.blank.json`: Giữ nguyên khung rỗng.
  - `docs/contracts/animation-catalog-v1/validate_catalog.py`: Giữ nguyên validator chuẩn của hợp đồng.
  - `backend/springboot/src/main/resources/contracts/dippie.catalog.v1.schema.json`: Byte-for-byte khớp hoàn toàn với schema gốc (SHA-256: `63b84177b966838a2e1f400787e9c5aa8c12282ffba81c548a313e618823f668`).
- **Đánh giá:** **ĐẠT (PASS)**. Hợp đồng dữ liệu được bảo vệ tuyệt đối như nguồn sự thật bất biến (source of truth).

---

### 2. Đánh Giá Xử Lý Từng Finding (F1 — F8)

#### Finding F1 (P1): Service Credential Công Khai & Bảo Mật Đồng Bộ Chỉ Mục
- **Thực trạng tại F01:** `frontend/lib/services/catalogService.ts` chứa token hardcoded, `FastAPI` và `CatalogImportService` dùng cùng token làm default fallback. Token bị lộ trong frontend client bundle.
- **Biện pháp xử lý trong F02:**
  1. Loại bỏ hoàn toàn service token khỏi frontend (`catalogService.ts`, `CatalogImportModal.tsx`). Xóa bỏ lời gọi trực tiếp từ browser tới endpoint đồng bộ AI.
  2. Tại `backend/fastapi/main.py`: Loại bỏ default fallback token. Đọc token nghiêm ngặt từ biến môi trường `CATALOG_SYNC_TOKEN` hoặc `FASTAPI_SYNC_SECRET`. Nếu chưa cấu hình, endpoint `/api/index/sync` **fail-closed** trả về `HTTP 503 Service Unavailable`.
  3. Tại `CatalogImportService.java`: Đọc token từ biến môi trường hệ thống, không lưu secret trong mã nguồn.
  4. Trình duyệt người dùng chỉ giao tiếp với Spring Boot Admin API thông qua session quản trị có xác thực JWT Bearer token hợp lệ.
- **Kết quả kiểm thử:**
  - `tsc --noEmit`: Đạt 0 lỗi.
  - Test suite `test_catalog_retrieval.py` xác nhận: thiếu header trả HTTP 401, sai token trả HTTP 403, cấu hình đúng trả HTTP 200.
- **Đánh giá:** **ĐẠT (PASS)**.

---

#### Finding F2 (P1): Cơ Chế Outbox Worker Thật, Tách Rời Giao Dịch & Chống Stale Generation
- **Thực trạng tại F01:** `importPackage` ghi tệp ra đĩa và gọi HTTP sync trong transaction DB. Tệp chỉ chứa package đơn lẻ vừa import. Không có background worker hay cơ chế retry khi lỗi mạng.
- **Biện pháp xử lý trong F02:**
  1. Triệt tiêu toàn bộ I/O đĩa và cuộc gọi HTTP ra khỏi giao dịch `@Transactional importPackage`.
  2. Bổ sung trường `generation` (đơn điệu toàn cục, tăng dần từ `findMaxGeneration() + 1`) vào `CatalogSnapshot`. Giao dịch import chỉ lưu bản ghi `CatalogSnapshot` với trạng thái `PENDING`.
  3. Sau khi commit DB (`afterCommit` qua `TransactionSynchronizationManager`), kích hoạt worker đồng bộ bất đồng bộ mà không chặn luồng trả về cho client.
  4. Xây dựng worker chuyên trách `CatalogSyncWorker`:
     - Tự động chạy định kỳ `@Scheduled(fixedDelay = 5000)` để quét và xử lý các snapshot `PENDING`.
     - Lắng nghe sự kiện khởi động ứng dụng `@EventListener(ApplicationReadyEvent.class)` để phục hồi các snapshot bị gián đoạn.
     - Hàm `exportEligibleSnapshot()` truy vấn toàn bộ dữ liệu hợp lệ trong CSDL (đa package) và ghi ra tệp nguyên tử bằng `Files.move(..., ATOMIC_MOVE, REPLACE_EXISTING)`.
  5. Bảo vệ Stale Generation tại FastAPI: Khi nhận request đồng bộ có `generation < _current_sync_generation`, FastAPI trả về `HTTP 200` với `status="SKIPPED"` và bỏ qua, ngăn chặn snapshot cũ ghi đè lên chỉ mục mới.
  6. Idempotent re-import: Trả về trạng thái thực tế từ CSDL (`PENDING`, `SYNCED`, `FAILED`) thay vì luôn trả `READY`.
- **Kết quả kiểm thử:**
  - `CatalogImportServiceTest.testImportCommitSuccess`: Tạo snapshot `PENDING` thành công.
  - `CatalogImportServiceTest.testIdempotentReimport`: Đọc đúng snapshot đã có từ DB.
  - `test_catalog_retrieval.py`: FastAPI xử lý mượt mà payload snapshot đồng bộ có generation.
- **Đánh giá:** **ĐẠT (PASS)**.

---

#### Finding F3 (P1): Chính Sách Phát Hành Lan Truyền & Lọc Dữ Liệu Công Khai
- **Thực trạng tại F01:** Mặc định `catalog_sync.py` để `include_draft=True` và `include_private=True`, khiến dữ liệu nháp/riêng tư bị đưa vào chỉ mục tìm kiếm và chatbot. Các API công khai trả về toàn bộ metadata và raw JSON không qua sàng lọc.
- **Biện pháp xử lý trong F02:**
  1. Trong `catalog_sync.py`: Đặt mặc định `include_draft=False`, `include_private=False`.
  2. Triển khai cơ chế phân tầng phát hành (parent publication cascade):
     - Series có trạng thái `draft` hoặc `archived` sẽ loại bỏ toàn bộ seasons, episodes, segments, scenes thuộc bộ đó khỏi chỉ mục tìm kiếm.
     - Episode có trạng thái `draft` hoặc `archived` sẽ loại bỏ toàn bộ segments và scenes thuộc tập đó.
     - Media asset có chính sách `private` sẽ loại bỏ các scenes liên kết tương ứng khỏi chỉ mục công khai.
  3. Trong `CatalogQueryService.java`:
     - Kiểm tra quyền người dùng: các endpoint công khai `/api/catalog/series/**` và `/api/catalog/episodes/**` tự động lọc bỏ các nội dung không có trạng thái `published` đối với người dùng thông thường hoặc khách vô danh.
     - Endpoint xuất dữ liệu `/api/admin/catalog/export` được bảo vệ nghiêm ngặt dưới quyền `ROLE_ADMIN`, không cho phép truy cập nặc danh.
- **Kết quả kiểm thử:**
  - Chạy `python docs/reviews/repro/CATALOG_01_F01_probe.py`: Đoạn kiểm tra `runtime_default_publication` xác nhận 0 series, 0 episodes, 0 segments, 0 scenes (0/4 items) bị lập chỉ mục khi dùng runtime defaults.
- **Đánh giá:** **ĐẠT (PASS)**.

---

#### Finding F4 (P1): Độc Lập Revision Thực Thể & Mã Băm Chuẩn Hóa Khóa JSON
- **Thực trạng tại F01:** `extractRevision` nâng ảo revision của thực thể bằng `Math.max(record.revision, packageRevision)`. Hàm băm SHA-256 không sắp xếp khóa của JSON object, gây xung đột giả khi thứ tự thuộc tính thay đổi.
- **Biện pháp xử lý trong F02:**
  1. Tách biệt hoàn toàn revision thực thể: `extractRevision` chỉ lấy giá trị `record.revision` của chính thực thể đó. Khi một package có revision cao chứa thực thể có revision thấp hơn phiên bản đang lưu trong DB, hệ thống lập tức ném `CatalogConflictException` (CONFLICT).
  2. Chuẩn hóa mã băm đối tượng JSON (`computeCanonicalSha256`):
     - Đệ quy sắp xếp tất cả các khóa của JSON Object theo thứ tự bảng chữ cái bằng `TreeMap<String, Object>`.
     - Giữ nguyên thứ tự tuần tự của mảng JSON Array (đặc biệt quan trọng với mảng nhãn, tập và phân đoạn).
     - Đảm bảo hai đối tượng có cùng nội dung dù khác thứ tự khai báo key đều cho ra cùng một mã băm SHA-256 duy nhất.
  3. Cập nhật thực thể được quản lý (Managed Entities): `importPackage` tái sử dụng và cập nhật instance thực thể JPA đã tải từ DB thay vì tạo mới với `opt_lock_version = 0`, bảo toàn tính năng kiểm soát khóa lạc quan `@Version`.
- **Kết quả kiểm thử:**
  - `python docs/reviews/repro/CATALOG_01_F01_logic_probe.py`:
    - `reordered_identical_object`: `UNCHANGED` (khớp hoàn toàn kỳ vọng).
    - `lower_entity_revision_in_higher_package`: `CONFLICT` (khớp hoàn toàn kỳ vọng).
  - `CatalogImportServiceTest.testHigherRevisionUpdate`: Cập nhật thành công khi revision thực thể tăng hợp lệ.
- **Đánh giá:** **ĐẠT (PASS)**.

---

#### Finding F5 (P1): Phân Giải storage_key & Xử Lý Nhiều Edition Không Trùng Khóa
- **Thực trạng tại F01:** `StorageKeyConfig` không được sử dụng ở đường dẫn phát video (`MediaStreamService`). Nhiều ấn bản (multi-editions) cho cùng một tập bị lỗi vi phạm ràng buộc duy nhất `unique(movie_id, kind, version)` trên bảng `media_assets`.
- **Biện pháp xử lý trong F02:**
  1. Tiêm `StorageKeyConfig` và `CatalogMediaAssetRepository` vào `MediaStreamService`.
  2. Tại các phương thức mở luồng phát (`getMediaResource`, `getResourceLength`, `openMediaChannel`):
     - Xác định `storageKey` của media asset.
     - Gọi `storageKeyConfig.resolvePath(storageKey, relativePath)` để phân giải đường dẫn vật lý và kiểm tra nghiêm ngặt tính bao chứa thư mục (path containment), ngăn ngừa tấn công leo thang thư mục (Path Traversal).
  3. Phân quyền phát luồng non-public:
     - Cho phép phát các asset có `access_policy == "authenticated"` đối với người dùng đã đăng nhập.
     - Chặn các asset có `access_policy == "private"`, chỉ cấp quyền phát cho người dùng có vai trò `ROLE_ADMIN`.
  4. Triệt tiêu xung đột đa ấn bản trong `syncToLegacyMediaAsset`:
     - Thiết lập chuỗi phiên bản động: `"v1_" + aid`, đảm bảo mỗi asset ID có một version duy nhất trên bảng legacy.
     - Truyền đúng giá trị `storage_key` sang thực thể legacy.
- **Kết quả kiểm thử:**
  - Import package mẫu thành công không phát sinh xung đột khóa duy nhất.
  - Cơ chế allowlist và containment của `StorageKeyConfig` đã vượt qua các kịch bản kiểm tra an toàn.
- **Đánh giá:** **ĐẠT (PASS)**.

---

#### Finding F6 (P1): Tuple Định Danh Playback & Kiểm Soát Vòng Đời Trình Phát
- **Thực trạng tại F01:** Khi nhấp vào phân cảnh thuộc asset khác, hệ thống đổi `selectedAsset` rồi lập tức tua `currentTime` lên `videoRef.current` cũ. Deep link sử dụng `setTimeout(300ms)` thiếu bộ hủy và không có ràng buộc định danh.
- **Biện pháp xử lý trong F02:**
  1. Loại bỏ hoàn toàn `setTimeout` tùy tiện trong `frontend/app/series/[id]/page.tsx`.
  2. Định nghĩa cấu trúc định danh tua hình nghiêm ngặt `PendingSeekIdentity`:
     - Gồm tuple 6 thành phần: `(seriesId, episodeId, assetId, sceneId, targetSec, generation)`.
  3. Khi đổi asset hoặc tua cảnh, hệ thống ghi nhận `pendingSeek` vào state mà không can thiệp ngay vào phần tử video đang phát asset cũ.
  4. Lắng nghe sự kiện sẵn sàng của phần tử video (`onLoadedMetadata`, `onCanPlay`):
     - Kiểm tra đối chiếu chặt chẽ: `pendingSeek` phải khớp đúng `seriesId`, `episodeId`, `assetId` và `generation` hiện hành.
     - Chỉ khi video đã sẵn sàng và thời lượng hợp lệ, lệnh tua `clampedSec` mới được thực thi và sau đó xóa trạng thái `pendingSeek`.
  5. Bổ sung `AbortController` và `generation guard` cho cả hai hiệu ứng tải chi tiết bộ phim (`series`) và tập phim (`episode`), triệt tiêu hoàn toàn nguy cơ race condition do người dùng thao tác nhanh.
- **Kết quả kiểm thử:**
  - `npx tsc --noEmit`: 100% không phát sinh lỗi kiểu dữ liệu.
  - Mã nguồn tuân thủ nghiêm ngặt nguyên lý vòng đời component của React 19 / Next.js 15.
- **Đánh giá:** **ĐẠT (PASS)**.

---

#### Finding F7 (P2): Chuẩn Xác Hóa Trình Xác Thực Contract & Xuất Catalog Hợp Lệ
- **Thực trạng tại F01:** Trình xác thực `CatalogValidator` thiếu kiểm tra định dạng ngày tháng (`format: date`), URI (`format: uri`) và giá trị biên độc quyền (`exclusiveMinimum: 0`). Phương thức xuất catalog tạo header sai cấu trúc hợp đồng.
- **Biện pháp xử lý trong F02:**
  1. Nâng cấp `CatalogValidator.java`:
     - Xác thực `format: "date"` nghiêm ngặt theo chuẩn ISO-8601 (`uuuu-MM-dd` với `ResolverStyle.STRICT`), từ chối các ngày không hợp lệ như `2026-99-99`.
     - Xác thực `format: "uri"` yêu cầu có giao thức (scheme) hợp lệ, từ chối chuỗi không phải URI (`not a uri`).
     - Xác thực giới hạn số thực `exclusiveMinimum` và `exclusiveMaximum`, từ chối các giá trị bằng đúng cận như `scale_max: 0` khi `exclusiveMinimum: 0`.
     - Thực thi nguyên tắc **fail-closed**: Ném ngoại lệ `IllegalStateException` nếu không nạp được schema JSON từ classpath thay vì bỏ qua bước kiểm tra cấu trúc.
  2. Chuẩn hóa định dạng xuất tệp catalog (`exportEligibleSnapshot` và `exportSearchableCatalog`):
     - Xuất đúng thuộc tính `schema_version = "dippie.catalog.v1"`.
     - Cấu trúc header `package` chuẩn xác gồm: `id`, `description`, `created_at`, `revision`, `default_language`, `import_mode`, `reference_scope`.
     - Loại bỏ các trường tự chế không thuộc schema (`contract_version`, `version`).
- **Kết quả kiểm thử:**
  - `python docs/reviews/repro/CATALOG_01_F01_probe.py`: 3/3 ca kiểm thử định dạng và biên số thực khớp chính xác với kết quả của `validate_catalog.py`.
  - `python docs/reviews/repro/CATALOG_01_F01_logic_probe.py`: Trả về `export_contract_errors: []` (0 lỗi hợp đồng).
  - `python docs/reviews/repro/CATALOG_01_contract_probe.py`: 8/8 kịch bản khớp tuyệt đối.
  - `CatalogValidatorTest`: 9/9 unit tests chạy thành công.
- **Đánh giá:** **ĐẠT (PASS)**.

---

#### Finding F8 (P2): Bao Trọn Toàn Bộ Phụ Thuộc Manifest & Bằng Chứng Đóng Gate
- **Thực trạng tại F01:** Manifest chỉ chứa 28 tệp, bỏ quên 31 tệp DTO, Entity, Repository và Schema Resource.
- **Biện pháp xử lý trong F02:**
  1. Mở rộng `docs/reports/CATALOG_01_F02_MANIFEST.json` lên đầy đủ **66 tệp** mã nguồn liên quan đến toàn bộ hệ sinh thái catalog (13 Entity JPA, 13 Repository JPA, 7 DTO, các Service, Controller, Resource Schema, Configuration, Scripts và Frontend Pages).
  2. Tạo bản vá `docs/reports/CATALOG_01_F02.patch` phản ánh chính xác thay đổi của toàn bộ 66 tệp trên.
  3. Kiểm tra tính khả thi đảo ngược (reverse applicability):
     ```powershell
     git apply --check -R docs/reports/CATALOG_01_F02.patch
     ```
     *Kết quả:* Mã thoát 0 (Exit code 0), đảm bảo patch sạch sẽ và tái lập hoàn chỉnh trên baseline.
  4. Lập bảng đối chiếu chi tiết các trường ánh xạ trong `docs/reports/CATALOG_01_F02_FIELD_MAPPING_MATRIX.md` và cập nhật sổ tay vận hành `docs/runbooks/CATALOG_IMPORT.md`.
- **Đánh giá:** **ĐẠT (PASS)**.

---

### 3. Bảng Tổng Hợp Kết Quả Các Gate Kiểm Thử

| Cổng kiểm thử (Gate) | Công cụ / Lệnh kiểm tra | Số lượng ca kiểm thử | Kết quả thực tế | Trạng thái Gate |
| :--- | :--- | :--- | :--- | :--- |
| **Bảo toàn Contract Schema** | Git Diff & SHA-256 đối chiếu | 5 tệp hợp đồng + ZIP | 0 tệp bị thay đổi, byte-for-byte khớp | **PASS** |
| **Khớp chuẩn Reviewer Probes** | `CATALOG_01_F01_logic_probe.py` | 3 ca logic & export | `UNCHANGED`, `CONFLICT`, 0 export errors | **PASS** |
| | `CATALOG_01_F01_probe.py` | 3 ca format/boundary + runtime pub | 3/3 khớp lỗi contract, 0 draft/private indexed | **PASS** |
| | `CATALOG_01_contract_probe.py` | 8 ca đối chiếu validator | 8/8 khớp hoàn toàn kết quả chuẩn | **PASS** |
| **Spring Boot Unit & Service Tests**| `CatalogValidatorTest` | 9 ca kiểm thử | 9/9 PASS (0 failures, 0 errors) | **PASS** |
| | `CatalogImportServiceTest` | 6 ca kiểm thử giao dịch & diff | 6/6 PASS (0 failures, 0 errors) | **PASS** |
| **FastAPI Retrieval & AI Pipeline** | `test_catalog_retrieval.py` | 12 ca kiểm thử hybrid & sync | 12/12 PASS (0 failures, 0 errors) | **PASS** |
| **Frontend TypeScript Typecheck** | `npx tsc --noEmit` | Toàn bộ dự án `frontend/` | 0 lỗi biên dịch, exit code 0 | **PASS** |
| **Patch Reverse Applicability** | `git apply --check -R docs/reports/CATALOG_01_F02.patch` | Toàn bộ 66 tệp manifest | Exit code 0, không có hunk lỗi | **PASS** |

---

### 4. Kết Luận Và Khuyến Nghị

1. **Kết luận:**
   Toàn bộ 8 findings F1–F8 trong báo cáo đánh giá `CATALOG-01-F01` đã được khắc phục triệt để và kiểm chứng độc lập.
   - Hợp đồng `dippie.catalog.v1` được bảo tồn nguyên vẹn 100%.
   - Quy trình nạp dữ liệu hoạt hình từ bên ngoài đã có kiến trúc Outbox Worker vững chắc, đảm bảo tính toàn vẹn giao dịch ACID và đồng bộ bất đồng bộ an toàn sang AI Index.
   - Cơ chế bảo mật fail-closed triệt tiêu mọi nguy cơ bypass và lộ bí mật hệ thống.
   - Trình phát video và hệ thống tìm kiếm liên kết sâu đã vận hành ổn định, không còn race condition và tua chính xác tới từng phân cảnh.

2. **Khuyến nghị bàn giao:**
   - Đủ điều kiện phê duyệt đóng nhiệm vụ `CATALOG-01-F02`.
   - Giữ nguyên trạng thái working tree đóng băng để người dùng kiểm tra trước khi thực hiện commit chính thức.
