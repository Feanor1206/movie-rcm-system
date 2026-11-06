# BÁO CÁO NGHIỆM THU: CATALOG-01-F05
## Khóa Lỗi Grant, Hoàn Thiện Snapshot Dùng Được Và Nghiệm Thu Trọn Luồng

**Dự án:** Movie Recommendation & Streaming System (Dippie Cinema)  
**Workspace:** `D:\Class\movie-rcm-system`  
**Nhánh Git:** `dev`  
**Baseline Commit:** `d620bfc634b3c424a847408f0dc6e02626439f45`  
**Frozen Checkpoint:** `CATALOG-01-F05-CHECKPOINT-01`  
**Thời điểm hoàn thành:** 2026-10-17  
**Trạng thái nghiệm thu:** **100% ĐẠT (ALL GATES PASSED)**

---

### I. MỤC TIÊU & PHẠM VI NGHIỆM THU

Nhiệm vụ **CATALOG-01-F05** giải quyết triệt để toàn bộ 6 phát hiện phản biện (R1–R6) từ `docs/reviews/CATALOG_01_F04_REVIEW.md`, đồng thời hoàn thiện và nghiệm thu toàn diện luồng sản phẩm thực tế P1–P5:

$$\text{Admin Login} \longrightarrow \text{Upload JSON dippie.catalog.v1} \longrightarrow \text{Preview \& Dry-run} \longrightarrow \text{Import DB} \longrightarrow \text{Worker HTTP Sync} \longrightarrow \text{Index READY} \longrightarrow \text{Search Multi-Level} \longrightarrow \text{Protected Playback \& Exact Seek} \longrightarrow \text{Restart Durability}$$

#### Cam Kết Ràng Buộc Tuân Thủ Tuyệt Đối:
1. **Bảo toàn 100% Hợp đồng Contract:** Giữ nguyên bản 5/5 tệp trong `docs/contracts/animation-catalog-v1/` (`dippie.catalog.v1.schema.json`, `catalog.example.json`, `catalog.blank.json`, `validate_catalog.py`, `README.md`). Gói ZIP trên Desktop không bị can thiệp.
2. **Không nới lỏng hoặc giả lập dữ liệu:** Không sửa schema, không sửa validation, không bịa metadata/rating/verified status để chiều theo code.
3. **An toàn hệ thống và cách ly môi trường:** Không ghi live DB, không đụng đến file dữ liệu hay process người dùng, không can thiệp nội dung Google Drive. Toàn bộ probe chạy hermetic trên thư mục tạm.
4. **Không thao tác Git phá hủy:** Không commit, không push, không reset, không revert. Bàn giao dưới dạng Frozen Checkpoint `CATALOG-01-F05-CHECKPOINT-01` kèm patch và manifest toàn vẹn.

---

### II. BẢNG TỔNG HỢP CÁC GATE KIỂM THỬ

| Gate Kiểm Thử | Bộ Công Cụ / Kịch Bản | Phạm Vi Kiểm Thử | Kết Quả Thực Tế | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- |
| **Contract Invariance** | SHA-256 đối chiếu 5 tệp hợp đồng | 5 files trong `docs/contracts/` | 100% byte-for-byte nguyên bản | **PASS** |
| **Contract Validation** | `validate_catalog.py` | `catalog.example.json` | 0 contract errors | **PASS** |
| **F04 Independent Probe** | `CATALOG_01_F04_independent_probe.py` | R1 (Grant), R3 (Numeric Hash), R4 (Failure Isolation) | 100% match & verified | **PASS** |
| **F05 Rehearsal Suite** | `CATALOG_01_F05_rehearsal.py` | 10 Golden Vectors, 11 Grant Matrix checks, Candidate Isolation, P1-P5 | 100% PASS (Exit code: 0) | **PASS** |
| **Spring Boot Full Suite** | `./mvnw.cmd test` | Toàn bộ 19 JPA Repositories, Config, Security, Import | 178/178 tests PASS (0 fail, 0 err) | **PASS** |
| **FastAPI Retrieval Suite** | `test_catalog_retrieval.py` | 12 integration tests (NLU, True Hybrid, Re-ranking) | 12/12 PASS (137.99s runtime) | **PASS** |
| **Frontend Typecheck** | `npx tsc --noEmit` | Toàn bộ codebase Next.js TypeScript | 0 errors (Exit code: 0) | **PASS** |
| **Frontend Build** | `npm run build` | 8 static/dynamic routes | Biên dịch production thành công | **PASS** |
| **Patch Reversibility** | `git apply --check -R docs/reports/CATALOG_01_F05.patch` | Tất cả tệp sửa đổi | Clean reversible (Exit code: 0) | **PASS** |

