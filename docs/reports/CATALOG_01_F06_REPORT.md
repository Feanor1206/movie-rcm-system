# BÁO CÁO NGHIỆM THU TOÀN DIỆN: CATALOG-01-F06
## CHỐT SNAPSHOT SẢN PHẨM DÙNG ĐƯỢC TOÀN LUỒNG (END-TO-END PRODUCT READINESS)

- **Định danh Snapshot Checkpoint:** `CATALOG-01-F06-CHECKPOINT-01`
- **Thời điểm nghiệm thu:** 2026-10-17T13:41:00+07:00
- **Workspace:** `d:\Class\movie-rcm-system` | **Branch:** `dev`
- **Baseline Git Commit:** `d620bfc634b3c424a847408f0dc6e02626439f45`
- **Trạng thái Gate tổng thể:** **100% PASSED (TẤT CẢ CÁC CỔNG ĐÃ THÔNG QUA VÀ ĐƯỢC CHỨNG THỰC)**

---

## 1. TỔNG QUAN KẾT QUẢ & NĂNG LỰC SẢN PHẨM THỰC TẾ

Phiên bản `CATALOG-01-F06` là cột mốc hoàn thiện trọn vẹn sản phẩm **Dippie Cinema**, xóa bỏ hoàn toàn khoảng cách giữa "code vượt qua unit test" và "hệ thống vận hành được trong thực tế". Toàn bộ luồng nghiệp vụ 7 bước:
```
Đăng nhập quản trị (Admin Login)
  → Nhập catalog JSON chuẩn dippie.catalog.v1 (/admin/import)
  → Kiểm tra tính hợp lệ & Xem trước khác biệt (Validate & Preview)
  → Ghi dữ liệu bền vững nguyên tử vào 12 bảng thực thể (Atomic DB Commit)
  → Outbox Worker đồng bộ sang FastAPI qua HTTP thật (/api/index/sync)
  → Chỉ mục AI & Hybrid Index đạt trạng thái READY với đúng thế hệ (Generation) & Hash
  → Tìm kiếm nội dung đa cấp độ (Bộ / Tập / Truyện ngắn / Phân cảnh) & Chatbot CineBot
  → Phát video đúng quyền bảo mật (Public / Protected via Playback Grant) & Tua chính xác mốc thời gian
  → Khởi động lại dịch vụ (Restart) → Toàn bộ dữ liệu và chỉ mục tự động phục hồi hoàn chỉnh.
```
đã được **diễn tập tự động thành công 100% trên stack dịch vụ thật (Live Production Stack)** thông qua script diễn tập độc lập `scripts/rehearsal_f06_production_stack.py` (bằng chứng lưu tại `docs/reviews/evidence/CATALOG_01_F06_rehearsal.json`).

---

## 2. NGUYÊN NHÂN GỐC RỄ (ROOT CAUSE) & GIẢI PHÁP ĐÓNG DỨT ĐIỂM S1 – S3

### Finding S1: Thiếu Tính Nguyên Tử (Atomicity) và Nguy Cơ Ô Nhiễm Trạng Thái Khi Build Index Lỗi
- **Nguyên nhân gốc rễ:** 
  Trong hàm `sync_index` (`backend/fastapi/main.py`), việc ghi đĩa tệp trạng thái `catalog_sync_state.json` và cập nhật từ điển `active_catalog` được thực hiện **trước** hoặc **không có cơ chế rollback** nếu quá trình xây dựng chỉ mục ứng viên `active_index.build_from_catalog(...)` gặp ngoại lệ. Nếu quá trình vector hóa hoặc nạp metadata thất bại giữa chừng, trạng thái trên đĩa đã ghi nhận thế hệ mới, khiến FastAPI sau khi restart sẽ nạp một catalog bị hỏng hoặc không đồng bộ với chỉ mục bộ nhớ. Ngoài ra, đường dẫn tệp trạng thái bị hardcode, bỏ qua biến môi trường `SYNC_STATE_PATH`.
