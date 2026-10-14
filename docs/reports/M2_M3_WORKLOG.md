# M2 & M3 Implementation Worklog

> **Mode:** 30-minute round-based iteration with Codex review gates  
> **Repository:** `D:\Class\movie-rcm-system`  

---

## Round 1 — M2 Catalog Contract & Paginated Backend Slice

- **Started At:** 2026-10-14T02:45:00+07:00
- **targetRoundId:** 1 | **promptVersion:** 1
- **Run ID:** `run-round1-20261014-0245`
- **Goal:**
  1. Chốt contract M2 tại `docs/contracts/M2_CATALOG_CONTRACT.md`: canonical IDs, nullable metadata, legacy compatibility, combined query/genre/sort/paging.
  2. Triển khai backend browse paginated/filter endpoint `GET /api/movies/browse` và kết hợp search + genre trên legacy `GET /api/movies`.
  3. Xây dựng test suite tích hợp `CatalogIntegrationTest.java` với test fixtures riêng.
  4. Thu thập kết quả kiểm thử, tạo checkpoint patch `ROUND_1.patch`, manifest SHA256, và báo cáo `ROUND_1_REPORT.md`.
  5. Cập nhật `M2_M3_STATUS.json` thành `ready_for_review` sau 30 phút.


---

## Round 2 — R1 Genre Token Exact & R2 Search Semantics Consistency

- **Started At:** 2026-10-14T03:10:00+07:00
- **targetRoundId:** 2 | **promptVersion:** 2
- **Run ID:** `run-round2-20261014-0310`
- **Reviewed Run ID:** `run-round1-20261014-0245`
- **Findings to resolve:**
  1. **R1 (P2):** Genre filters vẫn substring, trái token contract (Drama khớp Melodrama, Animation khớp NonAnimation, input wildcards mở rộng match).
  2. **R2 (P2):** Legacy search thay semantics tùy có genre (`search-only` bỏ description, thêm genre lại tìm description).
- **Goal:**
  1. Cập nhật `MovieService` với shared `buildGenreTokenPredicate` (R1) và `buildSearchPredicate` (R2) an toàn, chính xác.
  2. Cập nhật `CatalogIntegrationTest.java` với 8 bài kiểm thử tích hợp (16/16 tests Spring Boot PASS).
  3. Cập nhật `docs/contracts/M2_CATALOG_CONTRACT.md` (trạng thái READY FOR REVIEW, sửa Spirited Away videoUrl, ghi rõ token match và search semantics).
  4. Triển khai shared catalog client `frontend/lib/services/catalogService.ts` và test suite `catalog_service_suite.mjs` (4/4 tests PASS, 25/25 M1 regression tests PASS, 0 tsc errors).
  5. Đã tạo snapshot `.round2_snapshot/`, patch `ROUND_2.patch` (numstat & reverse check pass exit 0), manifest `ROUND_2_MANIFEST.json`, và báo cáo `ROUND_2_REPORT.md`.
  6. Hoàn tất Vòng 2 trong khung thời gian 30 phút, phát hành trạng thái `ready_for_review` và freeze source code.

---

## Round 3 — C1 Lifecycle/Cancellation, C2 Payload Validation, C3 Genre Whitespace

- **Started At:** 2026-10-14T06:15:00+07:00
- **targetRoundId:** 3 | **promptVersion:** 3
- **Run ID:** `run-round3-20261014-0615`
- **Reviewed Run ID:** `run-round2-20261014-0315`
- **Findings to resolve:**
  1. **C1 (P2):** Timeout/caller cancellation chỉ bao phủ headers. Timer clear và listener remove trước khi parse body. Caller abort sau headers không truyền tới transport/body; timeout không bao phủ slow body. Phân biệt intentional cancellation với timeout/network error.
  2. **C2 (P2):** Malformed payload biến thành empty/phantom data (`{}` thành id="", year=0, rating=0; `{}` page data thành empty success page; detail không verify requested ID khớp response ID; 404 parse JSON trước status check; blank query precedence).
  3. **C3 (P2):** Genre whitespace hard-coded một dấu cách (`Animation,  Family` hoặc tabs/multiple spaces không khớp query). Cần normalize tổng quát tại boundary DB query, bảo toàn internal spaces cho genre tên dài.
