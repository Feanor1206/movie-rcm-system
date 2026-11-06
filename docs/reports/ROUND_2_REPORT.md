# ROUND 2 Implementation & Verification Report

> **Loop Mode:** 30-Minute Round-Based Review Cycle (`docs/GEMINI_CODEX_REVIEW_LOOP.md`)  
> **Target Round ID:** 2 | **Prompt Version:** 2  
> **Milestone:** M2 (Catalog Backend & Animation Discovery)  
> **Run ID:** `run-round2-20261014-0315`  
> **Status:** READY FOR REVIEW  
> **Implementation Engineer:** Antigravity (Gemini)  
> **Lead Reviewer:** Codex  

---

## 1. Executive Summary

Trong **Vòng 2**, kỹ sư triển khai đã hoàn thành trọn vẹn toàn bộ các mục tiêu cốt lõi được giao trong `docs/prompts/GEMINI_CURRENT_TASK.md` và giải quyết dứt điểm hai phát hiện P2 từ Codex trong `docs/reviews/LOOP_ROUND_1_REVIEW.md`:

1. **R1 (P2) — Genre Token Exact Matching:**
   - Khắc phục triệt để tình trạng so khớp chuỗi con (`%genre%`) làm sai lệch danh mục.
   - Xây dựng shared predicate `buildGenreTokenPredicate(...)` và tiện ích escape wildcard SQL `escapeLike(...)` áp dụng chuẩn mực biên giới mã token trong chuỗi CSV (độc lập, đầu danh sách, cuối danh sách, giữa danh sách kèm biến thể khoảng trắng).
   - Đảm bảo token `Drama` tuyệt đối không khớp `Melodrama`, cờ `animationOnly` và token `Animation` tuyệt đối không nhận `NonAnimation`.
   - Giữ nguyên cơ chế phân trang tại tầng Database (JPA Criteria / DB pagination), không nạp toàn bộ bản ghi vào RAM.

2. **R2 (P2) — Search Semantics Consistency:**
   - Đồng bộ hóa ngữ nghĩa tìm kiếm giữa tất cả các endpoint: `GET /api/movies?search=...`, `GET /api/movies?search=...&genre=...`, và `GET /api/movies/browse?query=...`.
   - Toàn bộ đều áp dụng shared predicate `buildSearchPredicate(...)` tìm kiếm trên cả hai trường `title` HOẶC `description`.
   - Đảm bảo tính an toàn đối với các phim có `description` là `null`, bảo toàn nguyên lý tập con (thêm bộ lọc thể loại chỉ thu hẹp kết quả, không mở rộng hay làm xuất hiện thêm kết quả mới).
   - Bảo toàn 100% tính tương thích ngược cho CineBot và các legacy consumers.

3. **Cập nhật Contract Giao tiếp (`M2_CATALOG_CONTRACT.md`):**
   - Đã gỡ bỏ tiêu đề tự nhận APPROVED; chuyển trạng thái thành `READY FOR REVIEW (Round 2 Update)`.
   - Đã chỉnh sửa giá trị ví dụ `videoUrl` của Spirited Away từ `/videos/the-last-orbit.mp4` thành `null`, đặc tả rõ ràng chính sách xử lý trường nullable trong dữ liệu phim.
   - Bổ sung tài liệu đặc tả chi tiết về cơ chế khớp token thể loại (Mục 1.3) và thứ tự ưu tiên tìm kiếm `query` > `search` (Mục 1.4).

4. **Triển khai Shared Frontend Catalog Client (`frontend/lib/services/catalogService.ts`):**
   - Cung cấp các hàm chuẩn hóa: `browseCatalog`, `getCatalogMovieById`, và `normalizeCatalogMovie`.
   - Bao phủ toàn bộ quá trình truyền tải mạng và phân tích cú pháp JSON body trong một cửa sổ timeout duy nhất (mặc định 7000ms) qua `AbortController`.
   - Đảm bảo fallback an toàn cho các trường nullable (`backdrop`, `videoUrl`) và phân loại lỗi rõ ràng (`CatalogApiError` với HTTP status và type).

---

## 2. Root Cause Analysis & Detailed Fixes

