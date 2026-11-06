# M3 — Web nhẹ, dễ dùng và vận hành rõ ràng

promptVersion: 10
targetRoundId: 10
milestone: M3
reviewMode: manual
reviewedRunId: run-round9-20261014-0950

Bạn là Gemini kỹ sư triển khai tại D:\Class\movie-rcm-system. Codex đã nghiệm thu M2 tại docs/reviews/LOOP_ROUND_9_REVIEW.md. Đọc review, docs/PRODUCT_MILESTONES.md, USER_EXPERIENCE_BLUEPRINT và contracts M1/M2. Đây là milestone lớn M3; hoàn thành các nhóm việc liên quan trong cùng phạm vi, không chia thành hàng loạt ticket một nút. Không làm lại M1/M2, không AI. Quy trình manual hiện hành ưu tiên hướng dẫn autonomous/heartbeat cũ.

## Mục tiêu sản phẩm

Người xem dùng thoải mái trên điện thoại, điều khiển được bằng bàn phím, không bị modal/toast/widget che hành động; metadata/ảnh lỗi có trạng thái hữu ích; web có số đo độ nhẹ và cấu hình dev/test/prod rõ. Giữ tông xanh lá hiện tại, contrast đã đạt, canonical IDs và toàn bộ state machine library/uncertain/actor/session.

## 1. Mobile và khả năng tiếp cận

Audit Home/Search/Detail/Profile, AuthModal, player overlay và shell CineBot ở 375x667 và desktop; kiểm tra thêm viewport hẹp nếu cần. Sửa overflow thực tế, controls chồng nhau, label/focus thiếu; đo bounds/touch targets quan trọng, không kết luận chỉ dựa ảnh màn hình đầu trang. Kiểm tra cả dưới fold: rating stars, xóa điểm, error/retry và orphan controls. Chat floating trigger không che watchlist/favorite/rating hoặc toast trên mobile; không đổi AI/chat semantics.

AuthModal/player/dialog: focus vào phần tử hợp lý khi mở, giữ Tab/Shift+Tab trong dialog, Escape/close có hành vi rõ và restore focus về opener; khóa nền/scroll đúng, cleanup trên unmount, không dùng conditional hooks sai. Pending submit có feedback và không double-submit, không thay password/session logic đã accepted. Add focus behavior cho CineBot chỉ phần UI shell nếu cần; test chat bằng mock, không gọi AI backend. Labels/aria cho icon buttons và feedback accessible; reduced-motion tôn trọng cả CSS lẫn scroll smooth/animations JS. Giữ không tự phát media khi chưa có thao tác chủ động; không thêm player/platform mới.

## 2. Ảnh lỗi và nhẹ mạng có bằng chứng

Media null đã có fallback, bổ sung lỗi tải thực tế cho URL tồn tại nhưng404/broken ở Card/Hero/Detail và consumer liên quan. Placeholder đúng phim, không lấy ảnh tác phẩm khác hoặc local fixture che lỗi. Kiểm tra Next Image host policy thực tế; không mở allowlist tùy tiện cho mọi remote host. Responsive sizes, ưu tiên đúng hero/LCP, lazy dưới fold; không gán priority hàng loạt. Profile metadata tránh burst requests trùng/unbounded nếu measurement chỉ ra, giữ TTL/cancel/actor isolation.

Trước khi tối ưu ghi baseline: git/source/build identity, Node/Chrome, viewport, cache cold/warm, local fixture/catalog size, network/CPU conditions. Đo route JS/build size + resource bytes/request count và navigation/render timings khả dụng qua Chrome performance APIs/CDP; CLS/LCP chỉ báo nếu công cụ thực sự thu được, INP không tự suy từ load timing. Chốt budget phù hợp baseline trước thay đổi rồi đo cùng điều kiện sau. Không tuyên bố nhanh hơn từ build pass hoặc một lần đo nhiễu, không cài dependency/hạ tầng lớn chỉ để tạo điểm số đẹp. Ghi cả chỉ tiêu chưa đạt.

## 3. Dev/test/prod và seed policy

Đọc cấu hình thật trước sửa. DataInitializer hiện @Component gọi seedMovies/seed50Users cho mọi profile; application.yml active dev, sql.init always, JWT secret hardcoded, prod datasource password fallback và ddl-auto update. Tách policy để prod không tạo demo accounts/interactions/catalog; test dùng DB/fixture riêng, dev seed opt-in rõ và tương thích local workflow.

