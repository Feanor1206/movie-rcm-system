# M1-F02 — Hoàn thiện lifecycle và tính đúng đắn của M1 — Báo cáo ready for review

> **Ticket:** M1-F02 (Follow-up toàn diện khắc phục findings F1–F5 từ Codex review)  
> **Kỹ sư triển khai:** Gemini  
> **Kỹ sư trưởng nghiệm thu:** Codex  
> **Baseline snapshot:** `.f02_snapshot/`  
> **Patch file:** `docs/reports/M1-F02.patch`  
> **Trạng thái:** **READY FOR REVIEW M1-F02**  

---

## 1. Tóm tắt bối cảnh và mục tiêu

Sau đợt nghiệm thu độc lập M1-F01 từ Codex (`docs/reviews/M1-F01_REVIEW.md`), kết luận là **CHANGES REQUESTED** với 2 blockers P1 (F1, F2) và 3 nhóm P2 (F3, F4, F5). 
Gemini đã tạo baseline snapshot xác thực `.f02_snapshot/` (đối soát SHA256 trên 13 files liên quan) và triển khai một đợt duy nhất hoàn thiện toàn bộ findings F1–F5 theo đúng yêu cầu trong `docs/prompts/M1-F02_GEMINI_PROMPT.md`.

Các sửa đổi tập trung vào:
1. **Ownership xuyên suốt async boundaries:** Đảm bảo mọi side effect (401 callback, locks, finally, state rollback, toasts) đều được bảo vệ nghiêm ngặt theo actor session.
2. **State ownership đồng bộ ngay khi render:** Snapshot mang `ownerKey`, render ngay lập tức derive danh sách rỗng cho User B trước khi passive effects kịp kích hoạt.
3. **Phân tách session generation và read generation:** Same-actor refresh không bao giờ làm kẹt pending mutation hoặc ghi đè mất dữ liệu vừa commit.
4. **Timeout bao trùm cả đọc body JSON và authoritative reconcile:** Hủy bỏ timeout đúng thời điểm, Profile hydration có timeout + abort controller + unmount cleanup.
5. **Backend duplicate recovery chỉ trả về thực thể đã được lưu trữ:** Thay thế `.orElse(unsavedItem)` bằng `.orElseThrow(...)` với mã HTTP 409 Conflict, bảo đảm mọi ID trả về đều là ID số nguyên dương đã persist.

---

## 2. Ma trận khắc phục và nghiệm thu F1–F5

