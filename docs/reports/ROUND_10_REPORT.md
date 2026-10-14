# Báo cáo Nghiệm thu Milestone M3 (Round 10 Report)

- **Milestone:** M3 — Web nhẹ, dễ dùng và vận hành rõ ràng
- **Round ID:** 10
- **Prompt Version:** 10
- **Run ID:** `run-round10-20261014-1015`
- **Reviewed Prior Run ID:** `run-round9-20261014-0950` (Codex Review: ACCEPTED, M2 hoàn tất)
- **Trạng thái:** `ready_for_review`
- **Thời gian thực hiện:** 2026-10-14 10:15 – 10:55 (~40 phút)

---

## 1. Tổng quan Triển khai Milestone M3

Milestone M3 hoàn thành toàn bộ 4 nhóm mục tiêu cốt lõi theo `docs/prompts/M3_UX_OPERATIONS_GEMINI_PROMPT.md` và `docs/prompts/GEMINI_CURRENT_TASK.md`:

1. **Mobile và Khả năng Tiếp cận (A11y & Modals):**
   - Đầy đủ lifecycle focus cho các modal: `AuthModal`, video player modal trong `MovieDetail`, và `CineBot` shell.
   - Initial focus vào trường nhập đầu tiên/nút tương tác chính; bẫy phím Tab/Shift+Tab bên trong dialog; phím Escape đóng dialog; khóa cuộn nền (`overflow: hidden`); phục hồi focus (`focus()`) chính xác về opener sau khi đóng.
   - Controls không bị chồng lấn; kích thước touch target đạt tối thiểu **>= 44x44px** trên các nút icon và trigger nổi.
   - Hỗ trợ `@media (prefers-reduced-motion: reduce)` triệt để trên toàn bộ CSS transitions, animations, và scroll-behavior.

2. **Ảnh Lỗi và Tối ưu Mạng:**
   - Xử lý trạng thái tải ảnh lỗi thực tế (`onError`) trên `MovieCard`, `EditorialHero`, và `MovieDetail` khi gặp URL 404/broken. Hiển thị fallback placeholder sạch kèm tên phim hoạt hình mà không làm biến dạng layout hoặc vỡ ảnh.
   - Khai báo an toàn `remotePatterns` trong `next.config.ts` cho các domain ảnh cần thiết (`images.unsplash.com` và local fixture `127.0.0.1:8080`), không mở allowlist tùy tiện.

3. **Tách biệt Môi trường Dev/Test/Prod & Chính sách Seed:**
   - Ngăn chặn seed dữ liệu demo lên môi trường production: Gắn `@ConditionalOnProperty(prefix = "app.seed", name = "enabled", havingValue = "true", matchIfMissing = false)` lên `DataInitializer.java`.
   - Cấu hình chuẩn trong `application.yml`:
     - Top-level & Prod profile: `app.seed.enabled: false`, `sql.init.mode: never`, `ddl-auto: validate`, yêu cầu biến môi trường bắt buộc `${SPRING_DATASOURCE_PASSWORD}` và `${APP_JWT_SECRET}` (không có giá trị fallback nguy hiểm).
     - Dev profile: `app.seed.enabled: true`, `sql.init.mode: always`, `ddl-auto: update`.
     - Test profile (`application-test.yml`): `app.seed.enabled: false`, `sql.init.mode: never`.
   - Bổ sung integration test `SeedAndConfigPolicyTest.java`: xác nhận bean `DataInitializer` không khởi tạo và bảng người dùng hoàn toàn không có tài khoản demo tự động khi tắt seed.
   - Xuất bản DDL chuẩn hóa và versioned migration: `docs/runbooks/db/schema_v1.sql`.

4. **CI & Sổ tay Vận hành (Operations Runbook):**
   - Cập nhật `.github/workflows/ci.yml` kích hoạt trên branch `chore/taicautruc`, bao gồm: Spring Boot test suite với JDK 17 và profile test cách ly; TypeScript typecheck (`tsc --noEmit`); 4 bộ behavioral test suites; baseline preview dry-run test; Next.js build.
   - Biên soạn sổ tay vận hành hoàn chỉnh tại `docs/runbooks/OPERATIONS_RUNBOOK.md` bao quát biến môi trường, seed policy, quy trình nâng cấp/rollback database và kiểm tra sức khỏe hệ thống.

---

## 2. Ma trận Nghiệm thu (Acceptance Matrix)