- **Goal:**
  1. Triển khai C1 & C2 trong `frontend/lib/services/catalogService.ts`.
  2. Triển khai C3 trong `backend/springboot/src/main/java/com/dippie/moviercm/service/MovieService.java`.
  3. Bổ sung tests toàn diện trong `backend/springboot/src/test/java/com/dippie/moviercm/CatalogIntegrationTest.java` và `frontend/tests/catalog_service_suite.mjs`.
  4. Cập nhật `docs/contracts/M2_CATALOG_CONTRACT.md`.
- **Completed:**
  1. Đã triển khai C1 & C2 trong `catalogService.ts`: `executeWithLifecycle` bao phủ toàn bộ request + body parsing, phân loại intentional cancellation (`isCanceled: true`, status 499), timeout (status 408); validate chặt chẽ payload `Movie` và phân trang (loại bỏ dữ liệu giả, ném 502 khi thiếu trường bắt buộc), kiểm tra khớp ID chi tiết phim, 404 trả về `null` an toàn, query precedence fallback `search`.
  2. Đã triển khai C3 trong `MovieService.java`: `buildGenreTokenPredicate` áp dụng `REGEXP_LIKE` biên giới token `(^|[,])[ \t]*TOKEN[ \t]*([,]|$)` chuẩn hóa mọi khoảng trắng/tab và bảo toàn internal spaces.
  3. Kiểm thử Spring Boot: 17/17 tests PASS (9 catalog integration + 8 auth/library).
  4. Kiểm thử Frontend Catalog Suite: 9/9 tests PASS; M1 regression suite: 25/25 tests PASS; `npx tsc --noEmit`: 0 lỗi.
  5. Cập nhật contract `docs/contracts/M2_CATALOG_CONTRACT.md` lên v1.2.0 (Round 3 Update).
  6. Tạo snapshot `.round3_snapshot/`, patch `ROUND_3.patch` (numstat & reverse check pass exit 0), manifest `ROUND_3_MANIFEST.json` và report `ROUND_3_REPORT.md`.
  7. Hoàn tất Vòng 3 trong khung thời gian 30 phút, phát hành trạng thái `ready_for_review` và freeze source code.

---

## Round 4 — Search / Browse UI Catalog Integration & MovieCard Fallbacks

- **Started At:** 2026-10-14T07:50:00+07:00
- **targetRoundId:** 4 | **promptVersion:** 4
- **Run ID:** `run-round4-20261014-0750`
- **Reviewed Run ID:** `run-round3-20261014-0615`
- **Goal:**
  1. Kết nối `SearchExperience.tsx` với `catalogService.browseCatalog`, loại bỏ hoàn toàn mock data local.
  2. Khẳng định `animationOnly=true` trong toàn bộ hành trình hoạt hình; bảo lưu ràng buộc khi lọc thêm thể loại phụ.
  3. URL là Single Source of Truth cho query, genres, sort, page. Debounce input (350ms) có cleanup.
  4. Quản lý vòng đời bất đồng bộ với Generation Guard (`currentRequestId`), hủy bỏ request cũ và im lặng với caller cancellation.
  5. MovieCard có placeholder cho poster null/empty, ngăn Next Image crash; bảo toàn canonical IDs và M1 watchlist actions.
