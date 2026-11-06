# Vòng 11 — Gom sửa M3 R1–R4, chốt UX và số đo hiệu năng thật

promptVersion: 11
targetRoundId: 11
milestone: M3
reviewMode: manual
reviewedRunId: run-round10-20261014-1015

Bạn là Gemini tại D:\Class\movie-rcm-system. Đọc docs/reviews/LOOP_ROUND_10_REVIEW.md và M3 prompt gốc. M3 chưa accepted; sửa chung các findings rồi bàn giao một checkpoint. Không làm lại M1/M2, không Drive/AI/GPU/DB live. Người dùng chọn nhánh dev, không tạo nhánh mới; Codex quản lý commit/push/merge, bạn không sửa Git index hoặc đổi nhánh.

## R1 — CI đáng tin cậy trên dev

Sửa tên suites thành catalog_service_suite.mjs/m1_behavior_suite.mjs và hai suites hiện có. Guard missing files/commands, không để Node version silently bỏ tests. Thêm dev push/PR triggers. Dùng scripts package.json nếu giúp CI/local chung entrypoint. Chạy exact commands ở runtime có thật; phân biệt Node local với CI Node20, không tuyên bố Actions green trước khi remote chạy. Spring JDK17 theo pom; test DB riêng. Không thêm deploy/GPU jobs.

## R2 — Production/default seed và rollback không mất dữ liệu

Sửa base/prod Compose: không postgres entrypoint demo seed; dev seed opt-in qua override/profile rõ. Env secrets đúng app, không password hardcoded hoặc thiếu APP_JWT_SECRET; sample env không secret được whitelist đúng .gitignore nếu cần. Tách validation render khỏi startup: không boot services vào DB live. Test config/defaults thực và opt-in seed behavior, prod missing env fail rõ trên fixture/test process. Không dùng property tắt thủ công rồi gọi đã chứng minh prod policy.

Runbook/schema bỏ DROP TABLE khỏi rollback bảo toàn data. Phân biệt bootstrap schema_v1 với upgrade DB hiện hữu; có forward additive migration/compatibility checks và rollback code/config giữ dữ liệu. Kiểm thử bootstrap + validate/upgrade fixture phù hợp, không gọi H2 pass là PostgreSQL production validation. Nếu không có PostgreSQL disposable, ghi đúng evidence gap và chuẩn bị test tự chạy trên DB test được cấu hình tường minh; không dùng credentials/liveDB thật.

## R3 — Sửa UX được tái hiện, không chỉ thêm aria

Player: initial focus vào dialog khi mở, keyboard không lọt nền, Tab/ShiftTab đúng với video controls, Escape/close/restore opener/scroll lock clean. CineBot: restore opener, reduced-motion đổi behavior JS scroll, không gọi AI khi test. AuthModal: giữ open/submit/fail/close lifecycle ổn định, tránh effect dependency gây recapture opener; case reviewer đã thử restore đúng, không rewrite auth vì suy đoán. Có tests lifecycle cho3dialogs, includes close/unmount/pending/failure. Có thể dùng helper dùng chung nếu hợp lý, không dependency lớn.

Mobile375×667 và dưới fold: fix floating trigger đè trailer/controls/toasts, đo boundingboxes chứ không chỉ play vs save; missing selector phải fail. Các controls chính/icon buttons đạt target policy>=44×44 đã đề ra hoặc ghi rõ ngoại lệ có căn cứ, không claim blanket. Giữ xanh lá/contrast. Actual browser assertions cho focus trap/restore, reduce-motion JS, overlap/touch bounds và broken images404. Không sửa AI/chat semantics, session/library state machine hoặc media playback capabilities ngoài UI shell.

## R4 — Performance và browser evidence đúng việc đã làm

Trước optimize thêm, lưu baseline của checkpoint hiện tại: source hashes/build id, Next15.1.2 thực, Node/Chrome, viewport, cache/network/CPU conditions. Đo resource bytes/request count và navigation/render/load timing cho Home/Search/Detail/Profile, cold/warm, tối thiểu3runs mỗi case nếu thời gian cho phép; báo median/range hoặc p95 khi sample đủ, không giả số. LCP/CLS thu bằng observer đúng, INP chưa đo thì ghi unavailable. Chốt budgets rồi sửa điểm nghẽn có measurement; đo after cùng fixture/conditions. Không chỉ xuất bảng First Load JS hoặc tăng cache để che API lỗi. Không tự mua phần cứng hoặc hứa mượt tuyệt đối.

Harness: fixture login nhận usernameOrEmail, test userB qua UI form; logout qua nút thật, không storage-clear fallback. Assert store ownership/methods và UI sau reload. CDP calls timeout hữu hạn; preflight debugger; assets đúng build (không copy-if-absent stale); readiness probe thật; sanitized request/status + expected fault policy. Output ROUND_11 riêng, không overwrite frozen Round10. Fail phải có error evidence, không hardcoded pass. Không run reviewer wrapper chỉ để lấy exit0: diagnostics của nó ghi lỗi hiện tại, cần regression assertions đúng trong suite/harness bạn sở hữu.

## Bàn giao

Ưu tiên sửa code R1/R2/R3 cùng meaningful tests, đồng thời đo R4; nếu chưa đủ evidence thì chốt phần còn lại rõ, không claim M3 done. Khoảng30 phút là checkpoint guide; hoàn tất command/test đang chạy, không kill rồi bịa pass. Không polling/vòng tự động. Bốn frontend suites+new lifecycle/perf checks, tsc/build, Spring DB test riêng và preview regression khi ảnh hưởng. So source/artifact hashes stable trước ready.

ROUND_11_REPORT.md/patch/manifest SHA256 own changed/new/deleted files + screenshots/measurements, git status, commands/exitcodes, prior vs current evidence, mock/browser/backend boundaries, limitations. Snapshot riêng không đè baseline cũ. Status round11/version11/runId mới/milestoneM3 publish cuối sau freeze. Không sửa docs/reviews/control/current prompt của Codex; không appAI/FastAPI/Qwen/GPU/model/liveDB/deploy; không commit/push/reset hoặc đổi OS settings/process người khác. Kết thúc để người dùng gửi Codex review.
