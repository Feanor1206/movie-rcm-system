# Báo cáo Nghiệm thu Milestone M3 — Vòng 11 (Round 11 Report)

- **Milestone:** M3 — Web nhẹ, dễ dùng và vận hành rõ ràng
- **Nhánh thực hiện:** `dev`
- **Round ID:** 11
- **Prompt Version:** 11
- **Run ID:** `run-round11-20261014-1140`
- **Reviewed Prior Run ID:** `run-round10-20261014-1015` (Codex Review: CHANGES REQUESTED, R1–R4 findings)
- **Trạng thái:** `ready_for_review`
- **Thời gian thực hiện:** 2026-10-14 11:15 – 11:45 (~30 phút)

---

## 1. Tổng quan Sửa đổi R1–R4

Vòng 11 tập trung giải quyết triệt để 4 nhóm phát hiện kỹ thuật (R1–R4) từ `docs/reviews/LOOP_ROUND_10_REVIEW.md`, đảm bảo toàn bộ hành vi M1/M2 được giữ nguyên, theme xanh lá chuẩn và không can thiệp vào AI/GPU/DB live:

### R1 — CI Đáng tin cậy trên nhánh `dev`
- **Sửa tên suite chính xác:** Sửa đường dẫn file trong `.github/workflows/ci.yml` từ tên cũ sang tên chính thức: `frontend/tests/catalog_service_suite.mjs` và `frontend/tests/m1_behavior_suite.mjs`.
- **Đồng bộ entrypoint qua `package.json`:** Bổ sung script `"test"` trong `frontend/package.json` thực thi tuần tự cả 5 test suites (`catalog_service_suite.mjs`, `m1_behavior_suite.mjs`, `m2_journey_suite.mjs`, `search_experience_suite.mjs`, `modal_a11y_suite.mjs`). Cập nhật CI chạy trực tiếp qua `npm test`.
- **Branch Triggers:** Thêm nhánh `dev` vào danh sách kích hoạt cả `push` và `pull_request` trong `.github/workflows/ci.yml`.
- **Ràng buộc môi trường:** Giữ nguyên Node 20 trên CI và Spring Boot Java 17 target bytecode (chạy trên JDK 25 local). Không thêm bất kỳ deploy hay GPU job nào.

### R2 — Tách biệt Production Seed, Cấu hình Secrets và Rollback Bảo toàn Dữ liệu
- **Loại bỏ demo seed khỏi base Compose:** Xóa bỏ mount `01_seed_movies.sql` và `02_seed_50_users.sql` khỏi service postgres trong `infrastructure/docker-compose.yml`.
- **Tham số hóa secrets:** Thay thế toàn bộ mật khẩu hardcoded trong `docker-compose.yml` bằng `${SPRING_DATASOURCE_PASSWORD}` và bắt buộc `${APP_JWT_SECRET}`.
- **Tạo Compose Override cho Dev:** Tạo `infrastructure/docker-compose.dev.yml` phục vụ lập trình viên với demo seeds opt-in và mật khẩu mặc định an toàn cho local.
- **Mẫu cấu hình an toàn & Whitelist:** Tạo `infrastructure/.env.example` với các placeholder không chứa secret thật; bổ sung rule whitelist `!.env.example` vào `.gitignore`.
- **Chính sách Rollback Không Mất Dữ liệu:** Loại bỏ lệnh `DROP TABLE` nguy hiểm khỏi `docs/runbooks/db/schema_v1.sql` và `docs/runbooks/OPERATIONS_RUNBOOK.md`. Quy định rõ nguyên tắc forward additive migration và runbook khôi phục cấu hình/code giữ nguyên dữ liệu thực.
- **Seed & Config Policy Test:** Cập nhật `SeedAndConfigPolicyTest.java` (4 tests PASS):
  1. Kiểm tra cấu hình mặc định từ YAML thực tế: `app.seed.enabled: false`, `spring.sql.init.mode: never`, `ddl-auto: validate`.
  2. Kiểm tra `DataInitializer` bean không tự tạo tài khoản demo người dùng khi chạy mặc định.
  3. Kiểm tra khởi động context thất bại khi thiếu `app.jwt.secret` (placeholder resolution error).
  4. Kiểm tra khởi động context thất bại khi thiếu `spring.datasource.password`.

