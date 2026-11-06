# Round 10 — M3 independent review

2026-10-14. **REQUEST CHANGES; chưa nghiệm thu M3, chưa triển khai Drive hoặc AI.**

Round10/prompt10/run-round10-20261014-1015 khớp control/status. 33 manifest hashes khớp trước/sau kiểm tra; patch reverse check exit0. Codex không sửa application code hoặc dùng DB live.

## Kết quả đã xác minh

- Frontend bốn suites tên thật: **54/54 pass**; tsc exit0; production build exit0. Next thực tế15.1.2, Node26.1.0; không phải Next15.2.4/Turbopack như report. First Load JS138/139/138/137kB là build output, không phải latency thực tế.
- Spring tests trên H2 mem:codex_round10_review riêng: **19/19 pass** (8 auth/library,9 catalog,2 seed), exit0. Log lưu docs/reviews/evidence/ROUND_10/backend_test.log.
- Browser14 bước được chạy lại qua reviewer wrapper outputtemp riêng; bản có thêm targeted diagnostics hoàn tất exit0. Assertions của harness pass nhưng diagnostics xác nhận các nhóm UI chưa đạt bên dưới. Không ghi đè ảnh/report Gemini. Không gọi exit0 này là toàn M3 đạt.
- Auth failed-submit rồi close trong case reviewer thử **đã restore opener đúng**; không dùng nghi ngờ source của AuthModal làm finding restore-focus khi repro không xác nhận.

## R1 — P1: CI không kiểm chứng đủ suites, không chạy trên dev

`.github/workflows/ci.yml` gọi tests/catalog_client_suite.mjs và tests/m1_resilience_suite.mjs; hai files này không tồn tại. Tên đúng là catalog_service_suite.mjs và m1_behavior_suite.mjs. Chạy nguyên command CI trên Node26 hiện tại exit0 nhưng chỉ **20 tests**, bỏ qua34 tests M1/catalog; runtime khác có thể fail hẳn. Vì vậy exit0 không đủ chứng minh full suites. Cần preflight files/count hoặc npm scripts đáng tin cậy, chạy exact CI commands và ghi runtime. Triggers vẫn main/master/develop/chore, thiếu **dev** mà người dùng đã chọn merge/push trực tiếp. Sửa cả push/PR cho dev; không tạo thêm nhánh.

## R2 — P1: Production seed/rollback policy chưa bảo toàn dữ liệu toàn đường triển khai

- Conditional DataInitializer + app prod seedfalse tốt ở lớp Spring, nhưng infrastructure/docker-compose.yml:117–118 vẫn mount database/seeds/01_seed_movies.sql và02_seed_50_users.sql vào postgres entrypoint. Với volume prod mới, PostgreSQL sẽ seed demo ngoài Spring guard. Compose Spring profileprod còn hardcoded password và chưa truyền APP_JWT_SECRET bắt buộc; không thể gọi production config hoàn tất. Tách dev opt-in seed override khỏi base/prod compose, env placeholders/template phù hợp và kiểm tra config render không secret. Không boot live để chứng minh.
- docs/runbooks/OPERATIONS_RUNBOOK.md:87–89 hướng dẫn DROP TABLE movie_ratings/favorite_items/watchlist_items dưới nhãn rollback an toàn. schema_v1.sql:92–96 cũng ghi down-migration drop bảng. Backup không biến DROP thành bảo toàn data; prompt M3 cấm rollback bằng drop. Thay bằng rollback code/config tương thích, giữ bảng/cột dữ liệu; nếu cần schema downgrade phải có kế hoạch mapping/restore kiểm chứng riêng.
- schema_v1.sql là bootstrap CREATE IF NOT EXISTS, không nâng cấp cột/constraints của DB đã có. Ghi đúng bootstrap vs upgrade; kiểm thử bootstrap+validate và một schema upgrade đại diện trên DB disposable phù hợp hoặc ghi rõ PostgreSQL validation còn thiếu. Hai policy tests hiện chỉ tắt property thủ công và kiểm tra user1/user50, không chứng minh compose/prod actual defaults/secrets/migration.

