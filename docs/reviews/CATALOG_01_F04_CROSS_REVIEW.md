# ĐÁNH GIÁ ĐỘC LẬP (CROSS-REVIEW): CATALOG-01-F04
## Kiểm Chứng Độc Lập Luồng Snapshot Vận Hành & Khắc Phục Triệt Để H1–H5

**Ngày đánh giá:** 2026-10-17  
**Phạm vi:** D:\Class\movie-rcm-system (branch dev)  
**Baseline Commit:** `d620bfc634b3c424a847408f0dc6e02626439f45`  
**Checkpoint:** `CATALOG-01-F04-CHECKPOINT-01`  
**Kết luận:** **ACCEPTED / READY FOR MERGE**

---

### 1. BẢO TOÀN HỢP ĐỒNG (CONTRACT INVARIANCE)
- Kiểm tra 5 tệp hợp đồng trong `docs/contracts/animation-catalog-v1/`:
  - `dippie.catalog.v1.schema.json` -> 100% UNCHANGED
  - `catalog.example.json` -> 100% UNCHANGED
  - `catalog.blank.json` -> 100% UNCHANGED
  - `validate_catalog.py` -> 100% UNCHANGED
  - `README.md` -> 100% UNCHANGED
- Chạy `validate_catalog.py`: kết quả `VALID` trên cả cấu trúc, tham chiếu nội tại và dấu thời gian.
- Gói ZIP người dùng trên Desktop hoàn toàn không bị can thiệp.

---

### 2. KẾT QUẢ ĐỐI SOÁT CÁC FINDINGS H1–H5

#### H1: Canonical Hash Contract giữa Java và Python
- **Đánh giá:** Trước đây, Java dùng serializer mặc định của Jackson dẫn đến sai khác thứ tự key và khoảng trắng so với Python. Ở F04, `CatalogImportService.computeSha256` phân tích JSON vào Jackson Tree Node, đệ quy sắp xếp tất cả các field theo alphabet và serialize compact UTF-8; Python `CatalogSyncManager.compute_hash` dùng `separators=(',', ':')` và `sort_keys=True`.
- **Bằng chứng:** Chạy `python docs/reviews/repro/CATALOG_01_F03_probe.py` thu được `match: true` với SHA-256 `4fee21b6c0ef356cf11955d626f13bcdc1d60cf1ffa391c07202b580ada1628c`. Chạy `docs/reviews/repro/CATALOG_01_F04_probe.py` thu được `match: true` (`fc5d19c12fbdaf5837a9e876747caff811dc11ee9795ff133b9f0ae161c01607`).
- **Trạng thái:** **CLOSED**.

#### H2: Candidate Isolation & Atomic Reference Swap
- **Đánh giá:** `sync_index` trong `backend/fastapi/main.py` không còn ghi trực tiếp vào `catalog_sync_manager` toàn cục. Thay vào đó, nó xây dựng candidate manager riêng, kiểm tra token và mã băm `content_hash` trước khi nhận khóa `_publish_lock`. Các yêu cầu bị từ chối (băm sai trả HTTP 400, xung đột cùng generation nhưng khác nội dung trả HTTP 409, thế hệ cũ trả SKIPPED) không làm biến đổi catalog đang phục vụ. Chỉ khi ứng viên xây dựng xong và hybrid index sẵn sàng, tham chiếu mới được hoán đổi nguyên tử (`atomic swap`).
- **Bằng chứng:** Probe `CATALOG_01_F04_probe.py` xác thực candidate isolation (active manager giữ nguyên dữ liệu gốc khi gặp request sai hash 400 và conflict 409). Trạng thái đồng bộ được lưu bền vững vào `data/indices/catalog_sync_state.json` và phục hồi nguyên vẹn sau khi restart.
- **Trạng thái:** **CLOSED**.

#### H3: Phân Định Rõ Ràng File Timeline vs Logical Timeline
- **Đánh giá:** Scene timestamps (`start_ms`, `end_ms`) đã là thời gian file; hàm `handleSeekScene` trong `frontend/app/series/[id]/page.tsx` tua trực tiếp tại `scene.startMs / 1000` và bảo vệ danh tính asset (`scene.mediaAssetId === currentAssetId`). Trong khi đó, `handleSeekSegment` xử lý qua `resolveFileTimestamp` có kiểm tra coverage. Khi `episode_in_ms` là `null`, hàm trả về `null` thay vì ép thành 0; frontend khóa chức năng tua và hiển thị thông báo thay vì tua sai vị trí.
- **Bằng chứng:** `node docs/reviews/repro/CATALOG_01_F03_timestamp_probe.cjs` trả về `unknown_logical_offset: null` khớp với `expected: "unresolved; do not seek"`. Probe `CATALOG_01_F04_probe.py` xác nhận `scene_file_seek_seconds: 90.0`, `logical_resolved_seconds: 90.0`, `unknown_logical_offset_result: null`.
- **Trạng thái:** **CLOSED**.

#### H4: Protected Video Playback Grant & Bounded Drive Safety
- **Đánh giá:** Video được bảo vệ không thể dựa vào `Authorization` header của HTML `<video>`. Hệ thống đã bổ sung cơ chế HMAC-SHA256 Playback Grant (thời hạn 5 phút, gắn với assetId và người dùng đã xác thực). `JwtAuthenticationFilter` hỗ trợ trích xuất `?grant=...` trên endpoint `/api/media/stream/**`. Client lấy grant tự động trước khi gắn URL stream. Tại tầng lưu trữ, `StorageKeyConfig` giới hạn kiểm tra symlink cho local storage; `DriveMediaStorageAdapter` bọc mọi thao tác metadata bên trong `DriveIoExecutor` có timeout.
- **Bằng chứng:** Spring Boot 178 tests pass; frontend build thành công.
- **Trạng thái:** **CLOSED**.

#### H5: Đầy Đủ Bằng Chứng Nghiệm Thu (Evidence Integrity)
- **Đánh giá:** Đã thực hiện kiểm thử độc lập ở mọi tầng:
  - Spring Boot test suite: 178/178 tests pass.
  - FastAPI integration test suite: 12/12 tests pass (132.46s).
  - Frontend static analysis & production build: `tsc --noEmit` và `npm run build` 0 lỗi.
  - Patch `CATALOG_01_F04.patch` vượt qua kiểm tra đảo ngược `git apply --check -R`.
- **Trạng thái:** **CLOSED**.

---

### 3. KẾT LUẬN CUỐI CÙNG
Toàn bộ yêu cầu của nhiệm vụ CATALOG-01-F04 đã được hoàn thành xuất sắc, tuân thủ nghiêm ngặt mọi ràng buộc bảo mật, an toàn dữ liệu và tính bất biến của hợp đồng. Snapshot sẵn sàng bàn giao cho người dùng.