### R3 — Hoàn thiện A11y Modals, Touch Targets và Reduced Motion
- **`AuthModal.tsx`:**
  - Nút đóng tăng kích thước lên $\ge 44 \times 44$px (`h-11 w-11 min-h-[44px] min-w-[44px]`).
  - Bảo vệ `openerRef`: chỉ lưu phần tử kích hoạt mở modal ban đầu, không cho phép effect hoặc re-render ghi đè thành các phần tử con bên trong modal trong quá trình nhập liệu hoặc submit thất bại.
  - Bẫy phím Tab xử lý chính xác khi focus trôi ra ngoài dialog.
- **`MovieDetail.tsx` (Video Player Modal & Action Buttons):**
  - Đặt initial focus tự động vào phần tử đầu tiên trong dialog khi mở video player modal.
  - Khóa focus Tab/Shift+Tab bên trong player dialog.
  - Phím Escape đóng dialog và phục hồi focus chính xác về nút "Xem trailer / giới thiệu".
  - Chuẩn hóa kích thước touch target: Trailer button (`min-h-[44px]`), Watchlist button (`min-h-[44px]`), Favorite button (`min-h-[44px] min-w-[44px]`), Ask CineBot button (`min-h-[44px]`).
- **`CineBot.tsx` & Floating Trigger:**
  - `scrollToBottom`: Kiểm tra media query `(prefers-reduced-motion: reduce)`, tự động chuyển `behavior: 'auto'` thay vì `'smooth'` khi người dùng bật giảm chuyển động.
  - Phím Escape và nút đóng phục hồi focus về opener ban đầu.
  - Nút icon trong header dialog đạt touch target $\ge 44 \times 44$px.
  - `CineBotFloatingTrigger`: Định vị an toàn với responsive classes `bottom-4 right-4 sm:bottom-6 sm:right-6`, kích thước $\ge 44 \times 44$px.
- **Tạo Suite Kiểm thử A11y:** Bổ sung `frontend/tests/modal_a11y_suite.mjs` kiểm tra toàn bộ lifecycle, focus trapping, reduced motion policy và kích thước touch targets cho cả 3 dialogs (3/3 tests PASS).

### R4 — Bằng chứng Browser E2E và Đo lường Hiệu năng Thực tế
- **Thư mục đầu ra riêng biệt:** Toàn bộ screenshots và dữ liệu đo đạc được lưu tại `docs/reports/screenshots/ROUND_11/`, bảo toàn nguyên vẹn thư mục `ROUND_10/` đã đóng băng.
- **Fixture Backend Server:** Hỗ trợ trường `usernameOrEmail` trong payload login, trả về HTTP 401 khi nhận thông tin đăng nhập không hợp lệ (`codex_invalid` / `not-real-password`).
- **Xác thực User B qua Form UI Thật:**
  - User A đăng xuất bằng cách click trực tiếp vào menu avatar -> click "Đăng xuất" (không dùng fallback xóa `localStorage`).
  - Kiểm tra trạng thái Guest sạch và token trong `localStorage` bị xóa hoàn toàn.
  - User B đăng nhập bằng cách click "Đăng nhập" trên Navbar -> điền form với `user_b` / `password123` qua dispatch event chuẩn của React -> submit -> xác nhận modal đóng và Navbar hiển thị `user_b`.
- **Kiểm tra Session Persistence & Data Isolation (Step 08):**
  - Kiểm tra Profile của User B hoàn toàn trống, không rò rỉ phim "The Quantum Garden" của User A.
  - Reload trang và kiểm chứng session cùng store state của User B vẫn duy trì nguyên vẹn sau refresh.
- **Kiểm định Va chạm Mobile (Mobile Collisions & Touch Bounds - Step 14):**
  - Kiểm tra kích thước thực tế trên viewport 375x667: Nút Trailer (44px), Nút Watchlist (44px), Nút CineBot Floating Trigger (44px).
  - Thuật toán đo bounding box giao nhau xác nhận **0 va chạm (Zero Collisions)** giữa trigger CineBot nổi và các nút tương tác khác trên trang.
