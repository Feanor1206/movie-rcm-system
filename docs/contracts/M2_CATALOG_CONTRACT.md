# M2 Catalog & Animation Discovery Contract Specification

> **Milestone:** M2 — Catalog backend và hành trình khám phá hoạt hình  
> **Repository:** `D:\Class\movie-rcm-system`  
> **Version:** 1.2.0 (Round 3 Update)  
> **Status:** READY FOR REVIEW (Round 3 Update)  

---

## 1. Mục đích & Nguyên tắc cốt lõi

Tài liệu này định nghĩa chuẩn giao tiếp kỹ thuật (API Contract) cho toàn bộ hệ thống Catalog phim thuộc Milestone M2, bảo đảm tính nhất quán xuyên suốt giữa Spring Boot backend, Next.js frontend, AI recommender pipeline, và các module thư viện/tài khoản cá nhân đã nghiệm thu tại M1.

### 1.1 Nguyên tắc Canonical ID
1. **Định danh duy nhất và bất biến (Immutable):**
   - Mã phim `movieId` (ví dụ: `the-last-orbit`, `spirited-away`, `your-name`, `spider-verse`) là chuỗi slug chuẩn (lowercase kebab-case), tồn tại duy nhất trong toàn hệ thống.
   - Tuyệt đối không tự động đổi ID, không map mờ (fuzzy-matching) tiêu đề sang một ID khác để tránh lưu sai tác phẩm trong Watchlist/Favorites/Ratings.
2. **Xử lý tác phẩm không tồn tại (404 Non-existent):**
   - Khi truy vấn một `movieId` không tồn tại trong cơ sở dữ liệu, backend trả về mã `HTTP 404 Not Found` với body có cấu trúc rõ ràng.
   - Tuyệt đối không tạo bản ghi phim giả (phantom movie) hoặc ngầm định tạo mới khi gặp ID lạ.

### 1.2 Quản lý Nullable Metadata
- **Trường bắt buộc (Non-nullable):** `id` (String), `title` (String), `year` (Integer), `rating` (Double), `genres` (List<String>).
- **Trường cho phép null (Nullable):** `runtime` (String), `description` (String), `poster` (String URL), `backdrop` (String URL), `videoUrl` (String URL).
- **Chuẩn hóa thể loại (Genres):**
   - Trong DB, thể loại được lưu trữ dưới dạng chuỗi phân cách bởi dấu phẩy (ví dụ: `"Animation,Adventure,Family,Fantasy"` hoặc `"Animation, Adventure, Family"`).
   - Khi serialize qua DTO `MovieResponse`, các token được `trim()` sạch sẽ thành mảng các chuỗi chuẩn không chứa khoảng trắng thừa: `["Animation", "Adventure", "Family", "Fantasy"]`.

### 1.3 Chính sách So khớp Thể loại theo Token Chính xác & Chuẩn hóa Khoảng trắng Tổng quát (R1 & C3)
- Lọc thể loại (`genre`, `genres`, hoặc `animationOnly=true`) so khớp **chính xác từng token thể loại** trong chuỗi CSV (case-insensitive) thông qua biểu thức quy chuẩn biên giới token:
  `(^|[,])[ \t]*TOKEN[ \t]*([,]|$)`
- **Chuẩn hóa khoảng trắng phân cách tổng quát:**
  - Cho phép bất kỳ số lượng khoảng trắng thừa (spaces) hoặc dấu tab (`\t`) xung quanh dấu phẩy hoặc ở hai đầu chuỗi mà không làm sai lệch kết quả lọc (ví dụ: `"  Animation,   Family  "` hay `"\tAnimation\t,\tAdventure\t"`).
  - Bảo toàn tuyệt đối các khoảng trắng bên trong tên thể loại dài (internal spaces) như `"Sci-Fi & Fantasy"` hoặc `"Martial Arts"`.
- **Chống nhận nhầm token gần giống (Near-match Rejection):**
  - Tuyệt đối không dùng substring `LIKE '%token%'` thông thường.
  - `genre=Drama` chỉ khớp các tác phẩm có token thể loại `Drama`, **không khớp** `Melodrama`.
  - `genre=Animation` hoặc `animationOnly=true` chỉ khớp các tác phẩm có token thể loại `Animation`, **không khớp** `NonAnimation`.