- **Giải pháp xử lý triệt để:**
  1. **Candidate Index Isolation:** Tạo và hoàn thiện đối tượng index ứng viên trước khi hoán đổi con trỏ.
  2. **Rollback Guard on Error:** Lưu lại trạng thái tiêu đề và thế hệ cũ (`prev_titles`, `prev_gen`, `prev_hash`). Nếu quá trình `build_from_catalog` phát sinh ngoại lệ, lập tức khôi phục lại chỉ mục cũ và ném lỗi HTTP 500 kèm thông báo rõ ràng, không làm thay đổi trạng thái đang phục vụ.
  3. **Atomic Disk Write on Success Only:** Chỉ khi candidate index build thành công 100% mới gọi hàm `_save_sync_state(generation, content_hash, ...)` ghi nguyên tử ra đĩa qua tệp tạm `.tmp` rồi hoán đổi (`os.replace`).
  4. **Dynamic State Path:** Hỗ trợ biến môi trường `SYNC_STATE_PATH = Path(os.environ.get("SYNC_STATE_PATH", ...))` cho phép các môi trường test và rehearsal chạy hoàn toàn cách ly.
  5. **Warm Startup Indexing:** Bổ sung bước tự động dựng lại `hybrid_index` từ `_loaded_cat` ngay khi FastAPI khởi động lại, giúp chỉ mục sẵn sàng phục vụ truy vấn ngay lập tức mà không phải chờ truy vấn đầu tiên.
- **Xác thực:**
  - `python docs/reviews/repro/CATALOG_01_F05_independent_probe.py`: **100% PASS** (Test rollback khi build lỗi, thế hệ và titles cũ được bảo toàn nguyên vẹn).
  - `python docs/reviews/repro/CATALOG_01_F04_independent_probe.py`: **100% PASS** (Test CAS generation, hash match, index query consistency).

---

### Finding S2: Sai Lệch Cấu Hình Vận Hành Thực Tế & Lỗ Hổng Xác Thực
- **Nguyên nhân gốc rễ:**
  1. Cấu hình token đồng bộ giữa Spring Boot (`application.yml`) và FastAPI (`.env.example`) chưa có giá trị fallback đồng nhất (`CATALOG_SYNC_TOKEN` vs `FASTAPI_SYNC_SECRET`).
  2. Spring Boot `DataInitializer` khởi tạo sẵn danh sách 50 người dùng thử nghiệm nhưng trùng lặp username `admin` và `user`, dẫn đến lỗi `DataIntegrityViolationException: Unique index or primary key violation` khi bật chế độ seed.
  3. Quản trị viên không có tài khoản chuẩn được ghi rõ trong tài liệu với mật khẩu nhất quán.
  4. Các hàm gọi API catalog trong `frontend/lib/services/catalogService.ts` (`fetchSeriesList`, `fetchSeriesDetail`, `fetchEpisodeDetail`) không tự động đính kèm `Authorization: Bearer <token>`, khiến người dùng đã đăng nhập hoặc các endpoint yêu cầu quyền bị từ chối nếu không truyền token thủ công.
  5. Thiếu tệp fixture dữ liệu sản xuất chuẩn có liên kết trực tiếp với các tệp video mẫu có sẵn trong thư mục `media/`.
- **Giải pháp xử lý triệt để:**
  1. **Spring Boot Config:** Ràng buộc `app.catalog.sync-token: ${CATALOG_SYNC_TOKEN:${FASTAPI_SYNC_SECRET:}}` và bổ sung cấu hình timeout `sync-timeout-seconds: ${APP_CATALOG_SYNC_TIMEOUT_SECONDS:60}` (cho phép FastAPI khởi tạo trọng số mô hình E5 trong lần đồng bộ đầu tiên mà không bị timeout HTTP).
  2. **DataInitializer Fix:** Bổ sung điều kiện kiểm tra tồn tại `if (!userRepository.existsByUsername(u[0]))` trước khi thêm vào danh sách seed, đồng thời bootstrap tài khoản chuẩn:
     - `admin` / `admin@dippie.com` (Mật khẩu: `password123`, Quyền: `ROLE_ADMIN`).
     - `user` / `user@dippie.com` (Mật khẩu: `password123`, Quyền: `ROLE_USER`).
  3. **Frontend Auth Propagation:** Tiêm tự động `...getAuthHeader()` vào tất cả các yêu cầu trong `catalogService.ts`.
  4. **Rehearsal Production Fixture:** Xây dựng tệp fixture hoàn chỉnh tại `docs/fixtures/rehearsal_catalog.json` tuân thủ 100% JSON Schema Draft 2020-12, bao gồm:
     - 2 series, 2 seasons, 3 episodes, 1 segment, 3 characters.
     - 3 media assets (`asset_feature_01`, `asset_feature_02`, `asset_trailer_01`) trỏ đúng vào các file video thực tế `media/synthetic/feature_test.mp4` và `media/synthetic/trailer_test.mp4`.
     - 1 scene có mốc thời gian bắt đầu 15,000ms trên coverage bắt đầu tại 10,000ms.
