# ROUND 7 Implementation & Verification Report

> **Loop Mode:** Round-Based Review Cycle (`docs/GEMINI_CODEX_REVIEW_LOOP.md`)  
> **Target Round ID:** 7 | **Prompt Version:** 7  
> **Milestone:** M2 (Catalog Backend & Animation Discovery)  
> **Run ID:** `run-round7-20261014-0852`  
> **Status:** READY FOR REVIEW  
> **Implementation Engineer:** Antigravity (Gemini)  
> **Lead Reviewer:** Codex  

---

## 1. Executive Summary

Trong **Vòng 7**, toàn bộ các findings **D1, D2, D3** từ đợt review Round 6 của Codex cùng các mảnh bằng chứng cổng M2 còn thiếu đã được giải quyết đồng bộ, triệt để và được xác minh qua các bài kiểm thử component thực thi mã nguồn thật (production code):

1. **D1 — Tách vòng đời Similar Rail khỏi Main Detail ([`app/movies/[id]/page.tsx`](file:///d:/Class/movie-rcm-system/frontend/app/movies/[id]/page.tsx)):**
   - Main detail hiển thị ngay lập tức khi `getCatalogMovieById(canonicalId)` thành công (`setMovie(fetchedMovie)` và `setLoading(false)`). Toàn bộ tiêu đề, thông tin và các hành động lưu/chấm điểm được giải phóng khỏi skeleton, không còn bị phụ thuộc vào request similar rail tùy chọn.
   - Similar rail được nạp nền bất đồng bộ độc lập: nếu similar service phản hồi chậm hoặc thất bại (timeout / 500), lỗi tương tự chỉ gán danh sách gợi ý rỗng (`setSimilarMovies([])`), tuyệt đối **không** biến màn hình chính thành error banner hoặc 404.
   - Duy trì generation guard (`isCurrent`) và abort controller dọn dẹp triệt để tại async boundary khi unmount hoặc đổi ID.

2. **D2 — Hero hỗ trợ trọn vẹn ngữ nghĩa M1 Pending & Uncertain Intent ([`features/home/components/EditorialHero.tsx`](file:///d:/Class/movie-rcm-system/frontend/features/home/components/EditorialHero.tsx)):**
   - Đọc đầy đủ các selector từ `useWatchlist()`: `isActionPending`, `isActionUnconfirmed`, `getActionIntent`.
   - Khi ở trạng thái bất định (uncertain):
     - Ý định ADD (commit POST thành công nhưng mất phản hồi mạng): Hiển thị nhãn chữ **"Thử lưu lại"**, aria-label **"Chưa xác nhận lưu • Thử lưu lại [tên phim] vào danh sách xem"**, badge cảnh báo màu hổ phách **"Chưa xác nhận"** kèm icon `RefreshCw`. Tuyệt đối không hiển thị "Xóa khỏi Watchlist".
     - Ý định REMOVE (commit DELETE thành công nhưng mất phản hồi): Hiển thị nhãn chữ **"Thử xóa lại"**, aria-label **"Chưa xác nhận xóa • Thử xóa lại [tên phim] khỏi danh sách xem"**, badge cảnh báo. Tuyệt đối không hiển thị "Thêm vào Watchlist".
     - Khi người dùng click retry: gọi `toggleWatchlist` thực thi đúng ý định đã lưu của journal.
   - Khi ở trạng thái in-flight (pending): nút bị `disabled`, hiển thị icon xoay `Loader2` và nhãn **"Đang cập nhật..."**, chống submit trùng lặp.
   - Khi xác nhận thành công: chuyển đổi mượt mà trở lại toggle bình thường ("Đã lưu Watchlist" / "+ Thêm vào Watchlist").

3. **D3 — Thực thi hiệu lực TTL và Dọn dẹp Metadata Profile ([`features/profile/components/ProfileOverview.tsx`](file:///d:/Class/movie-rcm-system/frontend/features/profile/components/ProfileOverview.tsx)):**
   - Loại bỏ đường vòng tồn tại vô hạn trong state `remoteMovies`: bổ sung trường `expiresAt` cho mỗi bản ghi `found` (TTL 5 phút).
   - Hàm `resolveMovieItem(id)` kiểm tra `now <= expiresAt`; nếu đã hết hạn, trả về `{ status: 'loading' }` thay vì trả dữ liệu cũ.
   - Xóa bỏ ID không còn trong thư viện: effect dọn dẹp tự động prune các key khỏi `remoteMovies` và abort các fetcher đang bay khi danh sách ID thay đổi, ngăn ngừa rò rỉ bộ nhớ.
   - Cơ chế tái xác thực (revalidation):
     - Tự động kích hoạt khi item được truy cập lại sau khi hết hạn TTL.
     - Tự động kích hoạt qua sự kiện `window.addEventListener('focus')` khi người dùng quay lại tab (không dùng timer polling nền).
     - Nút "Thử tải lại" (`handleRefetchLibrary`) chủ động dọn dẹp các cache entry hết hạn.
   - Xử lý lỗi an toàn: 404 đánh dấu `not_found` (orphan với nút gỡ); lỗi mạng đánh dấu `error` (kèm nút "Thử tải lại", không xóa thư viện người dùng, không ngụy trang thành 404). Bảo toàn logic rating retry M1-F06.

4. **Bằng chứng Cổng M2 — Hành trình Xuyên Bề mặt End-to-End (Test 7):**
   - Xây dựng bài kiểm thử tích hợp toàn diện chạy trên production `WatchlistProvider` và backend transport lưu trữ giả lập (persisted transport).
   - Luồng nghiệp vụ: Khám phá `spirited-away` trên Home/Hero $\rightarrow$ Lưu vào Watchlist $\rightarrow$ Điều hướng sang Detail và chấm điểm 9/10 $\rightarrow$ Giả lập reload trình duyệt / remount provider mới $\rightarrow$ ProfileOverview nạp lại thư viện từ transport và hydrate metadata, hiển thị chính xác phim trong Watchlist và dòng đánh giá điểm 9.
   - **Ghi chú về bằng chứng:** Kiểm thử trên là component/integration test thực thi mã nguồn TypeScript trong môi trường harness Node.js. Môi trường hiện tại không có công cụ tự động hóa browser (Playwright/Puppeteer), do đó việc build pass hay component test pass được ghi nhận trung thực là xác minh cấp component/logic, không đánh đồng với visual QA trên trình duyệt thật.

5. **Bàn giao Dữ liệu Catalog An toàn & Dry-Run Tool (Item 5):**
   - **Ghi nhận khoảng cách (Catalog Gap):** Spring Boot backend hiện đang seed 6 phim viễn tưởng / chính kịch (`DataInitializer.java`), chưa có bản ghi hoạt hình.
   - **Tập Candidate Fixture:** Đã tạo [`docs/fixtures/animation_catalog_fixture.json`](file:///d:/Class/movie-rcm-system/docs/fixtures/animation_catalog_fixture.json) chứa 6 tác phẩm hoạt hình (`spirited-away`, `your-name`, `isle-of-dogs`, `spider-verse`, `coraline`, `fantasia-1940`) từ fixture repository. Toàn bộ media chưa xác thực (trailer mp4 giả, stock photo) được gán `null`. Provenance được ghi nhận minh bạch là `repository_fixture_unverified_external`.
   - **Công cụ Preview / Dry-Run:** Đã tạo [`scripts/preview_animation_catalog.cjs`](file:///d:/Class/movie-rcm-system/scripts/preview_animation_catalog.cjs) thực thi chính sách `additive_idempotent`:
     - So khớp ID tuyệt đối (không fuzzy-matching).
     - Phân loại rõ ràng: `ADD` (bản ghi mới), `SKIP` (đã có và trùng khớp hoàn toàn — bảo đảm tính bất biến, không nhân đôi), `CONFLICT` (cùng ID nhưng khác metadata — từ chối ghi đè).
     - Có sẵn chế độ self-test tự động (`--test`): 3/3 tests PASS.
     - Tuyệt đối không chạm DB live, không seed production bừa bãi.
   - Cập nhật contract và runbook tại [`docs/contracts/M2_CATALOG_CONTRACT.md`](file:///d:/Class/movie-rcm-system/docs/contracts/M2_CATALOG_CONTRACT.md).

---

## 2. Changeset & Hash Manifest

### 2.1 Danh sách tập tin thay đổi / tạo mới trong Vòng 7

| Tập tin | Trạng thái | SHA256 Hash | Kích thước (Bytes) |
| :--- | :--- | :--- | :--- |
| `frontend/app/movies/[id]/page.tsx` | **Modified** | `782d30aad829740a18688c80b6b8fa1e997743cf09be2ac8ee911d0de3075142` | 6,890 |
| `frontend/features/home/components/EditorialHero.tsx` | **Modified** | `38a52213330a19ee4c8d35f7653469631b3ab1eb6763201e4cb378a91c7479a4` | 6,394 |
| `frontend/features/profile/components/ProfileOverview.tsx` | **Modified** | `a7c60d21e5cb332177d598d2437824d78eded92b5774dd5fe2e2ac4fd463b224` | 52,652 |
| `frontend/tests/m2_journey_suite.mjs` | **Modified** | `eb1736de40bc6b9a00d32a12b207f548f65d689078d5e735909dca112b558e93` | 45,077 |
| `docs/contracts/M2_CATALOG_CONTRACT.md` | **Modified** | `5f42ed225950f26839f1c7065e809994e0196b9d625ace1a3b295fb206ad3678` | 14,533 |
| `docs/fixtures/animation_catalog_fixture.json` | **Added** | `e8941b33059e452ed3e12aae80e79e5ab09abf3dba153e9e769b21afb33bf742` | 2,833 |
| `scripts/preview_animation_catalog.cjs` | **Added** | `256aa04e252cf8eaad4db2c7def6da1b92cb4ef575011098657a9c558144731d` | 7,383 |

### 2.2 Tính toàn vẹn của Patch

- **Patch file:** [`docs/reports/ROUND_7.patch`](file:///d:/Class/movie-rcm-system/docs/reports/ROUND_7.patch)
- **Lệnh kiểm tra numstat:**
  ```bash
  git apply --numstat docs/reports/ROUND_7.patch
  ```
  *Kết quả:*
  ```
  28	22	frontend/app/movies/[id]/page.tsx
  53	6	frontend/features/home/components/EditorialHero.tsx
  92	10	frontend/features/profile/components/ProfileOverview.tsx
  477	73	frontend/tests/m2_journey_suite.mjs
  25	3	docs/contracts/M2_CATALOG_CONTRACT.md
  80	0	docs/fixtures/animation_catalog_fixture.json
  175	0	scripts/preview_animation_catalog.cjs
  ```
  *Exit code:* `0`.
- **Lệnh kiểm tra reverse patch check:**
  ```bash
  git apply --reverse --check docs/reports/ROUND_7.patch
  ```
  *Exit code:* `0` (Sạch sẽ tuyệt đối, không có conflict hay reject).

---

## 3. Verification & Execution Evidence

### 3.1 Test Suites Execution (53/53 Passed)

Chạy đồng thời toàn bộ 4 test suites của frontend:
```bash
node --test tests/m2_journey_suite.mjs tests/search_experience_suite.mjs tests/catalog_service_suite.mjs tests/m1_behavior_suite.mjs
```

**Kết quả chi tiết:**
```
✔ 1. Catalog Client: browseCatalog constructs correct query string and normalizes PageResponse (137.9301ms)
✔ 2. C1: External abort after headers received while body is pending aborts transport and throws cancellation (34.1158ms)
✔ 3. C1: Slow body triggers timeout and cleans up timers (70.7057ms)
✔ 4. C1: Pre-aborted external signal rejects immediately without setting timer (22.4619ms)
✔ 5. C2: Malformed paginated payload (data={} or missing items) throws 502 (21.1226ms)
✔ 6. C2: normalizeCatalogMovie rejects missing required fields and never fabricates phantom zeros (19.0819ms)
✔ 7. C2: getCatalogMovieById verifies response ID matches requested canonical ID (36.0612ms)
✔ 8. C2: getCatalogMovieById returns null on 404 HTML body without syntax error (16.8944ms)
✔ 9. C2: Search/Query precedence: blank query falls back to search parameter (15.6956ms)
✔ 1. Auth login sends verbatim raw password with spaces (128.5104ms)
✔ 2. R1 (P1): Logout while response JSON is pending does NOT resurrect session (48.0894ms)
✔ 3. R1: Runtime validation rejects malformed auth payloads (30.3157ms)
✔ 4. F1 (P1): Late A 401 response after B login does NOT trigger handleSessionExpired on B (91.0231ms)
✔ 5. F1 (P1): Old A finally does NOT release B synchronous lock for the same item (88.2935ms)
✔ 6. F2 (P1): First render of User B derives empty state before passive effects flush (50.4998ms)
✔ 7. F3 (P2): Same-actor refresh does NOT invalidate pending mutation or leave pending stuck (39.4103ms)
✔ 8. F4 (P2): Slow JSON body parsing after headers triggers timeout and aborts (34.9137ms)
✔ 9. R3: Targeted rollback: X failure retains successfully added Y (31.372ms)
✔ 10. R4: Unavailable sessions do NOT write to guest storage (31.0941ms)
✔ 11. R7: removeRating removes rating and sends DELETE request without mutating watchlist (35.5306ms)
✔ 12. G1 (P1): Boot checking to verified A restores nonempty library (watchlist, favorites, ratings) (35.5345ms)
✔ 13. G1 (P1): A -> logout -> B loads B nonempty library without leaking A library (32.8356ms)
✔ 14. G2 (P2): Older refresh body arriving after successful add preserves newly added items (35.3145ms)
✔ 15. G2 (P2): Refresh during delete followed by delete success keeps item deleted (36.0837ms)
✔ 16. G2 (P2): Rating update is protected against stale read returning old score (28.3043ms)
✔ 17. G3 (P2): Unknown write outcome (network error) triggers background reconcile (30.3117ms)
✔ 18. H1 (P2): Read initiated while write was pending cannot overwrite subsequent commit when read body arrives late (37.636ms)
✔ 19. H2 (P2): Unknown outcome on write network loss marks operation uncertain and retrying toggle maintains POST intent (33.3847ms)
✔ 20. H2 (P2): Unknown outcome on DELETE maintains delete intent on retry without inverting to POST (45.0041ms)
✔ 21. UI H2: MovieCard renders unconfirmed ADD badge/label and click triggers retry POST, returning to normal on confirm (40.1351ms)
✔ 22. UI H2: MovieCard renders unconfirmed DELETE label and click triggers retry DELETE, returning to normal on confirm (45.5267ms)
✔ 23. UI H2: MovieDetail renders unconfirmed Watchlist, Favorite, and Rating with explicit retry buttons and handles new rating selection (14.56ms)
✔ 24. UI H2: ProfileOverview renders persistent library error banner and orphan retry actions for Watchlist, Favorites, and Ratings (37.0409ms)
✔ 25. UI H2: ProfileOverview rating retry with production provider executes POST rating without deleting, and respects remove intent and confirmed transition across found/error/not_found rows (108.6621ms)
✔ 1. Home: Enforces animationOnly=true across all queries, handles empty and error states (13.6651ms)
✔ 2. Detail: Canonical ID lookup, real 404 vs server error, and deterministic similar rail (D1 decoupled) (6.7712ms)
✔ 3. MovieDetail: Safe media fallbacks (missing backdrop, missing poster, and video playback capability) (3.5441ms)
✔ 4. EditorialHero: Preserves M1 pending feedback and uncertain retry intent (D2) (4.2226ms)
✔ 5. Profile: Enforces 5-min TTL, clears stale IDs on library update, and preserves items on network error (D3) (6.252ms)
✔ 6. Cross-surface consistency: Canonical ID and attributes match across Home, Detail, and Profile (3.7176ms)
✔ 7. End-to-End M2 User Journey: Home -> Save/Rate -> Provider Persist -> Reload Profile (Cross-surface integration) (14.215ms)
✔ 1. S1 (P2): Delayed router navigation does NOT overwrite user typing draft (12.6645ms)
✔ 2. S1 (P2): External navigation (browser back/forward or deep link) syncs draft input (2.6193ms)
✔ 3. S1 (P2): Clear button resets input draft and triggers push with query removed (3.9298ms)
✔ 4. S2 (P2): Snapshot query key binding prevents false no-results on pending query transition (2.9618ms)
✔ 5. S2 (P2): Query transition from results to pending preserves previous results labeled as updating (2.6501ms)
✔ 6. S3 (P2): URL yearMin, yearMax, and size parameters are parsed, validated, and forwarded to browseCatalog (2.0149ms)
✔ 7. S3 (P2): Invalid year range (yearMin > yearMax) renders warning and resets cleanly (1.8618ms)
✔ 8. S4 (P2): Generation guard - Slow response A does NOT overwrite subsequent response B (2.511ms)
✔ 9. S4 (P2): Cancellation and cleanup on unmount (1.7791ms)
✔ 10. S4 (P2): MovieCard renders fallback placeholder when poster is missing or empty (2.0331ms)
✔ 11. S4 (P2): MovieCard renders Next Image with correct src and alt when poster is valid (1.2572ms)
✔ 12. S4 (P2): MovieCard renders unconfirmed watchlist status badge and executes retry action (1.5986ms)
ℹ tests 53
ℹ suites 0
ℹ pass 53
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1495.1377
```
**Exit Code:** `0` (53 passed, 0 failed, 0 skipped).

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
**Exit Code:** `0` (Search Experience hoàn toàn không có regression).

### 3.3 Dry-Run Catalog Onboarding Tool Verification

Chạy bộ kiểm thử tự động của công cụ preview dry-run:
```bash
node scripts/preview_animation_catalog.cjs --test
```
**Kết quả đầu ra:**
```
Running dry-run verification tests...
✔ Test 1: First run marks all 6 records as ADD
✔ Test 2: Idempotency: second run produces 0 adds and 6 skips
✔ Test 3: Conflict detection correctly flags differing metadata without overwrite
All 3 dry-run tests passed successfully!

[PREVIEW SUMMARY]
  + ADD (New animations to insert):      6
  = SKIP (Idempotent, already identical): 0
  ! CONFLICT (Same ID, differing data):   0
Status: DRY-RUN COMPLETED (NO CHANGES WRITTEN TO DATABASE)
```
**Exit Code:** `0`.

### 3.4 TypeScript Typecheck & Production Build

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

### 3.5 Báo cáo về Artifact Reviewer Repro (`ROUND_6_cutover_repro.cjs`)

Script [`docs/reviews/repro/ROUND_6_cutover_repro.cjs`](file:///d:/Class/movie-rcm-system/docs/reviews/repro/ROUND_6_cutover_repro.cjs) được Codex tạo trong đợt review Round 6 nhằm mục đích chẩn đoán (assert sự tồn tại của lỗi cũ, ví dụ `assert.equal(before, undefined)` và `assert.equal(button.props['aria-label'], 'Xóa khỏi Watchlist')`). Theo đúng chỉ thị của prompt ("không sửa artifact reviewer và không dùng exit 0 đó làm acceptance sau fix"), file repro này được **giữ nguyên vẹn 100% không chỉnh sửa**, và toàn bộ các assertion xác nhận hành vi đã được sửa đúng được chuyển thành các bài test chính thức trong test suite sản phẩm ([`m2_journey_suite.mjs`](file:///d:/Class/movie-rcm-system/frontend/tests/m2_journey_suite.mjs)).

### 3.6 Backend Test Baseline Reference

Backend Spring Boot giữ nguyên baseline đã nghiệm thu **17/17 tests PASS** từ Vòng 3 (không thay đổi mã nguồn backend trong Vòng 7).

---

## 4. Acceptance Matrix (Round 7)

| Hạng mục | Trạng thái Round 6 | Triển khai & Khắc phục Round 7 | Xác minh kiểm thử | Kết luận |
| :--- | :--- | :--- | :--- | :--- |
| **D1: Main Detail Loading** | Bị chặn bởi request `similar` tùy chọn. `setLoading(false)` gọi sau similar. | Tách độc lập similar rail. `setMovie` và `setLoading(false)` gọi ngay khi main lookup trả về. Similar timeout/error không làm vỡ trang chính. | Test 2 trong `m2_journey_suite.mjs` | **RESOLVED** |
| **D2: Hero Pending & Uncertain Intent** | Bỏ qua pending/uncertain/intent; ADD bất định hiển thị "Đã lưu" / "Xóa". | Đọc selector M1; ADD hiện "Thử lưu lại" + badge + aria-label lưu; REMOVE hiện "Thử xóa lại" + badge + aria-label xóa; pending disabled. | Test 4 trong `m2_journey_suite.mjs` | **RESOLVED** |
| **D3: Profile Metadata TTL & Cleanup** | `remoteMovies` lưu vĩnh viễn bỏ qua TTL cache; không dọn dẹp ID rời thư viện. | Thêm `expiresAt` vào state; `resolveMovieItem` từ chối metadata quá 5 phút; dọn dẹp ID đã xóa; revalidate trên `window.focus` và khi re-add. | Test 5 trong `m2_journey_suite.mjs` | **RESOLVED** |
| **M2 Gate: Cross-Surface E2E Journey** | Chỉ kiểm tra static render giữa 3 component độc lập. | Viết Test 7 chạy production `WatchlistProvider` + persisted transport: Home save $\rightarrow$ Detail rate $\rightarrow$ Persist $\rightarrow$ Reload Profile. | Test 7 trong `m2_journey_suite.mjs` | **RESOLVED** |
| **Catalog Data Handoff** | Thiếu fixture animation chuẩn và công cụ preview idempotent. | Tạo candidate fixture JSON (media unverified = null); tạo script dry-run có test ADD/SKIP/CONFLICT; bổ sung contract và runbook. | `scripts/preview_animation_catalog.cjs --test` | **RESOLVED** |

---

## 5. Scope Boundaries & Next Steps

- **Scope tuân thủ nghiêm ngặt:** Không can thiệp DB live, không can thiệp AI/FastAPI/Qwen, không commit/push git, không chạy loop polling.
- **Tiếp theo:** Đóng băng toàn bộ source code và bàn giao trạng thái `ready_for_review` để Codex tiến hành nghiệm thu Milestone M2.
