# BIÊN BẢN NGHIỆM THU SẢN PHẨM (PRODUCT ACCEPTANCE): CATALOG-01-F04

**Phiên bản bàn giao:** `CATALOG-01-F04-CHECKPOINT-01`  
**Dự án:** Hệ Thống Gợi Ý & Trình Chiếu Hoạt Hình Dippie Cinema  
**Workspace:** `D:\Class\movie-rcm-system` (Nhánh `dev`)  
**Baseline Commit:** `d620bfc634b3c424a847408f0dc6e02626439f45`  
**Ngày nghiệm thu:** 2026-10-17  

---

### 1. BẢO TOÀN HỢP ĐỒNG DỮ LIỆU & RÀNG BUỘC PHÁP LÝ
- **Hợp đồng dippie.catalog.v1:** Giữ nguyên 100% 5 tệp hợp đồng giao tiếp (`dippie.catalog.v1.schema.json`, `catalog.example.json`, `catalog.blank.json`, `validate_catalog.py`, `README.md`).
- **Gói ZIP người dùng:** Tuyệt đối không can thiệp hoặc thay đổi các tệp ngoài phạm vi.
- **Dữ liệu thật:** Không sửa đổi, nới lỏng schema hoặc bịa đặt siêu dữ liệu/đánh giá/trạng thái xác thực.
- **An toàn môi trường:** Không chạm vào Live DB, không can thiệp nội dung Google Drive, không đổi OAuth scopes.

---

### 2. KẾT QUẢ NGHIỆM THU THEO LUỒNG SẢN PHẨM THỰC TẾ (P1 – P4)

#### Luồng P1: Quản Trị Viên Nhập Dữ Liệu Catalog
- **Đăng nhập & Tải JSON:** Trang quản trị `/admin/import` tiếp nhận JSON hợp lệ theo chuẩn `dippie.catalog.v1`.
- **Xem trước (Preview):** Hệ thống thực thi dry-run, tính toán diffs thực tế giữa catalog hiện tại và catalog mới, tính mã băm canonical SHA-256 thống nhất.
- **Nhập dữ liệu (Import):** Giao dịch nguyên tử ghi vào 12 bảng cơ sở dữ liệu (`catalog_*`).
- **Đồng bộ Outbox sang AI Index:** Scheduled worker (`CatalogSyncWorker`) gửi dữ liệu sang FastAPI qua HTTP nội bộ kèm token bí mật.
- **Xác thực Canonical Hash & CAS:** Mã băm SHA-256 tính từ Java và Python trùng khớp 100% từng byte (`match: true`). FastAPI áp dụng thuật toán Compare-And-Swap (CAS), khóa luồng `_publish_lock`, cách ly ứng viên `candidate_manager` độc lập, chỉ cập nhật khi mọi bước thành công.
- **Kết quả:** Trạng thái outbox chuyển sang `READY` với đúng `generation` và `content_hash`.

#### Luồng P2: Tìm Kiếm Đa Tầng & Trò Chuyện CineBot
- **Tìm kiếm đa cấp độ:** Người dùng tìm kiếm bộ phim (`series`), tập phim (`episode`), đoạn phim (`segment`) hoặc phân cảnh cụ thể (`scene`).
- **Bộ lọc cứng & Quyền phát hành:** Đảm bảo chỉ các mục có `record.status == 'ready'` mới được hiển thị cho người dùng thông thường; bản nháp (`draft`) bị loại bỏ hoàn toàn khỏi public search.
- **Grounded AI Discovery:** Phản hồi của CineBot được kiểm chứng thực tế bám sát `plot_facts`, `characters` và các mốc thời gian phân cảnh.

#### Luồng P3: Trình Phát Video & Tua Thời Gian Chính Xác
- **Xác thực media bảo vệ (Protected Video Playback Grant):** Video có chính sách `authenticated` hoặc `private` được tự động cấp token grant ngắn hạn (5 phút, HMAC-SHA256) thông qua `POST /api/media/grant/{assetId}` và truyền qua `?grant=...` vào trình phát `<video>`, khắc phục hoàn toàn hạn chế header của thẻ video HTML5.
- **Tua phân cảnh (Scene File Timeline):** Khi người dùng bấm vào phân cảnh, trình phát tua trực tiếp tại `scene.startMs / 1000`, bảo đảm không cộng offset lần 2.
- **Tua đoạn phim (Segment Logical Timeline):** Ánh xạ qua `coverageJson`. Nếu có thông tin, tua chính xác; nếu `episode_in_ms` chưa xác định (`null`), hệ thống hiển thị thông báo thân thiện và khóa tua thay vì nhảy về 0s.

#### Luồng P4: Tính Bền Vững & Khôi Phục Sau Khi Khởi Động Lại (Restart Durability)
- **FastAPI:** Trạng thái đồng bộ (`generation`, `content_hash`, snapshot payload) được lưu trữ bền vững tại `data/indices/catalog_sync_state.json`. Khi restart, hệ thống tự động nạp lại và phục hồi hybrid index.
- **Spring Boot:** Khi restart, `ApplicationReadyEvent` quét các bản ghi `SYNCING` mồ côi và chuyển về `PENDING` để tái đồng bộ an toàn.
- **Tính đơn điệu của thế hệ:** Cơ chế ràng buộc cơ sở dữ liệu ngăn chặn trùng lặp thế hệ.

---

### 3. TỔNG HỢP CÁC BẰNG CHỨNG KIỂM THỬ MÁY (MACHINE EVIDENCE)

1. **Spring Boot Integration & Unit Tests:**
   - Số lượng: 178 tests.
   - Kết quả: `Tests run: 178, Failures: 0, Errors: 0, Skipped: 0` (`BUILD SUCCESS`).
2. **FastAPI AI & Endpoints Integration Tests:**
   - Số lượng: 12 tests (`test_catalog_retrieval.py`).
   - Thời gian chạy: 132.46s.
   - Kết quả: `Ran 12 tests in 132.461s - OK`.
3. **Frontend Static Typing & Production Build:**
   - Typecheck: `npx tsc --noEmit` -> 0 errors.
   - Build: `npm run build` -> 100% biên dịch thành công cho toàn bộ 8 routes.
4. **Repro Probes Độc Lập:**
   - `docs/reviews/repro/CATALOG_01_F03_probe.py`: `match: true`.
   - `docs/reviews/repro/CATALOG_01_F03_timestamp_probe.cjs`: `actual_seconds: null` (unresolved).
   - `docs/reviews/repro/CATALOG_01_F04_probe.py`: Toàn bộ 5 hạng mục H1, H2, H3, H4, Durability ĐẠT (`PASSED`).
5. **Đảo Ngược Toàn Vẹn Patch:**
   - `git apply --check -R docs/reports/CATALOG_01_F04.patch` -> Exit code 0.
6. **Bảng Kê Toàn Vẹn Manifest:**
   - `docs/reports/CATALOG_01_F04_MANIFEST.json` ghi nhận 112 tệp với SHA-256 đối chiếu từng tệp.

---

### 4. QUYẾT ĐỊNH BÀN GIAO
Snapshot **CATALOG-01-F04** hoàn toàn đáp ứng toàn bộ các tiêu chí kỹ thuật, nghiệp vụ và độ tin cậy vận hành, được chính thức phê duyệt nghiệm thu bàn giao (**ACCEPTED**).