- **Xác thực:**
  - `python docs/contracts/animation-catalog-v1/validate_catalog.py docs/fixtures/rehearsal_catalog.json`: **VALID**.
  - `mvnw test -Dtest=SeedAndConfigPolicyTest`: **PASS**.

---

### Finding S3: Thiếu Quy Trình Diễn Tập Toàn Stack Dịch Vụ Thật (Real Production-Stack Rehearsal)
- **Nguyên nhân gốc rễ:**
  Trước F06, các lượt kiểm thử chủ yếu dựa trên các test giả lập hoặc mock trong tiến trình đơn lẻ, chưa có kịch bản khởi động độc lập cả 2 tiến trình Spring Boot và FastAPI trên cổng mạng thật, thực hiện HTTP request thực tế qua tường lửa mạng nội bộ, commit DB thật, ghi file đĩa thật và restart tiến trình thật.
- **Giải pháp xử lý triệt để:**
  Phát triển bộ diễn tập tự động toàn diện `scripts/rehearsal_f06_production_stack.py` thực thi quy trình 10 bước độc lập trên cổng cách ly (FastAPI: 8008, Spring Boot: 8088) với cơ sở dữ liệu và thư mục trạng thái tạm biệt lập.
- **Kết quả diễn tập:**
  **TẤT CẢ 10 BƯỚC ĐÃ VƯỢT QUA 100%:**
  1. Khởi động FastAPI trên cổng 8008 -> Health Check 200 OK.
  2. Khởi động Spring Boot trên cổng 8088 -> Health Check 200 OK.
  3. Đăng nhập Admin (`admin@dippie.com` / `password123`) -> Cấp JWT thành công.
  4. Validate Catalog Package -> Trả về 200 OK, `valid: true`, 0 lỗi.
  5. Import Catalog Package -> Commit DB thành công, khởi tạo outbox snapshot.
  6. Outbox Sync Worker HTTP Ack -> Outbox đạt trạng thái `READY`, thế hệ 1, hash khớp, snapshot JSON lưu ra đĩa (22,369 bytes).
  7. Tìm kiếm & Khám phá Catalog:
     - Spring Boot trả về 2 series hợp lệ.
     - Keyword search khớp "Biên Niên Sử Thần Tốc".
     - FastAPI `/v1/discover` trả về 3 kết quả liên quan.
  8. Ma trận Bảo Mật Stream Media:
     - Stream tài nguyên công khai: 200 OK (137,961 bytes).
     - Truy cập tài nguyên bảo vệ ẩn danh: Bị chặn (HTTP 404 Fail-closed).
     - Admin xin cấp Playback Grant token: Thành công.
     - Stream tài nguyên bảo vệ kèm Grant token: 200 OK (137,961 bytes).
     - **Gate R1:** Sử dụng Grant token làm Bearer token vào API quản trị -> Bị từ chối (HTTP 401/403).
     - **Gate R2:** Sử dụng Grant token cho media asset khác -> Bị từ chối (HTTP 404).
  9. Tua Mốc Thời Gian & Phân Cảnh (Seek & Range Request):
     - Mốc logic scene 15,000ms -> Mốc file gốc tính toán chính xác 25,000ms (25.0s).
     - Yêu cầu HTTP Range `bytes=10000-20000`: Trả về chuẩn `HTTP 206 Partial Content` (10,001 bytes).
  10. Phục Hồi Sau Khởi Động Lại (Restart Recovery):
     - Dừng tiến trình FastAPI.
     - Khởi động lại FastAPI trỏ vào thư mục trạng thái đã lưu.
     - FastAPI phục hồi thế hệ 1 và trả về kết quả tìm kiếm ngay lập tức.
     - Spring Boot tiếp tục stream video bình thường: 200 OK.
  - Bằng chứng lưu tại: `docs/reviews/evidence/CATALOG_01_F06_rehearsal.json`.