- Các ký tự wildcard đặc biệt (`%`, `_`) và regex metacharacters trong query do người dùng nhập vào được escape để tìm kiếm theo ký tự nguyên văn (literal), không mở rộng pattern ngẫu nhiên.
- Khi truyền danh sách nhiều thể loại (`genres=Animation,Adventure`), backend áp dụng phép kết hợp logic **AND** (tác phẩm phải chứa đầy đủ tất cả các token được yêu cầu).

### 1.4 Chính sách Tìm kiếm Nhất quán (R2)
- Tìm kiếm từ khóa (`search` hoặc `query`) luôn áp dụng thống nhất tìm kiếm trong **`title` HOẶC `description`** (không phân biệt hoa thường, an toàn với trường description null) cho mọi endpoints:
  - `GET /api/movies?search=...` (legacy search-only).
  - `GET /api/movies?search=...&genre=...` (legacy combined search + genre).
  - `GET /api/movies/browse?query=...` (browse endpoint).
- Việc thêm bộ lọc thể loại chỉ có tác dụng thu hẹp tập kết quả (`AND`), bảo đảm tính chất toán học của bộ lọc: kết quả của `search=time&genre=Animation` phải là tập con của `search=time`.
- Khi client truyền cả `query` và `search` trên endpoint browse, tham số `query` được ưu tiên sử dụng. Nếu `query` rỗng hoặc chỉ chứa khoảng trắng, hệ thống tự động fallback về `search`.

### 1.5 Quy chuẩn Catalog Client & Xử lý Vòng đời / Lỗi (C1 & C2)
1. **Vòng đời thống nhất (Unified Request & Body Parsing Lifecycle):**
   - Cửa sổ timeout (mặc định 7000ms) và lắng nghe tín hiệu hủy (`AbortSignal`) bao phủ **toàn bộ quá trình gửi yêu cầu mạng VÀ phân tích cú pháp JSON body**.
   - Hủy bỏ chủ động từ caller (intentional cancellation) được phân loại riêng biệt (`status: 499`, `isCanceled: true`, `name: 'AbortError'`) để UI không hiển thị thông báo lỗi mạng sai lệch.
   - Quá thời gian phản hồi được phân loại là Timeout (`status: 408`, `isTimeout: true`).
   - Mọi bộ định thời (timers) và event listeners phải được dọn dẹp triệt để trong khối `finally` sau khi toàn bộ request và parse kết thúc.
2. **Kiểm định nghiêm ngặt Payload & Chống Dữ liệu Giả (Strict Validation):**
   - Phản hồi phân trang bắt buộc phải có `success: true`, `data` là object, và `data.items` là mảng. Phản hồi rỗng `data: {}` bị từ chối với mã lỗi `502 Bad Gateway`, không biến thành trang rỗng thành công.
   - Hàm `normalizeCatalogMovie` bắt buộc phải có các trường `id`, `title`, `year` (> 1800), `rating` (0..10). Tuyệt đối không bịa `id: ""`, `year: 0`, `rating: 0` khi thiếu trường.
   - Chi tiết phim (`getCatalogMovieById`): Xác minh `movie.id` trả về bắt buộc phải trùng khớp tuyệt đối với `id` yêu cầu để tránh lưu sai tác phẩm.
   - Chính sách HTTP 404: Trả về `null` an toàn ngay khi nhận status 404, không cố gắng parse JSON trên các body 404 HTML hoặc rỗng.

---

## 2. API Endpoints Specification

### 2.1 Legacy List Endpoint — `GET /api/movies` (Giữ tương thích 100%)
Bảo lưu toàn diện giao tiếp cho các client hiện hữu và CineBot AI chat service.

- **URL:** `/api/movies`
- **Method:** `GET`
- **Query Parameters:**
  - `search` (String, tùy chọn): Tìm kiếm không phân biệt hoa thường trong `title` HOẶC `description`.
  - `genre` (String, tùy chọn): Lọc theo token thể loại chính xác (ví dụ: `Animation`).
