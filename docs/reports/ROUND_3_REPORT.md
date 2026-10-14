# ROUND 3 Implementation & Verification Report

> **Loop Mode:** 30-Minute Round-Based Review Cycle (`docs/GEMINI_CODEX_REVIEW_LOOP.md`)  
> **Target Round ID:** 3 | **Prompt Version:** 3  
> **Milestone:** M2 (Catalog Backend & Animation Discovery)  
> **Run ID:** `run-round3-20261014-0615`  
> **Status:** READY FOR REVIEW  
> **Implementation Engineer:** Antigravity (Gemini)  
> **Lead Reviewer:** Codex  

---

## 1. Executive Summary

Trong **Vòng 3**, kỹ sư triển khai đã hoàn thành trọn vẹn toàn bộ các mục tiêu trọng tâm được giao trong `docs/prompts/GEMINI_CURRENT_TASK.md` và giải quyết triệt để 3 phát hiện C1–C3 từ Codex trong `docs/reviews/LOOP_ROUND_2_REVIEW.md`:

1. **C1 (P2) — Vòng đời Thống nhất cho Timeout & External Cancellation (`catalogService.ts`):**
   - Tái cấu trúc hàm điều phối `executeWithLifecycle` để cửa sổ timeout và bộ lắng nghe hủy (`AbortSignal`) bao phủ **toàn bộ chu kỳ**: cả gửi request mạng lẫn phân tích cú pháp streaming JSON body.
   - Dọn dẹp triệt để timer (`clearTimeout`) và gỡ bỏ event listener của caller trong khối `finally` sau khi toàn bộ chuỗi Promise hoàn tất.
   - Phân loại lỗi chính xác, độc lập:
     - Hủy chủ động từ caller (intentional cancellation): ném `CatalogApiError` với `status: 499`, `isCanceled: true`, `name: 'AbortError'`. UI nhận diện cờ này để không hiển thị lỗi mạng sai lệch khi người dùng gõ từ khóa mới.
     - Quá thời gian phản hồi: ném `CatalogApiError` với `status: 408`, `isTimeout: true`.
     - Tín hiệu đã bị hủy từ trước (pre-aborted signal): từ chối ngay lập tức mà không khởi tạo fetch hay timer.

2. **C2 (P2) — Kiểm định Nghiêm ngặt Payload, Chống Dữ liệu Giả & Xác minh ID (`catalogService.ts`):**
   - **Xác thực phim (`normalizeCatalogMovie`):** Kiểm tra bắt buộc các trường `id` (chuỗi không rỗng), `title` (chuỗi không rỗng), `year` (số hữu hạn > 1800), `rating` (số hữu hạn 0..10). Tuyệt đối không tự bịa `id: ""`, `year: 0`, `rating: 0` khi thiếu trường.
   - **Xác thực phân trang (`browseCatalog`):** Từ chối payload sai lệch như `data: {}` hoặc `data.items` không phải là mảng với lỗi `502 Bad Gateway`, không biến thành trang rỗng thành công.
   - **Khớp ID chi tiết phim (`getCatalogMovieById`):** Xác minh `movie.id` trả về từ server phải trùng khớp tuyệt đối với `id` được yêu cầu; nếu không khớp sẽ ném lỗi 502, ngăn chặn hoàn toàn việc lưu nhầm phim vào thư viện cá nhân.
   - **Chính sách HTTP 404:** Trả về `null` an toàn ngay khi nhận status 404 mà không cố gắng parse JSON, bảo đảm không bị `SyntaxError` khi gặp body HTML hoặc rỗng từ Tomcat/Nginx.
   - **Thứ tự ưu tiên Search/Query:** Xử lý fallback đúng chuẩn backend: `query` có khoảng trắng hoặc rỗng sẽ tự động chuyển sang tham số `search`.

