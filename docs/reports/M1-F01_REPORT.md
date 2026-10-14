# M1-F01 — Khắc phục tổng hợp findings nghiệm thu M1 — Báo cáo ready for review

> **Ticket:** M1-F01 (Follow-up toàn diện cho M1: R1–R8)  
> **Kỹ sư triển khai:** Gemini  
> **Kỹ sư trưởng nghiệm thu:** Codex  
> **Baseline snapshot:** `.f01_snapshot/`  
> **Trạng thái:** **READY FOR REVIEW M1-F01**  

---

## 1. Tóm tắt bối cảnh và mục tiêu

Sau đợt nghiệm thu độc lập M1 từ Codex (`docs/reviews/M1_ACCOUNT_LIBRARY_REVIEW.md`), verdict là **CHANGES REQUESTED** với 2 blockers P1 (R1, R2) và 6 nhóm P2 (R3–R8). Gemini đã tiếp nhận, tạo snapshot baseline bảo toàn toàn bộ hiện trạng, và triển khai trọn gói follow-up **M1-F01** theo đúng chỉ đạo trong `docs/prompts/M1-F01_GEMINI_PROMPT.md`.

Tất cả 8 nhóm findings R1–R8 đã được giải quyết triệt để trên mã nguồn thực tế, kiểm chứng bằng các bài kiểm thử chạy trực tiếp production code và integration tests Spring Boot với cơ chế đồng bộ barrier.

---

## 2. Ma trận khắc phục và nghiệm thu R1–R8

