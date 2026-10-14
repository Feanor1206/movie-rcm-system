# ROUND 4 Implementation & Verification Report

> **Loop Mode:** Round-Based Review Cycle (`docs/GEMINI_CODEX_REVIEW_LOOP.md`)  
> **Target Round ID:** 4 | **Prompt Version:** 4  
> **Milestone:** M2 (Catalog Backend & Animation Discovery)  
> **Run ID:** `run-round4-20261014-0750`  
> **Status:** READY FOR REVIEW  
> **Implementation Engineer:** Antigravity (Gemini)  
> **Lead Reviewer:** Codex  

---

## 1. Executive Summary

Trong **Vòng 4**, kỹ sư triển khai đã hoàn thành toàn diện lát cắt giao diện **Search / Browse kết nối trực tiếp với backend Catalog API** theo đúng yêu cầu trong `docs/prompts/GEMINI_CURRENT_TASK.md`:

1. **Kết nối Backend Catalog API & Khẳng định Ràng buộc Hoạt hình (Animation Constraint):**
   - Thay thế toàn bộ logic lọc dữ liệu tĩnh trong `SearchExperience.tsx` bằng hàm `browseCatalog` từ module dùng chung [`catalogService.ts`](file:///d:/Class/movie-rcm-system/frontend/lib/services/catalogService.ts).
   - Luôn truyền cờ `animationOnly=true` trong toàn bộ hành trình web hoạt hình; khi người dùng chọn thêm các thể loại phụ (như `Adventure`, `Family`, `Fantasy`), điều kiện `animationOnly=true` vẫn được bảo tồn nghiêm ngặt (kết hợp logic `AND` trên backend).
   - Tuyệt đối không fallback về dữ liệu phim tĩnh khi gặp sự cố mạng hoặc lỗi máy chủ.

2. **URL là Nguồn Chân lý Duy nhất (Single Source of Truth):**
   - Đọc và đồng bộ hóa hai chiều toàn bộ trạng thái tìm kiếm qua URL: từ khóa (`q` hoặc `query`), thể loại (`genres` hoặc legacy `genre`), tiêu chí sắp xếp (`sort`), chiều sắp xếp (`direction`), và số trang (`page`).
   - Duy trì tương thích hoàn hảo với các liên kết `/search?genre=...` sẵn có từ Navbar/Footer.
   - Nhập liệu phản hồi tức thì qua state draft `inputValue`; cơ chế debounce (350ms) tự động đồng bộ lên URL và dọn dẹp timer khi unmount.
   - Thay đổi từ khóa tìm kiếm, thể loại hoặc sắp xếp tự động reset `page` về 0; trong khi thao tác chuyển trang bảo lưu toàn vẹn các bộ lọc đang chọn.
   - Tự động chuẩn hóa các URL không hợp lệ (kẹp `page < 0` về 0) mà không gây crash giao diện.

3. **Bảo vệ Bất đồng bộ, Hủy yêu cầu & Chống Out-of-Order Race Conditions:**
   - Áp dụng **Request Generation Guard** (`currentRequestId`): loại bỏ triệt để nguy cơ phản hồi chậm từ truy vấn cũ A ghi đè kết quả của truy vấn mới B (chống stale response).
   - Tự động hủy (`AbortController.abort()`) yêu cầu mạng đang dang dở khi người dùng thay đổi bộ lọc hoặc khi rời trang (unmount).
   - Phân loại lỗi chính xác qua cờ `isCanceled`: hủy chủ động từ người dùng diễn ra im lặng, không hiển thị thông báo lỗi mạng giả.
   - Trạng thái giao diện phân định rạch ròi:
     - **Loading Skeleton:** Hiển thị 12 khung thẻ phim nhấp nháy khi tải lần đầu.
     - **Updating Indicator:** Hiển thị badge mờ "Đang cập nhật..." khi cập nhật kết quả nền.
     - **Error State:** Hộp thông báo lỗi riêng biệt kèm nút "Thử kết nối lại" (Retry); tuyệt đối không báo "Không tìm thấy phim" khi gặp lỗi hệ thống.
     - **Empty State:** Thông báo không có kết quả rõ ràng kèm nút "Đặt lại bộ lọc" và "Hỏi CineBot gợi ý ngay".

4. **Nâng cấp An toàn Thẻ Phim ([`MovieCard.tsx`](file:///d:/Class/movie-rcm-system/frontend/features/movies/components/MovieCard.tsx)):**
   - Thêm cơ chế placeholder trực quan với icon `Film` và tiêu đề phim khi `poster` bị null hoặc rỗng, ngăn chặn triệt để lỗi Next.js `<Image src="" />` crash hoặc hiển thị nhầm ảnh tác phẩm khác.
   - Sử dụng đường dẫn định danh chuẩn (`/movies/${movie.id}`).
   - Hiển thị đầy đủ năm phát hành (`year`) và điểm đánh giá (`rating`) số thực theo đúng contract.
   - Bảo toàn 100% cơ chế Watchlist M1 (xử lý bất đồng bộ, nhãn uncertain retry, unconfirmed badge).

---

## 2. Changeset & Files Modified in Round 4

Toàn bộ các chỉnh sửa trong Vòng 4 được đối chiếu qua snapshot baseline `.round4_snapshot/`:

| File | Trạng thái | Mô tả thay đổi |
| :--- | :--- | :--- |
| `frontend/features/search/components/SearchExperience.tsx` | **Chỉnh sửa** | Kết nối `browseCatalog` với `animationOnly=true`, đồng bộ hóa URL làm source of truth, generation guard chống out-of-order, debounce và phân trang. |
| `frontend/features/movies/components/MovieCard.tsx` | **Chỉnh sửa** | Bổ sung visual placeholder cho trường hợp `poster` null/empty; bảo toàn canonical links, media contract và M1 uncertain watchlist actions. |
| `frontend/tests/search_experience_suite.mjs` | **Tạo mới** | Bộ 6 unit & behavioral tests kiểm thử URL parsing/normalization, canonical serialization, generation guard (slow A vs fast B), error/empty distinction, và poster fallback. |

---

## 3. Verification & Evidence

### 3.1 Next.js Production Build
Lệnh thực thi:
```bash
npm run build
```
**Kết quả đầu ra:**
```
   ▲ Next.js 15.1.2
   - Environments: .env.local

   Creating an optimized production build ...
 ✓ Compiled successfully
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (0/7) ...
   Generating static pages (1/7) 
   Generating static pages (3/7) 
   Generating static pages (5/7) 
 ✓ Generating static pages (7/7)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                              Size     First Load JS
┌ ○ /                                    6.05 kB         136 kB
├ ○ /_not-found                          140 B           106 kB
├ ƒ /api/chat                            140 B           106 kB
├ ƒ /movies/[id]                         4.6 kB          135 kB
├ ○ /profile                             7.35 kB         137 kB
└ ○ /search                              5.51 kB         136 kB
+ First Load JS shared by all            105 kB
```
**Exit Code:** `0` (Build production thành công tuyệt đối, 0 warning/lỗi).

### 3.2 TypeScript Typecheck
Lệnh thực thi:
```bash
npx tsc --noEmit
```
**Exit Code:** `0` (0 lỗi typecheck).

### 3.3 Search Experience Suite
Lệnh thực thi:
```bash
node --test tests/search_experience_suite.mjs
```
**Kết quả đầu ra:**
```
✔ 1. URL Source of Truth: reads query, legacy genre, modern genres, sort, and clamps invalid page (1.5822ms)
✔ 2. Canonical Serialization: modifying query, filter, or sort resets page to 0, while paginating preserves filters (0.3649ms)
✔ 3. Async Request Generation Guard: slow response A does NOT overwrite subsequent response B (104.2588ms)
✔ 4. Animation Constraint Guarantee: animationOnly is ALWAYS true, even with sub-genres selected (0.5863ms)
✔ 5. Error vs Empty State Distinction: network/server failures do NOT present as no-results empty state (0.7491ms)
✔ 6. MovieCard Poster Fallback: null or empty poster does not crash and renders placeholder (0.5604ms)
ℹ tests 6
ℹ suites 0
ℹ pass 6
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 264.2354
```
**Exit Code:** `0` (6/6 tests PASS).

### 3.4 Catalog Service Transport Suite
Lệnh thực thi:
```bash
node --test tests/catalog_service_suite.mjs
```
**Kết quả đầu ra:**
```
✔ 1. Catalog Client: browseCatalog constructs correct query string and normalizes PageResponse (164.9305ms)
✔ 2. C1: External abort after headers received while body is pending aborts transport and throws cancellation (29.0347ms)
✔ 3. C1: Slow body triggers timeout and cleans up timers (76.2546ms)
✔ 4. C1: Pre-aborted external signal rejects immediately without setting timer (45.4581ms)
✔ 5. C2: Malformed paginated payload (data={} or missing items) throws 502 (35.5679ms)
✔ 6. C2: normalizeCatalogMovie rejects missing required fields and never fabricates phantom zeros (18.6568ms)
✔ 7. C2: getCatalogMovieById verifies response ID matches requested canonical ID (16.3988ms)
✔ 8. C2: getCatalogMovieById returns null on 404 HTML body without syntax error (15.151ms)
✔ 9. C2: Search/Query precedence: blank query falls back to search parameter (20.6545ms)
ℹ tests 9
ℹ suites 0
ℹ pass 9
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 884.5252
```
**Exit Code:** `0` (9/9 tests PASS).

### 3.5 M1 Behavioral Regression Suite
Lệnh thực thi:
```bash
node --test tests/m1_behavior_suite.mjs
```
**Kết quả đầu ra:**
```
ℹ tests 25
ℹ suites 0
ℹ pass 25
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1943.3951
```
**Exit Code:** `0` (25/25 tests PASS; toàn bộ cơ chế Auth/Library/Retry của M1 được bảo toàn nguyên vẹn).

### 3.6 Backend Spring Boot Integration Suite (Prior Evidence Vòng 3)
- Kết quả kiểm thử Spring Boot trước đó đạt **17/17 tests PASS** (8 Auth/Library + 9 Catalog Integration). Backend source code không bị thay đổi trong Vòng 4.

### 3.7 Patch Integrity Verification
Lệnh thực thi:
```bash
git apply --numstat docs/reports/ROUND_4.patch
git apply --reverse --check docs/reports/ROUND_4.patch
```
**Kết quả đầu ra:**
```
304	64	frontend/features/search/components/SearchExperience.tsx
23	12	frontend/features/movies/components/MovieCard.tsx
230	0	frontend/tests/search_experience_suite.mjs
```
- `git apply --reverse --check docs/reports/ROUND_4.patch` trả về **exit code 0** không có xung đột, chứng minh patch khôi phục hoàn hảo về baseline `.round4_snapshot/`.

---

## 4. Checkpoint Deliverables & Artifacts

- **Snapshot Baseline:** `.round4_snapshot/`
- **Patch Vòng 4:** [`docs/reports/ROUND_4.patch`](file:///D:/Class/movie-rcm-system/docs/reports/ROUND_4.patch)
- **Manifest File Hashes:** [`docs/reports/ROUND_4_MANIFEST.json`](file:///D:/Class/movie-rcm-system/docs/reports/ROUND_4_MANIFEST.json)
- **Báo cáo chi tiết:** [`docs/reports/ROUND_4_REPORT.md`](file:///D:/Class/movie-rcm-system/docs/reports/ROUND_4_REPORT.md)
- **Worklog:** [`docs/reports/M2_M3_WORKLOG.md`](file:///D:/Class/movie-rcm-system/docs/reports/M2_M3_WORKLOG.md)
- **Trạng thái quy trình:** [`docs/reports/M2_M3_STATUS.json`](file:///D:/Class/movie-rcm-system/docs/reports/M2_M3_STATUS.json) (`state: "ready_for_review"`)

---

## 5. Proposed Next Steps for Round 5

Sau khi Codex nghiệm thu Vòng 4:
1. **Triển khai Homepage Animation Rails:**
   - Kết nối danh mục phim hoạt hình nổi bật trên trang chủ (`app/page.tsx` và `EditorialHero.tsx` / `MovieSection.tsx`) với backend catalog qua `browseCatalog({ animationOnly: true, size: 10, sort: 'rating' })`.
2. **Triển khai Movie Detail Cutover:**
   - Kết nối trang chi tiết phim `app/movies/[id]/page.tsx` với backend `getCatalogMovieById(id)`.
