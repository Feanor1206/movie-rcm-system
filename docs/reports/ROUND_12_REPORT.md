# Báo cáo Nghiệm thu Milestone M3 — Vòng 12 (Round 12 Report)

- **Milestone:** M3 — Web nhẹ, dễ dùng và vận hành rõ ràng
- **Nhánh thực hiện:** `dev`
- **Round ID:** 12
- **Prompt Version:** 12
- **Run ID:** `run-round12-20261014-1245`
- **Reviewed Prior Run ID:** `run-round11-20261014-1140` (Codex Review: CHANGES REQUESTED, C1 & C2 findings)
- **Trạng thái:** `ready_for_review`
- **Thời gian thực hiện:** 2026-10-14 12:45 – 13:15 (~30 phút)

---

## 1. Tổng quan Sửa đổi C1 & C2

Vòng 12 tập trung giải quyết triệt để 2 nhóm phát hiện kỹ thuật cốt lõi (C1 và C2) từ `docs/reviews/LOOP_ROUND_11_REVIEW.md` và `docs/prompts/ROUND_12_GEMINI_PROMPT.md`. Toàn bộ các kết quả đạt được từ R1 (CI) và R3 (Modals/A11y/Touch bounds) cùng mọi hành vi M1/M2 được giữ nguyên; không can thiệp vào AI/FastAPI/GPU hoặc DB live:

### C1 — Đồng bộ Schema Bootstrap Thực tế và Chính sách Cấu hình Bắt buộc

1. **Đồng bộ hóa Nguồn Bootstrap Canonical (`01_init.sql`):**
   - File `database/schema/01_init.sql` (được Compose mount trực tiếp vào `/docker-entrypoint-initdb.d/01_init.sql`) đã được bổ sung đầy đủ bảng `favorite_items` với khóa ngoại tham chiếu `users(id)` và `movies(id)` (`ON DELETE CASCADE`), ràng buộc duy nhất `uq_user_movie_favorite(user_id, movie_id)`, và các chỉ mục `idx_favorite_user`, `idx_favorite_movie`.
   - Đồng bộ tên ràng buộc duy nhất `uq_user_movie_favorite` trên `docs/runbooks/db/schema_v1.sql`.
   - Đảm bảo volume PostgreSQL mới khi khởi tạo từ Compose sẽ tự động có đủ 5 bảng thực thể (`users`, `movies`, `watchlist_items`, `movie_ratings`, `favorite_items`).

2. **Migration Additive Bảo toàn Dữ liệu cho Cơ sở Dữ liệu Hiện hữu:**
   - Tạo file migration `database/migrations/02_add_favorite_items.sql` sử dụng cú pháp an toàn `CREATE TABLE IF NOT EXISTS favorite_items` và `CREATE INDEX IF NOT EXISTS`.
   - Tuyệt đối không sử dụng `DROP TABLE`, không ghi đè dữ liệu người dùng, không chạy lại init script trên volume đã có dữ liệu.

3. **Đồng bộ Biến Môi trường Configurable trong Docker Compose:**
   - Trong `infrastructure/docker-compose.yml`, đồng bộ hóa các biến `${POSTGRES_USER:-postgres}` và `${POSTGRES_DB:-movie_rcm_db}` thống nhất trên 3 vị trí:
     - Biến môi trường dịch vụ postgres (`POSTGRES_USER`, `POSTGRES_DB`).
     - Healthcheck của dịch vụ postgres (`pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-movie_rcm_db}`).
     - Chuỗi kết nối JDBC của dịch vụ spring-backend (`jdbc:postgresql://postgres:5432/${POSTGRES_DB:-movie_rcm_db}`).

4. **Kiểm tra Cấu hình Tiền khả thi Bắt buộc (`ProductionConfigPreflight`):**
   - Tạo bean `ProductionConfigPreflight` (`BeanFactoryPostProcessor` + `EnvironmentAware`).
   - Khi profile kích hoạt chứa `prod`, preflight chạy trước mọi khởi tạo kết nối hay repository bean. Nếu thiếu hoặc chưa gán giá trị hợp lệ cho `APP_JWT_SECRET` hoặc `SPRING_DATASOURCE_PASSWORD` (vẫn còn placeholder `${...}` hoặc rỗng), hệ thống lập tức ném ngoại lệ `IllegalStateException` chỉ rõ tên biến môi trường còn thiếu, ngăn chặn startup thất bại âm thầm hoặc rò rỉ cấu hình.
   - Cho phép cấu hình driver JDBC thông qua biến `${SPRING_DATASOURCE_DRIVER_CLASS_NAME:org.postgresql.Driver}` trong `application.yml` phục vụ kiểm thử tích hợp cô lập.

