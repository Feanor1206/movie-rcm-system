# Báo cáo Nghiệm thu Vòng 9 (Round 9 Report)

- **Milestone:** M2 — Catalog Backend và hành trình khám phá hoạt hình
- **Round ID:** 9
- **Prompt Version:** 9
- **Run ID:** `run-round9-20261014-0950`
- **Reviewed Prior Run ID:** `run-round8-20261014-0925` (Codex Review: CHANGES REQUESTED, findings B1–B3)
- **Trạng thái:** `ready_for_review`
- **Thời gian thực hiện:** 2026-10-14 09:50 – 10:05 (khoảng 15 phút)

---

## 1. Mục tiêu và Giải quyết Findings B1–B3

| Finding | Vấn đề từ Review Vòng 8 | Giải pháp và Kết quả Vòng 9 | Trạng thái |
| :--- | :--- | :--- | :--- |
| **B1 (P1)** | Harness browser tự ghi nhận pass bằng text cố định mà không assert DOM/network; ảnh PNG byte-identical do Next standalone thiếu static assets khiến trang unhydrated/unstyled. | 1. Tự động kiểm tra và copy `.next/static` và `public` vào `.next/standalone/`, bảo đảm 100% chunks CSS/JS load thành công (HTTP 200, 0 lỗi 404).<br>2. Bổ sung cơ chế giám sát network và evaluate exceptionDetails qua CDP.<br>3. Mọi bước phải pass assertion DOM cụ thể (selector, text, computed style, activeElement, network/fixture state) mới được ghi nhận và chụp ảnh.<br>4. Bổ sung negative self-check chứng minh harness văng lỗi thoát nonzero khi cố tình thiếu selector hoặc sai postcondition. | **ĐÃ GIẢI QUYẾT** |
| **B2 (P2)** | Fixture server thiếu `/api/auth/me` và `/api/auth/login`, khiến browser chạy ở guest mode chỉ ghi localStorage mà không gọi backend; standalone không đổi runtime env. | 1. Bổ sung `/api/auth/me` và `/api/auth/login` trên fixture server (port 8080).<br>2. Khởi tạo session xác thực chuẩn (`dippie_auth_token` và `dippie_auth_user`) qua production AuthProvider, assert hiển thị user `browser_user` trên UI trước khi thực hiện các thao tác account.<br>3. Kiểm chứng các request `POST /api/users/watchlist` và `POST /api/users/ratings` thực tế gửi tới fixture backend. | **ĐÃ GIẢI QUYẾT** |
| **B3 (P2)** | Tuyên bố `the-last-orbit` là ngoài fixture nhưng ID này có sẵn trong `frontend/lib/data/movies.ts:7`; Profile test không mở tab Đánh giá để assert điểm 9 ở UI. | 1. Chuyển sang canonical ID hoàn toàn synthetic: `m2-synthetic-anim-001` ("The Quantum Garden", year 2026, rating 9.1).<br>2. Thêm assertion tự động xác nhận `m2-synthetic-anim-001` **KHÔNG** tồn tại trong `frontend/lib/data/movies.ts`.<br>3. Trong Test 7 (`m2_journey_suite.mjs`), harness click mở tab "Đánh giá" trên `ProfileOverview` và assert điểm `9/10` được render thực tế trên DOM. | **ĐÃ GIẢI QUYẾT** |

---

## 2. Kết quả Kiểm thử Toàn diện

### 2.1. Negative Self-Check (`node scripts/run_browser_walkthrough.cjs --negative-test`)
- **Lệnh thực thi:** `node scripts/run_browser_walkthrough.cjs --negative-test`
- **Kết quả:** **PASS (Exit code 0)**
- **Nội dung kiểm tra:**
  - Check A: `waitForSelector` với selector cố tình không tồn tại `#non-existent-element-xyz-12345` -> Throws TimeoutError chính xác, không tự báo pass.
  - Check B: `waitForCondition` với điều kiện sai `1 === 2` -> Throws condition failure chính xác.
  - Chứng minh cơ chế assertion của harness có khả năng chặn đứng các lỗi sai hoặc selector thiếu.

