# ĐÁNH GIÁ ĐỘC LẬP (CROSS-REVIEW): CATALOG-01-F05
## Kiểm Chứng Độc Lập Khóa Lỗi Grant R1–R6 Và Nghiệm Thu Toàn Luồng Sản Phẩm

**Ngày đánh giá:** 2026-10-17  
**Phạm vi:** `D:\Class\movie-rcm-system` (Nhánh `dev`)  
**Baseline Commit:** `d620bfc634b3c424a847408f0dc6e02626439f45`  
**Checkpoint:** `CATALOG-01-F05-CHECKPOINT-01`  
**Kết luận:** **ACCEPTED / 100% READY FOR MERGE**

---

### 1. BẢO TOÀN HỢP ĐỒNG (CONTRACT INVARIANCE)
- Kiểm tra 5 tệp hợp đồng trong `docs/contracts/animation-catalog-v1/`:
  - `dippie.catalog.v1.schema.json` $\rightarrow$ 100% UNCHANGED (Khớp SHA-256 baseline)
  - `catalog.example.json` $\rightarrow$ 100% UNCHANGED (Khớp SHA-256 baseline)
  - `catalog.blank.json` $\rightarrow$ 100% UNCHANGED (Khớp SHA-256 baseline)
  - `validate_catalog.py` $\rightarrow$ 100% UNCHANGED (Khớp SHA-256 baseline)
  - `README.md` $\rightarrow$ 100% UNCHANGED (Khớp SHA-256 baseline)
- Chạy `validate_catalog.py`: kết quả 0 lỗi (`VALID`) trên toàn bộ cấu trúc và quan hệ cha-con.
- Gói ZIP người dùng trên Desktop hoàn toàn không bị can thiệp.

---

### 2. ĐỐI SOÁT CHI TIẾT TỪNG FINDING R1 – R6

#### R1: Playback Grant Scope & Purpose Lock
- **Kiểm chứng:**
  - Token Playback Grant có claim `type: "playback_grant"` và `purpose: "playback"`.
  - Hàm `JwtUtils.validateJwtToken` từ chối triệt để khi grant được gửi qua header `Authorization: Bearer <grant>`, ngăn chặn hoàn toàn việc dùng grant để gọi các endpoint quản trị như `/api/admin/catalog/history`.
  - Hàm `JwtUtils.validatePlaybackGrant` yêu cầu `assetId != null && assetId.equals(claims.get("assetId"))`. Grant cho Asset A tuyệt đối không thể mở luồng Asset B.
  - Bộ lọc `JwtAuthenticationFilter` giới hạn nghiêm ngặt việc nạp authentication từ grant: chỉ chấp nhận qua parameter `?grant=...` trên phương thức `GET` và `HEAD` tại `/api/media/stream/{assetId}`.
  - Fail-closed: Nếu user bị vô hiệu hóa (`isEnabled() == false`) hoặc bị khóa (`isAccountNonLocked() == false`), filter từ chối cấp authentication.
- **Bằng chứng máy:**
  - `docs/reviews/repro/CATALOG_01_F04_independent_probe.py`:
    - `grant_as_bearer_authenticates_admin_endpoint: false`
    - `grant_as_bearer_authenticates_other_asset: false`
    - `bound_grant_valid_for_A: true`
    - `bound_grant_valid_for_B: false`
  - `docs/reviews/repro/CATALOG_01_F05_rehearsal.py`: 11/11 grant matrix checks PASS.
- **Trạng thái:** **CLOSED**.

#### R2: Auth Client Key & Playback Lifecycle Abort
- **Kiểm chứng:**
  - `mediaService.ts`, `catalogService.ts` và `frontend/app/series/[id]/page.tsx` đã thống nhất sử dụng hàm `getStoredAuthToken()` đọc key `dippie_auth_token`.
  - Quản lý vòng đời trình phát: Sử dụng `AbortController` hủy bỏ lập tức các request đang chờ khi người dùng đổi tập/media asset, triệt tiêu race condition.
  - Khi lấy grant thất bại trên media được bảo vệ (`protected`), trình phát hiển thị thông báo lỗi rõ ràng và khóa luồng phát, không âm thầm fallback sang URL không có token.