### 2.1 R1 — Genre Token Exact Matching (`MovieService.java`)
- **Nguyên nhân:** Trước đây, các hàm lọc thể loại sử dụng `cb.like(cb.lower(root.get("genres")), "%" + token + "%")`. Do thể loại trong CSDL lưu trữ dưới dạng chuỗi phân cách bởi dấu phẩy (CSV, ví dụ: `"Drama,Romance"`), việc tìm kiếm chuỗi con dẫn đến nhận nhầm các token chứa từ khóa (như `"Melodrama"` khi tìm `"Drama"`, hoặc `"NonAnimation"` khi lọc `"Animation"`). Ngoài ra, các ký tự wildcard như `%` và `_` trong chuỗi người dùng nhập không được escape khiến câu lệnh LIKE mở rộng ngoài ý muốn.
- **Giải pháp:**
  - Viết hàm `escapeLike(String input)` thay thế các ký tự `\`, `%`, `_` thành `\\`, `\%`, `\_`.
  - Viết hàm `buildGenreTokenPredicate(...)` xây dựng Criteria Predicate đối chiếu chính xác token:
    - Bằng toàn bộ chuỗi: `genres = :token` hoặc `trim(genres) = :token`.
    - Ở đầu chuỗi: `genres LIKE ':token,%'` (kèm biến thể khoảng trắng `, `).
    - Ở cuối chuỗi: `genres LIKE '%,:token'` (kèm biến thể khoảng trắng `, `).
    - Ở giữa chuỗi: `genres LIKE '%,:token,%'` (kèm biến thể khoảng trắng `, `).
    - Sử dụng escape character `'\\'` chuẩn mực trong JPA Criteria.
  - Áp dụng thống nhất cho: `browseMovies` (tham số `genre`, `genres`, và cờ `animationOnly`), `filterByGenre`, và `getAllMovies(search, genre)`.

### 2.2 R2 — Search Semantics Consistency (`MovieService.java`)
- **Nguyên nhân:** Hàm `searchMovies(search)` trước đây gọi repository `findByTitleContainingIgnoreCase(query)`, chỉ tìm kiếm theo tiêu đề mà bỏ qua `description`. Trong khi đó, `getAllMovies(search, genre)` và `browseMovies` lại tìm kiếm trên cả `title` và `description`. Sự bất nhất này khiến một bộ phim chỉ có từ khóa trong phần mô tả (ví dụ "time" trong Your Name) sẽ không xuất hiện khi gọi `/api/movies?search=time`, nhưng lại xuất hiện khi thêm tham số `/api/movies?search=time&genre=Animation`, vi phạm nguyên tắc bộ lọc chỉ thu hẹp kết quả.
- **Giải pháp:**
  - Viết hàm `buildSearchPredicate(...)` tạo Criteria Predicate:
    - Tìm kiếm `title LIKE %term%` HOẶC (`description IS NOT NULL` VÀ `description LIKE %term%`).
    - Tự động escape các ký tự đặc biệt trong từ khóa tìm kiếm.
  - Áp dụng thống nhất cho `searchMovies(query)`, `getAllMovies(search, genre)`, và `browseMovies(...)`.
  - Trong `MovieController.java`, giữ quy tắc ưu tiên `query` > `search` cho các truy vấn browse.

---

## 3. Changeset & Files Modified in Round 2

Tất cả các thay đổi trong Vòng 2 được lưu trữ và đối chiếu qua snapshot baseline `.round2_snapshot/`:

| File | Trạng thái | Mô tả thay đổi |
| :--- | :--- | :--- |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/MovieService.java` | **Chỉnh sửa** | Thêm `buildGenreTokenPredicate` (R1) và `buildSearchPredicate` (R2); áp dụng vào toàn bộ browse và legacy queries. |
| `backend/springboot/src/test/java/com/dippie/moviercm/CatalogIntegrationTest.java` | **Chỉnh sửa** | Bổ sung 8 integration tests kiểm thử near-match tokens, description search, wildcard escaping, multi-genre AND, tie-breaker và error codes. |
| `docs/contracts/M2_CATALOG_CONTRACT.md` | **Chỉnh sửa** | Cập nhật contract: bỏ tiêu đề APPROVED, sửa Spirited Away videoUrl thành null, ghi nhận exact token matching và search semantics. |
| `frontend/lib/services/catalogService.ts` | **Tạo mới** | Shared catalog client Next.js với AbortSignal timeout bao phủ cả network lẫn JSON body parsing, chuẩn hóa nullable metadata. |
| `frontend/tests/catalog_service_suite.mjs` | **Tạo mới** | Unit & transport test suite cho frontend catalog client (query building, pagination, error parsing, timeout abort). |

---

## 4. Verification & Evidence

### 4.1 Backend Integration Tests (Spring Boot / Maven)
Lệnh thực thi:
```bash
cmd /c "set JAVA_HOME=C:\Program Files\Java\jdk-25.0.3&& mvnw.cmd test -Dspring.profiles.active=test"
```
**Kết quả đầu ra:**
```
[INFO] Running com.dippie.moviercm.AuthAndLibraryIntegrationTest
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 11.23 s -- in com.dippie.moviercm.AuthAndLibraryIntegrationTest
[INFO] Running com.dippie.moviercm.CatalogIntegrationTest
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.386 s -- in com.dippie.moviercm.CatalogIntegrationTest
[INFO] 
[INFO] Results:
[INFO] 
[INFO] Tests run: 16, Failures: 0, Errors: 0, Skipped: 0
[INFO] 
[INFO] ------------------------------------------------------------------------
[INFO] BUILD SUCCESS
[INFO] ------------------------------------------------------------------------
[INFO] Total time:  17.152 s
```
**Exit Code:** `0` (16/16 tests PASS tuyệt đối; 8 auth/library và 8 catalog integration).