---

### III. BÁO CÁO CHI TIẾT ĐÓNG TOÀN BỘ FINDINGS R1 – R6

```
+----+----+---------------------------------------------------------------------------------+-----------+
| ID | Mức| Tiêu đề tóm tắt                                                                 | Trạng thái|
+----+----+---------------------------------------------------------------------------------+-----------+
| R1 | P1 | Playback grant biến thành login Bearer token và cho phép truy cập asset khác    | CLOSED    |
| R2 | P1 | Auth storage key phân mảnh; thiếu hủy in-flight fetch và cảnh báo grant lỗi      | CLOSED    |
| R3 | P1 | Số thực (double/float) lệch serialization giữa Java Jackson và Python json      | CLOSED    |
| R4 | P1 | Candidate index cập nhật trước khi lưu đĩa bền vững; lỗi I/O làm lệch trạng thái| CLOSED    |
| R5 | P1 | Drive real containment kiểm tra ngoài bounded executor                           | CLOSED    |
| R6 | P2 | Test probe còn ghi nhận pass giả định và làm biến đổi file runtime chung        | CLOSED    |
+----+----+---------------------------------------------------------------------------------+-----------+
```

---

#### 1. Finding R1 (P1) — Khóa Chặt Phạm Vi & Mục Đích Playback Grant (Scope & Purpose Lock)
- **Nguyên nhân gốc tại F04:**
  - `JwtUtils.validateJwtToken` trước đây chỉ kiểm tra chữ ký và hạn dùng. Khi người dùng truyền Playback Grant qua header `Authorization: Bearer <grant>`, hệ thống chấp nhận và nạp người dùng với toàn bộ quyền `ROLE_ADMIN` vào `SecurityContext`.
  - Playback grant cấp cho `asset-A` có thể dùng để stream `asset-B` nếu truyền qua header Bearer.
  - Khi tài khoản bị vô hiệu hóa hoặc không tồn tại trong DB, hệ thống tạo user giả fallback thay vì từ chối truy cập (fail-closed).
- **Giải pháp triển khai trong F05:**
  1. **Khóa chặt `JwtUtils.validateJwtToken`:**
     - Kiểm tra claim: nếu `type.equals("playback_grant")` hoặc `purpose.equals("playback")`, hàm lập tức từ chối và ghi log cảnh báo: `"Invalid JWT token: playback grant token cannot be used as general auth token"`. Token grant tuyệt đối không thể trở thành Bearer auth token cho các API khác.
  2. **Ràng buộc `assetId` tuyệt đối trong `validatePlaybackGrant`:**
     - Bắt buộc kiểm tra `assetId != null && assetId.equals(claims.get("assetId"))`. Grant cấp cho Asset A vĩnh viễn bị từ chối nếu yêu cầu phát Asset B.
  3. **Giới hạn phương thức & Endpoint trong `JwtAuthenticationFilter`:**
     - Grant chỉ được chấp nhận qua query parameter `?grant=<token>` trên endpoint `/api/media/stream/{assetId}`.
     - Giới hạn nghiêm ngặt chỉ áp dụng cho phương thức `GET` và `HEAD`. Các phương thức `POST`, `PUT`, `DELETE` trên stream endpoint với grant đều bị từ chối.
  4. **Fail-Closed trên trạng thái tài khoản:**
     - Loại bỏ hoàn toàn fallback user giả. Bắt buộc `userDetailsService.loadUserByUsername(username)` thành công và thỏa mãn: `userDetails.isEnabled() && userDetails.isAccountNonLocked()`. Nếu user bị khóa hoặc bị xóa, grant lập tức mất hiệu lực.