Prod secrets/datasource/CORS lấy env phù hợp, fail rõ nếu thiếu cấu hình cần thiết, không log secret/token; dev/test có config riêng. Prod không tự update/drop schema hoặc chạy SQL demo: chuẩn bị SQL/migration/runbook versioned review được, nêu cách nâng DB hiện hữu và rollback bảo toàn data; không apply DB live. Không bắt buộc thêm Flyway/framework nếu SQL review được đủ phạm vi. Không thay chính sách FastAPI/Qwen serving. Test prod-policy bằng environment/config isolated hoặc in-memory DB, tuyệt đối không boot với DB prod live để chứng minh.

## 4. CI và runbook có thể chạy

.github/workflows/ci.yml hiện chỉ checkout/install/tsc, Node20, triggers main/master/develop; cập nhật theo branch thực tế và commands đã xác minh. Frontend behavioral suites + tsc + build, Spring tests với profile/DB riêng và JDK phù hợp pom. Nếu browser job sẵn môi trường phù hợp thì dùng portable harness; nếu Windows Chrome path hiện tại chưa portable thì tách browser/manual job rõ, không tạo CI xanh giả bằng skip tests âm thầm. Không GPU/model/download weights, DB live hoặc deploy job.

Gia cố harness hiện có thay vì xây lại: output directory/config ports được chọn, preflight cả Chrome debugger, stdout/stderr child được xử lý, CDP timeout hữu hạn, bắt runtime/network failure đúng chính sách (fault requests kỳ vọng được phân biệt), asset identity/hash và readiness thật. Assets phải đồng bộ với build mới, không chỉ copy-if-absent rồi dùng stale chunks. Lưu sanitized network/assertion evidence; fail có diagnostic chứ không obs success cố định. Không thay thư mục screenshots của checkpoint accepted; dùng M3/round10 riêng. Cleanup chỉ process/temp của lượt này, xác minh absolute target trước recursive delete/move.

Runbook: prerequisites, env examples không secret, dev/test/prod/standalone static/public, animation fixture preview chưa import live, startup/stop owned processes, health/smoke, rollback code/config/schema bảo toàn dữ liệu. CI local command pass khác remote Actions chưa chạy; Codex sẽ commit/push sau review, Gemini không tự commit/push.

## Gate nghiệm thu

Giữ 54 tests trước; thêm tests có ý nghĩa cho focus/modal lifecycle, broken images, config/seed policy và các lỗi tìm thấy. Browser: guest khám phá → mở form đăng nhập → fixture account A → save/favorite/rate → reload → retry faults → logout → account B; A data không lộ B. Desktop/mobile + keyboard; empty/slow/down API; image404. Fixture auth phải đủ cho hành trình đó; không cần gọi Spring/AI live. Spring integration DB riêng nếu thay backend/config. Đo before/after theo cùng điều kiện; screenshots + assertion/network logs, không gọi component adapter là browser E2E. Không tự nâng đây thành production readiness/deploy approval.

## Bàn giao vòng 10

Làm autonomously trong scope milestone, ưu tiên safety của prod seed/config và UX lỗi thực tế trước polish. Khoảng30 phút chốt checkpoint nhất quán; nếu toàn M3 chưa xong thì report completed/remaining/risks rõ, không gọi M3 done. Không polling/chờ heartbeat; freeze rồi kết thúc để người dùng chuyển Codex review. Scope nhiều nên có thể checkpoint một lần với phần còn lại rõ, không tự mở vòng khác.

Snapshot riêng; docs/reports/ROUND_10_REPORT.md, ROUND_10.patch, ROUND_10_MANIFEST.json SHA256 own changed/new/deleted files + git status; numstat/reverse check. M3 acceptance matrix, measured perf baseline/budgets/after, runbook path, commands/exit code, mock/browser/real backend boundaries và limitations. Publish status ready_for_review milestone=M3 roundId=10 promptVersion=10 runId mới/artifact paths cuối sau freeze. Không sửa review/current prompt/control Codex, không AI/FastAPI/Qwen/GPU/model/DB live/deploy hoặc Git commit/push/reset. Không đổi OS/app settings, không stop process người khác.
