# Báo cáo Nghiệm thu Milestone M3 — Vòng 13 (Round 13 Report)

- **Milestone:** M3 — Web nhẹ, dễ dùng và vận hành rõ ràng
- **Nhánh thực hiện:** `dev`
- **Round ID:** 13
- **Prompt Version:** 13
- **Run ID:** `run-round13-20261014-1325`
- **Reviewed Prior Run ID:** `run-round12-20261014-1245` (Codex Review: CHANGES REQUESTED, D1 & D2 defects)
- **Trạng thái:** `ready_for_review`
- **Thời gian thực hiện:** 2026-10-14 13:25 – 13:50 (~25 phút)

---

## 1. Tổng quan Sửa đổi D1 & D2

Vòng 13 giải quyết triệt để 2 khiếm khuyết nghiệm thu cuối cùng của Milestone M3 từ `docs/reviews/LOOP_ROUND_12_REVIEW.md` và `docs/prompts/GEMINI_CURRENT_TASK.md`. Toàn bộ các cải tiến đã được công nhận ở các vòng trước (A11y modals, Touch targets, Observer LCP/CLS session window, Cold/Warm protocol tách bạch, 14 browser journeys, tone xanh lá, M1/M2 behaviors) được giữ nguyên vẹn; không thêm tính năng, không can thiệp vào AI/FastAPI/GPU hoặc DB live:

### D1 — Cô lập Production Controls và Làm Xanh Đúng Lệnh CI

1. **Nguyên nhân Khiếm khuyết:**
   - Khi chạy lệnh CI thực tế `./mvnw test -Dspring.profiles.active=test`, tham số System Property `-Dspring.profiles.active=test` có độ ưu tiên cao hơn `defaultProperties` của `SpringApplicationBuilder`.
   - Các nested application contexts trong `SeedAndConfigPolicyTest` bị rò rỉ profile `test` vào môi trường (trở thành `prod,test`), nạp `application-test.yml` làm ghi đè `spring.datasource.password` thành rỗng và cung cấp sẵn `app.jwt.secret`, dẫn đến 1 failure và 3 errors trong bài test chính sách.
   - Khi chạy bare `mvnw.cmd test`, profile mặc định từ `application.yml` lại biến thành `prod,dev`. Cả hai trường hợp đều không đạt điều kiện profile `prod` duy nhất độc lập.