| Hạng mục M3 | Yêu cầu kỹ thuật | Kết quả kiểm chứng thực tế | Trạng thái |
| :--- | :--- | :--- | :---: |
| **A11y Modals** | Dialog focus trap, Esc, initial focus, restore opener, scroll lock | Đã triển khai và kiểm chứng trên `AuthModal`, player overlay `MovieDetail`, và `CineBot` | **ĐẠT** |
| **Touch Targets & Mobile** | Controls không che nhau, kích thước nút >= 44x44px trên mobile 375x667 | Chạy walkthrough mobile 375x667, xác nhận bounding box và không overlap controls | **ĐẠT** |
| **Reduced Motion** | Tuân thủ `prefers-reduced-motion: reduce` ở cả CSS lẫn JS animation | Toàn bộ keyframe animations, transitions và scroll-behavior được vô hiệu hóa khi reduce motion bật | **ĐẠT** |
| **Broken Image Fallback** | Ảnh 404/broken hiển thị title placeholder sạch, không méo layout | `onError` trên `MovieCard`, `EditorialHero`, `MovieDetail`; walkthrough step 10 assert placeholder | **ĐẠT** |
| **Seed & Profile Separation** | Prod tắt seed (`app.seed.enabled: false`), `ddl-auto: validate`, secrets bắt buộc | `DataInitializer` conditional; `SeedAndConfigPolicyTest` xác nhận không có demo accounts; `schema_v1.sql` sẵn sàng | **ĐẠT** |
| **Hành trình Browser E2E** | Multi-account walkthrough: Guest -> Login A -> Save/Rate -> Reload -> Logout -> Login B (0 data leak) | Walkthrough CDP 14 bước hoàn tất với 14 assertions DOM/network thật, lưu 14 screenshots tại `ROUND_10/` | **ĐẠT** |
| **CI & Runbook** | CI workflow hỗ trợ branch hiện tại và đầy đủ build/test; runbook chi tiết | `.github/workflows/ci.yml` cập nhật; `docs/runbooks/OPERATIONS_RUNBOOK.md` đầy đủ | **ĐẠT** |

---

## 3. Đo lường Hiệu năng và Ngân sách Tải trang (Performance Baseline & Measurement)

### Điều kiện đo lường chuẩn hóa:
- **Môi trường:** Node.js v26.1.0, Next.js 15.2.4 (Turbopack production build), Windows 11.
- **Hạ tầng đo:** Chrome Headless với CDP (DevTools Protocol), viewport Desktop (1280x800) và Mobile (375x667).
- **Network & Cache:** Cold cache lần đầu, Warm cache lần lặp; Local HTTP fixture 127.0.0.1:8080.
- **Ngân sách tối đa (Performance Budget):** First Load JS < 140 kB cho mọi route.

### Bảng so sánh Bundle Size Trước (Baseline M2) vs Sau (M3):

| Route | Kích thước trước (M2 Baseline) | Kích thước sau (M3) | Chênh lệch (Delta) | First Load JS (Shared + Route) | Ngân sách (< 140 kB) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `/` (Trang chủ) | 5.63 kB | 5.66 kB | +0.03 kB | **138 kB** | ĐẠT (Dưới ngân sách) |
| `/_not-found` | 140 B | 140 B | 0 B | **106 kB** | ĐẠT (Dưới ngân sách) |
| `/api/chat` | 140 B | 140 B | 0 B | **106 kB** | ĐẠT (Dưới ngân sách) |
| `/movies/[id]` (Chi tiết) | 6.29 kB | 6.68 kB | +0.39 kB | **139 kB** | ĐẠT (Dưới ngân sách) |
| `/profile` (Cá nhân) | 5.56 kB | 5.56 kB | 0 B | **138 kB** | ĐẠT (Dưới ngân sách) |
| `/search` (Tìm kiếm) | 4.46 kB | 4.46 kB | 0 B | **137 kB** | ĐẠT (Dưới ngân sách) |
| **Shared Chunks** | 105 kB | 105 kB | 0 B | **105 kB** | ĐẠT |

*Ghi chú:* Việc bổ sung a11y focus trapping, dialog backdrop và broken-image fallback handlers chỉ tăng nhẹ 0.03 kB ở Home và 0.39 kB ở Detail, hoàn toàn nằm trong ngân sách tải trang.

---

## 4. Kết quả Kiểm thử Chi tiết

### 4.1. Spring Boot Backend Tests (Maven)
- **Lệnh thực thi:** `.\mvnw.cmd test "-Dspring.profiles.active=test"`
- **Kết quả:** **19/19 TESTS PASS (Build Success, 0 failures, 0 errors)**
  - `AuthAndLibraryIntegrationTest`: **8/8 PASS** (Xác thực JWT, đăng nhập, phân quyền, thêm/xóa watchlist, favorites, movie ratings với H2 isolation).
  - `CatalogIntegrationTest`: **9/9 PASS** (Phân trang, lọc theo thể loại token-exact, query search kết hợp, 404 handler, sort order).
  - `SeedAndConfigPolicyTest`: **2/2 PASS** (Xác nhận `DataInitializer` bean không nạp khi `app.seed.enabled=false`, xác nhận bảng người dùng không tự tạo demo accounts).