3. **C3 (P2) — Chuẩn hóa Khoảng trắng Thể loại Tổng quát tại Boundary Database (`MovieService.java`):**
   - Thay thế việc hard-code từng dấu cách bằng biểu thức quy chuẩn biên giới token:
     `(^|[,])[ \t]*TOKEN[ \t]*([,]|$)`
     thông qua hàm chuẩn `REGEXP_LIKE` được hỗ trợ trên cả H2 in-memory test database và PostgreSQL 16 production database.
   - Xử lý mượt mà mọi biến thể khoảng trắng thừa (spaces), dấu tab (`\t`) ở đầu, cuối và giữa các dấu phẩy phân cách (ví dụ: `"  Animation,   Family  "` hay `"\tAnimation\t,\tAdventure\t"`).
   - Bảo toàn nguyên vẹn khoảng trắng bên trong tên thể loại nhiều từ (internal spaces) như `"Sci-Fi & Fantasy"` hoặc `"Martial Arts"`.
   - Giữ vững tính chất chống nhận nhầm token gần giống (`Melodrama` vs `Drama`, `NonAnimation` vs `Animation`) và escape các ký tự đặc biệt trong input.
   - Giữ nguyên cơ chế phân trang và lọc trực tiếp tại Database (JPA Criteria / DB pagination), không lọc in-memory.

4. **Cập nhật Contract Giao tiếp (`docs/contracts/M2_CATALOG_CONTRACT.md`):**
   - Nâng cấp phiên bản lên **1.2.0 (Round 3 Update)**.
   - Bổ sung Mục 1.3 về quy chuẩn biên giới token regex và khoảng trắng tổng quát.
   - Bổ sung Mục 1.5 đặc tả chi tiết về vòng đời catalog client, phân loại lỗi (cancellation vs timeout vs network), chính sách HTTP 404, và xác thực khớp ID.

---

## 2. Root Cause Analysis & Detailed Fixes

### 2.1 C1 — Timeout/Cancellation Body Lifecycle
- **Nguyên nhân:** Ở Vòng 2, `fetchWithTimeout` giải phóng timer và gỡ bỏ external abort listener ngay trong khối `finally` của `fetch()`. Khi `res.json()` đang phân tích cú pháp body, timer đã bị tắt và external abort không còn kích hoạt `controller.abort()`, dẫn đến việc caller hủy sau khi nhận headers thì body vẫn tiếp tục chạy và resolve thành công.
- **Giải pháp:** Viết hàm điều phối `executeWithLifecycle` bao bọc cả `fetch` và `res.json()`. Timer và listener duy trì hoạt động đến khi toàn bộ quá trình kết thúc. Phân loại rõ ràng cờ `isCanceled` (499) khi caller chủ động hủy để UI không báo lỗi kết nối.

### 2.2 C2 — Malformed Payload & ID Verification
- **Nguyên nhân:** `normalizeCatalogMovie` trước đây sử dụng fallback mặc định `raw.id || ''`, `typeof raw.year === 'number' ? raw.year : 0`, biến payload lỗi `{}` thành dữ liệu phim rỗng giả (phantom movie). Tương tự, `browseCatalog` chấp nhận `data: {}` thành trang rỗng thành công, và `getCatalogMovieById` không kiểm tra `movie.id` trả về có khớp với ID yêu cầu hay không.
- **Giải pháp:** Đặt điều kiện kiểm tra nghiêm ngặt `typeof raw.id === 'string' && raw.id.trim()`, `year > 1800`, `0 <= rating <= 10`. Thiếu trường bắt buộc ném lỗi 502 ngay lập tức. Xác minh `movie.id.toLowerCase() === requestedId.toLowerCase()`. Xử lý 404 trả về `null` trước khi parse body.

### 2.3 C3 — Generalized Genre Whitespace Boundary
- **Nguyên nhân:** `buildGenreTokenPredicate` trong Vòng 2 liệt kê các pattern LIKE thủ công với 1 dấu cách (`esc + ", %"`, `"%, " + esc`). Khi gặp dữ liệu có 2 dấu cách (`"Animation,  Family"`), dấu tab (`\t`), hoặc khoảng trắng ở đầu chuỗi (`"  Animation,Family"`), các pattern LIKE không khớp được vị trí token.
- **Giải pháp:** Sử dụng `REGEXP_LIKE(lower(genres), '(^|[,])[ \t]*' + escapedToken + '[ \t]*([,]|$)')`. Biểu thức này đối chiếu chuẩn xác biên giới token CSV với số lượng spaces/tabs tùy ý mà không chạm vào internal space của tên thể loại.