5. **Bộ Kiểm thử Executable Bootstrap & Policy (`SeedAndConfigPolicyTest.java`):**
   - Đã triển khai 8 tests thực thi hoàn chỉnh (**8/8 PASS**, tổng test suite backend: **25/25 PASS**):
     - `testDefaultYamlConfigurationMatchesProductionPolicy`: Khẳng định `app.seed.enabled: false`, `spring.sql.init.mode: never`, `ddl-auto: validate`.
     - `testDataInitializerDoesNotSeedUsersByDefault`: Khẳng định không tạo tài khoản demo.
     - `testProductionConfigPreflightFailsWhenJwtSecretMissing`: Negative control khẳng định preflight ném lỗi đúng biến `APP_JWT_SECRET`.
     - `testProductionConfigPreflightFailsWhenDatasourcePasswordMissing`: Negative control khẳng định preflight ném lỗi đúng biến `SPRING_DATASOURCE_PASSWORD`.
     - `testProductionContextStartsSuccessfullyWithValidSecretsAndDatabase`: Positive control nạp đúng cấu hình `application.yml` + test DB + secrets hợp lệ, xác nhận Hibernate validate thành công.
     - `testCanonicalBootstrapSqlInitializesAllTablesAndPassesHibernateValidation`: Khởi tạo DB sạch từ chính file `database/schema/01_init.sql`, sau đó chạy Hibernate với `ddl-auto: validate`, chứng minh 100% thực thể JPA (bao gồm `FavoriteItem`) khớp với schema khởi tạo của Compose.
     - `testAdditiveMigrationPreservesExistingDataAndValidatesSchema`: Tạo DB 4 bảng giả lập dữ liệu thực (users, movies, watchlist, ratings), áp dụng migration `02_add_favorite_items.sql`, xác nhận 100% dữ liệu cũ được bảo toàn nguyên vẹn và schema mới vượt qua Hibernate `ddl-auto: validate`.
     - `testConfigurablePostgresCredentialsResolution`: Khẳng định các biến `POSTGRES_USER` và `POSTGRES_DB` được nội suy đồng bộ.

---

### C2 — Hiệu chuẩn Đo đạc Hiệu năng, Observer Harness và Bóc tách Dữ liệu

1. **PerformanceObserver cho LCP và Layout Shift (Session Window Chuẩn):**
   - Tiêm script lắng nghe qua CDP `Page.addScriptToEvaluateOnNewDocument` trước bất kỳ điều hướng hay render nào.
   - Sử dụng `new PerformanceObserver(...).observe({ type: 'largest-contentful-paint', buffered: true })` và `new PerformanceObserver(...).observe({ type: 'layout-shift', buffered: true })`.
   - **Tuyệt đối không gán FCP vào LCP:** Nếu trình duyệt không sinh ra sample LCP, giá trị được trả về là `null` hoặc nhãn `unavailable`.
   - **Tổng hợp CLS theo Session Window chuẩn (W3C / Google Web Vitals):** Tính toán layout shift theo cửa sổ tối đa với khoảng cách nghỉ giữa các shift tối đa 1 giây và độ dài cửa sổ tối đa 5 giây; đồng thời bóc tách riêng số liệu `clsRaw`.
   - **Kiểm thử Tự chẩn đoán (Negative / Control Test):** Bổ sung flag `--negative-test` trong harness. Kiểm tra sự hiện diện của observer, cờ hỗ trợ API của trình duyệt, và độ nhạy phát hiện layout shift cố ý (ghi nhận layout shift `0.222 > 0`).

