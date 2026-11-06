# Gemini — Triển khai liên tục M2 và M3, Codex nghiệm thu sau

**Override quy trình hiện hành:** Người dùng đã chọn code theo vòng khoảng 30 phút rồi chờ Codex review. Đọc `docs/GEMINI_CODEX_REVIEW_LOOP.md`, `docs/prompts/GEMINI_REVIEW_CONTROL.json` và `docs/prompts/GEMINI_CURRENT_TASK.md`. Nội dung phía dưới giữ làm scope M2/M3; không dùng các câu “tự tiếp tục/không chờ review” để vượt gate vòng.

Người dùng cho phép một lượt triển khai xuyên suốt M2 → M3, tự kiểm tra/sửa lỗi trong scope. Quy trình này thay thế yêu cầu dừng sau từng milestone trong tài liệu cũ, chỉ cho M2/M3. Codex lập kế hoạch và nghiệm thu; Gemini code, không tự ghi Codex accepted.

Workspace `D:\Class\movie-rcm-system`. M1-F06 đã accepted tại `docs/reviews/M1-F06_REVIEW.md`. Đọc AGENTS.md nếu có, engineering rules, PRODUCT_MILESTONES, USER_EXPERIENCE_BLUEPRINT, M1 contract và source thực tế. Giữ dirty tree, Qwen fine-tuned, theme xanh lá và toàn bộ auth/library đã nghiệm thu.

## M2 — Catalog backend và hành trình khám phá hoạt hình

### Contract và dữ liệu

Spring đã có MovieController/Service/Repository, MovieResponse và `/api/movies/{id}`; Home/Search/Detail vẫn import movies local, Profile ưu tiên local lookup. Cải tiến modules hiện hữu, không dựng lại backend.

Chốt contract `docs/contracts/M2_CATALOG_CONTRACT.md` trước triển khai: canonical movieId, nullable metadata, query/filter/sort/page, error/status và compatibility. Giữ API list legacy tương thích với consumers AI hiện có; có thể thêm browse endpoint paginated riêng. Không thay list envelope hoặc tự lọc Animation trên legacy API làm hỏng integration.

Catalog ID phải xuyên Home/Search/Detail/Profile/library. Không rename/reassign existing IDs, fuzzy match title rồi lưu sang phim khác. Đường dẫn cũ có record/mapping có căn cứ thì resolve; record không tồn tại trả 404 thật, không tạo phantom movie. Movies local có thể giữ làm test/dev fixture nhưng không fallback như live catalog khi API lỗi.

Backend hiện seed phim fiction mẫu, frontend có records animation thật; ghi gap rõ. Chuẩn bị animation fixture/import manifest từ dữ liệu hiện có, provenance chính xác là repository fixture nếu chưa có nguồn ngoài xác minh. Import additive/idempotent, có preview/dry-run và conflict policy, không overwrite user data hoặc tự apply DB live. Không bịa video/subtitle/HD/4K, popularity, personalization hay child-safety. Test/dev DB riêng có animation và non-animation fixtures; website production API rỗng phải empty honest, không fake seed.

### Search và paging

Query tên/mô tả và các genre được chọn kết hợp AND theo semantics rõ; Animation là constraint của hành trình website hoạt hình, giữ trên các links Adventure/Family/Fantasy. Genre match theo token chuẩn, không substring sai thể loại. Search + genres + year bounds hợp lệ kết hợp, không else-if chọn một điều kiện.

Sorting whitelist rating/year/title, nulls policy, tie-break bằng movieId; paging repository/DB ổn định, page/size bounds và invalid parameters trả 400 có cấu trúc. Không fetch toàn catalog rồi filter/page in-memory như endpoint production. Runtime filter chỉ thêm nếu có runtimeMinutes nullable chuẩn hóa có căn cứ; không cần để hoàn tất M2 nếu chưa có schema/data phù hợp, ghi rõ scope.

Frontend URL là nguồn query/filter/sort/page; reload/deep link/back/forward giữ state. Changing query/filter/sort resets page phù hợp. Debounce search input, cancel và generation guard chống response cũ overwrite mới; bounded timeout qua body. Input vẫn responsive khi request chờ. Empty result cho clear filters, network error cho retry, không hiện empty khi chưa nhận dữ liệu hợp lệ.

### Home/Detail/Profile

Home lấy Animation catalog backend cho hero/rails; empty Animation không fallback fiction. Rails labels dựa trên dữ liệu/sort thật, không gọi personalized/trending nếu chưa có căn cứ. Tải riêng có giới hạn, tránh duplicate catalog requests không cần thiết.

Detail canonical ID lookup, thật sự phân biệt 404 với API error. Unknown year/rating/runtime và missing poster/backdrop có fallback dễ đọc; không parse runtime sai hoặc fill score giả. Similar section nếu chỉ genre overlap thì ghi nhãn phù hợp và deterministic, không claim AI personalization.

Profile dùng shared catalog client/hydration theo canonical ID, không coi local fixture là nguồn production. 404/orphan vẫn giải thích/xóa được; network failure không gắn “đã bị gỡ”. Catalog down không phá thư viện đã xác nhận. Giữ M1 uncertain/retry/actor/session behavior từ Card, Hero, Detail và Profile.