- **Quy tắc phối hợp điều kiện (Combined Filter):**
  - Khi cả `search` và `genre` cùng xuất hiện: Backend thực thi phép kết hợp **AND** (tìm kiếm chứa từ khóa `search` VÀ thuộc token thể loại `genre`).
- **Response Format (200 OK):**
  ```json
  {
    "success": true,
    "message": "Movies retrieved successfully",
    "data": [
      {
        "id": "spirited-away",
        "title": "Spirited Away",
        "year": 2001,
        "rating": 8.6,
        "runtime": "2h 05m",
        "genres": ["Animation", "Adventure", "Family", "Fantasy"],
        "description": "A young girl wanders into a magical bathhouse...",
        "poster": "https://images.unsplash.com/...",
        "backdrop": "https://images.unsplash.com/...",
        "videoUrl": null
      }
    ]
  }
  ```

### 2.2 Detail Endpoint — `GET /api/movies/{id}`
- **URL:** `/api/movies/{id}`
- **Method:** `GET`
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "message": "Movie retrieved successfully",
    "data": {
      "id": "spirited-away",
      "title": "Spirited Away",
      "year": 2001,
      "rating": 8.6,
      "runtime": "2h 05m",
      "genres": ["Animation", "Adventure", "Family", "Fantasy"],
      "description": "...",
      "poster": "...",
      "backdrop": "...",
      "videoUrl": null
    }
  }
  ```
- **Response (404 NOT FOUND):**
  ```json
  {
    "success": false,
    "message": "Movie not found with id: nonexistent-id",
    "data": null
  }
  ```

### 2.3 Paginated & Filtered Browse Endpoint — `GET /api/movies/browse`
Endpoint chuẩn cho trải nghiệm duyệt danh mục, tìm kiếm và phân trang website hoạt hình M2.

- **URL:** `/api/movies/browse`
- **Method:** `GET`
- **Query Parameters:**
  | Tham số | Kiểu | Mặc định | Mô tả & Validation |
  | :--- | :--- | :--- | :--- |
  | `query` / `search` | String | null | Tìm kiếm không phân biệt hoa thường trong `title` HOẶC `description` (`query` ưu tiên). |
  | `genre` | String | null | Lọc theo 1 token thể loại chính xác. |
  | `genres` | String | null | Lọc nhiều token thể loại phân cách bằng dấu phẩy (kết hợp AND). |
  | `animationOnly` | Boolean | false | Ràng buộc tác phẩm phải chứa token thể loại `Animation`. |
  | `yearMin` | Integer | null | Năm phát hành tối thiểu (`year >= yearMin`). |
  | `yearMax` | Integer | null | Năm phát hành tối đa (`year <= yearMax`). Phải thỏa mãn `yearMin <= yearMax`. |
  | `sort` | String | `"rating"` | Whitelist: `["rating", "year", "title"]`. Trường hợp không hợp lệ trả về `400 Bad Request`. |
  | `direction` | String | `"desc"` | Whitelist: `["asc", "desc"]` (không phân biệt hoa thường). |
  | `page` | Integer | `0` | Chỉ số trang 0-indexed. Phải `>= 0`. |
  | `size` | Integer | `12` | Kích thước trang. Bắt buộc `1 <= size <= 100`. |

- **Quy tắc Sắp xếp ổn định (Stable Sort Tie-break):**
  - Mọi câu truy vấn sắp xếp theo `rating`, `year` hoặc `title` đều được bổ sung thứ tự phụ bất biến: **`id ASC`**.
  - Đảm bảo kết quả phân trang không bị trôi hàng (row jumping / duplicate items across pages).

- **Phản hồi thành công (200 OK):**
  ```json
  {
    "success": true,
    "message": "Movies retrieved successfully",
    "data": {
      "items": [
        {
          "id": "spirited-away",
          "title": "Spirited Away",
          "year": 2001,
          "rating": 8.6,
          "runtime": "2h 05m",
          "genres": ["Animation", "Adventure", "Family", "Fantasy"],
          "description": "...",
          "poster": "...",
          "backdrop": "...",
          "videoUrl": null
        }
      ],
      "page": 0,
      "size": 12,
      "totalElements": 1,
      "totalPages": 1,
      "hasNext": false,
      "hasPrevious": false
    }
  }
  ```

- **Lỗi Validation (400 Bad Request):**
  Khi `page < 0`, `size < 1`, `size > 100`, `yearMin > yearMax`, hoặc `sort` nằm ngoài whitelist:
  ```json
  {
    "success": false,
    "message": "Tham số tìm kiếm không hợp lệ: <chi tiết lỗi>",
    "data": null
  }
  ```

---

## 3. Chính sách Dữ liệu & Animation Fixture

1. **Website Hoạt hình (Animation-First Portal):**
   - Khi client truy cập trang chủ hoặc bộ lọc khám phá hoạt hình, yêu cầu gửi `animationOnly=true` hoặc `genre=Animation`.
   - Nếu cơ sở dữ liệu không có tác phẩm hoạt hình nào thỏa mãn, API phản hồi danh sách rỗng (`items: []`, `totalElements: 0`), tuyệt đối không tự động nạp phim live-action (fiction) để che mắt người dùng.

2. **Provenance & Baseline Gap Status (Round 7 Update):**
   - **Baseline Hiện tại:** Máy chủ Spring Boot hiện đang seed 6 phim viễn tưởng / chính kịch (`the-last-orbit`, `afterlight`, `glass-horizon`, `deep-blue`, `quiet-places`, `nocturne`) trong `DataInitializer.java`.
   - **Kho Hoạt hình Candidate:** 6 tác phẩm hoạt hình (`spirited-away`, `your-name`, `isle-of-dogs`, `spider-verse`, `coraline`, `fantasia-1940`) được tập hợp tại fixture chuẩn:
     [`docs/fixtures/animation_catalog_fixture.json`](file:///d:/Class/movie-rcm-system/docs/fixtures/animation_catalog_fixture.json).
   - **Provenance:** Dữ liệu trích xuất từ repository fixture (`frontend/lib/data/movies.ts`), chưa qua xác minh bên ngoài.
   - **Xử lý Media chưa xác thực:** Toàn bộ các đường dẫn trailer giả lập (`/videos/*.mp4`) và ảnh stock Unsplash không có căn cứ pháp lý đã được **loại bỏ hoặc gán null**. Client áp dụng media fallback an toàn (icon `Film`, CSS gradient) để không làm vỡ giao diện.

3. **Chính sách Nhập Dữ liệu Bổ sung & Bất biến (Additive & Idempotent Policy):**
   - **Canonical ID Match:** So khớp nghiêm ngặt theo mã định danh duy nhất (chuỗi kebab-case chính xác). Tuyệt đối cấm ánh xạ mờ (fuzzy-matching) hoặc tự động đổi ID.
   - **Additive (Bổ sung mới):** Bản ghi candidate chưa tồn tại trong cơ sở dữ liệu sẽ được phân loại là `ADD`.
   - **Idempotent (Không nhân đôi):** Khi chạy lại lần hai trên hệ thống đã nạp, các bản ghi có ID và metadata trùng khớp hoàn toàn sẽ được phân loại là `SKIP`.
   - **No-Overwrite Conflict Policy (Chống ghi đè xung đột):** Nếu một ID candidate đã tồn tại trong hệ thống nhưng có metadata khác biệt (khác title, year, rating, genres), công cụ sẽ báo `CONFLICT` và **từ chối ghi đè**, yêu cầu can thiệp thủ công từ quản trị viên.

4. **Công cụ Dry-Run Preview & Runbook:**
   - Script thực thi an toàn, đối chiếu candidate fixture với mảng baseline in-memory hardcoded trong script (không truy vấn live catalog, không phải importer, không ghi DB):
     ```bash
     # Chạy preview / dry-run đối chiếu candidate fixture với hardcoded baseline:
     node scripts/preview_animation_catalog.cjs

     # Chạy bộ kiểm thử tự động của công cụ dry-run (ADD, SKIP, CONFLICT):
     node scripts/preview_animation_catalog.cjs --test
     ```
   - **Giới hạn phạm vi (M2 Scope Boundary):** Công cụ đóng vai trò phân tích và kiểm chứng quy tắc nạp dữ liệu (data onboarding rules). Tuyệt đối không tự động nạp hoặc import vào cơ sở dữ liệu live khi chưa qua cổng nghiệm thu M2.