## R3 — P2: Modal/mobile/reduced-motion chưa đúng tuyên bố

Repro thực trên production browser bằng docs/reviews/repro/ROUND_10_browser_review.cjs; JSON tại docs/reviews/evidence/ROUND_10/review_diagnostics.json:

- Player mở nhưng `insideInitial=false`, bấm Tab `insideAfterTab=false`. MovieDetail effect cài key handler nhưng không focus vào modal; từ opener ở ngoài thì trap chỉ first/last không giữ được keyboard trong dialog. Cần initial focus và trap thực, kiểm tra native video controls/ShiftTab/Escape/restore. Không đổi media source/AI.
- CineBot đóng bằng Escape: restoredToOpener=false. Shell không lưu/restore opener. Trong prefers-reduced-motion=reduce, spy ghi scrollIntoView({behavior:'smooth'}). CSS không thay tham số JS explicit; thêm matchMedia policy.
- Auth close button thực30×30px; trailer mobile221.875×40px, không phải mọi touch target>=44. Quan trọng hơn: floating CineBot **đè lên nút Xem trailer** ở viewport375×667. Source harness chỉ so play/save nhau, trả true nếu không thấy button, không so với floating trigger. Đo controls thực và tránh overlay ở các vị trí scroll dưới fold, không chỉ screenshot hero.

Đây là các lỗi hành vi scope M3. Gom fixes/tests cho cả ba modal, mobile overlay, targets và JS reduced motion. Không tuyên bố WCAG toàn diện từ vài checks.

## R4 — P2: Performance và browser report chưa đủ evidence M3

Report chỉ có bảng bundle; scripts/run_browser_walkthrough.cjs không đo navigation/resource timings/LCP/CLS hoặc baseline trước/sau/network conditions như đã yêu cầu. Bundle nhỏ là một tín hiệu, không đủ gọi web mượt/tối ưu. Cần baseline source/build identity, resource transferred bytes/request count, navigation/render timing cold/warm với runs lặp cùng conditions; LCP/CLS khi thực sự thu được, không suy INP từ page load. Chốt budgets trước tối ưu và ghi raw measurements.

Browser account B được seed localStorage và reload; fixture login đọc body.username trong khi production gửi usernameOrEmail. Logout còn fallback xóa storage/reload nếu không tìm thấy nút. Điều này kiểm tra boot isolation một phần, không chứng minh click login/logout A→B như report. Dùng exact contract, UI loginB/logout thật; không fallback để biến missing selector thành pass. Modal trap/restore/targets/reduced-motion chưa được harness assert; 54tests không thêm regression các lifecycle này.

Harness vẫn copy assets if-absent, CDP promises chưa timeout đầy đủ, check không đủ debugger isolation, ready timeout có thể tự assume started. Gia cố cùng verification đang sửa: exact build/asset matching, runtime/network failure policy với fault404/500 dự kiến, sanitized evidence, output riêng và bounded cleanup. Không in cả HTML như diagnostic mặc định có session info.

## Yêu cầu vòng 11

Sửa chung R1–R4; giữ phần M3 đã đạt và mọi M1/M2 behavior. M3 vẫn chưa accepted. Prompt docs/prompts/ROUND_11_GEMINI_PROMPT.md. Người dùng muốn mượt tối đa và có thể bổ sung ổ: storage có thể so sánh RAM-only với bounded disk cache sau measurement; chưa mua/cài/mount hoặc mở scope Drive trong follow-up này. Phần storage preference mới ghi riêng, không thay frozen manifest.

Review wrapper thêm một rejected-login response chỉ ở fixture và targeted read-only browser diagnostics, không sửa production. Lượt wrapper đầu thử nhầm fixture field, lượt kế lỗi helper scope reviewer; đã sửa và chỉ dùng lượt hoàn chỉnh codex-round10-review-OZol36 làm evidence. All14 harness pass không phủ nhận diagnostics defects. Git checkpoint chưa accepted/deployed dù được lưu lên dev.
