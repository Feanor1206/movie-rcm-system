# BIÊN BẢN NGHIỆM THU SẢN PHẨM (PRODUCT ACCEPTANCE): CATALOG-01-F05

**Phiên bản bàn giao:** `CATALOG-01-F05-CHECKPOINT-01`  
**Dự án:** Hệ Thống Gợi Ý & Trình Chiếu Hoạt Hình Dippie Cinema  
**Workspace:** `D:\Class\movie-rcm-system` (Nhánh `dev`)  
**Baseline Commit:** `d620bfc634b3c424a847408f0dc6e02626439f45`  
**Ngày nghiệm thu:** 2026-10-17  
**Quyết định nghiệm thu:** **CHẤP THUẬN TOÀN BỘ (ACCEPTED - PASS 100%)**

---

### 1. BẢO TOÀN HỢP ĐỒNG DỮ LIỆU & RÀNG BUỘC PHÁP LÝ
- **Hợp đồng dippie.catalog.v1:** Giữ nguyên 100% 5 tệp hợp đồng giao tiếp (`dippie.catalog.v1.schema.json`, `catalog.example.json`, `catalog.blank.json`, `validate_catalog.py`, `README.md`).
- **Gói ZIP người dùng:** Tuyệt đối không can thiệp hoặc thay đổi các tệp ngoài phạm vi bàn giao.
- **Dữ liệu thật:** Không sửa đổi, nới lỏng schema hoặc bịa đặt siêu dữ liệu/đánh giá/trạng thái xác thực.
- **An toàn môi trường:** Không chạm vào Live DB, không can thiệp nội dung Google Drive, không đổi OAuth scopes. Toàn bộ probe chạy độc lập trên môi trường cách ly (hermetic).

---

### 2. KẾT QUẢ NGHIỆM THU THEO LUỒNG SẢN PHẨM THỰC TẾ (P1 – P5)

#### Luồng P1: Quản Trị Viên Nhập Dữ Liệu Catalog
- **Đăng nhập & Tải JSON:** Trang quản trị `/admin/import` tiếp nhận JSON hợp lệ theo chuẩn `dippie.catalog.v1`.
- **Xem trước (Preview):** Hệ thống thực thi dry-run, tính toán diffs thực tế giữa catalog hiện tại và catalog mới, tính mã băm canonical SHA-256 thống nhất.
- **Nhập dữ liệu (Import):** Giao dịch nguyên tử ghi vào 12 bảng cơ sở dữ liệu (`catalog_*`).
- **Đồng bộ Outbox sang AI Index:** Scheduled worker (`CatalogSyncWorker`) gửi dữ liệu sang FastAPI qua HTTP nội bộ kèm token bí mật.
- **Kết quả:** Trạng thái outbox chuyển sang `READY` với đúng `generation` và `content_hash`.

#### Luồng P2: Đồng Bộ Worker & Canonical Hash Protocol
- **Mã băm chuẩn hóa (Canonical Hash):** Thuật toán `formatDouble` của Java Jackson và `json.dumps` của Python cho kết quả băm SHA-256 trùng khớp 100% trên cả 10/10 Golden Vectors (từ số mũ khoa học nhỏ `1e-08`, số âm không `-0.0`, đến ký tự tiếng Việt có dấu và mảng lồng nhau).
- **Compare-And-Swap (CAS):** FastAPI khóa luồng `_publish_lock`, dựng candidate index độc lập, lưu trạng thái đĩa bền vững trước khi hoán đổi con trỏ index active. Nếu lưu đĩa thất bại (500), active state được giữ nguyên 100% không bị ô nhiễm.

#### Luồng P3: Tìm Kiếm Đa Tầng & Tách Biệt Hệ Thời Gian Tua Video
- **Tìm kiếm đa cấp độ:** Người dùng tìm kiếm bộ phim (`series`), tập phim (`episode`), đoạn phim (`segment`) hoặc phân cảnh cụ thể (`scene`).
- **Tua phân cảnh (Scene File Timeline):** Tua trực tiếp tại `scene.startMs / 1000`, bảo đảm không cộng offset lần 2.
- **Tua đoạn phim (Segment Logical Timeline):** Ánh xạ qua `coverageJson`. Nếu có thông tin, tua chính xác; nếu `episode_in_ms` chưa xác định (`null`), hệ thống hiển thị thông báo thân thiện và khóa tua thay vì nhảy về 0s.