---

## 3. BẢNG MAPPING TOÀN BỘ FINDINGS TỪ REVIEW F01 ĐẾN F06

| Mã Finding | Đợt Review | Mô tả Vấn đề | Trạng thái | Cơ chế Khóa Lỗi & File Xử lý |
| :--- | :--- | :--- | :---: | :--- |
| **S1** | F05 Review | Thiếu atomic index build và rollback khi build lỗi tại FastAPI; hardcode đường dẫn trạng thái | **CLOSED** | `main.py`: Candidate isolation, rollback guard khôi phục state, `SYNC_STATE_PATH` env binding, restart index warmup. |
| **S2** | F05 Review | Cấu hình token đồng bộ không đồng nhất, seed user bị trùng lặp, frontend thiếu auth header | **CLOSED** | `application.yml`, `DataInitializer.java`, `catalogService.ts`, `docs/fixtures/rehearsal_catalog.json`. |
| **S3** | F05 Review | Thiếu rehearsal trên production stack thật với live services | **CLOSED** | `scripts/rehearsal_f06_production_stack.py`, `docs/reviews/evidence/CATALOG_01_F06_rehearsal.json`. |
| **R1** | F04 Review | Playback grant token bị lợi dụng làm Bearer token đăng nhập API quản trị | **CLOSED** | `JwtAuthenticationFilter.java`: Chặn hoàn toàn token có type `playback_grant` tại bộ lọc Bearer. |
| **R2** | F04 Review | Playback grant không bị ràng buộc với định danh media asset | **CLOSED** | `JwtUtils.java` & `MediaStreamController.java`: Kiểm tra claim `assetId` bắt buộc phải khớp với URL path. |
| **R3** | F04 Review | Tài nguyên bảo vệ trả về 401 thay vì 404 làm lộ cấu trúc tài nguyên nội bộ | **CLOSED** | `MediaStreamController.java`: Áp dụng chính sách Fail-Closed, trả về 404 Not Found cho mọi truy cập không hợp lệ. |
| **R4** | F04 Review | Nguy cơ tấn công duyệt thư mục (Path Traversal) qua `storage_key` | **CLOSED** | `DriveMediaStorageAdapter.java`: Kiểm tra path containment nghiêm ngặt, chuẩn hóa đường dẫn và chặn `..`. |
| **R5** | F04 Review | Lệch định dạng số nguyên và số thực trong tính mã băm content hash | **CLOSED** | `CatalogImportService.java`: Chuẩn hóa số nguyên thành `Long` và số thực thành chuỗi thập phân đồng nhất. |
| **R6** | F04 Review | Trạng thái Outbox bị kẹt ở `SYNCING` vĩnh viễn khi ứng dụng bị tắt đột ngột | **CLOSED** | `CatalogSyncWorker.java`: Tự động phục hồi snapshot `SYNCING` dở dang về `PENDING` khi ứng dụng khởi động lại. |
| **H1–H5** | F03 Review | Race condition khi tua video; HTTP Range không chuẩn; đồng bộ snapshot qua bộ nhớ giả | **CLOSED** | `series/[id]/page.tsx` (PendingSeekIdentity), `MediaStreamService.java` (HTTP 206), `CatalogSyncWorker.java` (HTTP sync). |
| **G1–G6** | F02 Review | Thiếu giao diện quản trị import; thiếu tính nguyên tử database; mất quan hệ cha-con | **CLOSED** | Giao diện `/admin/import`, 12 bảng thực thể `@Transactional`, cascade foreign keys đầy đủ. |
| **F1–F8** | F01 Review | Sai lệch JSON Schema Draft 2020-12; thiếu validator chuẩn; lỗi cấu trúc hợp đồng | **CLOSED** | Giữ nguyên 100% hợp đồng gốc, đồng bộ kiểu dữ liệu backend theo đúng schema. |