| Finding | Phân loại | Source thay đổi | Cơ chế xử lý | Test & Bằng chứng thực tế | Trạng thái |
|:---|:---|:---|:---|:---|:---|
| **R1** | **P1 (Blocker)** | [`frontend/lib/context/AuthContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/AuthContext.tsx) | **Auth request lifecycle guard xuyên suốt async boundaries:**<br>1. Kiểm tra `authGenerationRef` và hủy bỏ sau fetch headers, sau `await res.json()`, và ngay trước khi commit state/storage.<br>2. Timeout hữu hạn bao trùm cả fetch và đọc body JSON; cleanup trong `finally`.<br>3. `logout()`, đổi account, hoặc unmount component lập tức tăng generation và abort requests in-flight.<br>4. Runtime validation chặt chẽ: `token` phải là string không rỗng, `id` là số nguyên dương hợp lệ, bắt buộc `username` và `email` (đúng định dạng `@`). | `node --test tests/m1_behavior_suite.mjs`<br>- *Ca 2:* Logout khi res.json() pending -> không hồi sinh phiên (pass).<br>- *Ca 3:* Payload malformed/bad ID/non-string token -> bị từ chối, giữ guest (pass). | **RESOLVED** |
| **R2** | **P1 (Blocker)** | [`frontend/lib/context/WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx) | **Actor isolation cho toàn bộ mutations:**<br>1. Mọi thao tác (`toggleWatchlist`, `toggleFavorite`, `rateMovie`, `removeRating`) capture `mutationActorId = user?.id` và `mutationGen = syncGenerationRef.current`.<br>2. Khi actor chuyển đổi (A -> logout/B), `syncGenerationRef.current` tăng, state lập tức xóa trắng.<br>3. Mọi callback (success, catch, finally, rollback, toasts) đều kiểm tra `isCurrentActor()`. Nếu actor đã đổi, phản hồi trễ của A bị hủy bỏ, hoàn toàn không chạm vào state, storage, pending hay toasts của B. | `node --test tests/m1_behavior_suite.mjs`<br>- *Ca 4:* Mutation của User A thất bại muộn sau khi User B đã tải xong -> Watchlist của B giữ nguyên `['B-film']`, không bị rollback snapshot A, không hiển thị toast lỗi (pass). | **RESOLVED** |
| **R3** | **P2** | [`frontend/lib/context/WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx) | **Mutation consistency, synchronous lock và targeted rollback:**<br>1. Khóa đồng bộ `syncPendingKeysRef = useRef(new Set())` ngăn chặn duplicate writes trong cùng một tick (cuộc gọi thứ hai trả về `false` ngay lập tức).<br>2. Rollback có mục tiêu theo từng item (`curr.filter(...)` cho add, `[...curr, id]` cho delete): Thất bại của thao tác X không làm mất item Y đã thêm thành công trong lúc X đang chờ.<br>3. Timeout hữu hạn (7s) với `AbortController`, giải phóng pending khi hết hạn.<br>4. Xác thực response envelope (`res.ok` và `json.success === true`); response 200 có `success=false` bị bắt lỗi và rollback. | `node --test tests/m1_behavior_suite.mjs`<br>- *Ca 5:* Hai cuộc gọi cùng tick chỉ gửi 1 request mạng duy nhất (pass).<br>- *Ca 6:* X thất bại muộn vẫn giữ nguyên Y thành công (pass). | **RESOLVED** |
| **R4** | **P2** | [`frontend/lib/context/WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx) | **Trạng thái auth/library trung thực và phối hợp 401/403:**<br>1. `isGuestMode` strictly là `status === 'guest'` (không gộp `checking` hay `unavailable`).<br>2. Khi `checking` hoặc `unavailable`, mutations từ chối ghi vào guest storage và hiển thị toast thông báo rõ ràng.<br>3. Nhận mã `401` từ library fetch hoặc mutation tự động gọi `handleSessionExpired()`, dọn dẹp storage và mở modal đăng nhập.<br>4. Nhận mã `403` hiển thị thông báo không có quyền mà không invalidate phiên.<br>5. Same-actor refresh gặp lỗi mạng giữ nguyên snapshot phim đã xác nhận, chỉ báo lỗi đồng bộ thay vì xóa trắng state.<br>6. Payload list malformed được coi là error, không coi là empty hợp lệ. | `node --test tests/m1_behavior_suite.mjs`<br>- *Ca 7:* Session `unavailable` không ghi vào guest storage (pass).<br>- *Ca 8:* Phản hồi 401 kích hoạt `handleSessionExpired` (pass).<br>- *Ca 9:* Lỗi refresh cùng actor bảo lưu các phim đã xác nhận (pass). | **RESOLVED** |
| **R5** | **P2** | [`backend/springboot/.../WatchlistService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/WatchlistService.java)<br>[`FavoriteService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/FavoriteService.java)<br>[`RatingService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/RatingService.java)<br>[`GlobalExceptionHandler.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/config/GlobalExceptionHandler.java) | **Catalog validation và metadata chuẩn:**<br>1. `WatchlistService`, `FavoriteService`, `RatingService` kiểm tra `movieRepository.findById(movieId)`. Nếu không tồn tại, ném `IllegalArgumentException`, `GlobalExceptionHandler` trả về `400 Bad Request` có cấu trúc.<br>2. Tiêu đề và poster lưu trữ được lấy chuẩn xác từ catalog entity `Movie`, ngăn chặn hoàn toàn metadata giả mạo hoặc sai lệch từ client.<br>3. Cho phép xóa orphan cũ (phim không còn trong catalog) an toàn mà không bị chặn.<br>4. Integration test seed fixtures thực tế (`the-last-orbit`, `afterlight`, `glass-horizon`, `deep-blue`). | `mvnw.cmd test -Dtest=AuthAndLibraryIntegrationTest`<br>- *Ca 3:* Watchlist ghi đè client metadata bằng canonical catalog metadata (pass).<br>- *Ca 7:* ID không tồn tại trả về 400 Bad Request; xóa orphan legacy thành công 200 OK (pass). | **RESOLVED** |
| **R6** | **P2** | [`backend/springboot/.../LibraryPersistenceHelper.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/LibraryPersistenceHelper.java) | **Concurrent idempotency an toàn:**<br>1. Tạo bean `LibraryPersistenceHelper` với `@Transactional(propagation = Propagation.REQUIRES_NEW)` để cô lập thao tác insert.<br>2. Khi 2 transactions cùng gặp race condition (insert đồng thời vào unique constraint), ngoại lệ `DataIntegrityViolationException` được bắt mà không làm hỏng outer transaction (không bị rollback-only).<br>3. Service truy vấn lại bản ghi hiện có và trả về `200 OK` đồng nhất.<br>4. Chấm điểm đồng thời áp dụng chính sách ghi đè (last-write-wins) duy nhất 1 bản ghi.<br>5. Test dùng barrier thực tế (`CountDownLatch`) kích hoạt đồng thời 2 luồng. | `mvnw.cmd test -Dtest=AuthAndLibraryIntegrationTest`<br>- *Ca 8:* Hai luồng chạy đồng thời qua `CountDownLatch` trên Watchlist và Ratings đều nhận 200 OK, số dòng trong DB chính xác là 1 (pass). | **RESOLVED** |
| **R7** | **P2** | [`frontend/features/profile/components/ProfileOverview.tsx`](file:///D:/Class/movie-rcm-system/frontend/features/profile/components/ProfileOverview.tsx)<br>[`frontend/features/movies/components/MovieDetail.tsx`](file:///D:/Class/movie-rcm-system/frontend/features/movies/components/MovieDetail.tsx)<br>[`backend/springboot/.../MovieController.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/controller/MovieController.java) | **Profile hydration và remove rating:**<br>1. `ProfileOverview.tsx` tự động hydrate metadata các phim ngoài fixture local qua `GET /api/movies/{id}`.<br>2. `MovieController.java` trả về 404 khi phim không có trong catalog, giúp frontend phân biệt rõ ràng giữa 404 (không có trong catalog) và lỗi mạng/5xx (hiển thị thử tải lại, không tự ý gán nhãn đã bị gỡ).<br>3. Bổ sung `removeRating(id, title)` vào context, ProfileOverview và MovieDetail. Sửa lỗi `handleRemoveMissingItem` trước đây gọi nhầm `toggleWatchlist`.<br>4. Nút xóa orphan ở mọi tab có pending feedback (`Loader2`) và chống click đúp. | `node --test tests/m1_behavior_suite.mjs`<br>- *Ca 10:* `removeRating` gửi đúng DELETE request, dọn dẹp state và không chạm vào watchlist (pass). | **RESOLVED** |
| **R8** | **P2** | [`frontend/tests/m1_behavior_suite.mjs`](file:///D:/Class/movie-rcm-system/frontend/tests/m1_behavior_suite.mjs) | **Kiểm thử trực tiếp mã nguồn production:**<br>1. Thay thế hoàn toàn simulation tests cũ bằng test harness sử dụng `ts.transpileModule` và hook adapter tối thiểu, nạp và chạy trực tiếp file nguồn `AuthContext.tsx` và `WatchlistContext.tsx`.<br>2. Sử dụng mocked transport, storage, deferred promises và fake timers để kiểm chứng các tình huống chạy xen kẽ (interleaving) phức tạp. | `node --test tests/m1_behavior_suite.mjs` (10 tests, 10 pass, 0 fail, exit 0). | **RESOLVED** |

---

## 3. Danh sách files thay đổi trong M1-F01

### 3.1 Files mã nguồn sửa đổi (11 files)
1. [`frontend/lib/context/AuthContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/AuthContext.tsx): R1 guard đa async boundary, timeout bao phủ body, unmount cleanup, payload validation chặt chẽ, `handleSessionExpired`.
2. [`frontend/lib/context/WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx): R2 actor isolation, R3 synchronous pending lock, targeted rollback, mutation timeout, R4 strict guest check & 401 integration, R7 `removeRating`.
3. [`frontend/features/profile/components/ProfileOverview.tsx`](file:///D:/Class/movie-rcm-system/frontend/features/profile/components/ProfileOverview.tsx): R7 catalog hydration via `/api/movies/{id}`, phân biệt 404 vs lỗi kết nối, `removeRating`, pending feedback trên orphan deletion buttons.
4. [`frontend/features/movies/components/MovieDetail.tsx`](file:///D:/Class/movie-rcm-system/frontend/features/movies/components/MovieDetail.tsx): Tích hợp `removeRating` trực tiếp trên trang chi tiết phim khi người dùng đã chấm điểm.
5. [`frontend/tests/m1_behavior_suite.mjs`](file:///D:/Class/movie-rcm-system/frontend/tests/m1_behavior_suite.mjs): R8 suite kiểm thử chạy thực tế mã nguồn production `AuthContext.tsx` và `WatchlistContext.tsx`.
6. [`backend/springboot/src/main/java/com/dippie/moviercm/service/WatchlistService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/WatchlistService.java): R5 catalog validation, canonical metadata override, R6 concurrent recovery.
7. [`backend/springboot/src/main/java/com/dippie/moviercm/service/FavoriteService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/FavoriteService.java): R5 catalog validation, canonical metadata override, R6 concurrent recovery.
8. [`backend/springboot/src/main/java/com/dippie/moviercm/service/RatingService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/RatingService.java): R5 catalog validation, R6 concurrent rating last-write-wins policy.
9. [`backend/springboot/src/main/java/com/dippie/moviercm/controller/MovieController.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/controller/MovieController.java): Trả về HTTP 404 khi phim không có trong catalog cho endpoint `GET /api/movies/{id}`.
10. [`backend/springboot/src/test/java/com/dippie/moviercm/AuthAndLibraryIntegrationTest.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/test/java/com/dippie/moviercm/AuthAndLibraryIntegrationTest.java): R5 catalog validation tests, forged metadata override assertions, R6 concurrent barrier test với `CountDownLatch`.
11. [`docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md`](file:///D:/Class/movie-rcm-system/docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md): Cập nhật chính sách rollback bảo toàn dữ liệu và đặc tả R5/R6.

### 3.2 Files mã nguồn tạo mới (2 files)
12. [`backend/springboot/src/main/java/com/dippie/moviercm/service/LibraryPersistenceHelper.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/LibraryPersistenceHelper.java): Bean cô lập các thao tác insert bằng `REQUIRES_NEW` chống hỏng outer transaction khi gặp unique constraint race.
13. [`backend/springboot/src/main/java/com/dippie/moviercm/config/GlobalExceptionHandler.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/config/GlobalExceptionHandler.java): Xử lý `IllegalArgumentException` và validation trả về HTTP 400 có cấu trúc.

---

## 4. Kết quả kiểm thử thực tế

### 4.1 Frontend Behavioral Test Suite (`m1_behavior_suite.mjs`)
- **Lệnh chạy:**
  ```powershell
  node --test tests/m1_behavior_suite.mjs
  ```
- **Kết quả:**
  ```text
  ✔ 1. Auth login sends verbatim raw password with spaces (130.4025ms)
  ✔ 2. R1 (P1): Logout while response JSON is pending does NOT resurrect session (31.3968ms)
  ✔ 3. R1: Runtime validation rejects malformed auth payloads (23.7892ms)
  ✔ 4. R2 (P1): Late mutation failure from User A does NOT affect User B (57.3832ms)
  ✔ 5. R3: Synchronous pending lock prevents duplicate writes in same tick (51.698ms)
  ✔ 6. R3: Targeted rollback: X failure retains successfully added Y (40.7657ms)
  ✔ 7. R4: Unavailable and checking sessions do NOT write to guest storage (33.6283ms)
  ✔ 8. R4: 401 response on mutation triggers handleSessionExpired (34.0194ms)
  ✔ 9. R4: Same-actor refresh failure preserves confirmed items (28.8929ms)
  ✔ 10. R7: removeRating removes rating and sends DELETE request (29.9165ms)
  ℹ tests 10
  ℹ suites 0
  ℹ pass 10
  ℹ fail 0
  ℹ cancelled 0
  ℹ skipped 0
  ℹ todo 0
  ℹ duration_ms 894.7018
  ```
- **Exit code:** `0`

### 4.2 TypeScript & Production Build
- **Lệnh kiểm tra kiểu:**
  ```powershell
  npx tsc --noEmit
  ```
  *Kết quả:* Exit `0`, không có bất kỳ lỗi TypeScript nào.
- **Lệnh build production:**
  ```powershell
  npm run build
  ```
  *Kết quả:*
  ```text
     ▲ Next.js 15.1.2
     - Environments: .env.local

     Creating an optimized production build ...
   ✓ Compiled successfully
     Linting and checking validity of types ...
     Collecting page data ...
   ✓ Generating static pages (7/7)
     Finalizing page optimization ...
     Collecting build traces ...

  Route (app)                              Size     First Load JS
  ┌ ○ /                                    6.05 kB         134 kB
  ├ ○ /_not-found                          140 B           106 kB
  ├ ƒ /api/chat                            140 B           106 kB
  ├ ƒ /movies/[id]                         3.96 kB         132 kB
  ├ ○ /profile                             6.53 kB         135 kB
  └ ○ /search                              4.04 kB         132 kB
  + First Load JS shared by all            105 kB
  ```
  *Exit code:* `0`

### 4.3 Spring Boot Integration Test Suite
- **Lệnh chạy:**
  ```powershell
  $env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"; .\mvnw.cmd test -Dtest=AuthAndLibraryIntegrationTest
  ```
- **Kết quả:**
  ```text
  [INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 20.38 s -- in com.dippie.moviercm.AuthAndLibraryIntegrationTest
  [INFO] Results:
  [INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0
  [INFO] ------------------------------------------------------------------------
  [INFO] BUILD SUCCESS
  [INFO] ------------------------------------------------------------------------
  [INFO] Total time:  29.669 s
  ```
  *Bao phủ:*
  1. `testRegistrationAndLoginWithSpacesInPassword`: Mật khẩu có khoảng trắng giữ nguyên vẹn, hash không bị lộ.
  2. `testCurrentUserEndpoint`: Endpoint `/api/auth/me` xác thực token chuẩn xác.
  3. `testWatchlistFlow`: Canonical catalog metadata ghi đè tiêu đề/poster giả mạo; duplicate idempotency trả về 200 OK.
  4. `testFavoritesFlow`: Quy trình thêm, trùng lặp, liệt kê, xóa yêu thích hoạt động bền vững.
  5. `testRatingFlow`: Chấm điểm, cập nhật cùng 1 dòng, kiểm tra biên (0 và 11 bị từ chối 400), xóa đánh giá.
  6. `testActorIsolationBetweenUsers`: Phân lập tuyệt đối dữ liệu giữa User A và User B.
  7. `testCatalogValidation`: ID phim không tồn tại bị từ chối 400 Bad Request; xóa orphan legacy vẫn thành công 200 OK.
  8. `testConcurrentIdempotency`: Đồng bộ barrier đa luồng (`CountDownLatch`) gửi đồng thời request Watchlist và Rating; cả hai luồng đều nhận 200 OK, số dòng trong DB chính xác là 1.
- **Exit code:** `0`

### 4.4 Kiểm tra tính toàn vẹn của Patch (`M1-F01.patch`)
- **Numstat:**
  ```powershell
  git apply --numstat docs/reports/M1-F01.patch
  ```
  ```text
  8	2	backend/springboot/src/main/java/com/dippie/moviercm/controller/MovieController.java
  23	24	backend/springboot/src/main/java/com/dippie/moviercm/service/FavoriteService.java
  40	15	backend/springboot/src/main/java/com/dippie/moviercm/service/RatingService.java
  23	24	backend/springboot/src/main/java/com/dippie/moviercm/service/WatchlistService.java
  168	15	backend/springboot/src/test/java/com/dippie/moviercm/AuthAndLibraryIntegrationTest.java
  30	2	docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md
  13	3	frontend/features/movies/components/MovieDetail.tsx
  502	237	frontend/features/profile/components/ProfileOverview.tsx
  148	60	frontend/lib/context/AuthContext.tsx
  483	96	frontend/lib/context/WatchlistContext.tsx
  414	189	frontend/tests/m1_behavior_suite.mjs
  27	0	backend/springboot/src/main/java/com/dippie/moviercm/config/GlobalExceptionHandler.java
  47	0	backend/springboot/src/main/java/com/dippie/moviercm/service/LibraryPersistenceHelper.java
  ```
  *Exit code:* `0` (13 files).
- **Reverse Check:**
  ```powershell
  git apply --reverse --check docs/reports/M1-F01.patch
  ```
  *Exit code:* `0` (patch hợp lệ 100%, không xung đột hunk).

---

## 5. Hướng dẫn di chuyển dữ liệu (Migration) & Giới hạn hiện tại

### 5.1 Migration & Zero Data Loss
- Bảng `favorite_items` được tạo qua `CREATE TABLE IF NOT EXISTS`.
- **Chính sách rollback:** Nếu cần rollback mã nguồn về phiên bản trước M1, dữ liệu trong bảng `favorite_items` vẫn được bảo toàn nguyên vẹn trong DB; mã nguồn cũ không truy vấn bảng này mà không làm ảnh hưởng tính toàn vẹn hệ thống. Không thực hiện `DROP TABLE` làm mất mát dữ liệu yêu thích của người dùng.

### 5.2 Giới hạn kỹ thuật và các phần chưa kiểm tra (Limitations)
1. **Phạm vi giao diện người dùng:** Trong M1-F01, các trang Home và Search tiếp tục phục vụ danh mục phim khám phá thông qua local dataset kết hợp chat AI. Việc chuyển đổi toàn bộ danh mục Home/Search sang backend REST API động thuộc phạm vi milestone M2 theo roadmap.
2. **Kiểm thử trình duyệt tương tác thực tế (Live Browser Walkthrough):** Môi trường terminal hiện tại không có trình duyệt headless (Puppeteer/Playwright) hay màn hình đồ họa trực tiếp, do đó chưa thể cung cấp video/ảnh chụp walkthrough tương tác trên trình duyệt thực tế. Toàn bộ logic frontend đã được kiểm chứng bằng TypeScript compilation, production build Next.js, và test harness transpilation chạy trực tiếp 10 kịch bản production code.
3. **Database môi trường kiểm thử:** Integration tests chạy trên in-memory H2 PostgreSQL mode riêng biệt (`m1_test_db`). Không thao tác trực tiếp trên PostgreSQL production hay cơ sở dữ liệu live của người dùng.

---

## 6. Kết luận

Toàn bộ 8 nhóm findings R1–R8 của milestone M1 đã được khắc phục hoàn chỉnh, kiểm thử thành công và sẵn sàng để Kỹ sư trưởng Codex nghiệm thu.

Gemini dừng tại đây ở trạng thái: **READY FOR REVIEW M1-F01**. Không tự ý commit/push, không sửa đổi AI/FastAPI/Qwen, và không tự chuyển sang M2.
