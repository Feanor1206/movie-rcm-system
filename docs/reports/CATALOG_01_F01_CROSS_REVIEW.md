# BIÊN BẢN ĐÁNH GIÁ CHÉO ĐỘC LẬP: CATALOG-01-F01
## Đánh Giá Chất Lượng Triển Khai, Bảo Toàn Schema Và Khả Năng Vận Hành

**Người thực hiện đánh giá:** Independent Reviewer Role  
**Dự án:** Movie Recommendation & Streaming System  
**Nhiệm vụ:** CATALOG-01-F01 — Sửa toàn bộ findings C1–C10  
**Ngày đánh giá:** 2026-10-16  
**Kết luận tổng thể:** **CHẤP THUẬN (APPROVED / PASS)**

---

### 1. Kiểm tra tính toàn vẹn của Hợp đồng dữ liệu (Contract Invariance)

- **Mục tiêu:** Tuyệt đối không sửa đổi `dippie.catalog.v1.schema.json`, không sửa các tệp mẫu hợp đồng (`catalog.example.json`, `catalog.blank.json`), không sửa validator chuẩn `validate_catalog.py`.
- **Xác minh qua Git:**
  ```powershell
  git status --short docs/contracts/animation-catalog-v1/
  ```
  *Kết quả:* Không có bất kỳ tệp nào trong `docs/contracts/animation-catalog-v1/` bị thay đổi. Toàn bộ thư mục contract giữ nguyên 100% so với baseline.
- **Đánh giá:** **ĐẠT**. Đội ngũ phát triển đã tuân thủ nghiêm ngặt nguyên tắc coi contract là nguồn sự thật duy nhất, không nới lỏng schema để che giấu lỗi.

---

### 2. Đánh giá bảo mật và kiểm soát truy cập (Findings C1, C2)

- **Bảo mật Admin Controller:**
  - `AdminCatalogController.java` đã được bảo vệ kép: cấu hình cấp URL trong `SecurityConfig` (`/api/admin/**` yêu cầu `hasRole("ADMIN")`) và cấp phương thức qua `@PreAuthorize("hasRole('ADMIN')")`.
  - Frontend `catalogService.ts` đã truyền đúng `Authorization: Bearer <token>` lấy từ phiên đăng nhập.
- **Bảo mật Đồng bộ Chỉ mục FastAPI:**
  - Endpoint `/api/index/sync` yêu cầu header bí mật `X-Service-Token`. Các cuộc gọi không có token bị trả về HTTP 401; sai token bị trả về HTTP 403. Đã loại bỏ hoàn toàn tham số đường dẫn tệp đĩa `catalog_path` để ngăn chặn SSRF/LFI.
- **Danh sách trắng Storage Key:**
  - `StorageKeyConfig.java` triển khai kiểm tra allowlist chặt chẽ cho cả nhà cung cấp `local` và `drive`.
  - Xử lý lỗi ổ đĩa Windows không mount được (`X:`) một cách an toàn mà không làm sập ứng dụng.
- **Đánh giá:** **ĐẠT**.

---

### 3. Đánh giá tính chuẩn xác của Trình Xác Thực (Findings C3, C5)

- **Xác thực JSON Schema Draft 2020-12:**
  - `CatalogValidator.java` xử lý toàn diện các từ khóa JSON Schema: `$ref`, `allOf`, `not`, `anyOf`, `const`, `enum`, `type`, `pattern`, `minLength`, `minimum`, `maximum`, `required`, và `additionalProperties: false`.
  - Báo lỗi chính xác vị trí theo JSON Pointer Path (ví dụ: `/episodes/0/title`, `/series/0/unknown_field`).
  - Đã khắc phục triệt để các mã lỗi: `MISSING_REQUIRED_KEY`, `UNKNOWN_FIELD`, `PATH_TRAVERSAL`, `DUPLICATE_ID`, `BROKEN_REFERENCE`, `INVALID_INTERVAL`, `UNSORTED_CUES`.
