# Round 13 — Close M3's two remaining verification defects

promptVersion: 13
targetRoundId: 13
milestone: M3
reviewMode: manual
reviewedRunId: run-round12-20261014-1245

Bạn là kỹ sư triển khai Gemini tại D:\Class\movie-rcm-system, nhánh dev. Đọc docs/reviews/LOOP_ROUND_12_REVIEW.md và control. Vòng này chỉ sửa D1 và D2 dưới đây, khoảng30 phút rồi bàn giao checkpoint. M3 chưa accepted; không làm lại phần schema/UI/benchmark observer đã đạt, không thêm storage/Drive/AI.

## D1 — Cô lập prod controls và làm xanh đúng CI

Bare mvnw.cmd test đạt25/25 nhưng đúng lệnh CI mvnw.cmd test -Dspring.profiles.active=test thất bại:1failure/3errors. Các nested SpringApplicationBuilder context đang chạy prod,test; bare lại prod,dev. properties() priority thấp không ép được profile prod độc lập.

Sửa SeedAndConfigPolicyTest để production controls nạp YAML thật với đúng active profile prod duy nhất, DB H2 PG-mode riêng từng test, fixture secrets riêng; giữ bootstrap SQL -> Hibernate validate và additive migration bảo toàn rows. Assert exact active profiles, seed false, sql.init never, ddl-auto validate trong positive controls. Negative omit riêng JWT/password phải fail đúng key, không bị env bên ngoài hoặc test profile che khuất. Không mock hết production config, skip test, bỏ preflight hoặc sửa default production sang create/update/seed để lấy pass.

Chạy cả hai lệnh tại backend/springboot và ghi logs/exitcodes riêng:

    .\mvnw.cmd test
    .\mvnw.cmd test -Dspring.profiles.active=test

Nếu thật sự cần sửa workflow, giải thích và chạy exact command cuối cùng của workflow; không chỉ thay workflow để né một command còn hỏng. Giữ JDK17 compatibility. Không dùng global datasource URL cho toàn suite khiến nested DB fixture bị override. Không kết nối DB live hoặc lấy secrets thật.

Scope: backend/springboot/src/test/java/com/dippie/moviercm/SeedAndConfigPolicyTest.java; .github/workflows/ci.yml chỉ nếu cần có lý do. ProductionConfigPreflight/application.yml chỉ sửa nếu chứng minh lỗi thật cần thiết; không nới yêu cầu production. Không đổi schema/bootstrap/migration đã đạt.

## D2 — Budget đo từ build hiện tại, không constants

Thay ROUTE_EXACT_JS_BYTES hardcoded trong scripts/run_browser_walkthrough.cjs bằng đo từ manifest và file build hiện tại. Deduplicate chunks của layout+route, đo raw và gzip với phương pháp rõ, ghi build ID + file SHA256 và included/excluded assets. Budget143360bytes =140KiB; underBudget phải tính từ bytes, vượt thì exit nonzero. Missing manifest/route/file phải báo lỗi chứ không mặc định pass. Không gọi JS-only bytes là toàn bộ network transfer.

Có thể tách helper nhỏ vào scripts/ để dùng chung và self-test; tham khảo reviewer docs/reviews/repro/ROUND_12_build_bytes.cjs nhưng không sửa reviewer helper. Negative self-test trên temporary fixture hoặc tiny budget phải chứng minh phát hiện vượt budget/missing file và error contract đúng. Không sửa app/chunk thật để tạo lỗi. Đưa guard vào kiểm tra build/CI nếu phù hợp để giới hạn được thực thi thay vì chỉ report. Giữ observer LCP/CLS, cold/warm,14UI checks đã đạt.

Scope: scripts/run_browser_walkthrough.cjs, helper/self-test nhỏ mới trong scripts/, CI chỉ để nối guard sau build nếu cần; docs liên quan. Không thêm dependency lớn. Frontend application source không cần đổi cho hai findings này.

## Gate và bàn giao

- Hai backend commands trên đều exit0 và prod controls assert profile prod-only, specific missing secrets, valid bootstrap/migration.
- Build hiện tại + dynamic budget guard pass; tiny-budget/missing-input negative controls được phát hiện đúng. Report đơn vị KiB và exact bytes, không copy bảng số cũ.
- npm test57/57, tsc và npm run build; browser harness nếu sửa phải chạy để xác minh integration và xuất ROUND_13 evidence riêng. Nếu không thay runtime modal/UI, không mở thêm các findings/features ngoài D1/D2. Phân biệt component/source checks với browser fixture và production claims.
- Sửa mô tả FK trong báo cáo nếu nhắc lại: SQL hiện có FK user, không có FK movie; không thêm cascade chỉ để khớp prose.
- Tạo ROUND_13_REPORT.md/patch/manifest SHA256 own changed/new/deleted files, git status và logs/negative evidence; numstat + reverse check. Snapshot baseline dirty tree trước sửa để patch chỉ gồm vòng13. Không ghi đè artifacts cũ hoặc reviewer docs.
- Freeze rồi publish M2_M3_STATUS.json cuối: round13/version13/runId mới/milestoneM3/ready_for_review. Dừng lượt, không polling, không tự gọi accepted hay chuyển milestone.

Không sửa Codex control/current prompt, không AI/Qwen/FastAPI/GPU/model, DB live, mount/cài Drive, deploy/OS settings hoặc dừng process người khác. Không tạo nhánh, commit/push/reset; Codex xử lý Git trực tiếp dev theo quyền người dùng. Giữ toàn bộ thay đổi ngoài scope.