### 4.2 Frontend Catalog Client Tests
Lệnh thực thi:
```bash
node --test tests/catalog_service_suite.mjs
```
**Kết quả đầu ra:**
```
✔ 1. Catalog Client: browseCatalog constructs correct query string and normalizes PageResponse (101.9764ms)
✔ 2. Catalog Client: getCatalogMovieById returns null on 404, movie on 200 (21.2676ms)
✔ 3. Catalog Client: 400 validation error throws CatalogApiError with status 400 (13.457ms)
✔ 4. Catalog Client: Request timeout throws CatalogApiError with status 408 (70.5097ms)
ℹ tests 4
ℹ suites 0
ℹ pass 4
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 573.4546
```
**Exit Code:** `0` (4/4 tests PASS).

### 4.3 Frontend M1 Regression Behavioral Suite
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
ℹ duration_ms 1458.92
```
**Exit Code:** `0` (25/25 tests PASS; toàn bộ cơ chế M1 được bảo toàn nguyên vẹn).

### 4.4 TypeScript Typecheck
Lệnh thực thi:
```bash
npx tsc --noEmit
```
**Exit Code:** `0` (0 lỗi compile/typecheck trên toàn bộ frontend).

### 4.5 Patch Integrity Verification
Lệnh thực thi:
```bash
git apply --numstat docs/reports/ROUND_2.patch
git apply --reverse --check docs/reports/ROUND_2.patch
```
**Kết quả đầu ra:**
```
106	33	backend/springboot/src/main/java/com/dippie/moviercm/service/MovieService.java
132	62	backend/springboot/src/test/java/com/dippie/moviercm/CatalogIntegrationTest.java
29	13	docs/contracts/M2_CATALOG_CONTRACT.md
247	0	frontend/lib/services/catalogService.ts
180	0	frontend/tests/catalog_service_suite.mjs
```
- `git apply --reverse --check docs/reports/ROUND_2.patch` trả về **exit code 0** không có bất kỳ xung đột hay lỗi nào, chứng minh patch khôi phục hoàn hảo về baseline `.round2_snapshot/`.

---

## 5. Checkpoint Deliverables & Artifacts

- **Snapshot Baseline:** `.round2_snapshot/`
- **Patch Vòng 2:** [`docs/reports/ROUND_2.patch`](file:///D:/Class/movie-rcm-system/docs/reports/ROUND_2.patch)
- **Manifest File Hashes:** [`docs/reports/ROUND_2_MANIFEST.json`](file:///D:/Class/movie-rcm-system/docs/reports/ROUND_2_MANIFEST.json)
- **Contract Specification:** [`docs/contracts/M2_CATALOG_CONTRACT.md`](file:///D:/Class/movie-rcm-system/docs/contracts/M2_CATALOG_CONTRACT.md)
- **Frontend Catalog Service:** [`frontend/lib/services/catalogService.ts`](file:///D:/Class/movie-rcm-system/frontend/lib/services/catalogService.ts)
- **Status Loop:** [`docs/reports/M2_M3_STATUS.json`](file:///D:/Class/movie-rcm-system/docs/reports/M2_M3_STATUS.json) (`state: "ready_for_review"`)
- **Worklog:** [`docs/reports/M2_M3_WORKLOG.md`](file:///D:/Class/movie-rcm-system/docs/reports/M2_M3_WORKLOG.md)

---

## 6. Proposed Next Steps for Round 3

Sau khi Codex nghiệm thu Vòng 2:
1. **Kết nối UI Search/Browse Experience với Catalog Service:**
   - Thay thế mock data trên trang Search bằng `browseCatalog` từ `frontend/lib/services/catalogService.ts`.
   - Kết nối bộ lọc thể loại, ô tìm kiếm (debounced) và thanh phân trang đồng bộ với `URLSearchParams`.
2. **Cập nhật UI Animation Rails trên Homepage:**
   - Kết nối `browseCatalog({ animationOnly: true, size: 10, sortBy: 'rating' })` để nạp các hàng phim hoạt hình nổi bật từ backend API thực tế.
3. **Kiểm thử trải nghiệm người dùng cuối (E2E/Component Tests):**
   - Viết các test suite kiểm thử tương tác trên UI cho việc chuyển trang, áp dụng filter và xử lý trường hợp lỗi mạng/timeout hiển thị UI thân thiện.