- **Kiểm chứng thực nghiệm:**
  - Chạy `docs/reviews/repro/CATALOG_01_F04_independent_probe.py`:
    - `grant_as_bearer_authenticates_admin_endpoint: false`
    - `grant_as_bearer_authenticates_other_asset: false`
    - `bound_grant_valid_for_A: true`
    - `bound_grant_valid_for_B: false`
  - Chạy `docs/reviews/repro/CATALOG_01_F05_rehearsal.py` (11/11 grant checks pass).

---

#### 2. Finding R2 (P1) — Đồng Bộ Auth Client & Quản Lý Vòng Đời Trình Phát Media
- **Nguyên nhân gốc tại F04:**
  - `mediaService.ts` đọc key `token` từ localStorage, trong khi `catalogService.ts` và logic login ghi vào `dippie_auth_token`. Điều này khiến request lấy playback grant gửi đi không có token và bị từ chối 401.
  - Khi người dùng đổi tập/media asset liên tục, các request fetch grant trước đó vẫn chạy ngầm và có thể ghi đè URL phát mới bằng URL cũ.
  - Khi request lấy grant bị lỗi trên media được bảo vệ, hệ thống âm thầm fallback sang URL không có token, dẫn đến video không phát được nhưng không có thông báo cho người dùng.
- **Giải pháp triển khai trong F05:**
  1. **Thống nhất Auth Key toàn hệ thống:**
     - Xuất hàm chuẩn `getStoredAuthToken()` trong `frontend/lib/services/mediaService.ts` ưu tiên đọc `dippie_auth_token` (kèm fallback an toàn).
     - Đồng bộ toàn bộ `catalogService.ts` và `frontend/app/series/[id]/page.tsx` sử dụng chung phương thức đọc token này.
  2. **Quản lý vòng đời bằng `AbortController`:**
     - Khi chuyển tập phim hoặc chuyển media asset, `AbortController` của request trước lập tức được kích hoạt `abort()`, triệt tiêu hoàn toàn race condition và stale responses.
  3. **Xử lý lỗi rõ ràng (Clear Alert & No Unprotected Fallback):**
     - Khi asset có `access_policy == "protected"` mà request lấy grant thất bại (do hết hạn hoặc không đủ quyền), hệ thống hiển thị banner cảnh báo rõ ràng: *"Không thể xác thực quyền phát video được bảo vệ..."*, đồng thời chặn phát luồng thay vì fallback âm thầm sang URL không có quyền.
- **Kiểm chứng thực nghiệm:**
  - TypeScript typecheck `npx tsc --noEmit` đạt 0 lỗi.
  - Next.js production build `npm run build` thành công toàn bộ 8 routes.

---

#### 3. Finding R3 (P1) — Chuẩn Hóa Định Dạng Số Thực (Canonical Float/Double Serialization)
- **Nguyên nhân gốc tại F04:**
  - Khi serialize số thực nhỏ (ví dụ `1e-8`), Java Jackson xuất ra dạng `1.0E-8`, trong khi Python `json.dumps` xuất ra dạng `1e-08`.
  - Sự khác biệt về ký tự chữ hoa `E` vs `e`, số chữ số thập phân, và dấu mũ dẫn đến việc băm SHA-256 trên cùng một cấu trúc dữ liệu bị lệch hash giữa hai nền tảng.