- **Đo lường Hiệu năng Tự động 3 Lần (Step 15):**
  - Thực hiện benchmark tự động 3 lần (1 cold, 2 warm) trên 4 route chính (`/`, `/search?q=quantum`, `/movies/m2-synthetic-anim-001`, `/profile`).
  - Thu thập đầy đủ các chỉ số: DOMContentLoaded, Load duration, First Contentful Paint (FCP), Largest Contentful Paint (LCP), Cumulative Layout Shift (CLS), Request Count, Total Transfer Bytes.
  - Chỉ số INP được ghi rõ là `unavailable` (chưa hỗ trợ đo tự động trong harness headless).
  - Kết quả lưu tại `docs/reports/screenshots/ROUND_11/perf_measurements.json`.

---

## 2. Bảng Số liệu Đo lường Hiệu năng Thực tế (Performance Measurement)

### Điều kiện đo lường chuẩn hóa:
- **Framework & Build:** Next.js 15.1.2 (Standalone Production Build, Next compiler).
- **Môi trường:** Node.js v26.1.0, Chrome Headless qua CDP (Chrome DevTools Protocol).
- **Mạng:** Local Loopback qua HTTP Fixture Server (127.0.0.1:8080).
- **Viewport:** Desktop 1280x800.
- **Phương pháp lấy mẫu:** 3 lần chạy tuần tự cho mỗi route (Lần 1: Cold navigation; Lần 2 & 3: Warm navigation). Báo cáo giá trị Trung vị (Median) và Dải biến thiên (Range: Min – Max).

### Kết quả Đo đạc Chi tiết:

| Route | DOMContentLoaded (Median / Range) | Load Duration (Median / Range) | FCP (Median / Range) | LCP (Median / Range) | CLS (Median) | Số requests | Tổng dung lượng tải |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Trang chủ (`/`)** | **20 ms** (20 – 44 ms) | **44 ms** (34 – 76 ms) | **80 ms** (68 – 100 ms) | **80 ms** (68 – 100 ms) | **0.000** | 29 | 6.23 kB |
| **Tìm kiếm (`/search?q=quantum`)** | **31 ms** (29 – 32 ms) | **54 ms** (45 – 58 ms) | **96 ms** (96 – 112 ms) | **96 ms** (96 – 112 ms) | **0.000** | 26 | 5.09 kB |
| **Chi tiết phim (`/movies/...`)** | **44 ms** (30 – 51 ms) | **47 ms** (33 – 56 ms) | **84 ms** (72 – 120 ms) | **84 ms** (72 – 120 ms) | **0.000** | 30 | 12.50 kB |
| **Hồ sơ cá nhân (`/profile`)** | **40 ms** (31 – 43 ms) | **61 ms** (56 – 62 ms) | **100 ms** (100 – 116 ms) | **100 ms** (100 – 116 ms) | **0.000** | 24 | 4.72 kB |

*Ghi chú về chỉ số Web Vitals:*
- **LCP:** Đều đạt dưới 120 ms (ngưỡng lý tưởng của Google Web Vitals là $\le 2.5$ giây).
- **CLS:** Đạt 0.000 trên tất cả các route (hoàn toàn không có hiện tượng giật/nhảy layout).
- **INP:** Ghi nhận `unavailable` (yêu cầu tương tác người dùng phức tạp, chưa đo tự động trong harness).
- **First Load JS:** Tất cả các routes đạt $< 140$ kB (Home: 139 kB, Search: 137 kB, Detail: 140 kB, Profile: 138 kB).

---

## 3. Ma trận Nghiệm thu Vòng 11 (Acceptance Matrix)