2. **Giải pháp Cô lập Môi trường Cấu hình (`createIsolatedProdEnvironment`):**
   - Cập nhật [`backend/springboot/src/test/java/com/dippie/moviercm/SeedAndConfigPolicyTest.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/test/java/com/dippie/moviercm/SeedAndConfigPolicyTest.java):
     - Xây dựng helper `createIsolatedProdEnvironment` tùy biến `StandardEnvironment`.
     - Loại bỏ hoàn toàn `spring.profiles.active` khỏi `systemProperties` (được tạo bản sao riêng không chứa cờ `-D` của runner).
     - Loại bỏ `SPRING_PROFILES_ACTIVE` khỏi `systemEnvironment`.
     - Thiết lập tường minh `setActiveProfiles("prod")`.
     - Thêm `MapPropertySource("isolatedProdCustomProperties", ...)` ở vị trí ưu tiên cao nhất (`addFirst`), đảm bảo biến môi trường giả lập của từng test (URL DB H2 riêng biệt, mật khẩu DB, JWT secret) không bị ghi đè.
     - Khởi chạy context với tham số `--spring.profiles.active=prod`.

3. **Khẳng định Chính sách & Độ Đặc hiệu:**
   - Trong các positive controls (`testProdProfileStartsSuccessfullyWithValidSecretsAndSchema`, `testCanonicalInitScriptPassesHibernateValidate`, `testAdditiveMigrationPreservesDataAndPassesValidate`), bổ sung các assertion nghiêm ngặt:
     - `assertArrayEquals(new String[]{"prod"}, ctx.getEnvironment().getActiveProfiles())`: Khẳng định chỉ duy nhất profile `prod` hoạt động.
     - `assertEquals("false", ctx.getEnvironment().getProperty("app.seed.enabled"))`: Khẳng định seed bị tắt.
     - `assertEquals("never", ctx.getEnvironment().getProperty("spring.sql.init.mode"))`: Khẳng định sql init mode là `never`.
     - `assertEquals("validate", ctx.getEnvironment().getProperty("spring.jpa.hibernate.ddl-auto"))`: Khẳng định Hibernate ddl-auto là `validate`.
   - Trong các negative controls:
     - Omit `APP_JWT_SECRET`: Ném lỗi chính xác `Could not resolve placeholder 'APP_JWT_SECRET'`.
     - Omit `SPRING_DATASOURCE_PASSWORD`: Ném lỗi chính xác `Could not resolve placeholder 'SPRING_DATASOURCE_PASSWORD'`.

4. **Làm rõ Quan hệ Khóa ngoại (Foreign Key Clarification):**
   - Đính chính rõ ràng theo đúng schema SQL hiện hành: Bảng `favorite_items` hiện tại có khóa ngoại người dùng `CONSTRAINT fk_favorite_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE`, **không có khóa ngoại tham chiếu bảng `movies`**; tuyệt đối không tự ý thêm cascade vào movie chỉ để khớp văn phong miêu tả.

5. **Kết quả Thực thi Hai Lệnh Maven Độc lập:**
   - Lệnh CI chuẩn: `.\mvnw.cmd test "-Dspring.profiles.active=test"`: **25/25 PASS (0 failures, 0 errors, Exit code 0)**. Log ghi nhận: `The following 1 profile is active: "prod"`.
   - Lệnh Bare: `.\mvnw.cmd test`: **25/25 PASS (0 failures, 0 errors, Exit code 0)**. Log ghi nhận: `The following 1 profile is active: "prod"`.

---

### D2 — Đo lường Dynamic JavaScript First Load Budget từ Build Thực tế

1. **Loại bỏ Hằng số Cố định (Hardcoded Size Constants):**
   - Thay thế toàn bộ bảng `ROUTE_EXACT_JS_BYTES` hardcoded trong `scripts/run_browser_walkthrough.cjs` bằng công cụ đo lường động trực tiếp từ manifest và artifact build hiện hành.

2. **Module Đo lường Động [`scripts/compute_build_bytes.cjs`](file:///D:/Class/movie-rcm-system/scripts/compute_build_bytes.cjs):**
   - Đọc trực tiếp `app-build-manifest.json` và `BUILD_ID` từ thư mục `frontend/.next`.
   - Khử trùng lặp (deduplicate) các chunk JavaScript dùng chung giữa `/layout` và từng trang route (`/`, `/search`, `/movies/[id]`, `/profile`).
   - Phân biệt rõ ràng: Chỉ đo các file script JavaScript của route layout và page; loại trừ CSS, polyfills, React Server Components (RSC) payload và API routes; ghi nhận đây không phải là toàn bộ HTTP wire bytes.
   - Tính toán dung lượng thô (raw bytes), dung lượng nén gzip (`zlib.gzipSync`), và mã băm SHA-256 cho từng file chunk.
   - Áp dụng ngân sách chuẩn hóa: **140 KiB = 143,360 bytes**.
   - Cơ chế bảo vệ (Guard): Nếu bất kỳ route nào vượt quá 143,360 bytes gzip hoặc thiếu file/manifest, script ném lỗi và thoát với mã lỗi non-zero (`process.exit(1)`).

3. **Bộ Kiểm thử Tự chẩn đoán (Negative Self-Test Suite):**
   - Chạy qua cờ `node scripts/compute_build_bytes.cjs --negative-test` và tích hợp vào `--negative-test` của walkthrough harness (**5/5 self-tests PASS**):
     - *Negative Test 1 (Missing manifest):* Phát hiện thiếu `app-build-manifest.json` -> ném lỗi đúng hợp đồng.
     - *Negative Test 2 (Missing route in manifest):* Phát hiện route không có trong manifest -> ném lỗi đúng hợp đồng.
     - *Negative Test 3 (Missing chunk on disk):* Phát hiện chunk có trong manifest nhưng thiếu file vật lý -> ném lỗi đúng hợp đồng.
     - *Negative Test 4 (Over-budget detection with tiny budget):* Cấu hình budget 50 bytes trên fixture tạo sẵn -> xác nhận `underBudget === false` và ném lỗi `exceeded budget`.
     - *Positive Test 5 (Real build measurement):* Đo đạc build thật và khẳng định 100% routes đạt chuẩn.

4. **Tích hợp Guard vào CI Pipeline ([`.github/workflows/ci.yml`](file:///D:/Class/movie-rcm-system/.github/workflows/ci.yml)):**
   - Bổ sung bước kiểm tra tự động `Verify Route JS Budgets (<=140 KiB)` ngay sau bước `npm run build` trong job `frontend-check`. Bất kỳ thay đổi mã nguồn nào làm bundle vượt ngưỡng 140 KiB sẽ lập tức chặn CI.

5. **Bảng Số liệu Đo lường JavaScript First Load Thực tế (Build ID: `-KHpXRnpC_f3vy0Cq5Oqi`):**

| Route | Manifest Key | Số Chunks | Raw Bytes | Gzip Bytes | Dung lượng (KiB) | Ngân sách (KiB) | Trạng thái Budget |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Trang chủ (`/`)** | `/page` | 10 | 491,114 B | **139,231 B** | **135.97 KiB** | 140 KiB (143,360 B) | **✔ PASS** |
| **Tìm kiếm (`/search`)** | `/search/page` | 10 | 482,691 B | **138,015 B** | **134.78 KiB** | 140 KiB (143,360 B) | **✔ PASS** |
| **Chi tiết phim (`/movies/[id]`)** | `/movies/[id]/page` | 10 | 495,605 B | **140,419 B** | **137.13 KiB** | 140 KiB (143,360 B) | **✔ PASS** |
| **Hồ sơ (`/profile`)** | `/profile/page` | 10 | 499,727 B | **139,137 B** | **135.88 KiB** | 140 KiB (143,360 B) | **✔ PASS** |

---

## 2. Bảng Kết quả Đo lường Hiệu năng Thực tế (Vòng 13 Evidence)

### Điều kiện Đo đạc:
- **Framework & Build:** Next.js 15.1.2 (Standalone Production Build, Next compiler).
- **Build ID:** `-KHpXRnpC_f3vy0Cq5Oqi`.
- **Môi trường:** Node.js v26.1.0, Chrome Headless qua CDP (Chrome DevTools Protocol).
- **Mạng:** Local Loopback qua HTTP Fixture Server (127.0.0.1:8080).
- **Viewport:** Desktop 1280x800.
- **Phương pháp lấy mẫu:** 3 lần Cold (xóa & vô hiệu hóa cache) + 3 lần Warm (bật cache sau 1 lượt làm ấm) cho mỗi route.
- **Thư mục lưu trữ bằng chứng:** `docs/reports/screenshots/ROUND_13/`.

### Bảng Chỉ số Hiệu năng (Cold vs Warm):

| Route & Trạng thái Cache | DCL (Median / Range) | Load Duration (Median / Range) | FCP (Median / Range) | LCP Observer (Median / Range) | CLS Session Window (Median / Range) | CDP Wire Transfer Bytes | Số Requests |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Trang chủ (`/`) — COLD** | **39 ms** (36 – 40 ms) | **114 ms** (111 – 114 ms) | **132 ms** (124 – 136 ms) | **196 ms** (196 – 208 ms) | **0.014** (0.014 – 0.014) | **329.9 kB** | 33 |
| **Trang chủ (`/`) — WARM** | **32 ms** (26 – 41 ms) | **50 ms** (45 – 84 ms) | **124 ms** (120 – 132 ms) | **120 ms** (120 – 132 ms) | **0.014** (0.014 – 0.014) | **16.9 kB** | 29 |
| **Tìm kiếm (`/search`) — COLD** | **39 ms** (34 – 42 ms) | **106 ms** (101 – 112 ms) | **92 ms** (88 – 96 ms) | **144 ms** (144 – 148 ms) | **0.069** (0.069 – 0.069) | **320.4 kB** | 30 |
| **Tìm kiếm (`/search`) — WARM** | **17 ms** (15 – 29 ms) | **30 ms** (27 – 42 ms) | **88 ms** (84 – 96 ms) | **64 ms** (64 – 92 ms) | **0.069** (0.069 – 0.069) | **7.8 kB** | 26 |
| **Chi tiết phim (`/movies/...`) — COLD** | **42 ms** (38 – 51 ms) | **102 ms** (99 – 135 ms) | **88 ms** (84 – 92 ms) | **184 ms** (184 – 184 ms) | **0.000** (0.000 – 0.000) | **332.7 kB** | 34 |
| **Chi tiết phim (`/movies/...`) — WARM** | **38 ms** (32 – 42 ms) | **41 ms** (36 – 49 ms) | **84 ms** (84 – 88 ms) | **112 ms** (108 – 120 ms) | **0.000** (0.000 – 0.000) | **17.0 kB** | 30 |
| **Hồ sơ cá nhân (`/profile`) — COLD** | **44 ms** (39 – 45 ms) | **127 ms** (110 – 142 ms) | **84 ms** (84 – 88 ms) | **188 ms** (180 – 192 ms) | **0.008** (0.008 – 0.008) | **320.0 kB** | 28 |
| **Hồ sơ cá nhân (`/profile`) — WARM** | **20 ms** (18 – 24 ms) | **37 ms** (35 – 48 ms) | **84 ms** (80 – 88 ms) | **100 ms** (96 – 108 ms) | **0.022** (0.007 – 0.022) | **6.5 kB** | 24 |

---

## 3. Ma trận Nghiệm thu Vòng 13 (Acceptance Matrix)

| Hạng mục kiểm tra | Tiêu chí | Kết quả | Bằng chứng thực tế |
| :--- | :---: | :---: | :--- |
| **Backend Exact CI Command** | D1 | **PASS** | `mvnw.cmd test -Dspring.profiles.active=test`: **25/25 pass (exit 0)**. |
| **Backend Bare Command** | D1 | **PASS** | `mvnw.cmd test`: **25/25 pass (exit 0)**. |
| **Profile Isolation** | D1 | **PASS** | Nested contexts khẳng định chính xác `activeProfiles: ["prod"]`. |
| **Specific Missing Secret Error** | D1 | **PASS** | Bắt đúng key: `APP_JWT_SECRET` và `SPRING_DATASOURCE_PASSWORD`. |
| **Dynamic Build Bytes Engine** | D2 | **PASS** | `scripts/compute_build_bytes.cjs` đo trực tiếp manifest và chunks. |
| **Build Bytes Self-Test Suite** | D2 | **PASS** | `--negative-test`: **5/5 tests pass** (bắt đúng thiếu file, vượt budget). |
| **CI Budget Guard Step** | D2 | **PASS** | Đã nối step `Verify Route JS Budgets (<=140 KiB)` vào CI sau build. |
| **All Routes Under 140 KiB** | D2 | **PASS** | Home 135.97 KiB, Search 134.78 KiB, Detail 137.13 KiB, Profile 135.88 KiB. |
| **Frontend Test Suite** | M1/M2/M3 | **PASS** | Chạy `npm test`: **57/57 pass (exit 0)**. |
| **TypeScript Compilation** | M3 | **PASS** | Chạy `npx tsc --noEmit`: **0 errors (exit 0)**. |
| **Production Build** | M3 | **PASS** | Chạy `npm run build`: Tạo thành công standalone bundle (exit 0). |
| **Walkthrough Negative Self-Check** | M3 | **PASS** | `run_browser_walkthrough.cjs --negative-test`: **PASS exit 0**. |
| **14 Browser E2E Journeys** | M3 | **PASS** | 14/14 steps pass, xuất 14 screenshots trong `docs/reports/screenshots/ROUND_13/`. |
| **Bảo toàn Phạm vi** | Guardrail | **PASS** | Không sửa AI/FastAPI/Qwen, không dùng DB live, không commit/push. |

---

## 4. Hồ sơ Bàn giao Vòng 13

- **Báo cáo chi tiết:** [`docs/reports/ROUND_13_REPORT.md`](file:///D:/Class/movie-rcm-system/docs/reports/ROUND_13_REPORT.md)
- **Patch thay đổi mã nguồn:** [`docs/reports/ROUND_13.patch`](file:///D:/Class/movie-rcm-system/docs/reports/ROUND_13.patch)
- **Manifest băm SHA-256 (21 files):** [`docs/reports/ROUND_13_MANIFEST.json`](file:///D:/Class/movie-rcm-system/docs/reports/ROUND_13_MANIFEST.json)
- **Trạng thái vòng lặp:** [`docs/reports/M2_M3_STATUS.json`](file:///D:/Class/movie-rcm-system/docs/reports/M2_M3_STATUS.json) (`ready_for_review`)
- **Nhật ký tiến độ:** [`docs/reports/M2_M3_WORKLOG.md`](file:///D:/Class/movie-rcm-system/docs/reports/M2_M3_WORKLOG.md)
- **Thư mục ảnh chụp màn hình & số liệu thô Vòng 13:** [`docs/reports/screenshots/ROUND_13/`](file:///D:/Class/movie-rcm-system/docs/reports/screenshots/ROUND_13/)