- **Completed:**
  1. Đã triển khai `SearchExperience.tsx` đầy đủ: URL params sync, debounced input, generation guard, loading skeleton, empty state, error retry, pagination controls.
  2. Đã cập nhật `MovieCard.tsx` với poster placeholder an toàn và icon `Film`.
  3. Xây dựng test suite `search_experience_suite.mjs` (6/6 tests PASS).
  4. Chạy kiểm thử: `catalog_service_suite.mjs` (9/9 PASS), `m1_behavior_suite.mjs` (25/25 PASS), `npx tsc --noEmit` (0 lỗi), `npm run build` (build thành công tuyệt đối, 7/7 pages generated).
  5. Đã tạo snapshot `.round4_snapshot/`, patch `ROUND_4.patch` (numstat & reverse check pass exit 0), manifest `ROUND_4_MANIFEST.json`, và report `ROUND_4_REPORT.md`.
  6. Phát hành trạng thái `ready_for_review` trong `M2_M3_STATUS.json` và freeze source code.

---

## Round 5 — S1–S4 Search / Browse Fixes & Production Component Tests

- **Started At:** 2026-10-14T08:05:00+07:00
- **Completed At:** 2026-10-14T08:18:30+07:00
- **targetRoundId:** 5 | **promptVersion:** 5
- **Run ID:** `run-round5-20261014-0805`
- **Reviewed Run ID:** `run-round4-20261014-0750`
- **Goal:**
  1. Sửa S1: Bảo toàn input draft khi router navigation phản hồi trễ (own navigation acknowledgment vs external back/forward).
  2. Sửa S2: Gắn canonical query key vào `dataSnapshot`; ngăn chặn fake empty state hiển thị query mới khi request mới đang in-flight.
  3. Sửa S3: Trích xuất, kiểm tra hợp lệ và forward đầy đủ URL `yearMin`, `yearMax`, `size` sang `browseCatalog`; thêm summary bar và reset an toàn.
  4. Sửa S4: Thay thế hoàn toàn simulation tests bằng 12 tests chạy actual production code (`SearchExperience.tsx` và `MovieCard.tsx`) qua harness TypeScript transpilation.
- **Completed:**
  1. Đã sửa S1, S2, S3 trong `frontend/features/search/components/SearchExperience.tsx`.
  2. Đã viết lại toàn bộ `frontend/tests/search_experience_suite.mjs` chạy mã nguồn thực thi thật (12/12 PASS).
  3. Kiểm thử tổng hợp frontend: 46/46 tests PASS (12 actual search + 9 catalog client + 25 M1 behavior).
  4. Chạy reviewer repro `ROUND_4_search_repro.cjs`: 3/3 scenarios PASS.
  5. TypeScript `npx tsc --noEmit` exit 0; Next.js `npm run build` exit 0 (7/7 routes generated).
  6. Backend Spring Boot giữ nguyên baseline 17/17 tests PASS từ Round 3.
  7. Tạo patch `ROUND_5.patch` (`git apply --numstat` và `git apply --reverse --check` exit 0), manifest `ROUND_5_MANIFEST.json`, báo cáo `ROUND_5_REPORT.md`.
  8. Cập nhật `M2_M3_STATUS.json` lên `state: "ready_for_review"`, freeze toàn bộ source code.

---

## Round 6 — Home, Detail & Profile Catalog Backend Cutover & Journey Tests

- **Started At:** 2026-10-14T08:26:08+07:00
- **Completed At:** 2026-10-14T08:39:00+07:00
- **targetRoundId:** 6 | **promptVersion:** 6
- **Run ID:** `run-round6-20261014-0826`
- **Reviewed Run ID:** `run-round5-20261014-0805`
- **Goal:**
  1. Cutover Home page sang `browseCatalog` với `animationOnly=true`, loading skeleton, error retry, empty catalog state, safe hero backdrop fallback.
  2. Cutover Detail page sang `getCatalogMovieById` theo canonical ID, phân biệt 200, 404 (null) và 5xx/timeout với retry, deterministic similar rail từ backend, safe media fallbacks (backdrop, poster, video capability).
  3. Cutover Profile sang `getCatalogMovieById` cho toàn bộ canonical IDs, bounded metadata cache (200 items, 5-min TTL), phân biệt orphan 404 và network connection error, bảo lưu toàn bộ M1-F06 rating retry logic.
  4. Boundary cleanup: strict integer URL parsing (`/^\d+$/`) trong SearchExperience, strict literal ID comparison (`movie.id !== cleanId`) trong `getCatalogMovieById`.
  5. Xây dựng bộ test mới `m2_journey_suite.mjs` kiểm thử thực thi component và tính nhất quán xuyên suốt Home -> Detail -> Profile.