2. **Giao thức Đo lường Tách bạch Cold vs Warm:**
   - **Cold Runs (3 lần/route):** Trước mỗi lần chạy, gọi lệnh CDP `Network.clearBrowserCache` và `Network.setCacheDisabled({ cacheDisabled: true })`. Reset bộ đếm network. Đảm bảo toàn bộ assets tĩnh và API payload đều phải truyền tải qua mạng cục bộ.
   - **Warm Runs (3 lần/route):** Sau 1 lượt truy cập làm ấm (priming visit), kích hoạt cache (`cacheDisabled: false`), thực hiện 3 lần truy cập liên tiếp và ghi nhận các lượt phản hồi từ bộ nhớ đệm HTTP/CDP.
   - Toàn bộ kết quả Cold và Warm được lưu thành hai mảng mẫu độc lập và hai bảng tóm tắt (`coldSummary` và `warmSummary`) riêng biệt trong file JSON; không gộp chung median giữa cold và warm.

3. **Đối chiếu Dung lượng Mạng Thật qua CDP Network Accounting:**
   - Lắng nghe sự kiện `Network.loadingFinished` để ghi nhận chính xác `encodedDataLength` (wire transfer bytes).
   - Tách biệt rõ ràng giữa:
     - `cdpWireTransferBytes`: Tổng byte truyền tải thực tế qua dây mạng (wire).
     - `resourceTiming.transferBytes`: Byte truyền tải theo Resource Timing API.
     - `resourceTiming.encodedBodyBytes` và `decodedBodyBytes`: Dung lượng nén và giải nén của thân phản hồi.
     - Phân loại rõ các yêu cầu từ disk/memory cache.

4. **Điều kiện Trang Sẵn sàng (App-Ready Conditions):**
   - Bổ sung `waitForCondition` đa chiều: chờ `document.readyState === 'complete'`, kiểm tra phần tử cốt lõi của route (`main`, `input`, `h1`), và chờ nội dung định danh thực tế xuất hiện (`The Quantum Garden`, `Watchlist`, `Danh sách`, v.v.).
   - Áp dụng cửa sổ quan sát có giới hạn (bounded observation window: 400ms) sau khi giao diện sẵn sàng để các observer hoàn tất ghi nhận sự kiện layout shift và LCP cuối cùng.

5. **Kích thước JavaScript Tải lần đầu Chính xác (Exact First Load JS Bytes):**
   - Trích xuất trực tiếp từ manifest chunk của bản build production Next.js 15.1.2:
     - `/`: Raw = 490,624 bytes, Gzip = 138,925 bytes (**135.67 kB** $\le$ 140 kB budget)
     - `/search`: Raw = 482,201 bytes, Gzip = 137,709 bytes (**134.48 kB** $\le$ 140 kB budget)
     - `/movies/[id]`: Raw = 495,115 bytes, Gzip = 140,113 bytes (**136.83 kB** $\le$ 140 kB budget)
     - `/profile`: Raw = 499,237 bytes, Gzip = 138,831 bytes (**135.58 kB** $\le$ 140 kB budget)
   - Tất cả 4 route đều đạt ngân sách $\le 140$ kB (143,360 bytes).

---

## 2. Bảng Kết quả Đo lường Hiệu năng Chuẩn hóa (Corrected Benchmark Baseline)

### Điều kiện Môi trường Đo đạc:
- **Framework & Build:** Next.js 15.1.2 (Standalone Production Build, Next compiler).
- **Môi trường:** Node.js v26.1.0, Chrome Headless qua CDP (Chrome DevTools Protocol).
- **Mạng:** Local Loopback qua HTTP Fixture Server (127.0.0.1:8080).
- **Viewport:** Desktop 1280x800.
- **Phương pháp lấy mẫu:** 3 lần Cold (xóa & vô hiệu hóa cache) + 3 lần Warm (bật cache sau 1 lượt làm ấm) cho mỗi route.
- **Lưu trữ dữ liệu thô:** `docs/reports/screenshots/ROUND_12/perf_measurements.json`.

### Kết quả Đo đạc Chi tiết (Cold vs Warm):