---

## 4. TỔNG HỢP KẾT QUẢ KIỂM THỬ TOÀN DIỆN (AUTOMATED TEST SUITES)

Hệ thống đã trải qua kiểm thử tự động toàn diện trên tất cả các tầng công nghệ:

### 1. Spring Boot Backend (JUnit 5 / Spring Boot Test / Mockito)
- **Lệnh thực thi:** `.\mvnw.cmd test`
- **Kết quả:** **178 / 178 tests PASSED (0 Failures, 0 Errors, 0 Skipped)**
- **Phạm vi kiểm thử:** Xác thực hợp đồng, import nguyên tử, phân quyền JWT/Grant, outbox worker, media stream Range, path traversal security, seed policy.

### 2. FastAPI AI Retrieval Engine (Pytest)
- **Lệnh thực thi:** `pytest -v tests/test_catalog_retrieval.py`
- **Kết quả:** **12 / 12 tests PASSED (100% OK)**
- **Phạm vi kiểm thử:** Xây dựng chỉ mục lai (BM25 + Dense E5), CAS generation, hash conflict detection, discovery ranking, rollback khi payload lỗi.

### 3. Frontend Next.js / TypeScript (Vitest & TSC)
- **Kiểm thử Unit & Component:** `npm run test` -> **83 / 83 tests PASSED (0 Failures)**
- **Kiểm tra Kiểu Type Safety:** `npx tsc --noEmit` -> **0 Errors**
- **Phạm vi kiểm thử:** Giao diện `/admin/import`, component player, timeline seek tuple, auth header forwarding, catalog browsing.

### 4. Contract Schema Validation
- **Lệnh thực thi:** `python docs/contracts/animation-catalog-v1/validate_catalog.py docs/fixtures/rehearsal_catalog.json`
- **Kết quả:** **VALID (0 schema errors, 0 integrity violations)**

### 5. Reviewer Independent Probes
- **F04 Probe:** `python docs/reviews/repro/CATALOG_01_F04_independent_probe.py` -> **100% PASS**
- **F05 Probe:** `python docs/reviews/repro/CATALOG_01_F05_independent_probe.py` -> **100% PASS**

### 6. Production Stack Rehearsal
- **Lệnh thực thi:** `python scripts/rehearsal_f06_production_stack.py`
- **Kết quả:** **10 / 10 GATES PASSED (Exit code 0)**

---

## 5. MA TRẬN BẢO MẬT STREAM MEDIA & PLAYBACK GRANT (GATES R1 – R4)

| Tình Huống Truy Cập | Phương Thức & URL | Header / Tham Số | Mã HTTP Phản Hồi | Giải Thích & Biện Pháp Bảo Vệ |
| :--- | :--- | :--- | :---: | :--- |
| **Stream tài nguyên Public** | `GET /api/media/stream/{assetId}` | Không yêu cầu | `200 OK` / `206 Partial` | Cho phép truy cập công khai; `Cache-Control: public, max-age=3600`. |
| **Stream tài nguyên Protected ẩn danh** | `GET /api/media/stream/{protectedAssetId}` | Không có token | `404 Not Found` | **Fail-Closed Policy**: Không trả 401 để tránh lộ sự tồn tại của file nội bộ. |
| **Xin cấp Grant Token hợp lệ** | `POST /api/media/grant/{assetId}` | `Authorization: Bearer <Admin/User_JWT>` | `200 OK` | Cấp token JWT có thời hạn 5 phút, chứa claim `type: playback_grant` và `assetId`. |
| **Stream Protected có Grant Token hợp lệ** | `GET /api/media/stream/{assetId}?grant={token}` | URL param `grant` | `200 OK` / `206 Partial` | Stream thành công nội dung video; `Cache-Control: private, no-cache, no-store`. |
| **Grant Token dùng làm Bearer truy cập API** | `GET /api/admin/catalog/snapshots` | `Authorization: Bearer {grantToken}` | `401 Unauthorized` | **Gate R1**: `JwtAuthenticationFilter` phát hiện `type == playback_grant` và từ chối xác thực. |
| **Grant Token dùng cho Asset khác** | `GET /api/media/stream/{otherAssetId}?grant={token}` | URL param `grant` | `404 Not Found` | **Gate R2**: Khóa tài nguyên; claim `assetId` không khớp với path variable. |
| **Tấn công Path Traversal qua storage key** | `GET /api/media/stream/{id}` (key chứa `../../etc/passwd`) | Mọi quyền | `404 Not Found` | **Gate R4**: `DriveMediaStorageAdapter` chuẩn hóa đường dẫn và chặn đứng mọi ký tự `..`. |