### 2.2. Browser Walkthrough Suite (14 Screenshots tại `docs/reports/screenshots/ROUND_9/`)
- **Lệnh thực thi:** `node scripts/run_browser_walkthrough.cjs`
- **Kết quả:** **14/14 BƯỚC ĐẠT ASSERTIONS (Exit code 0)**
- Toàn bộ 14 file ảnh PNG đều có kích thước và hash SHA256 độc lập (zero byte-identical), ghi lại trạng thái thực tế sau khi đã verify DOM.
- File log cấu trúc chi tiết được lưu tại: `docs/reports/screenshots/ROUND_9/walkthrough_evidence.json`.

| STT | Bước kiểm thử | Viewport | DOM & State Assertion | Trạng thái | SHA256 Ảnh mới (ROUND_9) |
| :---: | :--- | :---: | :--- | :---: | :--- |
| **01** | `01_home_desktop` | 1280x800 | Hero hiển thị phim synthetic `The Quantum Garden`, computed style màu thương hiệu `rgb(16, 185, 129)`, navbar hiển thị user `browser_user`. | PASS | `d8b229989a12ac510c8f179e47f4055385b24308ce0cbecba03309b52c657813` |
| **02** | `02_keyboard_focus_desktop` | 1280x800 | Phím Tab kích hoạt focus outline/ring trên thẻ `<a>` tương tác (computed style outline/boxShadow/ring active). | PASS | `feaa184524664723c01119f741cbf668418ac196efc8ad2bb3026e4f4ba2cb22` |
| **03** | `03_detail_desktop` | 1280x800 | URL `/movies/m2-synthetic-anim-001`, hiển thị title "The Quantum Garden", năm 2026, các nút rating 10 sao. | PASS | `a1163107ed8c6745f0c6ae83e876769d01cbb68f8aed0fca574ca490d9fe5ba3` |
| **04** | `04_detail_saved_rated_desktop` | 1280x800 | Click "+ Thêm vào Watchlist" -> UI chuyển sang "Đã lưu Watchlist", fixture backend ghi nhận watchlist. Click star 9 -> fixture backend ghi nhận rating 9. | PASS | `4f18618d6dc636040640900e754418ec4ca872aa27faf499eb9842e4e8ef5d1b` |
| **05** | `05_profile_desktop` | 1280x800 | Mở `/profile`: Watchlist hiển thị card `m2-synthetic-anim-001`. Click tab "Đã chấm điểm" -> DOM render điểm `9/10`. | PASS | `cb006583f2bfae94f00dad9c88ae189896626986b6830d8fba15e3e6c32ed7fd` |
| **06** | `06_search_deep_link_back_desktop` | 1280x800 | Deep link `/search?q=quantum`: draft input giữ "quantum", kết quả hiển thị phim. Navigate tới detail rồi `history.back()` -> URL, draft và kết quả được bảo toàn nguyên vẹn mà không navigate đè. | PASS | `66b69c43bdbdbe6493abb8d9bb68264faccee37266256965babff2083b62eb40` |
| **07** | `07_detail_404_desktop` | 1280x800 | Truy cập ID không tồn tại -> render tiêu đề 404 "Không tìm thấy phim hoạt hình" và nút "Về trang chủ". | PASS | `d67ced13def97e81af798e38085aa0a41b50604cc802bfe81fbc11092c778c40` |
| **08** | `08_search_empty_desktop` | 1280x800 | Tìm từ khóa vô nghĩa -> render banner rỗng "Không tìm thấy bộ phim hoạt hình nào". | PASS | `ab638d5db2516ba418f2b7fcc8a4a07039b4604b9353544632296748da65a157` |
| **09** | `09_catalog_error_desktop` | 1280x800 | Backend HTTP 500 fault -> render banner lỗi "Không thể nạp danh mục hoạt hình" kèm nút "Thử kết nối lại". | PASS | `3b7a351755b911dddfbd34152dcce9a2b694ecfc9059a909465d494a604746cc` |
| **10** | `10_hero_uncertain_retry_desktop` | 1280x800 | Hero save khi đứt kết nối + reconcile lỗi -> hiển thị badge hổ phách "Chưa xác nhận" và nút "Thử lưu lại". Sau khi phục hồi kết nối, bấm retry -> chuyển thành công sang "Đã lưu Watchlist". | PASS | `3e37de8772a94871e0ebecdb7dddf7f0d33bb5c5762af11a82739d80d1eee562` |
| **11** | `11_home_mobile` | 375x667 | Viewport mobile 375px, hero banner co giãn responsive, menu navbar tương thích màn hình nhỏ. | PASS | `ed205039dd8e0cab716cd394560d8d13f338156df688541c2daf7af3c840ec92` |
| **12** | `12_detail_mobile` | 375x667 | Chi tiết phim hiển thị layout cột xếp chồng poster/metadata, nút hành động full-width. | PASS | `a2cbf98e9c53bc30329cd4c6db4b893fbae772a5fd2159256ad9412f36ed4853` |
| **13** | `13_search_mobile` | 375x667 | Ô tìm kiếm mobile co giãn vừa màn hình 375px, lưới card phim hiển thị responsive. | PASS | `37b4a033e3ffa5fc87c59469c831296d61127adf39c419be7ad77921fb20dabb` |
| **14** | `14_profile_mobile` | 375x667 | Thanh tab thư viện co giãn responsive, card phim và thông tin người dùng hiển thị sạch sẽ. | PASS | `eff94e16579a58137a917f2c424771f5291d7537fbf28e2ec38528481ae0f5c9` |

