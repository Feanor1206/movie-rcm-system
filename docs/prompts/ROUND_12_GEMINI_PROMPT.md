# Vòng 12 — Khép M3: production bootstrap và phép đo hiệu năng đúng

promptVersion: 12
targetRoundId: 12
milestone: M3
reviewMode: manual
reviewedRunId: run-round11-20261014-1140

Bạn là Gemini tại D:\Class\movie-rcm-system, nhánh dev. Đọc docs/reviews/LOOP_ROUND_11_REVIEW.md. R1 CI và R3 UX/modal đã closed ở checkpoint; giữ nguyên, không làm lại. M3 còn đúng hai nhóm C1/C2. Không tự sang Drive/AI, không tạo nhánh hay sửa Git index/commit/push/reset.

## C1 — Bootstrap thật phải khớp schema entities

Base Compose mount database/schema/01_init.sql thiếu favorite_items, còn app prod ddl-auto validate. Chọn canonical bootstrap source rõ, dùng đúng file cho new-volume initialization và runbook. Đồng bộ các bản DDL cần thiết hoặc loại duplication bằng reference/build copy an toàn; không sửa SQL không được Compose dùng rồi gọi đã fix. Database cũ cần additive Favorite migration riêng, không DROP/overwrite data hoặc dùng init script như upgrade volume hiện hữu.

Test executable: chạy chính bootstrap SQL rồi Hibernate validate trên DB test, chứng minh đủ entity tables/columns; giữ create-drop tests cũ nhưng không dùng chúng thay validation DDL. Nếu PostgreSQL disposable sẵn dùng instance riêng; nếu không, H2 PG-mode test + PostgreSQL opt-in test/runbook rõ, không bịa Postgres pass. Không cài/start DB live.

Config negative secret test phải load actual prod YAML và có positive-control fixture DB+valid secrets start/validate được, sau đó omit riêng từng secret và assert lỗi đúng key; không assert placeholder chung trong context chưa load config. Compose configurable POSTGRES_USER/POSTGRES_DB phải đồng bộ healthcheck và app connection variables. Mandatory env dùng config preflight fail rõ; env example không secret. Dev override vẫn opt-in, không seed production. Run render validation nếu docker có sẵn, nếu không ghi limitations. Giữ FastAPI/Qwen service/config nguyên vẹn.

## C2 — Sửa benchmark trước khi kết luận tối ưu

- Cài PerformanceObserver cho largest-contentful-paint/layout-shift trước navigation/render (CDP new-document script hoặc cách tương đương). Không gán FCP vào LCP. Unsupported/no sample => null/unavailable. Có negative/control test phát hiện missing observer hoặc intentionally delayed content/layout shift, để metric không thành0 giả. CLS theo session-window chuẩn; nếu chỉ raw shifts thì ghi raw, không gắn nhãn CLS chuẩn.
- Cold thật: clear/disable HTTP cache hoặc fresh context trước mỗi cold run, xác minh qua CDP cache flags/networkbytes. Warm: cache enabled cùng route đã warm. Tách raw arrays/summaries cold và warm, tối thiểu3runs mỗi loại/route nếu thời gian cho phép; không gom1cold+2warm thành một median. Tách local/backend cache conditions nếu không reset được, không gọi tất cả là cold.
- Đối chiếu transferred bytes bằng CDP Network loadingFinished/encodedDataLength có request accounting, ghi cache/304/opaque timing; ResourceTiming encodedBodySize/decodedBodySize riêng. API cross-origin timing không được im lặng tính0 rồi gọi full network footprint. Không đếm trùng redirects/preload/body; ghi methodology.
- Chờ điều kiện app-ready: đúng route data/error state, requests liên quan complete, font/media conditions và bounded observation window; không chỉ readyState+sleep. Ghi source/buildID/Node/Chrome/viewport/network/CPU/cache policy, budgets và route JS exact bytes thay display làm tròn sát140kB. Local loopback không đại diện mạng người xem; có thể thêm một profile throttle có mô tả nếu tool hỗ trợ nhưng không trộn conditions.
- Trước/after phải cùng đo và có change thực; nếu vòng này chỉ sửa phép đo thì gọi là corrected baseline, không bịa speedup. Chỉ optimize thêm khi measurement chỉ ra bottleneck cụ thể, tránh dependency lớn. Người dùng sẵn sàng thêm ổ nếu video benchmark sau này cần, chưa mua/cài/mount trong M3.

Giữ14browser journey checks đã đạt và structural tests nhưng report phân loại đúng. Không sửa reviewer scripts để lấy pass. Output ROUND_12 riêng, không ghi đè Round11. Không thêm full-stack/AI/storage features.

## Bàn giao

Chạy npm test + meaningful new bootstrap/metric tests, tsc/build khi affected, Spring DB test riêng, browser+corrected performance harness. Commands exitcodes thật, prior evidence riêng. Chốt checkpoint khoảng30phút và hoàn tất command đang chạy; còn gap phải ghi rõ, không tự gọi M3 accepted. ROUND_12_REPORT.md/patch/manifest SHA256 own changed/new/deleted files, raw metrics/screenshots/git status, numstat/reverse check. Freeze source rồi publish status round12/version12/runId mới/milestoneM3/ready_for_review cuối; kết thúc lượt, không polling. Không sửa review/control/current prompt Codex, không liveDB/AI/GPU/model/deploy/OS settings, không kill process người khác.