### 4.2. Frontend Behavioral Test Suites (Node test runner)
- **Lệnh thực thi:**
  - `node frontend/tests/catalog_service_suite.mjs`
  - `node frontend/tests/m1_behavior_suite.mjs`
  - `node frontend/tests/m2_journey_suite.mjs`
  - `node frontend/tests/search_experience_suite.mjs`
- **Kết quả:** **54/54 TESTS PASS (100% Pass rate)**
  - `catalog_service_suite.mjs`: **9/9 PASS** (C1/C2 cancellation, timeouts, payload validation, non-existent 404, query precedence).
  - `m1_behavior_suite.mjs`: **25/25 PASS** (R1–R7, F1–F4, G1–G3, H1–H2 session isolation, cross-account zero-leak, uncertain retry state machine).
  - `m2_journey_suite.mjs`: **8/8 PASS** (Cross-surface integration Home -> Detail -> Profile, canonical synthetic ID, Hero uncertain retry).
  - `search_experience_suite.mjs`: **12/12 PASS** (S1–S4 search draft preserving, generation guard, query debounce, image fallback placeholder).

### 4.3. TypeScript & Baseline Tools
- **TypeScript Typecheck:** `npx tsc --noEmit` -> **PASS (Exit code 0, 0 lints/errors)**.
- **Animation Baseline Preview:** `node scripts/preview_animation_catalog.cjs --test` -> **3/3 PASS**.

---

## 5. Bằng chứng Thực nghiệm Walkthrough Browser (14 Bước tại `docs/reports/screenshots/ROUND_10/`)

- **Harness thực thi:** `node scripts/run_browser_walkthrough.cjs`
- **Kết quả:** **14/14 BƯỚC PASS ASSERTIONS DOM & NETWORK (Exit code 0)**
- **File nhật ký cấu trúc:** `docs/reports/screenshots/ROUND_10/walkthrough_evidence.json`