Gate nội bộ M2: meaningful Spring DB tests filters/paging/404/validation/compatibility; actual frontend/component tests URL navigation và response ordering; Home animation-only/empty; Detail valid/404/unavailable; catalog IDs và library mutations đồng nhất. TypeScript/build + M1 suite; Spring DB test riêng. Làm walkthrough/browser khi có tool hỗ trợ; không gọi hook adapter là E2E.

## M3 — UX nhẹ và vận hành có bằng chứng

Chỉ bắt đầu sau internal M2 gate xanh. Khắc phục mobile/desktop overflow, keyboard/focus modal, labels/accessibility, contrast, reduced motion và thông báo loading/empty/error/retry trong các hành trình M1/M2. Không redesign theme đã accepted. Không autoplay audio/video.

Đo baseline bundle/network/ảnh và hiệu năng trên cấu hình ghi rõ; đặt budget cụ thể từ baseline trước khi tối ưu, báo trước/sau, chỉ tiêu chưa đạt phải ghi thật. Responsive images, lazy loading cho phần dưới fold, tối ưu hero image phù hợp, missing/error image placeholders và bounded requests. Không tuyên bố nhanh/tối ưu chỉ vì build pass; không thêm dependency/hạ tầng lớn để chạy một phép đo.

Tách dev/test/prod config và seed: demo accounts/interactions không tự tạo khi prod, test dùng fixture/DB riêng; production secrets/config cần env phù hợp, không in secrets/tokens. Không sửa serving AI policy. Chuẩn bị migration/runbook/rollback bảo toàn dữ liệu; không drop tables để rollback và không tự chạy migration vào DB live.

CI frontend/Spring dùng checks thực sự đã chạy được và branch/PR triggers phù hợp repo; không thêm GPU tests hoặc AI training. Test jobs dùng service/DB tách biệt, không production credentials. Không tự publish/deploy/commit/push để chứng minh CI; phân biệt local command evidence và remote CI chưa chạy.

Gate M3: guest khám phá → auth thật → lưu/thích/chấm điểm → reload → retry lỗi → logout → account B; mobile/keyboard; backend slow/down; animation empty; missing image; bundle/performance evidence và runbook. Nếu thiếu browser/perf tool, ghi needs evidence, hoàn tất phần độc lập, không bịa PASS hoặc chạy vào live environment.

## Vòng làm việc tự chủ

Mỗi lát cắt: đọc source → implement → behavior tests → chạy checks → tự review diff như reviewer → sửa regression → kiểm tra lại phần affected. Tự tìm lỗi cả success/error/race cases, không chỉ làm xanh tests đã viết. M2 internal pass thì chốt report/patch M2 rồi tiếp tục M3, không dừng xin người dùng paste prompt tiếp.

Khi command lỗi, đọc output và sửa cách gọi; tránh pwsh -Command lồng double quotes mất biến, dùng .ps1 -File khi cần. Snapshot phải được kiểm tra existence/hash, không gọi snapshot incomplete là baseline. Chỉ theo dõi process do mình tạo, không dừng services khác. Command completed/error phải được xử lý, không “standing by” khi task đã lỗi. Không tự thay permissions hay settings Antigravity/OS để né prompt.

Giữ checkpoint tại `docs/reports/M2_M3_WORKLOG.md`. Trạng thái `docs/reports/M2_M3_STATUS.json` gồm runId, phase, state (working/validating/ready_for_review/blocked), lastCompletedStep, nextStep, artifacts, limitations. Cập nhật status cuối cùng sau khi code/report/patch đã ổn định. READY_FOR_REVIEW là Gemini bàn giao, không Codex acceptance.

Nếu context bị rút gọn hoặc turn bị ngắt, đọc worklog/status và tiếp tục phần còn lại. Không bắt đầu lại hoặc đè snapshot cũ. Prompt không thể tự khởi động lại agent đã dừng bởi quota/app/permission; ghi checkpoint/blocker rõ nếu xảy ra. Nếu lỗi phụ thuộc lặp lại, chẩn đoán root cause, không rerun cùng command vô hạn. Chỉ dừng khi hoàn tất M2/M3 hoặc có blocker thật vượt tools/phạm vi; báo cụ thể phần đã làm và bước tiếp tục.

## Bàn giao

`docs/reports/M2_CATALOG_REPORT.md` + `M2_CATALOG.patch`, rồi `M3_UX_OPERATIONS_REPORT.md` + `M3_UX_OPERATIONS.patch`. Snapshot riêng từng milestone, patches chỉ gồm own changes; numstat/reverse checks pass. Giữ artifact M2 để kiểm tra trên đúng snapshot: sau M3 có overlap, nói rõ reverse check M2 xác minh trên stage nào, không claim current-tree pass nếu đã drift.

Tổng kết `docs/reports/M2_M3_FINAL_REPORT.md`: journey acceptance matrix, source/runtime identity, actual commands/exit code, test/mock/browser boundaries, perf before/after, migration/runbook và unresolved findings. Không gộp skipped với pass hoặc mock evidence với production proof.

Không sửa AI/FastAPI/Qwen/recommender/chat semantics, thêm hosting/playback platform, đổi framework, deploy/public services, DB live, commit/push/reset. Không mở milestone khác ngoài M2/M3. Khi cả hai hoàn tất: READY FOR CODEX REVIEW — M2 + M3. Codex review độc lập sau bàn giao.