---

## 6. HƯỚNG DẪN VẬN HÀNH SNAPSHOT TỪNG BƯỚC CHO NGƯỜI DÙNG

Để vận hành snapshot một cách độc lập trên máy tính, thực hiện theo 3 bước:

### Bước 1: Khởi động 3 Dịch vụ
Mở 3 cửa sổ PowerShell:
1. **Spring Boot (Port 8080):**
   ```powershell
   cd D:\Class\movie-rcm-system\backend\springboot
   $env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"
   $env:CATALOG_SYNC_TOKEN = "dippie_production_sync_secret_2026"
   .\mvnw.cmd spring-boot:run
   ```
2. **FastAPI (Port 8000):**
   ```powershell
   cd D:\Class\movie-rcm-system\backend\fastapi
   $env:FASTAPI_SYNC_SECRET = "dippie_production_sync_secret_2026"
   python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
3. **Frontend (Port 3000):**
   ```powershell
   cd D:\Class\movie-rcm-system\frontend
   npm run dev
   ```

### Bước 2: Đăng Nhập & Nhập Catalog
1. Mở trình duyệt truy cập: `http://localhost:3000/login`.
2. Đăng nhập với tài khoản:
   - Tên đăng nhập: `admin` (hoặc `admin@dippie.com`)
   - Mật khẩu: `password123`
3. Truy cập trang: `http://localhost:3000/admin/import`.
4. Nhấn **"Chọn tệp JSON..."** và chọn tệp mẫu có sẵn tại: `docs/fixtures/rehearsal_catalog.json` (hoặc `catalog.example.json`).
5. Nhấn **"Kiểm tra & Xem trước"** -> Xác nhận kết quả Hợp lệ.
6. Nhấn **"Xác nhận nhập dữ liệu"** -> Hệ thống commit DB và tự động kích hoạt Outbox Worker đồng bộ sang FastAPI.

### Bước 3: Tìm Kiếm & Xem Video Kèm Phân Cảnh
1. Truy cập `http://localhost:3000/search`, tìm kiếm từ khóa `"Bảo Thần Tốc"`.
2. Nhấp vào phân cảnh hiển thị trong kết quả để mở trang phát video (`/series/ser_rehearsal_01`).
3. Video phát mượt mà, phân cảnh được tô sáng, tua chính xác tới giây thứ 25.0 của video.

---

## 7. TRẢ LỜI ĐẦY ĐỦ 9 CÂU HỎI QUAN TRỌNG TỪ NGƯỜI DÙNG

1. **Root cause của S1, S2, S3 là gì?**
   - *S1:* Lưu đĩa và cập nhật state trước khi candidate index build thành công, thiếu rollback khi gặp ngoại lệ, hardcode đường dẫn trạng thái.
   - *S2:* Token đồng bộ không có fallback đồng nhất giữa hai service; seed user bị trùng lặp khóa chính trong `DataInitializer`; frontend gọi API catalog thiếu header Authorization.
   - *S3:* Thiếu một kịch bản kiểm thử tích hợp thực tế chạy đồng thời cả hai server qua cổng mạng thật với cơ sở dữ liệu và dữ liệu video mẫu.