| STT | File Ảnh | Viewport | Hành động & Khẳng định DOM/Network | Trạng thái | SHA256 Ảnh (ROUND_10) |
| :---: | :--- | :---: | :--- | :---: | :--- |
| **01** | `01_home_guest_desktop.png` | 1280x800 | Khách truy cập trang chủ, navbar hiển thị nút "Đăng nhập", không rò rỉ session cũ. | PASS | `d806a64ddad3f53392476b70128e7626305a41505367b7e2cc4a779ca720c2b2` |
| **02** | `02_auth_modal_desktop.png` | 1280x800 | Click "Đăng nhập" -> Mở `AuthModal`: `role="dialog"`, focus tự động vào trường email, khóa cuộn trang nền. | PASS | `9c43d9646b9aeb6eeaa5ea63eb5c6b9074b785fcb9fa3748259074b8fb1777d4` |
| **03** | `03_login_user_a_desktop.png` | 1280x800 | Đăng nhập tài khoản `user_a`: session được cấp, navbar hiển thị `user_a`, modal đóng sạch và trả focus. | PASS | `d5aa112f4835613cbf2b2fa231bc5f0bbd4a27ce5b66d6cc0c1154c153b890f5` |
| **04** | `04_detail_saved_rated_user_a.png` | 1280x800 | Vào phim `m2-synthetic-anim-001`, click lưu watchlist và chấm điểm 9. Backend fixture ghi nhận thành công. | PASS | `8a93aa0f55cf73a5a7566f1225501d26d2466f8be0f9b5bc7583713f040209df` |
| **05** | `05_profile_user_a_desktop.png` | 1280x800 | Mở `/profile` của `user_a`: Watchlist hiển thị phim vừa lưu; tab Đánh giá hiển thị chính xác điểm `9/10`. | PASS | `a65aee7aa163d7e5d8ff69e8b7705ef27b3602d3cf8ddc969b46617e1cb95908` |
| **06** | `06_hero_uncertain_retry_desktop.png` | 1280x800 | Simulates lỗi mạng khi click toggle Hero -> hiển thị badge hổ phách "Chưa xác nhận" và nút "Thử lưu lại". Bấm thử lại -> phục hồi thành công. | PASS | `8dbb091f893e433db9b82bfec6ff38a2e588e1467406a6556f8f8cc856cbf09d` |
| **07** | `07_logout_switch_user_b.png` | 1280x800 | `user_a` đăng xuất sạch -> đăng nhập tài khoản mới `user_b`. Navbar cập nhật `user_b`. | PASS | `91ea70a1a0f9b14b82d0ea9e8f158f9fcfe60ffc31f47849e7b2a6fe1a1d17cf` |
| **08** | `08_user_b_isolation_profile.png` | 1280x800 | **Bảo mật cách ly tài khoản:** Vào `/profile` của `user_b`: hiển thị rỗng, **0% rò rỉ dữ liệu** của `user_a`. | PASS | `6903d6d5efbe3a1e2f5b5c9dc421c4b7bca0f5e1f0e427e1f44c92c90c52bbdf` |
| **09** | `09_search_deep_link_back_desktop.png` | 1280x800 | Deep link `/search?q=quantum`: draft giữ nguyên từ khóa, điều hướng qua lại với `history.back()` không mất kết quả. | PASS | `85a1a1f0a28f7fcb59aa0c73228a0ca20ec1b4b9b9a695d7dd76bc7e2ef3c8d7` |
| **10** | `10_image_404_fallback_desktop.png` | 1280x800 | **Fallback ảnh hỏng:** Tải phim có ảnh 404 -> UI kích hoạt fallback placeholder hiển thị tiêu đề phim, không vỡ layout. | PASS | `a859ea43422cb33560fe2eb15a5fbc40d24c0840c115c234a6efc9ecdb480f22` |
| **11** | `11_detail_404_desktop.png` | 1280x800 | Truy cập ID phim không tồn tại -> hiển thị trang 404 thân thiện kèm nút điều hướng quay về trang chủ. | PASS | `4b301c2789ce86326442657d24d27e77a16f6b553e4c49d8e6fa3013d2f95fcb` |
| **12** | `12_catalog_error_retry_desktop.png` | 1280x800 | Backend gặp sự cố 500 -> hiển thị banner lỗi trang trọng kèm nút "Thử kết nối lại", không làm crash giao diện. | PASS | `32a760eb80fa05b5cc48184c8a24aa7b82451000bbdd1bf2f36f6d0f507ba5fc` |
| **13** | `13_home_mobile.png` | 375x667 | **Mobile 375px:** Hero co giãn mượt mà, layout nút và trigger CineBot không che khuất nhau, touch targets >= 44x44px. | PASS | `c9735d97f1f108d4b8ca30fae8a718b958c2c31e9bb82531d0db2e2b313ef0ce` |
| **14** | `14_detail_mobile.png` | 375x667 | **Mobile 375px Chi tiết:** Layout cuộn dọc, cụm đánh giá sao và nút lưu thư viện dễ bấm bằng một tay. | PASS | `ce24ce3a42eb896b02005bc18b444b02534ff7fdb7e7efbc0b9ca04c7c8c3c2b` |

---

## 6. Phạm vi và Giới hạn Hoạt động (Boundaries & Constraints)

- **AI & GPU:** Toàn bộ công việc của Milestone M3 tuân thủ nghiêm ngặt phạm vi giao diện web và vận hành hệ thống. **Tuyệt đối không can thiệp** vào dịch vụ FastAPI, Qwen AI, Ollama, GPU backend hoặc huấn luyện mô hình.
- **Cơ sở dữ liệu:** Không thực hiện bất kỳ thao tác nào làm ảnh hưởng đến cơ sở dữ liệu production live. Tất cả bài test chạy trên cơ sở dữ liệu in-memory test H2 cách ly hoặc fixture backend độc lập.
- **Git workflow:** Không tự ý `git commit`, `git push`, hoặc `git reset`. Mọi thay đổi được bàn giao dưới dạng patch sạch `ROUND_10.patch` và manifest `ROUND_10_MANIFEST.json`.
- **Media Storage (Google Drive):** Đã bổ sung tài liệu thiết kế backlog theo yêu cầu người dùng tại `docs/DRIVE_MEDIA_STORAGE_DESIGN.md` và cập nhật mục tiêu tại `docs/PRODUCT_MILESTONES.md`. Không tự ý cài đặt, mount ổ đĩa, hoặc triển khai mã nguồn ngoài phạm vi M3 trong vòng này.

---

## 7. Kết luận và Bàn giao

Milestone M3 đã hoàn thành xuất sắc toàn bộ tiêu chí đặt ra, vượt qua tất cả bài kiểm tra tự động và bằng chứng thực tế.

Mã nguồn đã được **FREEZE**. Trạng thái sẵn sàng cho Codex kiểm tra:
`M2_M3_STATUS.json` -> `state: "ready_for_review"`.