---

## 3. Changeset & Files Modified in Round 3

Tất cả các thay đổi trong Vòng 3 được so sánh và kiểm chứng đối chiếu với snapshot baseline `.round3_snapshot/`:

| File | Trạng thái | Mô tả thay đổi |
| :--- | :--- | :--- |
| `backend/springboot/src/main/java/com/dippie/moviercm/service/MovieService.java` | **Chỉnh sửa** | Triển khai `escapeRegex` và biểu thức `REGEXP_LIKE` biên giới token tổng quát cho `buildGenreTokenPredicate` (C3). |
| `backend/springboot/src/test/java/com/dippie/moviercm/CatalogIntegrationTest.java` | **Chỉnh sửa** | Bổ sung fixtures và test case kiểm thử C3: repeated spaces, tabs, multi-word genres (Sci-Fi & Fantasy, Martial Arts), near-match và multi-genre AND. |
| `docs/contracts/M2_CATALOG_CONTRACT.md` | **Chỉnh sửa** | Nâng cấp v1.2.0: đặc tả chi tiết quy chuẩn token boundaries C3 và vòng đời / validation client C1 & C2. |
| `frontend/lib/services/catalogService.ts` | **Chỉnh sửa** | Tái cấu trúc `executeWithLifecycle` (C1), validate nghiêm ngặt payload / ID mismatch / 404 policy / precedence (C2). |
| `frontend/tests/catalog_service_suite.mjs` | **Chỉnh sửa** | Mở rộng 9 unit & transport tests bao phủ toàn diện C1 (external abort body, slow body timeout, pre-aborted signal) và C2 (malformed payload, missing fields, ID mismatch, 404 HTML, precedence). |

---

## 4. Verification & Evidence

### 4.1 Backend Spring Boot Tests (17/17 PASS)
Lệnh thực thi:
```bash
cmd /c "set JAVA_HOME=C:\Program Files\Java\jdk-25.0.3&& mvnw.cmd test -Dspring.profiles.active=test"
```
**Kết quả đầu ra:**
```
[INFO] Running com.dippie.moviercm.AuthAndLibraryIntegrationTest
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 9.610 s -- in com.dippie.moviercm.AuthAndLibraryIntegrationTest
[INFO] Running com.dippie.moviercm.CatalogIntegrationTest
[INFO] Tests run: 9, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.472 s -- in com.dippie.moviercm.CatalogIntegrationTest
[INFO] 
[INFO] Results:
[INFO] 
[INFO] Tests run: 17, Failures: 0, Errors: 0, Skipped: 0
[INFO] 
[INFO] ------------------------------------------------------------------------
[INFO] BUILD SUCCESS
[INFO] ------------------------------------------------------------------------
[INFO] Total time:  16.093 s
```
**Exit Code:** `0` (17/17 tests PASS tuyệt đối; 8 Auth/Library + 9 Catalog Integration).

### 4.2 Frontend Catalog Service Suite (9/9 PASS)
Lệnh thực thi:
```bash
node --test tests/catalog_service_suite.mjs
```
**Kết quả đầu ra:**
```
✔ 1. Catalog Client: browseCatalog constructs correct query string and normalizes PageResponse (108.0109ms)
✔ 2. C1: External abort after headers received while body is pending aborts transport and throws cancellation (28.1262ms)
✔ 3. C1: Slow body triggers timeout and cleans up timers (71.9714ms)
✔ 4. C1: Pre-aborted external signal rejects immediately without setting timer (16.305ms)
✔ 5. C2: Malformed paginated payload (data={} or missing items) throws 502 (21.2055ms)
✔ 6. C2: normalizeCatalogMovie rejects missing required fields and never fabricates phantom zeros (17.2497ms)
✔ 7. C2: getCatalogMovieById verifies response ID matches requested canonical ID (15.6039ms)
✔ 8. C2: getCatalogMovieById returns null on 404 HTML body without syntax error (18.3007ms)
✔ 9. C2: Search/Query precedence: blank query falls back to search parameter (15.9329ms)
ℹ tests 9
ℹ suites 0
ℹ pass 9
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 652.0674
```
**Exit Code:** `0` (9/9 tests PASS).

