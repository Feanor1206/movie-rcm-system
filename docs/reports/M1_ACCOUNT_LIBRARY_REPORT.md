# M1 — Tài khoản thật và thư viện cá nhân hoàn chỉnh — Báo cáo ready for review

> **Milestone:** M1 (AUTH-01 + LIB-01 + LIB-02)  
> **Kỹ sư triển khai:** Gemini  
> **Kỹ sư trưởng nghiệm thu:** Codex  
> **Baseline branch:** `chore/taicautruc`  
> **Trạng thái:** READY FOR REVIEW M1  

---

## 1. Vấn đề và phạm vi

### 1.1 Vấn đề người dùng được giải quyết
1. **Loại bỏ xác thực giả lập và offline fallback giả tạo:** Trước M1, khi Spring Boot ngắt kết nối hoặc request thất bại, client tự sinh `mock_jwt_...` và mock user từ danh sách `MOCK_50_USERS`, khiến người dùng lầm tưởng đã đăng nhập thật nhưng dữ liệu không thể lưu trữ. Mật khẩu bị `trim()` làm hỏng các mật khẩu hợp lệ có chứa khoảng trắng.
2. **Cô lập thư viện cá nhân theo Actor (Actor Isolation):** Trước M1, thư viện dùng chung `localStorage`, tự gán phim mẫu (`afterlight`, `quiet-places`, `the-last-orbit`) cho mọi tài khoản mới, và dùng phép hợp union giữ lại dữ liệu cũ khi backend rỗng. Khi người dùng A đăng xuất rồi người dùng B đăng nhập, phản hồi trễ của A có thể làm rò rỉ hoặc ghi đè dữ liệu B.
3. **Hoàn thiện Persistence cho Yêu thích (Favorites) & Đánh giá (Ratings):** Trước M1, mục Favorites chỉ lưu tạm thời trên trình duyệt, không có bảng DB và không có REST endpoint. Watchlist và Ratings chưa có cơ chế kiểm soát idempotency khi click đúp hoặc xóa lặp.
4. **Phản hồi UI trung thực, chống thao tác trùng lặp:** Loại bỏ việc hiển thị toast "Đã lưu" trước khi backend xác nhận; bổ sung optimistic update kèm rollback tự động khi gặp lỗi mạng/server, ngăn chặn double-submit trên tất cả các nút tương tác (Watchlist, Favorites, Stars). Hồ sơ người dùng hiển thị đúng thông tin định danh và xử lý an toàn các tác phẩm đã gỡ khỏi catalog.

### 1.2 Contract và Ticket thực hiện
- Thực hiện toàn vẹn milestone **M1** gộp:
  - `AUTH-01`: Xác thực thật và trạng thái tài khoản trung thực.
  - `LIB-01`: Đọc và phân tách thư viện theo Actor (Guest / Authenticated).
  - `LIB-02`: Lưu trữ bền vững Watchlist, Favorites, Ratings qua Spring Boot backend.