| Route & Trạng thái Cache | DCL (Median / Range) | Load Duration (Median / Range) | FCP (Median / Range) | LCP Observer (Median / Range) | CLS Session Window (Median / Range) | CDP Wire Transfer Bytes | Số Requests |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Trang chủ (`/`) — COLD** | **118 ms** (93 – 158 ms) | **265 ms** (259 – 421 ms) | **132 ms** (132 – 196 ms) | **496 ms** (496 – 500 ms) | **0.014** (0.014 – 0.014) | **330.4 kB** | 33 |
| **Trang chủ (`/`) — WARM** | **59 ms** (57 – 89 ms) | **98 ms** (90 – 101 ms) | **132 ms** (120 – 140 ms) | **268 ms** (264 – 268 ms) | **0.014** (0.014 – 0.014) | **16.4 kB** | 29 |
| **Tìm kiếm (`/search`) — COLD** | **74 ms** (44 – 95 ms) | **167 ms** (159 – 177 ms) | **92 ms** (88 – 108 ms) | **240 ms** (236 – 252 ms) | **0.069** (0.069 – 0.071) | **319.8 kB** | 30 |
| **Tìm kiếm (`/search`) — WARM** | **44 ms** (34 – 60 ms) | **81 ms** (76 – 82 ms) | **92 ms** (84 – 96 ms) | **140 ms** (136 – 144 ms) | **0.069** (0.069 – 0.069) | **7.3 kB** | 26 |
| **Chi tiết phim (`/movies/...`) — COLD** | **54 ms** (49 – 134 ms) | **190 ms** (174 – 232 ms) | **88 ms** (88 – 116 ms) | **344 ms** (344 – 356 ms) | **0.000** (0.000 – 0.000) | **332.7 kB** | 34 |
| **Chi tiết phim (`/movies/...`) — WARM** | **52 ms** (42 – 55 ms) | **54 ms** (45 – 84 ms) | **88 ms** (84 – 92 ms) | **108 ms** (108 – 108 ms) | **0.000** (0.000 – 0.000) | **17.0 kB** | 30 |
| **Hồ sơ cá nhân (`/profile`) — COLD** | **51 ms** (46 – 89 ms) | **84 ms** (80 – 165 ms) | **84 ms** (84 – 104 ms) | **148 ms** (148 – 152 ms) | **0.008** (0.008 – 0.008) | **320.0 kB** | 28 |
| **Hồ sơ cá nhân (`/profile`) — WARM** | **31 ms** (29 – 37 ms) | **62 ms** (57 – 85 ms) | **84 ms** (80 – 88 ms) | **116 ms** (112 – 120 ms) | **0.007** (0.007 – 0.007) | **6.5 kB** | 24 |

*Ghi chú về phép đo đã hiệu chuẩn:*
- **LCP thực tế:** Lấy từ `PerformanceObserver` có `buffered: true`. Giá trị LCP cold nằm trong khoảng 148 – 496 ms, LCP warm nằm trong khoảng 108 – 268 ms (đều vượt trội so với ngưỡng khuyến nghị $\le 2500$ ms của Google).
- **Dung lượng mạng thực tế (CDP Wire Transfer):** Lần tải Cold tải đầy đủ toàn bộ scripts, fonts và styles (~320 – 332 kB), trong khi lần tải Warm chỉ tốn từ 6.5 – 17.0 kB nhờ cơ chế cache của trình duyệt.
- **CLS Session Window:** Nằm trong khoảng 0.000 – 0.069 (đều dưới ngưỡng an toàn 0.100).
- **Tính chất Baseline:** Đây là bộ chỉ số baseline được hiệu chuẩn đúng quy chuẩn (Corrected Baseline). Không tuyên bố tốc độ tăng giả tạo khi chưa thay đổi mã nguồn logic.

---

## 3. Ma trận Nghiệm thu Vòng 12 (Acceptance Matrix)