- **Khớp chuẩn Contract Probe:**
  - Thực thi `python docs/reviews/repro/CATALOG_01_contract_probe.py`: 8/8 kịch bản kiểm tra khớp 100% với `validate_catalog.py`, bao gồm cả đối tượng bí danh đa ngôn ngữ và phân đoạn có mốc thời gian null.
- **Đánh giá:** **ĐẠT**.

---

### 4. Đánh giá CSDL, Giao Dịch và Phòng Chống Xung Đột (Findings C4, C6, C7)

- **DDL và Mô hình Thực thể JPA:**
  - 12 bảng thực thể và bảng snapshot outbox `catalog_snapshots` đã được khai báo hoàn chỉnh trong `schema.sql`.
  - Cột `raw_json` lưu trữ nguyên vẹn dữ liệu gốc, ngăn ngừa tình trạng mất mát thông tin khi mở rộng schema.
  - Cột `opt_lock_version` kết hợp `@Version` bảo vệ ứng dụng khỏi xung đột cập nhật đồng thời (Lost Updates).
- **Xem trước khác biệt & Kiểm soát Revision:**
  - `validateAndPreview()` tính toán đúng số lượng `toCreate`, `toUpdate`, `unchanged`, `conflicts` dựa trên SHA-256 và revision.
  - Chặn đứng hành vi ghi đè dữ liệu cũ khi revision thấp hơn (`CatalogConflictException`).
  - Chặn sửa đổi nội dung trên cùng một revision mà mã băm khác nhau.
  - Cho phép re-import idempotent nếu cùng revision và cùng mã băm.
  - Sửa lỗi ternary unboxing NPE trong Java bằng các hàm helper an toàn `getIntOrNull` và `getLongOrNull`.
- **Đánh giá:** **ĐẠT**.

---

### 5. Đánh giá Giao Diện Web & Tìm Kiếm (Findings C8, C9)

- **Deep Linking Phân Cảnh:**
  - Đường ray tìm kiếm tạo liên kết đầy đủ: `/series/{seriesId}?episode={epId}&scene={scId}&asset={assetId}&t={startMs}`.
  - Trang `/series/[id]` đọc tham số URL và tự động chọn đúng bộ, tập, nguồn media và tua video đến đúng mốc thời gian phân cảnh.
- **Triệt tiêu Race Condition khi chuyển tập:**
  - Đã bổ sung `AbortController` và generation counter `episodeGenRef`. Khi người dùng chuyển tập liên tục, dữ liệu tập cũ bị hủy và xóa ngay lập tức, không để lại phân cảnh của tập trước.
- **Đồng bộ Nguồn Phát khi Tua Cảnh:**
  - Khi nhấp vào phân cảnh, nếu `scene.mediaAssetId` khác với `selectedAsset.id`, hệ thống tự động hoán đổi `selectedAsset` sang đúng video tương ứng của phân cảnh đó trước khi seek.
- **Khả năng tiếp cận & Trải nghiệm người dùng:**
  - Loại bỏ hoàn toàn lỗi button-in-button click trap.
  - Bổ sung `role="button"`, `tabIndex={0}`, và trình lắng nghe phím Enter/Space cho người dùng khiếm thị hoặc dùng bàn phím.
- **Đánh giá:** **ĐẠT**.

---

### 6. Bảng Tổng Hợp Kiểm Thử Chéo

```
======================================================================
1. Spring Boot Tests:
   - CatalogValidatorTest:      9/9 PASS  [Time: 0.46s]
   - CatalogImportServiceTest:  6/6 PASS  [Time: 11.46s]
   -> Total: 15/15 PASS (0 failures, 0 errors)

2. Python Contract Probe:
   - CATALOG_01_contract_probe.py: 8/8 cases MATCHED (0 exceptions)

3. FastAPI Retrieval & NLU Tests:
   - test_catalog_retrieval.py: 12/12 PASS [Time: 40.31s]
   -> Total: 12/12 PASS (0 failures, 0 errors)

4. Frontend TypeScript Validation:
   - npx tsc --noEmit: 0 errors (Exit code: 0)
======================================================================
```

**KÝ TÊN XÁC NHẬN:**  
Đánh giá chéo độc lập: **PASSED / SẴN SÀNG BÀN GIAO**