- Đã công bố và áp dụng contract: [`docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md`](file:///D:/Class/movie-rcm-system/docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md).

---

## 2. Files và thay đổi

### 2.1 Backend (Spring Boot)
- [`backend/springboot/src/main/resources/schema.sql`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/resources/schema.sql): Thêm bảng `favorite_items` với khóa ngoại `user_id` và ràng buộc `UNIQUE (user_id, movie_id)`.
- [`backend/springboot/src/main/java/com/dippie/moviercm/entity/FavoriteItem.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/entity/FavoriteItem.java): Entity JPA quản lý mục yêu thích của người dùng.
- [`backend/springboot/src/main/java/com/dippie/moviercm/repository/FavoriteItemRepository.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/repository/FavoriteItemRepository.java): Repository truy vấn danh sách, kiểm tra tồn tại và xóa theo `userId` + `movieId`.
- [`backend/springboot/src/main/java/com/dippie/moviercm/dto/FavoriteRequest.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/dto/FavoriteRequest.java): DTO tiếp nhận `movieId`, `movieTitle`, `posterUrl` với validation `@NotBlank`.
- [`backend/springboot/src/main/java/com/dippie/moviercm/service/FavoriteService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/FavoriteService.java): Nghiệp vụ thêm/xóa mục yêu thích; bảo đảm idempotency (không sinh duplicate), lấy `userId` từ authenticated principal và làm giàu metadata từ `MovieRepository`.
- [`backend/springboot/src/main/java/com/dippie/moviercm/controller/FavoriteController.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/controller/FavoriteController.java): REST controller tại `/api/users/favorites` (`GET`, `POST`, `DELETE /{movieId}`).
- [`backend/springboot/src/main/java/com/dippie/moviercm/controller/AuthController.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/controller/AuthController.java): Bổ sung kiểm tra null an toàn cho `GET /api/auth/me`, trả về `401 Unauthorized` có cấu trúc khi token vắng mặt hoặc không hợp lệ.
- [`backend/springboot/src/main/java/com/dippie/moviercm/service/WatchlistService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/WatchlistService.java): Tinh chỉnh idempotency khi thêm trùng phim vào watchlist (trả về item hiện có thay vì ném lỗi 500) và làm giàu dữ liệu từ catalog.
- [`backend/springboot/src/main/java/com/dippie/moviercm/repository/MovieRatingRepository.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/repository/MovieRatingRepository.java): Bổ sung phương thức `deleteByUserIdAndMovieId`.
- [`backend/springboot/src/main/java/com/dippie/moviercm/service/RatingService.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/RatingService.java): Sắp xếp lịch sử đánh giá theo thời gian cập nhật mới nhất, bổ sung `deleteRating`.
- [`backend/springboot/src/main/java/com/dippie/moviercm/controller/RatingController.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/controller/RatingController.java): Bổ sung endpoint `DELETE /api/users/ratings/{movieId}`.
- [`backend/springboot/src/test/resources/application-test.yml`](file:///D:/Class/movie-rcm-system/backend/springboot/src/test/resources/application-test.yml): Cấu hình database in-memory H2 riêng biệt (`jdbc:h2:mem:m1_test_db`), tuyệt đối không đụng chạm đến database người dùng.
- [`backend/springboot/src/test/java/com/dippie/moviercm/AuthAndLibraryIntegrationTest.java`](file:///D:/Class/movie-rcm-system/backend/springboot/src/test/java/com/dippie/moviercm/AuthAndLibraryIntegrationTest.java): Bộ test tích hợp Spring Boot bao phủ toàn diện 6 ca kiểm thử auth, watchlist, favorites, ratings, boundary, và actor isolation giữa 2 người dùng.

### 2.2 Frontend (Next.js / TypeScript)
- [`frontend/lib/context/AuthContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/AuthContext.tsx): Loại bỏ triệt để mock logins/passwords, gửi mật khẩu nguyên văn (raw password), xác minh session khi khởi động qua `/api/auth/me`, quản lý 4 trạng thái (`guest`, `checking`, `authenticated`, `unavailable`), áp dụng generation guard (`generationRef`) và `AbortController` timeout (8s) để chặn đứng phản hồi trễ sau khi đăng xuất/đổi tài khoản.
- [`frontend/lib/context/WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx): Phân lập hoàn toàn kho lưu trữ khách (`dippie_guest_library_v1`, mặc định rỗng, không gài phim mẫu) với tài khoản backend; đồng bộ cả Watchlist, Favorites và Ratings; xóa trắng state ngay khi actor chuyển đổi; cơ chế optimistic update với tự động rollback khi thất bại; ngăn chặn double click qua `pendingKeys`.
- [`frontend/features/auth/components/AuthModal.tsx`](file:///D:/Class/movie-rcm-system/frontend/features/auth/components/AuthModal.tsx): Bỏ nút demo tài khoản/mật khẩu tự động điền, thông báo lỗi tiếng Việt bình tĩnh, vô hiệu hóa form khi đang xử lý để chống duplicate submit.
- [`frontend/features/movies/components/MovieCard.tsx`](file:///D:/Class/movie-rcm-system/frontend/features/movies/components/MovieCard.tsx): Bổ sung phản hồi trực quan khi pending (`Loader2`), disable click khi đang gửi mutation, truyền đầy đủ poster vào mutation.
- [`frontend/features/movies/components/MovieDetail.tsx`](file:///D:/Class/movie-rcm-system/frontend/features/movies/components/MovieDetail.tsx): Bổ sung pending state cho nút Watchlist, Yêu thích (Heart) và Star ratings; vô hiệu hóa thao tác khi request đang xử lý.
- [`frontend/features/profile/components/ProfileOverview.tsx`](file:///D:/Class/movie-rcm-system/frontend/features/profile/components/ProfileOverview.tsx): Hiển thị đúng thông tin định danh thật từ `useAuth()`; hỗ trợ chế độ khách với nhãn "Lưu trên thiết bị này" và nút khuyến khích đăng nhập; hiển thị loading, error, retry; xử lý êm đẹp các bản ghi không còn trong catalog (không crash, không hiển thị phantom movie, cho phép xóa).
- [`frontend/tests/m1_behavior_suite.mjs`](file:///D:/Class/movie-rcm-system/frontend/tests/m1_behavior_suite.mjs): Bộ test kiểm tra hành vi độc lập 9 kịch bản với native Node.js test runner.

---

## 3. Ma trận nghiệm thu

| STT | Kịch bản kiểm thử | Kỳ vọng | Thực tế đạt được | Bằng chứng | Trạng thái |
|:---|:---|:---|:---|:---|:---|
| 1 | Đăng ký & Đăng nhập mật khẩu có khoảng trắng | Mật khẩu được gửi nguyên văn; đăng nhập thành công với mật khẩu đúng, thất bại nếu bị trim | Mật khẩu giữ nguyên các khoảng trắng đầu/cuối/giữa; hash mật khẩu không bị expose | `AuthAndLibraryIntegrationTest.testRegistrationAndLoginWithSpacesInPassword`, `m1_behavior_suite.mjs (Ca 1)` | PASSED |
| 2 | Backend sập hoặc lỗi mạng | Không tự tạo user/token giả lập, UI báo lỗi kết nối rõ ràng | Trả về `success: false` kèm thông báo lỗi; `token` và `user` giữ nguyên `null`, không lưu `mock_jwt` vào storage | `m1_behavior_suite.mjs (Ca 2)` | PASSED |
| 3 | Payload phản hồi bị dị dạng | Không tin tưởng `success: true` nếu thiếu các trường bắt buộc (`token`, `id`) | Payload thiếu `token` hoặc `id` bị từ chối; không kích hoạt session | `m1_behavior_suite.mjs (Ca 3)` | PASSED |
| 4 | Kiểm tra session khởi động (`/api/auth/me`) | Token hợp lệ -> `authenticated`; Token 401/403 -> xóa token, chuyển `guest`; lỗi mạng -> `unavailable` | Chuyển đúng trạng thái; 401 dọn dẹp storage; 5xx/mất mạng chuyển `unavailable` kèm nút thử lại | `AuthAndLibraryIntegrationTest.testCurrentUserEndpoint`, `m1_behavior_suite.mjs (Ca 4)` | PASSED |
| 5 | Chống phục hồi phiên cũ (Stale response guard) | Khi người dùng logout hoặc chuyển tài khoản trong lúc request đang gửi, phản hồi về muộn không được ghi đè | `generationRef` và `AbortController` hủy bỏ và bỏ qua hoàn toàn phản hồi từ thế hệ cũ | `m1_behavior_suite.mjs (Ca 5)` | PASSED |
| 6 | Trạng thái thư viện khách ban đầu | Khách mới bắt đầu với thư viện rỗng, không có phim mẫu (`afterlight`, `quiet-places`, `the-last-orbit`) | `dippie_guest_library_v1` khởi tạo rỗng (`watchlist: []`, `favorites: []`, `ratings: {}`) | `m1_behavior_suite.mjs (Ca 6)` | PASSED |
| 7 | Backend trả về danh sách rỗng | Thư viện chuyển thành rỗng, không dùng union để giữ lại dữ liệu mẫu/khách | State được thay thế hoàn toàn bằng mảng rỗng `[]` | `m1_behavior_suite.mjs (Ca 7)` | PASSED |
| 8 | Cách ly dữ liệu giữa User A và User B | A -> logout -> B: B không thấy bất kỳ dữ liệu nào của A; phản hồi trễ của A không sửa state B | User A có 1 item mỗi danh mục; User B đăng nhập có 0 item; cách ly tuyệt đối 100% | `AuthAndLibraryIntegrationTest.testActorIsolationBetweenUsers`, `m1_behavior_suite.mjs (Ca 8)` | PASSED |
| 9 | Idempotency của Watchlist và Favorites | Thêm trùng không tạo bản ghi kép; xóa lặp trả về 200 an toàn | Database áp dụng `UNIQUE(user_id, movie_id)`; Service trả về item hiện có; xóa lặp trả 200 OK | `AuthAndLibraryIntegrationTest.testWatchlistFlow`, `testFavoritesFlow` | PASSED |
| 10 | Ràng buộc đánh giá (Rating scale 1–10) | Rating ngoài phạm vi [1, 10] bị validation từ chối; cùng phim cập nhật đúng 1 bản ghi | Chấm 0 điểm hoặc 11 điểm trả về 400 Bad Request; chấm lại cập nhật cùng row duy nhất | `AuthAndLibraryIntegrationTest.testRatingFlow` | PASSED |
| 11 | Optimistic update và rollback khi lỗi | Thao tác UI cập nhật ngay, nhưng nếu server lỗi hoặc mất kết nối thì rollback và báo lỗi | Local state tự động khôi phục snapshot trước khi thao tác; toast hiển thị thông báo lỗi kiểu `'error'` | `m1_behavior_suite.mjs (Ca 9)` | PASSED |
| 12 | Xử lý phim không còn trong catalog | Thư viện có `movieId` lạ hoặc bị gỡ không làm crash trang Profile, giải thích rõ lý do và cho phép xóa | Profile hiển thị card cảnh báo "Không có trong catalog", cung cấp nút xóa khỏi danh sách | [`ProfileOverview.tsx`](file:///D:/Class/movie-rcm-system/frontend/features/profile/components/ProfileOverview.tsx#L240-L260) | PASSED |
| 13 | TypeScript compiler & Next.js production build | Không có lỗi kiểu dữ liệu; build production pass thành công | `npx tsc --noEmit` exit 0; `npm run build` exit 0 (7/7 routes compiled) | Terminal execution logs | PASSED |

---

## 4. Kiểm tra thực hiện

### 4.1 Spring Boot Integration Tests
- **Môi trường:** Java SE 25.0.3 (`C:\Program Files\Java\jdk-25.0.3`), Maven Wrapper (`mvnw.cmd`).
- **Database kiểm thử:** In-memory H2 tách biệt (`jdbc:h2:mem:m1_test_db;DB_CLOSE_DELAY=-1;MODE=PostgreSQL`). Tuyệt đối không đụng đến cơ sở dữ liệu dev hay database người dùng.
- **Lệnh thực thi:**
  ```powershell
  $env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"
  .\mvnw.cmd test
  ```
- **Kết quả:** `BUILD SUCCESS`
  ```
  [INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 18.10 s -- in com.dippie.moviercm.AuthAndLibraryIntegrationTest
  [INFO] Total time: 22.831 s
  [INFO] Finished at: 2026-10-13T23:02:42+07:00
  ```
- **Exit code:** `0`

### 4.2 Frontend Behavioral Tests
- **Môi trường:** Node.js v26.1.0, native test runner `node:test` và `node:assert/strict`.
- **Lệnh thực thi:**
  ```powershell
  node --test tests/m1_behavior_suite.mjs
  ```
- **Kết quả:**
  ```
  ✔ 1. Auth login preserves verbatim raw password with spaces (1.15ms)
  ✔ 2. Server error / down does NOT create fake user or fake JWT token (0.33ms)
  ✔ 3. Malformed success payload missing token or id is rejected (1.09ms)
  ✔ 4. Session verification (/me): 401 clears stored token and returns to guest (1.14ms)
  ✔ 5. Generation guard: late in-flight response after logout is discarded (no resurrection) (0.21ms)
  ✔ 6. Guest initial state is empty: no demo items seeded (0.88ms)
  ✔ 7. Empty backend library replaces state with empty (no union merge with demo/guest items) (0.15ms)
  ✔ 8. Actor isolation: User A -> Logout -> User B has zero leakage (0.30ms)
  ✔ 9. Optimistic update rollbacks on backend write failure (0.21ms)
  ℹ tests 9 | pass 9 | fail 0 | cancelled 0 | duration_ms 157.78
  ```
- **Exit code:** `0`

### 4.3 Static Type & Production Build Verification
- **Lệnh thực thi:**
  ```powershell
  npx tsc --noEmit
  npm run build
  ```
- **Kết quả:**
  - TypeScript: Không phát hiện lỗi (Exit code 0).
  - Next.js Build: `Compiled successfully`, tối ưu hóa 7/7 static/dynamic routes (Exit code 0).

### 4.4 Patch Integrity Verification
- **File patch:** [`docs/reports/M1_ACCOUNT_LIBRARY.patch`](file:///D:/Class/movie-rcm-system/docs/reports/M1_ACCOUNT_LIBRARY.patch).
- **Lệnh kiểm tra 1 (Numstat):**
  ```powershell
  git apply --numstat docs/reports/M1_ACCOUNT_LIBRARY.patch
  ```
  *Kết quả:* Exit code 0, bao gồm đúng 21 files thuộc scope M1.
- **Lệnh kiểm tra 2 (Reverse Check):**
  ```powershell
  git apply --reverse --check docs/reports/M1_ACCOUNT_LIBRARY.patch
  ```
  *Kết quả:* Exit code 0, kiểm tra tương thích đảo ngược thành công tuyệt đối, không có conflict, không sửa tay hunk headers.

---

## 5. Kết quả và limitations

### 5.1 Phần đã đạt được
- Toàn bộ cơ chế xác thực thật, session verification, generation guard, và raw password đã được tích hợp và kiểm thử.
- Tách bạch hoàn toàn thư viện khách và thư viện tài khoản, zero data leak giữa các tài khoản khác nhau.
- Thêm mới hoàn chỉnh persistence cho mục Favorites (schema, entity, repo, service, controller, DTO).
- Bảo đảm tính idempotent cho mọi thao tác Watchlist, Favorites, Ratings.
- UI Profile, MovieCard, MovieDetail, AuthModal phản ánh sự thật, có pending feedback, ngăn ngừa double click và hỗ trợ rollback.
- Toàn bộ thay đổi sẵn có của đồng đội từ trước M1 được bảo toàn tuyệt đối.

### 5.2 Phần chưa kiểm tra / Limitations
- Chưa chạy integration trực tiếp với live database production PostgreSQL (chỉ chạy với database test H2 in-memory).
- Không khởi động hoặc kiểm tra tiến trình mô hình Qwen3-4B / GPU inference theo quy định nghiêm ngặt của engineering rules.
- Thư viện chưa đồng bộ hai chiều thời gian thực qua WebSocket (đồng bộ qua REST polling/reload theo đúng contract M1).

---

## 6. Hướng dẫn Migration Database

Nếu áp dụng migration lên PostgreSQL production:
```sql
-- Migration script: M1_add_favorite_items.sql
CREATE TABLE IF NOT EXISTS favorite_items (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL,
    movie_id VARCHAR(100) NOT NULL,
    movie_title VARCHAR(255) NOT NULL,
    poster_url VARCHAR(500),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_favorite_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_user_movie_favorite UNIQUE (user_id, movie_id)
);

CREATE INDEX IF NOT EXISTS idx_favorite_user_id ON favorite_items(user_id);
```
Rollback script:
```sql
DROP TABLE IF EXISTS favorite_items;
```

---

## 7. Bàn giao

- **Trạng thái:** READY FOR REVIEW M1
- Không thực hiện `git commit`, `git push`, hoặc tự ý chuyển sang milestone M2.
- Đã sẵn sàng để Kỹ sư trưởng Codex tiến hành nghiệm thu chi tiết.