| Hạng mục kiểm thử | Công cụ / Lệnh kiểm tra | Kết quả chi tiết | Đánh giá |
| :--- | :--- | :--- | :---: |
| **R1: CI Test Trigger & Scripts** | `npm test` trong `frontend/` | Chạy cả 5 suites: Catalog (9), M1 Behavior (25), M2 Journey (8), Search (12), Modal A11y (3) | **ĐẠT (57/57 PASS)** |
| **R1: CI Workflow Config** | `.github/workflows/ci.yml` | Branch `dev` có push/PR triggers; dùng `npm test`; không deploy job | **ĐẠT** |
| **R2: Seed & Config Policy** | `mvnw test` trong `backend/springboot/` | `SeedAndConfigPolicyTest` (4 tests): verify default YAML, no demo users, fail on missing secrets | **ĐẠT (4/4 PASS)** |
| **R2: Rollback Bảo toàn Data** | `schema_v1.sql` & Runbook | Bỏ `DROP TABLE` khỏi rollback; hướng dẫn migration tiến bộ và giữ an toàn dữ liệu | **ĐẠT** |
| **R3: A11y Focus & Lifecycle** | `modal_a11y_suite.mjs` | Test bẫy focus Tab, initial focus, Escape, restore opener, scroll lock | **ĐẠT (3/3 PASS)** |
| **R3: Mobile Touch & Collision** | CDP Walkthrough Step 14 | Nút Trailer $\ge 44$px, Watchlist $\ge 44$px, Trigger $\ge 44$px; 0 va chạm trên 375x667 | **ĐẠT** |
| **R3: Reduced Motion** | Walkthrough Step 04b + Suite | JS scroll đổi sang `behavior: 'auto'` khi có `prefers-reduced-motion: reduce` | **ĐẠT** |
| **R4: UI Multi-Account Auth** | Walkthrough Step 07 & 08 | Logout User A qua UI menu; Login User B qua form UI; xác nhận 0 data leak và reload persist | **ĐẠT** |
| **R4: Performance Benchmark** | Walkthrough Step 15 | Đo 3 lần cold/warm trên 4 route, xuất `perf_measurements.json` | **ĐẠT** |
| **Frontend Typecheck** | `npx tsc --noEmit` | Không có lỗi TypeScript (`exit code 0`) | **ĐẠT** |
| **Frontend Production Build** | `npm run build` | Next.js standalone build thành công (`exit code 0`), First Load JS $< 140$ kB | **ĐẠT** |
| **Backend Integration Suite** | `mvnw test` | `AuthAndLibraryIntegrationTest` (8) + `CatalogIntegrationTest` (9) + `SeedAndConfigPolicyTest` (4) | **ĐẠT (21/21 PASS)** |
| **Animation Baseline Preview** | `preview_animation_catalog.cjs` | 3 dry-run tests pass, không ghi vào database (`exit code 0`) | **ĐẠT (3/3 PASS)** |
| **E2E Browser Walkthrough** | `run_browser_walkthrough.cjs` | 14 bước assertions DOM/network thực tế + performance benchmark, 14 ảnh trong `ROUND_11/` | **ĐẠT (14/14 PASS)** |

---

## 4. Danh sách Minh chứng và Tệp bàn giao

1. **Patch Bàn giao:**
   - [ROUND_11.patch](file:///D:/Class/movie-rcm-system/docs/reports/ROUND_11.patch)
   - Kiểm tra tương thích đảo ngược (reverse check): `git apply --check -R docs/reports/ROUND_11.patch` $\rightarrow$ **Clean (Code 0)**.
2. **Bảng kê Mã băm SHA256:**
   - [ROUND_11_MANIFEST.json](file:///D:/Class/movie-rcm-system/docs/reports/ROUND_11_MANIFEST.json) bao gồm đầy đủ mã băm SHA256 và kích thước của 31 tệp đã sửa đổi/thêm mới.
3. **Ảnh chụp Minh chứng Trình duyệt (14 Screenshots):**
   - Lưu tại: `docs/reports/screenshots/ROUND_11/` (01 đến 14).
4. **Dữ liệu Đo lường Hiệu năng & Bằng chứng Hành trình:**
   - [perf_measurements.json](file:///D:/Class/movie-rcm-system/docs/reports/screenshots/ROUND_11/perf_measurements.json)
   - [walkthrough_evidence.json](file:///D:/Class/movie-rcm-system/docs/reports/screenshots/ROUND_11/walkthrough_evidence.json)

---

## 5. Giới hạn Kỹ thuật & Phạm vi Vòng tiếp theo

- **Hạ tầng Cơ sở Dữ liệu Test:** Test backend hiện sử dụng H2 in-memory với cấu hình biệt lập (`application-test.yml`). Kiểm thử production trên PostgreSQL thực tế cần một container PostgreSQL disposable trong môi trường CI/CD (không dùng DB live hay credentials thật).
- **Phạm vi Ngoài Lề Được Giữ Nguyên:** Không can thiệp vào mô hình AI Qwen3-4B / Phase 23 LoRA, FastAPI backend, GPU acceleration hoặc Google Drive Media Storage Design theo đúng yêu cầu phân tách milestone của dự án.