- **Completed:**
  1. Đã hoàn thành cutover mã nguồn trên 7 files ứng dụng và 2 test suites.
  2. Kiểm thử tổng hợp frontend: **51/51 tests PASS** (5 M2 journey + 12 search component + 9 catalog client + 25 M1 behavior).
  3. Chạy reviewer repro `ROUND_4_search_repro.cjs`: 3/3 scenarios PASS (0 regression).
  4. TypeScript `npx tsc --noEmit` exit 0; Next.js `npm run build` exit 0 (7/7 routes generated).
  5. Backend Spring Boot giữ nguyên baseline 17/17 tests PASS từ Round 3.
  6. Tạo patch `ROUND_6.patch` (`git apply --numstat` và `git apply --reverse --check` exit 0), manifest `ROUND_6_MANIFEST.json`, báo cáo `ROUND_6_REPORT.md`.
---

## Round 7 — D1–D3 Resolution, M2 E2E Cross-Surface Journey & Catalog Preview Tool

- **Started At:** 2026-10-14T08:52:00+07:00
- **Completed At:** 2026-10-14T09:07:30+07:00
- **targetRoundId:** 7 | **promptVersion:** 7
- **Run ID:** `run-round7-20261014-0852`
- **Reviewed Run ID:** `run-round6-20261014-0826`
- **Goal:**
  1. D1: Tách vòng đời similar rail khỏi main detail loading trong `app/movies/[id]/page.tsx`; hiển thị ngay khi main lookup trả về; similar failure không làm vỡ trang chính.
  2. D2: Cập nhật `EditorialHero.tsx` đọc selector M1 pending/uncertain/intent; hiển thị "Thử lưu lại" / "Thử xóa lại" kèm badge và aria-label chính xác; disable pending.
  3. D3: Thực thi hiệu lực TTL 5 phút và dọn dẹp ID rời thư viện trong `ProfileOverview.tsx`; tái xác thực trên `window.focus` và khi re-add; 404 orphan khác error mạng.
  4. M2 Gate Evidence: Xây dựng bài test tích hợp xuyên bề mặt (Test 7) trên production `WatchlistProvider` và persisted transport: Home save -> Detail rate -> Persist -> Reload Profile.
  5. Catalog Data Handoff: Tạo `docs/fixtures/animation_catalog_fixture.json` (media unverified = null); tạo script preview / dry-run `scripts/preview_animation_catalog.cjs` với chính sách additive_idempotent (ADD, SKIP, CONFLICT); cập nhật `M2_CATALOG_CONTRACT.md`.
- **Completed:**
  1. Đã hoàn thành sửa D1, D2, D3 trên 3 components chính và cập nhật contract.
  2. Tạo bộ candidate fixture hoạt hình và công cụ preview dry-run an toàn (3/3 self-tests PASS).
  3. Kiểm thử tổng hợp frontend: **53/53 tests PASS** (7 M2 journey + 12 search component + 9 catalog client + 25 M1 behavior).
  4. Chạy reviewer repro `ROUND_4_search_repro.cjs`: 3/3 scenarios PASS (0 regression). Giữ nguyên vẹn file repro reviewer `ROUND_6_cutover_repro.cjs`.
  5. TypeScript `npx tsc --noEmit` exit 0; Next.js `npm run build` exit 0 (7/7 routes generated).
  6. Backend Spring Boot giữ nguyên baseline 17/17 tests PASS từ Round 3.
  7. Tạo patch `ROUND_7.patch` (`git apply --numstat` và `git apply --reverse --check` exit 0), manifest `ROUND_7_MANIFEST.json`, báo cáo `ROUND_7_REPORT.md`.
  8. Cập nhật `M2_M3_STATUS.json` lên `state: "ready_for_review"`, freeze toàn bộ source code.