| Hạng mục kiểm tra | Mã tiêu chí | Kết quả | Ghi chú bằng chứng thực tế |
| :--- | :---: | :---: | :--- |
| **Compose Bootstrap Schema** | C1 | **PASS** | `01_init.sql` có `favorite_items`. Test khởi tạo H2 PG-mode + Hibernate validate thành công. |
| **Additive Migration** | C1 | **PASS** | `02_add_favorite_items.sql` tạo bảng IF NOT EXISTS, bảo toàn 100% dữ liệu cũ trên 4 bảng ban đầu. |
| **Configurable Compose Variables** | C1 | **PASS** | `POSTGRES_USER` và `POSTGRES_DB` đồng bộ giữa postgres env, healthcheck và Spring URL. |
| **Production Config Preflight** | C1 | **PASS** | Preflight phát hiện và ném lỗi rõ `APP_JWT_SECRET` và `SPRING_DATASOURCE_PASSWORD` khi thiếu. |
| **Spring Boot Policy Suite** | C1 | **PASS** | `SeedAndConfigPolicyTest.java` đạt 8/8 tests pass. Tổng suite backend: **25/25 pass**. |
| **Buffered PerformanceObserver** | C2 | **PASS** | LCP lấy qua observer có `buffered: true`, không fallback sang FCP. Negative control phát hiện shift 0.222. |
| **CLS Session Window Aggregation**| C2 | **PASS** | Thuật toán Session Window W3C tính đúng khoảng cách 1s / độ dài tối đa 5s. |
| **Tách biệt Cold và Warm Runs** | C2 | **PASS** | 3 cold (cache cleared/disabled) + 3 warm (cache enabled). Dữ liệu mảng và median tách biệt. |
| **CDP Wire Byte Accounting** | C2 | **PASS** | Theo dõi `encodedDataLength` qua sự kiện `loadingFinished`. Cold: ~330 kB, Warm: ~7-17 kB. |
| **First Load JS Exact Bytes** | C2 | **PASS** | Cả 4 route đều $\le 140$ kB (Home: 135.67 kB, Search: 134.48 kB, Detail: 136.83 kB, Profile: 135.58 kB). |
| **Frontend Test Suite** | M1/M2/M3 | **PASS** | Chạy `npm test`: **57/57 pass** (0 failures, 0 skipped). |
| **TypeScript Typecheck** | M3 | **PASS** | Chạy `npx tsc --noEmit`: **0 errors**. |
| **14 Browser E2E Journeys** | M3 | **PASS** | Chạy `run_browser_walkthrough.cjs`: **14/14 steps pass**, 14 screenshots tại `ROUND_12/`. |
| **Bảo toàn Thay đổi Ngoài Scope**| Guardrail | **PASS** | Không sửa AI/FastAPI/Qwen, không dùng DB live, không commit/push. Theme xanh lá giữ nguyên. |

---

## 4. Danh sách File Thay đổi và Bằng chứng Xác thực (Manifest & Hashes)

### Các File Thay đổi Thuộc Scope Vòng 12:
1. `backend/springboot/src/main/resources/application.yml` (modified)
2. `backend/springboot/src/main/java/com/dippie/moviercm/config/ProductionConfigPreflight.java` (added)
3. `backend/springboot/src/test/java/com/dippie/moviercm/SeedAndConfigPolicyTest.java` (modified)
4. `database/schema/01_init.sql` (modified)
5. `database/migrations/02_add_favorite_items.sql` (added)
6. `docs/runbooks/db/schema_v1.sql` (modified)
7. `infrastructure/docker-compose.yml` (modified)
8. `scripts/run_browser_walkthrough.cjs` (modified)

### Thư mục Screenshots & Bằng chứng Riêng biệt:
- Toàn bộ bằng chứng ảnh và số liệu thô được lưu độc lập tại: `docs/reports/screenshots/ROUND_12/`
  - 14 screenshots PNG tương ứng 14 bước walkthrough.
  - `perf_measurements.json`: Dữ liệu đo đạc cold/warm tách biệt, exact JS bytes và metadata CDP.
  - `walkthrough_evidence.json`: Bảng đối chiếu kỳ vọng và thực tế của 14 bước walkthrough.
- Thư mục `docs/reports/screenshots/ROUND_11/` được đóng băng nguyên vẹn.

### Kiểm tra Nghịch đảo Patch (Reverse Patch Check):
- `git diff > docs/reports/ROUND_12.patch`
- `git apply --check -R docs/reports/ROUND_12.patch` -> **Exit code 0 (PASS)**.

### Hash Manifest:
- Toàn bộ 25 file thay đổi và sinh mới đã được băm SHA-256 và lưu tại `docs/reports/ROUND_12_MANIFEST.json`.
