# ROUND 6 Implementation & Verification Report

> **Loop Mode:** Round-Based Review Cycle (`docs/GEMINI_CODEX_REVIEW_LOOP.md`)  
> **Target Round ID:** 6 | **Prompt Version:** 6  
> **Milestone:** M2 (Catalog Backend & Animation Discovery)  
> **Run ID:** `run-round6-20261014-0826`  
> **Status:** READY FOR REVIEW  
> **Implementation Engineer:** Antigravity (Gemini)  
> **Lead Reviewer:** Codex  

---

## 1. Executive Summary

Trong **Vòng 6**, toàn bộ hành trình người dùng trên ba bề mặt chính (**Home**, **Movie Detail**, và **Profile**) đã được chuyển đổi hoàn toàn (cutover) sang kết nối với máy chủ backend Catalog API thông qua module dùng chung [`catalogService.ts`](file:///d:/Class/movie-rcm-system/frontend/lib/services/catalogService.ts), loại bỏ triệt để việc import dữ liệu phim tĩnh (`@/lib/data/movies`) trên toàn bộ các route sản phẩm:

1. **Home (`frontend/app/page.tsx` & `EditorialHero.tsx`):**
   - Loại bỏ hoàn toàn `import { animationMovies, featuredMovie } from '@/lib/data/movies'`.
   - Toàn bộ nội dung Home được truy vấn từ backend qua `browseCatalog` với cờ `animationOnly=true` nghiêm ngặt:
     - Spotlight Hero & Tuyệt tác đánh giá cao: `browseCatalog({ animationOnly: true, sort: 'rating', direction: 'desc', size: 10 })`.
     - Khám phá hoạt hình mới nhất: `browseCatalog({ animationOnly: true, sort: 'year', direction: 'desc', size: 10 })`.
     - Hoạt hình phiêu lưu & kỳ ảo: `browseCatalog({ animationOnly: true, genres: ['Adventure', 'Fantasy'], size: 10 })`.
   - Xử lý trạng thái đầy đủ:
     - **Loading Skeleton:** Hiển thị khung tải động cho Hero và các rails.
     - **Error State:** Banner thông báo lỗi máy chủ kèm nút "Thử kết nối lại" (Retry), tuyệt đối không fallback về phim giả lập tĩnh.
     - **Empty State:** Hiển thị thông báo hữu ích khi backend chưa có dữ liệu hoạt hình kèm liên kết sang Tìm kiếm và CineBot.
   - [`EditorialHero.tsx`](file:///d:/Class/movie-rcm-system/frontend/features/home/components/EditorialHero.tsx): Xử lý an toàn ảnh nền `backdrop` (nếu null/rỗng thì hiển thị gradient background có nhận diện thương hiệu, tránh Next.js `<Image src="" />` crash) và truyền `poster` chuẩn vào `toggleWatchlist`.

2. **Movie Detail (`frontend/app/movies/[id]/page.tsx` & `MovieDetail.tsx`):**
   - Thay thế `movies.find` tĩnh bằng hàm `getCatalogMovieById(canonicalId)`.
   - Chọn mô hình nạp dữ liệu ở cấp component (request-time loading) với `useEffect` và `AbortController` để `next build` hoàn tất độc lập mà không yêu cầu máy chủ live hoặc GPU.
   - Phân biệt rạch ròi 3 trạng thái phản hồi:
     - **Valid 200:** Hiển thị chi tiết tác phẩm; tải danh sách phim tương đồng (similar rail) một cách xác định từ backend (`browseCatalog({ animationOnly: true, genres: ... })`), loại bỏ current movie ID, không mạo danh AI.
     - **Real 404 (null):** Hiển thị màn hình 404 chuyên biệt với mã định danh `canonicalId` và đường dẫn điều hướng khám phá kho hoạt hình.
     - **5xx / Timeout / Network Error:** Hiển thị banner lỗi kết nối máy chủ kèm nút "Thử kết nối lại", tuyệt đối **không** che giấu thành 404 giả.
   - [`MovieDetail.tsx`](file:///d:/Class/movie-rcm-system/frontend/features/movies/components/MovieDetail.tsx):
     - Safe backdrop & poster fallback: render container gradient / placeholder icon `Film` khi metadata rỗng, ngăn ngừa crash `<Image src="" />`.
     - Video capability: chỉ hiển thị nút "Xem trailer / giới thiệu" khi `movie.videoUrl` tồn tại hợp lệ, không bịa đường dẫn tĩnh `/videos/${id}.mp4`.
     - Bảo toàn 100% cơ chế M1 (uncertain toggle, rating score inputs, retry buttons).

3. **Profile (`frontend/features/profile/components/ProfileOverview.tsx`):**
   - Loại bỏ hoàn toàn `movieMap` và import dữ liệu tĩnh `movies`.
   - Mọi mã phim (canonical IDs) trong `watchlist`, `favorites`, `ratings` đều được hydrate qua `getCatalogMovieById`.
   - Thiết lập **Bộ nhớ đệm giới hạn (Bounded Metadata Cache)**: dung lượng tối đa 200 items, thời gian hết hạn (TTL) 5 phút; chỉ lưu trữ metadata phim công khai, không lưu trữ danh sách cá nhân của người dùng. Tự động deduplicate các request trùng lặp giữa các tab.
   - Phân biệt chính xác giữa **Orphan 404** ("Không có trong catalog (404)" kèm nút gỡ bỏ mục mồ côi) và **Lỗi kết nối mạng** ("Không thể kết nối máy chủ" kèm nút "Thử tải lại"); sự cố mạng không bao giờ xóa nhầm thư viện hoặc gắn cờ orphan.
   - Bảo toàn trọn vẹn toàn bộ các bản sửa lỗi rating retry từ M1-F06.

4. **Boundary Cleanups:**
   - **Literal ID Matching:** Cập nhật `getCatalogMovieById` trong [`catalogService.ts`](file:///d:/Class/movie-rcm-system/frontend/lib/services/catalogService.ts) so sánh literal `movie.id !== cleanId` (loại bỏ `.toLowerCase()` che giấu sai lệch hoa thường theo đúng contract).
   - **Strict Pure Integer URL Parsing:** Cập nhật [`SearchExperience.tsx`](file:///d:/Class/movie-rcm-system/frontend/features/search/components/SearchExperience.tsx) sử dụng hàm `parseStrictInteger` (kiểm tra `/^\d+$/`), từ chối các chuỗi số thực hoặc tiền tố ký tự như `1.5` hay `2junk`.

---

## 2. Changeset & Hash Manifest

### 2.1 Danh sách tập tin thay đổi trong Vòng 6

| File | Trạng thái | SHA256 Hash | Size (Bytes) |
| :--- | :--- | :--- | :--- |
| `frontend/lib/services/catalogService.ts` | **Modified** | `7da7217b58a437e944bb723f648d0913f481edd43b8a432bcb58cc86b4c5f3f9` | 13,410 |
| `frontend/features/search/components/SearchExperience.tsx` | **Modified** | `586450650c0e90ca46b2b0810b8afd21f2e591441dd452de54b07855e272b311` | 22,826 |
| `frontend/app/page.tsx` | **Modified** | `77a59db5c25f0798f3abbe5607adc537ee88e47edb37c70fc1197a6513fa5731` | 15,432 |
| `frontend/features/home/components/EditorialHero.tsx` | **Modified** | `97215e54295e3cf31bea42d304500c7f4d9c72c048cf9f56192afa70f1ba380b` | 4,438 |
| `frontend/app/movies/[id]/page.tsx` | **Modified** | `1be0d4aeb74669d172d1c9d7327e2f5a84f98657e2a20137423f66dbe8cae324` | 6,549 |
| `frontend/features/movies/components/MovieDetail.tsx` | **Modified** | `d62906744c59aeabd21905220d37417c4eb384651a151c5147e4f35109d73f0b` | 20,989 |
| `frontend/features/profile/components/ProfileOverview.tsx` | **Modified** | `e34c67fd4b2438dc49af91d874ae8551b5583ed203dfe767851c87ec684ca13e` | 49,814 |
| `frontend/tests/catalog_service_suite.mjs` | **Modified** | `ebf5a153a329b1510ee18aa9d50c65fe5f10a251a662006d4eb38a9f9fb5f924` | 11,626 |
| `frontend/tests/m2_journey_suite.mjs` | **Added** | `68073b8fb37663eafeebc5057e2cdaeb7430d070bbdd6557276911c3b42aae20` | 28,786 |

### 2.2 Tính toàn vẹn của Patch

- **Patch file:** [`docs/reports/ROUND_6.patch`](file:///d:/Class/movie-rcm-system/docs/reports/ROUND_6.patch)
- **Lệnh kiểm tra numstat:**
  ```bash
  git apply --numstat docs/reports/ROUND_6.patch
  ```
  *Kết quả:*
  ```
  2	2	frontend/lib/services/catalogService.ts
  22	15	frontend/features/search/components/SearchExperience.tsx
  168	46	frontend/app/page.tsx
  15	9	frontend/features/home/components/EditorialHero.tsx
  152	7	frontend/app/movies/[id]/page.tsx
  40	23	frontend/features/movies/components/MovieDetail.tsx
  46	61	frontend/features/profile/components/ProfileOverview.tsx
  27	0	frontend/tests/catalog_service_suite.mjs
  795	0	frontend/tests/m2_journey_suite.mjs
  ```
  *Exit code:* `0`.
- **Lệnh kiểm tra reverse patch check:**
  ```bash
  git apply --reverse --check docs/reports/ROUND_6.patch
  ```
  *Exit code:* `0` (Sạch sẽ tuyệt đối, không có reject hay conflict).

---

## 3. Verification & Execution Evidence

### 3.1 Test Suites Execution (51/51 Passed)

Chạy đồng thời toàn bộ 4 test suites của frontend:
```bash
node --test tests/m2_journey_suite.mjs tests/search_experience_suite.mjs tests/catalog_service_suite.mjs tests/m1_behavior_suite.mjs
```

**Kết quả chi tiết:**
```
✔ 1. Catalog Client: browseCatalog constructs correct query string and normalizes PageResponse (133.6505ms)
✔ 2. C1: External abort after headers received while body is pending aborts transport and throws cancellation (36.3143ms)
✔ 3. C1: Slow body triggers timeout and cleans up timers (77.5217ms)
✔ 4. C1: Pre-aborted external signal rejects immediately without setting timer (18.504ms)
✔ 5. C2: Malformed paginated payload (data={} or missing items) throws 502 (22.9437ms)
✔ 6. C2: normalizeCatalogMovie rejects missing required fields and never fabricates phantom zeros (21.6812ms)
✔ 7. C2: getCatalogMovieById verifies response ID matches requested canonical ID (40.9487ms)
✔ 8. C2: getCatalogMovieById returns null on 404 HTML body without syntax error (17.7867ms)
✔ 9. C2: Search/Query precedence: blank query falls back to search parameter (20.5305ms)
✔ 1. Auth login sends verbatim raw password with spaces (141.2937ms)
✔ 2. R1 (P1): Logout while response JSON is pending does NOT resurrect session (32.3087ms)
✔ 3. R1: Runtime validation rejects malformed auth payloads (29.3533ms)
✔ 4. F1 (P1): Late A 401 response after B login does NOT trigger handleSessionExpired on B (102.9678ms)
✔ 5. F1 (P1): Old A finally does NOT release B synchronous lock for the same item (84.8272ms)
✔ 6. F2 (P1): First render of User B derives empty state before passive effects flush (51.3824ms)
✔ 7. F3 (P2): Same-actor refresh does NOT invalidate pending mutation or leave pending stuck (34.8588ms)
✔ 8. F4 (P2): Slow JSON body parsing after headers triggers timeout and aborts (43.4651ms)
✔ 9. R3: Targeted rollback: X failure retains successfully added Y (40.0877ms)
✔ 10. R4: Unavailable sessions do NOT write to guest storage (36.7929ms)
✔ 11. R7: removeRating removes rating and sends DELETE request without mutating watchlist (36.9208ms)
✔ 12. G1 (P1): Boot checking to verified A restores nonempty library (watchlist, favorites, ratings) (38.0228ms)
✔ 13. G1 (P1): A -> logout -> B loads B nonempty library without leaking A library (47.8661ms)
✔ 14. G2 (P2): Older refresh body arriving after successful add preserves newly added items (37.67ms)
✔ 15. G2 (P2): Refresh during delete followed by delete success keeps item deleted (35.9132ms)
✔ 16. G2 (P2): Rating update is protected against stale read returning old score (28.3427ms)
✔ 17. G3 (P2): Unknown write outcome (network error) triggers background reconcile (28.6815ms)
✔ 18. H1 (P2): Read initiated while write was pending cannot overwrite subsequent commit when read body arrives late (33.8164ms)
✔ 19. H2 (P2): Unknown outcome on write network loss marks operation uncertain and retrying toggle maintains POST intent (27.5012ms)
✔ 20. H2 (P2): Unknown outcome on DELETE maintains delete intent on retry without inverting to POST (39.699ms)
✔ 21. UI H2: MovieCard renders unconfirmed ADD badge/label and click triggers retry POST, returning to normal on confirm (42.4317ms)
✔ 22. UI H2: MovieCard renders unconfirmed DELETE label and click triggers retry DELETE, returning to normal on confirm (64.4502ms)
✔ 23. UI H2: MovieDetail renders unconfirmed Watchlist, Favorite, and Rating with explicit retry buttons and handles new rating selection (13.2959ms)
✔ 24. UI H2: ProfileOverview renders persistent library error banner and orphan retry actions for Watchlist, Favorites, and Ratings (28.653ms)
✔ 25. UI H2: ProfileOverview rating retry with production provider executes POST rating without deleting, and respects remove intent and confirmed transition across found/error/not_found rows (119.6976ms)
✔ 1. Home: Enforces animationOnly=true across all queries, handles empty and error states (13.4119ms)
✔ 2. Detail: Canonical ID lookup, real 404 vs server error, and deterministic similar rail (6.8505ms)
✔ 3. MovieDetail: Safe media fallbacks (missing backdrop, missing poster, and video playback capability) (4.3685ms)
✔ 4. Profile: Resolves all canonical IDs via API, uses bounded cache, and distinguishes orphan from network error (8.0477ms)
✔ 5. Cross-surface consistency: Canonical ID and attributes match across Home, Detail, and Profile (3.6799ms)
✔ 1. S1 (P2): Delayed router navigation does NOT overwrite user typing draft (10.8315ms)
✔ 2. S1 (P2): External navigation (browser back/forward or deep link) syncs draft input (2.068ms)
✔ 3. S1 (P2): Clear button resets input draft and triggers push with query removed (2.2987ms)
✔ 4. S2 (P2): Snapshot query key binding prevents false no-results on pending query transition (2.6714ms)
✔ 5. S2 (P2): Query transition from results to pending preserves previous results labeled as updating (2.0243ms)
✔ 6. S3 (P2): URL yearMin, yearMax, and size parameters are parsed, validated, and forwarded to browseCatalog (2.3805ms)
✔ 7. S3 (P2): Invalid year range (yearMin > yearMax) renders warning and resets cleanly (3.2901ms)
✔ 8. S4 (P2): Generation guard - Slow response A does NOT overwrite subsequent response B (2.3182ms)
✔ 9. S4 (P2): Cancellation and cleanup on unmount (1.9113ms)
✔ 10. S4 (P2): MovieCard renders fallback placeholder when poster is missing or empty (2.7317ms)
✔ 11. S4 (P2): MovieCard renders Next Image with correct src and alt when poster is valid (1.922ms)
✔ 12. S4 (P2): MovieCard renders unconfirmed watchlist status badge and executes retry action (2.9745ms)
ℹ tests 51
ℹ suites 0
ℹ pass 51
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1562.8282
```
**Exit Code:** `0` (51 passed, 0 failed, 0 skipped).

### 3.2 Codex Search Repro Execution (Zero Regression)

Chạy script kiểm tra độc lập của Codex (`docs/reviews/repro/ROUND_4_search_repro.cjs`):
```bash
node docs/reviews/repro/ROUND_4_search_repro.cjs
```
**Kết quả đầu ra:**
```json
[
  {
    "scenario": "delayed router update B arrives after user typed C",
    "pushes": [
      "/search?q=B"
    ],
    "before": "C",
    "after": "C"
  },
  {
    "scenario": "old empty data while new query pending",
    "showsNoResultsForNew": false,
    "showsLoading": true
  },
  {
    "scenario": "year and size URL options sent to browseCatalog",
    "yearMin": 2000,
    "yearMax": 2005,
    "size": 2
  }
]
```
**Exit Code:** `0` (Bảo đảm Search Experience không có bất kỳ regression nào).

### 3.3 TypeScript Typecheck & Production Build

- **Typecheck:**
  ```bash
  npx tsc --noEmit
  ```
  *Exit code:* `0` (0 lỗi).
- **Production Build:**
  ```bash
  npm run build
  ```
  *Exit code:* `0` (Tất cả 7/7 routes biên dịch thành công, bao gồm `/`, `/movies/[id]`, `/profile`, `/search`).

### 3.4 Backend Test Baseline Reference

Backend Spring Boot giữ nguyên baseline đã nghiệm thu **17/17 tests PASS** từ Vòng 3.

---

## 4. Acceptance Matrix (Round 6)

| Khu vực | Trạng thái trước Vòng 6 | Triển khai Vòng 6 | Kiểm thử xác minh | Kết luận |
| :--- | :--- | :--- | :--- | :--- |
| **Home Page** | Dùng mảng tĩnh `animationMovies` và `featuredMovie`. Không kết nối API. | Kết nối `browseCatalog` với `animationOnly=true` cho cả 3 rails; hỗ trợ Skeleton, Error Retry, Empty message. Safe backdrop fallback. | Test 1 trong `m2_journey_suite.mjs` | **RESOLVED** |
| **Movie Detail** | Dùng `movies.find` local. Không hỗ trợ real 404 vs server error. Video bịa `/videos/${id}.mp4`. | Dùng `getCatalogMovieById`. Phân biệt 200, 404 (null), và 5xx/timeout (banner retry, không giả 404). Video chỉ hiện khi có `videoUrl`. Safe media fallback. Similar rail từ backend. | Test 2 & 3 trong `m2_journey_suite.mjs` | **RESOLVED** |
| **Profile** | Dùng `movieMap` local bypass API cho các phim quen thuộc. Raw fetch không qua shared client. | Loại bỏ `movieMap`. Mọi canonical ID hydrate qua `getCatalogMovieById`. Bounded cache (200 entries, 5-min TTL). Phân biệt orphan 404 và connection error. | Test 4 trong `m2_journey_suite.mjs` | **RESOLVED** |
| **Cross-Surface Journey** | Dữ liệu giữa các trang có thể lệch nhau nếu khác nguồn. | Nhất quán 100% canonical ID và metadata giữa Home, Detail, và Profile. | Test 5 trong `m2_journey_suite.mjs` | **RESOLVED** |
| **Boundary Cleanups** | `parseInt` nhận `1.5`/`2junk`; `getCatalogMovieById` dùng `.toLowerCase()`. | `parseStrictInteger` kiểm tra `/^\d+$/`. `getCatalogMovieById` so sánh literal `movie.id !== cleanId`. | Test 7 trong `catalog_service_suite.mjs` | **RESOLVED** |

---

## 5. Scope Boundaries & Next Steps

- **Scope tuân thủ:** Toàn bộ công việc gói gọn trong phạm vi cutover Home, Detail, Profile và test journey tương ứng. Không can thiệp sang backend hay DB live, không chạm AI/FastAPI/Qwen, không commit/push.
- **Tiếp theo:** Sẵn sàng cho Codex review toàn bộ lát cắt M2 UI Cutover trong Vòng 6.