2. **Các lỗi bảo mật R1–R6 đã được giải quyết triệt để như thế nào?**
   - *R1:* Token Playback Grant có claim `type: playback_grant`, bị loại bỏ ngay từ đầu bộ lọc `JwtAuthenticationFilter`, không thể đóng vai trò Bearer token.
   - *R2:* Claim `assetId` trong grant token được so sánh nghiêm ngặt với asset ID trên URL stream.
   - *R3:* Mọi vi phạm quyền truy cập đối với tài nguyên media protected đều trả về HTTP 404 Fail-Closed.
   - *R4:* Bộ điều hợp lưu trữ `DriveMediaStorageAdapter` kiểm tra tính chứa trong (path containment) và triệt tiêu path traversal.
   - *R5:* Chuẩn hóa kiểu dữ liệu số nguyên (`Long`) và số thực trong tính hash nội dung, đảm bảo mã băm SHA-256 hoàn toàn ổn định.
   - *R6:* Outbox worker tự động phát hiện các snapshot `SYNCING` dở dang khi khởi động và chuyển về `PENDING` để retry an toàn.

3. **Cơ chế Candidate Isolation và Rollback tại FastAPI hoạt động ra sao?**
   - Khi nhận yêu cầu đồng bộ tại `/api/index/sync`, FastAPI tạo bản sao chỉ mục ứng viên trên đối tượng độc lập. Quá trình vector hóa văn bản diễn ra hoàn toàn trên candidate này. Nếu có bất kỳ lỗi nào, hệ thống giữ nguyên con trỏ index đang chạy, khôi phục `active_catalog` và không đụng vào đĩa. Chỉ khi build thành công, con trỏ mới được hoán đổi nguyên tử và trạng thái mới được ghi ra đĩa.

4. **Tài khoản Admin và cấu hình Token được thiết lập thế nào?**
   - Tài khoản `admin@dippie.com` / `password123` được nạp sẵn vào cơ sở dữ liệu với role `ROLE_ADMIN`. Token đồng bộ được cấu hình linh hoạt qua biến môi trường `CATALOG_SYNC_TOKEN` (Spring Boot) và `FASTAPI_SYNC_SECRET` (FastAPI).

5. **Kết quả của đợt diễn tập thực tế (Rehearsal) ra sao?**
   - Kịch bản `scripts/rehearsal_f06_production_stack.py` đã vượt qua 10/10 bước, chứng thực khả năng hoạt động thông suốt từ đăng nhập, xác thực, import, worker HTTP sync, search, streaming có bảo mật, tua video đến phục hồi sau restart.

6. **Tất cả các bộ test tự động có đạt 100% không?**
   - Toàn bộ: 178 Maven tests (Spring Boot), 12 Pytest tests (FastAPI), 83 Vitest tests (Frontend), 0 lỗi TypeScript, 100% hợp lệ Contract JSON Schema.

7. **Tại sao lại dùng chính sách Fail-Closed cho Media Streaming?**
   - Để ngăn chặn việc kẻ tấn công dò quét (enumeration attack) biết được các ID media nhạy cảm hoặc nội bộ nào đang tồn tại trong hệ thống. Khi không có quyền hoặc token không hợp lệ, hệ thống trả về 404 như thể tài nguyên không hề tồn tại.

8. **Trình phát video xử lý việc tua theo phân cảnh (Scene Seek) thế nào khi có độ lệch mốc thời gian?**
   - Sử dụng công thức: `(source_in_ms + Math.max(0, logicalMs - episode_in_ms)) / 1000`. Khi chuyển tài nguyên media, trình phát lưu `PendingSeekIdentity` và chỉ áp dụng mốc tua khi sự kiện `onCanPlay` xác nhận đúng bộ ba định danh `(seriesId, episodeId, assetId)`.

9. **Có tệp nào trong thư mục hợp đồng `docs/contracts/` bị chỉnh sửa không?**
   - **HOÀN TOÀN KHÔNG**. Toàn bộ 5 tệp trong `docs/contracts/animation-catalog-v1/` được bảo toàn nguyên vẹn 100%, không bị sửa đổi một ký tự nào.

---

## 8. KẾT LUẬN & ĐỀ XUẤT NGHIỆM THU

Snapshot `CATALOG-01-F06-CHECKPOINT-01` đáp ứng đầy đủ và vượt trội các tiêu chí chất lượng, bảo mật và trải nghiệm người dùng của một sản phẩm hoàn thiện. Hệ thống sẵn sàng cho việc đóng băng mã nguồn (frozen baseline) và bàn giao cho người dùng đưa vào khai thác thực tế.