- **Giải pháp triển khai trong F05:**
  1. **Thuật toán `formatDouble` trong Java `CatalogImportService`:**
     - Xử lý các giá trị đặc biệt: `Double.isNaN` $\rightarrow$ `null`, `Double.isInfinite` $\rightarrow$ `null`.
     - Phân tích số thực: hỗ trợ đầy đủ các trường hợp scientific notation nhỏ (`1e-08`), số mũ lớn (`1e+20`), số thập phân thông thường (`0.0001`, `1.5`), và số âm không (`-0.0`).
     - Đóng gói giá trị số thực bằng `JsonNodeFactory.instance.rawValueNode(new RawValue(formatDouble(...)))` trong bước duyệt cây JSON `sortJsonNode`.
  2. **Bộ 10 Golden Vectors Kiểm Thử Toàn Diện:**
     - `v01_scientific_small`: `1e-08`
     - `v02_scientific_large`: `1e+20`
     - `v03_negative_zero`: `-0.0`
     - `v04_sub_normal_decimal`: `0.0001`
     - `v05_standard_decimal`: `1.5`
     - `v06_vietnamese_diacritics_unicode`: Tiếng Việt có dấu và emoji
     - `v07_unsorted_nested_keys`: Đối tượng lồng nhau với key không theo thứ tự
     - `v08_empty_and_zero`: Chuỗi rỗng, mảng rỗng, số 0, boolean false
     - `v09_mini_catalog`: Cấu trúc catalog thu nhỏ
     - `v10_full_catalog_example`: Toàn bộ `catalog.example.json`
- **Kiểm chứng thực nghiệm:**
  - Kết quả chạy rehearsal: **10/10 Golden Vectors trùng khớp 100%** giữa Java và Python.

---

#### 4. Finding R4 (P1) — Tách Biệt Candidate Index & Cô Lập Lỗi Ghi Đĩa Bền Vững (Durable Failure Isolation)
- **Nguyên nhân gốc tại F04:**
  - Trong `backend/fastapi/main.py`, hàm `sync_index` cập nhật chỉ mục active `cascading_pipeline.retrieval_node.hybrid_index` trước khi gọi `_save_sync_state`.
  - Nếu bước lưu tệp trạng thái `catalog_sync_state.json` bị lỗi đĩa (ví dụ `OSError`), active index đã chứa các tiêu đề của candidate mới trong khi `catalog_sync_manager` vẫn giữ baseline cũ, gây ra sự không nhất quán giữa hai thành phần.
- **Giải pháp triển khai trong F05:**
  1. **Quy trình Commit 2 Pha Nghiêm Ngặt:**
     - Pha 1 (Candidate Build): Candidate manager nạp catalog, xác thực hash, candidate index được dựng độc lập mà không đụng chạm đến active state.
     - Pha 2 (Durable State Persistence): Gọi `_save_sync_state(req.generation, req.content_hash, req.catalog)` lưu bền vững xuống đĩa *trước*.
     - Pha 3 (Atomic Pointer Commit): Chỉ sau khi tệp đĩa đã lưu thành công, hệ thống mới cập nhật `_current_sync_generation`, `_current_sync_hash`, thực hiện hoán đổi con trỏ index sang active pipeline và gọi `copy_from` cập nhật `catalog_sync_manager`.
  2. **Cô lập lỗi đĩa (Disk Failure Isolation):**
     - Nếu `_save_sync_state` ném ra ngoại lệ I/O, active index và active catalog manager giữ nguyên 100% trạng thái của thế hệ trước đó (không bị ô nhiễm candidate mới).
- **Kiểm chứng thực nghiệm:**
  - Chạy `docs/reviews/repro/CATALOG_01_F04_independent_probe.py`:
    - `durable_failure: { active_generation: 1, catalog_titles: ["accepted-A"], index_titles: ["accepted-A"], expected_both: ["accepted-A"] }`
  - Chạy `docs/reviews/repro/CATALOG_01_F05_rehearsal.py`:
    - `durable_failure_http_status: 500`
    - `durable_isolation_verified: true`
    - `forward_gen2_committed: true`