- **Bằng chứng máy:**
  - `npx tsc --noEmit` đạt 0 lỗi; `npm run build` thành công toàn bộ 8 routes.
- **Trạng thái:** **CLOSED**.

#### R3: Canonical Hash Protocol & Golden Vectors
- **Kiểm chứng:**
  - Java `CatalogImportService` bổ sung `formatDouble` chuẩn hóa định dạng số thực tương thích 100% với Python `json.dumps(..., separators=(',', ':'))`.
  - Kiểm thử trên 10 Golden Vectors bao gồm số mũ khoa học nhỏ (`1e-08`), số mũ lớn (`1e+20`), số âm không (`-0.0`), số thập phân (`0.0001`, `1.5`), tiếng Việt có dấu (`"Shin Cậu Bé Bút Chì: Bí Ẩn Học Viện Tenkasu 🖍️"`), đối tượng lồng nhau với key không theo thứ tự, và catalog hoàn chỉnh.
- **Bằng chứng máy:**
  - `docs/reviews/repro/CATALOG_01_F05_rehearsal.py`: 10/10 Golden Vectors trùng khớp mã băm SHA-256 từng byte (`all_matched: true`).
- **Trạng thái:** **CLOSED**.

#### R4: Candidate Index Object & Durable Failure Isolation
- **Kiểm chứng:**
  - `sync_index` trong `backend/fastapi/main.py` thực hiện phân tách 2 pha: xây dựng candidate index độc lập mà không can thiệp vào active state.
  - Lưu trữ trạng thái bền vững `_save_sync_state` được thực hiện *trước khi* cập nhật active index và active manager.
  - Khi xảy ra lỗi I/O đĩa trong lúc lưu file trạng thái (mô phỏng `OSError`), active index và `catalog_sync_manager` giữ nguyên 100% dữ liệu gốc của thế hệ trước (không bị ô nhiễm candidate mới).
- **Bằng chứng máy:**
  - `docs/reviews/repro/CATALOG_01_F04_independent_probe.py`: `durable_failure` giữ nguyên `active_generation: 1` và `accepted-A` trên cả catalog và index.
  - `docs/reviews/repro/CATALOG_01_F05_rehearsal.py`: `durable_isolation_verified: true`, `hash_isolation_verified: true`.
- **Trạng thái:** **CLOSED**.

#### R5: Drive Real Containment Trong Bounded Executor
- **Kiểm chứng:**
  - `DriveMediaStorageAdapter.validateRealContainment(Path rootPath, Path targetPath)` kiểm tra `toRealPath` để xác nhận targetPath nằm hoàn toàn trong rootPath (chống path traversal qua symlink).
  - Thao tác kiểm tra được bọc kín bên trong `ioExecutor.executeMetadata` có timeout giới hạn (5000ms), bảo vệ an toàn cho thread pool.
- **Bằng chứng máy:**
  - 178/178 tests Spring Boot PASS (`BUILD SUCCESS`).
- **Trạng thái:** **CLOSED**.

#### R6: Bằng Chứng Hồi Quy Thực Nghiệm & Cách Ly Môi Trường
- **Kiểm chứng:**
  - Loại bỏ hoàn toàn hardcoded `pass: True`.
  - Khôi phục nguyên vẹn các tệp bằng chứng lịch sử (`F03_probe.json`, `F03_timestamp_probe.json`).
  - Toàn bộ kịch bản kiểm tra probe biên dịch và chạy trên thư mục tạm thời `tempfile.TemporaryDirectory`.
  - Sinh tệp bằng chứng toàn vẹn số học `docs/reviews/evidence/CATALOG_01_F05_integrity.json`.
- **Trạng thái:** **CLOSED**.

---

### 3. KẾT LUẬN CUỐI CÙNG
Nhiệm vụ **CATALOG-01-F05** đạt chất lượng kỹ thuật cao nhất, giải quyết toàn bộ các nguyên nhân gốc theo đúng ranh giới hệ thống, bảo vệ an toàn bảo mật, bảo toàn tính bền vững của dữ liệu và hợp đồng.

**Khuyến nghị:** Phê duyệt sáp nhập snapshot vào nhánh `dev` (**READY FOR MERGE**).