### 2.3. Bốn Test Suites Frontend (`node --test frontend/tests/*.mjs`)
- **Kết quả:** **54/54 PASS** (0 fail, 0 skipped, thời gian chạy: ~1.7 giây).
  - `catalog_client_suite.mjs`: 9/9 PASS.
  - `m1_resilience_suite.mjs`: 25/25 PASS.
  - `m2_journey_suite.mjs`: 8/8 PASS (bao gồm Test 7 synthetic ID + Profile rating UI assertion, và Test 8 Hero uncertain retry).
  - `search_experience_suite.mjs`: 12/12 PASS.

### 2.4. TypeScript Check (`npx tsc --noEmit`)
- **Kết quả:** **Exit code 0** (zero errors).

### 2.5. Preview Catalog Dry-run Tests (`node scripts/preview_animation_catalog.cjs --test`)
- **Kết quả:** **3/3 PASS** (First run ADD, Idempotent SKIP, Conflict detection).

### 2.6. Patch Integrity Checks
- `git apply --check -R docs/reports/ROUND_9.patch`: **Exit code 0**
- `git apply --numstat docs/reports/ROUND_9.patch`:
  ```
  63   28   frontend/tests/m2_journey_suite.mjs
  694  144  scripts/run_browser_walkthrough.cjs
  ```

---

## 3. Ranh giới Phạm vi và Tuyên bố Mock vs Spring Real

1. **Phạm vi M2:** Toàn bộ công việc Vòng 9 tập trung giải quyết triệt để 3 findings B1, B2, B3 về verification harness, asset pipeline, authenticated fixture session và DOM assertions. Không sửa đổi logic ứng dụng production (D1–D3 đã được nghiệm thu từ trước).
2. **Mock Fixture Server:** Fixture server trong `scripts/run_browser_walkthrough.cjs` đóng vai trò transport giả lập chuẩn theo contract REST (`/api/auth/*`, `/api/movies/*`, `/api/users/*`). Không kết nối tới cơ sở dữ liệu live của Spring Boot hay PostgreSQL.
3. **Qwen AI / M3 Scope Boundary:** Không đụng tới module CineBot Qwen AI, không gọi GPU/Ollama, không bật Docker services live, không mở phạm vi sang M3.
4. **Git Discipline:** Không thực hiện bất kỳ lệnh `git commit`, `git push`, hoặc `git reset`. Working directory giữ nguyên vẹn ngoài các file bàn giao theo quy định.

---

## 4. Danh mục File Bàn giao Vòng 9

1. `docs/reports/ROUND_9_REPORT.md` (Báo cáo này)
2. `docs/reports/ROUND_9.patch` (Patch diff của các file mã nguồn test/script)
3. `docs/reports/ROUND_9_MANIFEST.json` (Bảng mã hash SHA256 và kích thước của 17 file do Vòng 9 tạo/sửa)
4. `docs/reports/screenshots/ROUND_9/` (Thư mục 14 ảnh chụp mới và file bằng chứng JSON `walkthrough_evidence.json`)
5. `docs/reports/M2_M3_STATUS.json` (`state: "ready_for_review"`, `promptVersion: 9`, `roundId: 9`)
6. `docs/reports/M2_M3_WORKLOG.md` (Cập nhật lịch sử vòng làm việc)