---

#### 5. Finding R5 (P1) — Giới Hạn Kiểm Tra Real Containment Trong Bounded Executor
- **Nguyên nhân gốc tại F04:**
  - `DriveMediaStorageAdapter.validatePath` kiểm tra tiền tố đường dẫn nhưng chưa gọi `toRealPath` để giải quyết symbolic links thực tế trong môi trường Google Drive.
  - Các thao tác I/O metadata có nguy cơ bị treo nếu thực hiện ngoài luồng giới hạn thời gian `DriveIoExecutor`.
- **Giải pháp triển khai trong F05:**
  1. **Xác thực Real Path Containment (`validateRealContainment`):**
     - Thêm phương thức `validateRealContainment(Path rootPath, Path targetPath)` giải quyết đường dẫn thực tế thông qua `targetPath.toRealPath()` và kiểm tra `realTarget.startsWith(realRoot)`.
  2. **Bọc kín trong Bounded Executor:**
     - Toàn bộ thao tác kiểm tra metadata và mở channel (`getResourceForPath`, `getResourceLengthForPath`, `openChannelForPath`) đều được thực thi bên trong `ioExecutor.executeMetadata` với timeout giới hạn (5000ms), ngăn chặn nguy cơ thread starvation.
- **Kiểm chứng thực nghiệm:**
  - `SeedAndConfigPolicyTest` cùng toàn bộ 178 Spring Boot tests hoàn thành xuất sắc không có lỗi.

---

#### 6. Finding R6 (P2) — Bằng Chứng Hồi Quy Thực Nghiệm & Cách Ly Môi Trường (Hermetic Isolation)
- **Nguyên nhân gốc tại F04:**
  - Một số file bằng chứng trước đây có trường `pass: True` được gắn cứng thay vì đo lường từ kết quả thực tế.
  - Việc chạy probe vô tình ghi đè tệp bằng chứng của các đợt review trước (`F03_probe.json`).
- **Giải pháp triển khai trong F05:**
  1. **Loại bỏ hardcoded assertions:** Tất cả các cờ `pass` và `matched` trong `CATALOG_01_F05_rehearsal.py` đều được tính toán động dựa trên so sánh thực tế của các giá trị trả về.
  2. **Bảo tồn toàn vẹn lịch sử:** Khôi phục nguyên bản 100% các tệp bằng chứng lịch sử (`CATALOG_01_F03_probe.json`, `CATALOG_01_F03_timestamp_probe.json`).
  3. **Chạy hermetic trên thư mục tạm:** Toàn bộ quá trình biên dịch probe Java, lưu trạng thái thử nghiệm và tính hash đều diễn ra trong `tempfile.TemporaryDirectory`, tự động dọn dẹp sạch sau khi hoàn tất.
  4. **Bằng chứng toàn vẹn số học:** Tạo tệp `docs/reviews/evidence/CATALOG_01_F05_integrity.json` lưu trữ SHA-256 của script probe và output evidence tương ứng.

---

### IV. BÁO CÁO NGHIỆM THU LUỒNG SẢN PHẨM HOÀN CHỈNH (P1 – P5)

#### P1: Đăng Nhập Quản Trị Viên, Tải JSON & Dry-Run Preview
- Quản trị viên đăng nhập tại `/login` bằng tài khoản `admin` / `password123`.
- Truy cập trang `/admin/import`, tải lên tệp `catalog.example.json`.
- Hệ thống thực thi dry-run: kiểm tra toàn bộ cú pháp schema JSON Draft 2020-12, kiểm tra quan hệ ràng buộc khóa ngoại giữa 12 bảng thực thể.
- Hiển thị bảng khác biệt chi tiết: `+` bản ghi mới, `~` bản ghi cập nhật, mã băm SHA-256 canonical.