#### Luồng P4: Bảo Mật Phát Video Công Khai & Video Protected Qua Playback Grant
- **Tài nguyên công khai (`public`):** Phát trực tiếp qua byte-range HTTP 206 kèm `Cache-Control: public, max-age=3600`.
- **Tài nguyên bảo vệ (`protected`):** Frontend tự động gọi `POST /api/media/grant/{assetId}` để nhận Playback Grant Token ngắn hạn (5 phút).
- **Khóa phạm vi bảo mật (R1):** Playback Grant bị từ chối tuyệt đối khi dùng làm Bearer token trên endpoint quản trị (`/api/admin/...`), bị từ chối khi dùng để stream asset khác, và từ chối nếu tài khoản bị khóa hoặc vô hiệu hóa.

#### Luồng P5: Tính Bền Vững & Khôi Phục Sau Khi Khởi Động Lại (Restart Durability)
- **FastAPI:** Trạng thái đồng bộ (`generation`, `content_hash`, snapshot payload) được lưu trữ bền vững tại `data/indices/catalog_sync_state.json`. Khi restart, hệ thống tự động nạp lại và phục hồi hybrid index.
- **Spring Boot:** Khi restart, `ApplicationReadyEvent` quét các bản ghi `SYNCING` dở dang và chuyển về `PENDING` để tái đồng bộ an toàn.
- **Tính đơn điệu của thế hệ:** Cơ chế ràng buộc cơ sở dữ liệu ngăn chặn trùng lặp thế hệ.

---

### 3. TỔNG HỢP CÁC BẰNG CHỨNG KIỂM THỬ MÁY (MACHINE EVIDENCE)

1. **Spring Boot Integration & Unit Tests:**
   - Số lượng: 178 tests.
   - Kết quả: `Tests run: 178, Failures: 0, Errors: 0, Skipped: 0` (`BUILD SUCCESS`).
2. **FastAPI AI & Endpoints Integration Tests:**
   - Số lượng: 12 tests (`test_catalog_retrieval.py`).
   - Thời gian chạy: 137.99s.
   - Kết quả: `Ran 12 tests in 137.988s - OK`.
3. **Frontend Static Typing & Production Build:**
   - Typecheck: `npx tsc --noEmit` -> 0 errors.
   - Build: `npm run build` -> 100% biên dịch thành công cho toàn bộ 8 routes.
4. **F04 Independent Probe:**
   - `docs/reviews/repro/CATALOG_01_F04_independent_probe.py`: 100% PASS (grant isolation, numeric hash, durable failure isolation).
5. **F05 Rehearsal Suite & Golden Vectors:**
   - `docs/reviews/repro/CATALOG_01_F05_rehearsal.py`: 10/10 Golden Vectors matched, 11/11 Playback Grant Matrix checks passed, Candidate Isolation and Atomic Rollback passed, P1-P5 flows passed (`OVERALL STATUS: PASSED`).
6. **Đảo Ngược Toàn Vẹn Patch:**
   - `git apply --check -R docs/reports/CATALOG_01_F05.patch` -> Exit code 0.
7. **Bảng Kê Toàn Vẹn Manifest:**
   - `docs/reports/CATALOG_01_F05_MANIFEST.json` ghi nhận toàn bộ tệp với SHA-256 và kích thước bytes tương ứng.

---

### 4. QUYẾT ĐỊNH BÀN GIAO
Snapshot **CATALOG-01-F05** đạt 100% tiêu chuẩn chất lượng tại tất cả các gate kỹ thuật, hoàn toàn đóng toàn bộ các findings R1–R6 và hoàn thiện luồng sản phẩm P1–P5. Phê duyệt bàn giao chính thức (**ACCEPTED**).