### 4.3 Frontend M1 Regression Behavioral Suite (25/25 PASS)
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
ℹ duration_ms 1382.9451
```
**Exit Code:** `0` (25/25 tests PASS; toàn bộ cơ chế Auth/Library/Retry của M1 được bảo toàn nguyên vẹn).

### 4.4 TypeScript Typecheck
Lệnh thực thi:
```bash
npx tsc --noEmit
```
**Exit Code:** `0` (0 lỗi compile/typecheck).

### 4.5 Patch Integrity Verification
Lệnh thực thi:
```bash
git apply --numstat docs/reports/ROUND_3.patch
git apply --reverse --check docs/reports/ROUND_3.patch
```
**Kết quả đầu ra:**
```
19	36	backend/springboot/src/main/java/com/dippie/moviercm/service/MovieService.java
57	8	backend/springboot/src/test/java/com/dippie/moviercm/CatalogIntegrationTest.java
27	10	docs/contracts/M2_CATALOG_CONTRACT.md
268	120	frontend/lib/services/catalogService.ts
252	50	frontend/tests/catalog_service_suite.mjs
```
- `git apply --reverse --check docs/reports/ROUND_3.patch` trả về **exit code 0** không có bất kỳ xung đột hay lỗi nào, chứng minh patch khôi phục hoàn hảo về baseline `.round3_snapshot/`.

---

## 5. Checkpoint Deliverables & Artifacts

- **Snapshot Baseline:** `.round3_snapshot/`
- **Patch Vòng 3:** [`docs/reports/ROUND_3.patch`](file:///D:/Class/movie-rcm-system/docs/reports/ROUND_3.patch)
- **Manifest File Hashes:** [`docs/reports/ROUND_3_MANIFEST.json`](file:///D:/Class/movie-rcm-system/docs/reports/ROUND_3_MANIFEST.json)
- **Contract Specification:** [`docs/contracts/M2_CATALOG_CONTRACT.md`](file:///D:/Class/movie-rcm-system/docs/contracts/M2_CATALOG_CONTRACT.md)
- **Frontend Catalog Service:** [`frontend/lib/services/catalogService.ts`](file:///D:/Class/movie-rcm-system/frontend/lib/services/catalogService.ts)
- **Status Loop:** [`docs/reports/M2_M3_STATUS.json`](file:///D:/Class/movie-rcm-system/docs/reports/M2_M3_STATUS.json) (`state: "ready_for_review"`)
- **Worklog:** [`docs/reports/M2_M3_WORKLOG.md`](file:///D:/Class/movie-rcm-system/docs/reports/M2_M3_WORKLOG.md)

---

## 6. Proposed Next Steps for Round 4

Sau khi Codex nghiệm thu Vòng 3:
1. **Triển khai Search / Browse Experience Slice trên Frontend:**
   - Kết nối `browseCatalog` vào `SearchExperience.tsx` với cờ `animationOnly=true` mặc định cho hành trình hoạt hình.
   - Đồng bộ trạng thái tìm kiếm (debounced input), lọc thể loại, sắp xếp và phân trang với URL parameters (`URLSearchParams`).
   - Xử lý mượt mà các trạng thái loading skeleton, empty results, và error retry thông qua cờ `isCanceled` (không hiển thị lỗi khi người dùng gõ tìm kiếm mới).
2. **Cập nhật Homepage Rails:**
   - Kết nối danh mục hoạt hình nổi bật trên trang chủ với backend catalog API thay cho mock data.