| Finding | Mức độ | File nguồn | Cơ chế xử lý | Test & Bằng chứng thực tế | Kết luận |
|:---|:---|:---|:---|:---|:---|
| **F1** | **P1 (Blocker)** | [`frontend/lib/context/WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx) | **Bảo vệ toàn bộ side effect của mutation cũ:**<br>1. Callback `handleSessionExpired` khi gặp 401 được bọc điều kiện `isStillCurrentSession()`. Nếu session đã đổi sang User B, 401 của User A bị loại bỏ, không log out User B.<br>2. Khóa đồng bộ trong `syncPendingLocksRef` được gắn namespace actor: `${actorKey}:${movieId}:${action}`. Khối `finally` của User A chỉ xóa đúng khóa của A, không xóa khóa của User B đối với cùng một bộ phim.<br>3. Toàn bộ `AbortController` của mutation in-flight được lưu trong `activeMutationAbortControllersRef` và tự động abort khi actor đổi hoặc component unmount.<br>4. Mutation phản hồi sau khi actor đã đổi lập tức hủy bỏ, không commit state và không return true. | 1. `docs/reviews/repro/M1_F01_runtime_repro.cjs`<br>- *late A 401 after B authenticated:* `expiryCalls: 0`.<br>- *A finally releases B same-item lock:* `bWrites: 1` (khóa B giữ nguyên).<br>2. `frontend/tests/m1_behavior_suite.mjs`<br>- Test 4 (F1 401 guard) pass.<br>- Test 5 (F1 lock isolation) pass. | **RESOLVED** |
| **F2** | **P1 (Blocker)** | [`frontend/lib/context/WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx) | **State có ownership, không expose dữ liệu A ở render B:**<br>1. Snapshot mang thuộc tính `ownerKey` (`LibrarySnapshot { ownerKey, watchlist, favorites, ratings }`).<br>2. Render đồng bộ tính toán `visibleWatchlist`, `visibleFavorites`, `visibleRatings`, counts, và selectors dựa trên `snapshot.ownerKey === currentActorKey`.<br>3. Khi actor chuyển A → B, ngay tại Render #1 (trước khi bất kỳ `useEffect` hay passive effects nào chạy), UI lập tức nhận `[]` (hoặc guest data nếu chuyển sang guest). Dữ liệu của A hoàn toàn không bị rò rỉ.<br>4. Detect chuyển đổi actor được thực hiện đồng bộ ngay trong render body để tăng `sessionGenRef` và dọn dẹp các in-flight controller. | 1. `docs/reviews/repro/M1_F01_runtime_repro.cjs`<br>- *first B render before effect-driven rerender:* `watchlist: []`.<br>2. `frontend/tests/m1_behavior_suite.mjs`<br>- Test 6 (F2 first render derivation) pass. | **RESOLVED** |
| **F3** | **P2** | [`frontend/lib/context/WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx) | **Tách session generation khỏi read generation:**<br>1. Tách biệt `sessionGenRef` (vòng đời phiên đăng nhập) và `readGenRef` (yêu cầu tải lại thư viện).<br>2. Same-actor `refetchLibrary()` chỉ tăng `readGenRef`, không tăng `sessionGenRef`, do đó không hủy bỏ mutation in-flight của chính actor đó.<br>3. Phản hồi tải thư viện từ máy chủ được đối soát (reconcile) trong functional updater `setSnapshot((prev) => ...)`: các phim đang nằm trong `syncPendingLocksRef` của phiên hiện tại được bảo lưu, ngăn chặn tình trạng read response cũ ghi đè mất kết quả mutation vừa hoàn tất.<br>4. Mutation kết thúc thành công giải phóng đúng khóa pending của mình. | 1. `docs/reviews/repro/M1_F01_runtime_repro.cjs`<br>- *refresh while same-actor mutation pending:* `pending: false, watchlist: ["X"]`.<br>2. `frontend/tests/m1_behavior_suite.mjs`<br>- Test 7 (F3 same-actor refresh & reconciliation) pass. | **RESOLVED** |
| **F4** | **P2** | [`frontend/lib/context/WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx)<br>[`frontend/features/profile/components/ProfileOverview.tsx`](file:///D:/Class/movie-rcm-system/frontend/features/profile/components/ProfileOverview.tsx) | **Timeout bao phủ body parsing và reconcile unknown outcome:**<br>1. Cả `loadLibraryForCurrentActor` và các mutation (`toggleWatchlist`, `toggleFavorite`, `rateMovie`, `removeRating`) duy trì timer timeout trong suốt quá trình đọc `res.json()`. Timer chỉ được xóa sau khi `res.json()` hoàn tất hoặc trong `finally`.<br>2. Khi mutation gặp timeout (unknown outcome), hàm `reconcileAuthoritativeLibrary` được tự động kích hoạt ngầm để đối soát lại trạng thái chính thức từ máy chủ mà không làm đảo ngược hành động của người dùng.<br>3. `ProfileOverview.tsx` bổ sung `AbortController` theo từng movie ID (`activeHydrationAbortControllersRef`), timeout 6000ms bao phủ cả body JSON, hủy bỏ controller khi unmount, và xác thực bắt buộc các trường `id` và `title` trước khi gán trạng thái `found`. | 1. `docs/reviews/repro/M1_F01_runtime_repro.cjs`<br>- *mutation body pending after headers:* `pending: true, activeTimerMs: [7000]`.<br>2. `frontend/tests/m1_behavior_suite.mjs`<br>- Test 8 (F4 body timeout abort) pass. | **RESOLVED** |
| **F5** | **P2** | [`backend/springboot/.../WatchlistService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/WatchlistService.java)<br>[`FavoriteService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/FavoriteService.java)<br>[`RatingService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/RatingService.java)<br>[`GlobalExceptionHandler.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/config/GlobalExceptionHandler.java)<br>[`AuthAndLibraryIntegrationTest.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/test/java/com/dippie/moviercm/AuthAndLibraryIntegrationTest.java) | **Backend duplicate recovery chỉ trả về thực thể đã persist:**<br>1. Thay thế hoàn toàn `.orElse(unsavedItem)` và `.orElse(newRating)` trong khối catch `DataIntegrityViolationException` bằng `.orElseThrow(() -> new IllegalStateException(...))`.<br>2. `GlobalExceptionHandler` bổ sung handler cho `IllegalStateException`, trả về `409 Conflict` với envelope chuẩn, ngăn chặn hoàn toàn việc trả `200 OK` với ID null.<br>3. Bổ sung test concurrency cho Favorites song song với Watchlist và Ratings với `CountDownLatch` barrier trong `AuthAndLibraryIntegrationTest.java`.<br>4. Assertions kiểm tra nghiêm ngặt `assertNotNull(item.getId())` và `assertTrue(item.getId() > 0)` cho tất cả các bản ghi sau race condition. | 1. `mvnw.cmd test -Dtest=AuthAndLibraryIntegrationTest`<br>- Test 8 (concurrent idempotency cho Watchlist, Favorites, Ratings) pass, DB count = 1, IDs > 0, exit 0. | **RESOLVED** |

---

## 3. Danh sách files thay đổi trong M1-F02 (9 files)

1. [`backend/springboot/src/main/java/com/dippie/moviercm/config/GlobalExceptionHandler.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/config/GlobalExceptionHandler.java): Thêm xử lý `IllegalStateException` trả về HTTP 409 Conflict.
2. [`backend/springboot/src/main/java/com/dippie/moviercm/service/WatchlistService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/WatchlistService.java): Thay `.orElse(item)` bằng `.orElseThrow()` đảm bảo chỉ trả về item đã persist.
3. [`backend/springboot/src/main/java/com/dippie/moviercm/service/FavoriteService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/FavoriteService.java): Thay `.orElse(item)` bằng `.orElseThrow()` đảm bảo chỉ trả về item đã persist.
4. [`backend/springboot/src/main/java/com/dippie/moviercm/service/RatingService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/RatingService.java): Thay `.orElse(newRating)` bằng `.orElseThrow()`.
5. [`backend/springboot/src/test/java/com/dippie/moviercm/AuthAndLibraryIntegrationTest.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/test/java/com/dippie/moviercm/AuthAndLibraryIntegrationTest.java): Thêm test concurrent Favorites và assert positive ID (`id > 0`).
6. [`docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md`](file:///D:/Class/movie-rcm-system/docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md): Bổ sung Mục 5 cam kết kiến trúc F1–F5.
7. [`frontend/features/profile/components/ProfileOverview.tsx`](file:///D:/Class/movie-rcm-system/frontend/features/profile/components/ProfileOverview.tsx): Timeout bao phủ body JSON, AbortController per-movie, unmount cleanup, validation movie data.
8. [`frontend/lib/context/WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx): State ownership `snapshot.ownerKey`, derive synchronous trong render, session vs read generation, namespaced locks, body timeout, background reconcile.
9. [`frontend/tests/m1_behavior_suite.mjs`](file:///D:/Class/movie-rcm-system/frontend/tests/m1_behavior_suite.mjs): Regression suite mở rộng 11 ca kiểm thử thực tế trực tiếp mã nguồn production.

---

## 4. Kết quả kiểm thử thực tế và nghiệm thu

### 4.1 Bằng chứng kiểm tra trực tiếp Codex Repro (`docs/reviews/repro/M1_F01_runtime_repro.cjs`)
- **Lệnh thực hiện:**
  ```powershell
  node docs/reviews/repro/M1_F01_runtime_repro.cjs
  ```
- **Kết quả:**
  ```json
  [
    {
      "scenario": "late A 401 after B authenticated",
      "expiryCalls": 0
    },
    {
      "scenario": "first B render before effect-driven rerender",
      "watchlist": []
    },
    {
      "scenario": "refresh while same-actor mutation pending",
      "pending": false,
      "watchlist": [
        "X"
      ]
    },
    {
      "scenario": "A finally releases B same-item lock",
      "bWrites": 1
    },
    {
      "scenario": "mutation body pending after headers",
      "pending": true,
      "activeTimerMs": [
        7000
      ]
    }
  ]
  ```
- **Exit code:** `0`

### 4.2 Frontend Behavior Suite (`frontend/tests/m1_behavior_suite.mjs`)
- **Lệnh thực hiện:**
  ```powershell
  node --test tests/m1_behavior_suite.mjs
  ```
- **Kết quả:**
  ```text
  ✔ 1. Auth login sends verbatim raw password with spaces (116.5359ms)
  ✔ 2. R1 (P1): Logout while response JSON is pending does NOT resurrect session (29.9178ms)
  ✔ 3. R1: Runtime validation rejects malformed auth payloads (23.8307ms)
  ✔ 4. F1 (P1): Late A 401 response after B login does NOT trigger handleSessionExpired on B (70.319ms)
  ✔ 5. F1 (P1): Old A finally does NOT release B synchronous lock for the same item (44.9775ms)
  ✔ 6. F2 (P1): First render of User B derives empty state before passive effects flush (43.7467ms)
  ✔ 7. F3 (P2): Same-actor refresh does NOT invalidate pending mutation or leave pending stuck (37.4754ms)
  ✔ 8. F4 (P2): Slow JSON body parsing after headers triggers timeout and aborts (32.5085ms)
  ✔ 9. R3: Targeted rollback: X failure retains successfully added Y (28.7882ms)
  ✔ 10. R4: Unavailable sessions do NOT write to guest storage (32.6385ms)
  ✔ 11. R7: removeRating removes rating and sends DELETE request without mutating watchlist (35.359ms)
  ℹ tests 11
  ℹ suites 0
  ℹ pass 11
  ℹ fail 0
  ℹ cancelled 0
  ℹ skipped 0
  ℹ todo 0
  ℹ duration_ms 791.331
  ```
- **Exit code:** `0`

### 4.3 Backend Spring Boot Integration Tests
- **Lệnh thực hiện:**
  ```powershell
  $env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"; .\mvnw.cmd test -Dtest=AuthAndLibraryIntegrationTest
  ```
- **Kết quả:**
  ```text
  [INFO] Running com.dippie.moviercm.AuthAndLibraryIntegrationTest
  ...
  [INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 9.432 s -- in com.dippie.moviercm.AuthAndLibraryIntegrationTest
  [INFO] 
  [INFO] Results:
  [INFO] 
  [INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0
  [INFO] 
  [INFO] ------------------------------------------------------------------------
  [INFO] BUILD SUCCESS
  [INFO] ------------------------------------------------------------------------
  [INFO] Total time:  15.028 s
  ```
- **Exit code:** `0`

### 4.4 TypeScript Typecheck & Production Build
- **Typecheck:**
  ```powershell
  npx tsc --noEmit
  ```
  *Kết quả:* Exit `0`, 0 error.
- **Production Build:**
  ```powershell
  npm run build
  ```
  *Kết quả:* Exit `0`, tạo thành công tất cả 7 routes tĩnh/động.

### 4.5 Xác minh tính hợp lệ của Patch File (`docs/reports/M1-F02.patch`)
- **Numstat:**
  ```powershell
  git apply --numstat docs/reports/M1-F02.patch
  ```
  *Kết quả:* Exit `0`
  ```text
  6	0	backend/springboot/src/main/java/com/dippie/moviercm/config/GlobalExceptionHandler.java
  1	1	backend/springboot/src/main/java/com/dippie/moviercm/service/FavoriteService.java
  1	1	backend/springboot/src/main/java/com/dippie/moviercm/service/RatingService.java
  1	1	backend/springboot/src/main/java/com/dippie/moviercm/service/WatchlistService.java
  35	3	backend/springboot/src/test/java/com/dippie/moviercm/AuthAndLibraryIntegrationTest.java
  27	0	docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md
  46	5	frontend/features/profile/components/ProfileOverview.tsx
  621	281	frontend/lib/context/WatchlistContext.tsx
  164	96	frontend/tests/m1_behavior_suite.mjs
  ```
- **Reverse Check:**
  ```powershell
  git apply --reverse --check docs/reports/M1-F02.patch
  ```
  *Kết quả:* Exit `0` (patch khớp chính xác với working tree và đảo ngược sạch sẽ về baseline `.f02_snapshot`).

---

## 5. Giới hạn & các phần chưa kiểm tra

1. **Cơ sở dữ liệu ngoài & tài khoản thực tế:** Kiểm thử chạy trên in-memory H2 database độc lập và mock transport trong test harness; không tác động tới PostgreSQL staging/production hay tài khoản người dùng thực.
2. **Qwen AI serving:** Toàn bộ thành phần AI (FastAPI, Qwen weights, serving pipeline) được giữ nguyên vẹn, không nạp lại model và không chiếm dụng tài nguyên GPU.
3. **Browser E2E tự động:** Không có công cụ trình duyệt E2E tự động (Playwright/Puppeteer) cài sẵn trong container; các tương tác lifecycle phức tạp đã được kiểm chứng bằng harness nạp trực tiếp file nguồn production TSX với mock hooks/DOM environment.

---

## 6. Kết luận

Toàn bộ 5 findings F1–F5 từ đợt review độc lập của Codex đã được giải quyết triệt để và chứng minh tính đúng đắn qua cả repro của Codex, behavior suite của frontend, và integration test của backend.

Gemini xin bàn giao và dừng tại trạng thái:  
**READY FOR REVIEW M1-F02** để Codex tiến hành nghiệm thu độc lập. Không tự ý commit/push hoặc chuyển sang M2.