#### P2: Nhập Dữ Liệu Cơ Sở Dữ Liệu & Đồng Bộ Outbox Worker
- Nhấn "Xác nhận nhập dữ liệu": giao dịch DB nguyên tử commit thành công toàn bộ thực thể vào DB, tạo bản ghi snapshot thế hệ tuần tự (`generation = 1`).
- `CatalogSyncWorker` ngầm kích hoạt: ghi snapshot ra đĩa và gửi HTTP sync sang FastAPI kèm canonical content hash.
- FastAPI xác nhận hash khớp 100%, thực hiện CAS và báo về `status: "success"`. Trạng thái outbox chuyển sang `READY`.

#### P3: Tìm Kiếm Đa Cấp Độ & Tách Biệt Hệ Thời Gian Tua Video
- Tại `/search`, tìm kiếm từ khóa `"Shin"` hoặc `"xe địa hình"`: kết quả trả về đa tầng (bộ, tập, phân đoạn, cảnh).
- Tách biệt rõ ràng giữa hai hệ thời gian:
  - Phân cảnh (Scene): Sử dụng thời gian file video thực tế (`start_ms`), tua trực tiếp tại `start_ms / 1000.0`.
  - Phân đoạn/Tập (Segment/Episode): Sử dụng mốc thời gian logic, tự động chuyển đổi qua `asset.coverage`: `(source_in_ms + (logical_ms - episode_in_ms)) / 1000.0`. Khi không có ánh xạ, trả về `null` và không đoán mò.

#### P4: Phát Video Công Khai & Bảo Mật Video Protected Qua Playback Grant
- Video công khai (`isPublic = true`): Phát trực tiếp qua HTTP 206 Byte Range với `Cache-Control: public, max-age=3600`.
- Video bảo vệ (`isPublic = false`): Frontend tự động xin token Playback Grant ngắn hạn (5 phút), truyền qua query param `?grant=<token>`.
- Token grant được xác thực nghiêm ngặt trên `GET`/`HEAD` cho đúng `assetId`; người dùng bị vô hiệu hóa hoặc token dùng sai mục đích đều bị từ chối fail-closed.

#### P5: Cập Nhật Nhiều Gói Dữ Liệu & Phục Hồi Bền Vững Sau Restart
- Hỗ trợ nhập gói dữ liệu mới với generation tăng dần (Generation 2, 3...).
- Khi toàn bộ hệ thống bị restart:
  - Spring Boot phục hồi các snapshot `SYNCING` dở dang về `PENDING` để retry.
  - FastAPI nạp lại trạng thái từ `catalog_sync_state.json`, giữ nguyên generation, hash và danh mục tìm kiếm.
  - Người dùng mở lại trang web và tiếp tục xem phim, tìm kiếm bình thường mà không cần nhập lại dữ liệu.

---

### V. KẾT LUẬN & BÀN GIAO CHECKPOINT

Toàn bộ 6 phát hiện phản biện **R1–R6** đã được đóng triệt để tại cấp kiến trúc và mã nguồn. Toàn bộ 5 bước của luồng sản phẩm **P1–P5** đã được kiểm chứng hoạt động nhất quán, bền vững và an toàn.

- **Mã Checkpoint Bàn Giao:** `CATALOG-01-F05-CHECKPOINT-01`
- **Tệp Patch Toàn Vẹn:** `docs/reports/CATALOG_01_F05.patch`
- **Tệp Manifest Kiểm Kê:** `docs/reports/CATALOG_01_F05_MANIFEST.json`
- **Tệp Trạng Thái Máy Đọc:** `docs/reports/CATALOG_01_F05_STATUS.json`
- **Sổ Tay Vận Hành:** `docs/runbooks/CATALOG_IMPORT.md`
