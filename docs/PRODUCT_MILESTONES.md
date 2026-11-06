> Cập nhật 14/10/2026: Codex đã ACCEPTED M2 tại docs/reviews/LOOP_ROUND_9_REVIEW.md. M3 bắt đầu bằng docs/prompts/M3_UX_OPERATIONS_GEMINI_PROMPT.md (round10/version10). Manual handoff, automation tắt; nội dung autonomous/internal-gate cũ bên dưới không thay thế review gate hiện hành.

# Milestones sản phẩm — ưu tiên web và nghiệp vụ, AI để sau

Quyết định người dùng ngày 13/10/2026: giao Gemini theo milestone lớn, không dừng bàn giao ở từng ticket nhỏ. Codex lập prompt và nghiệm thu; Gemini triển khai. Tài liệu này thay thế thứ tự giao việc cũ trong START_HERE và ENGINEERING_EXECUTION_PLAN.

SERVE-01-F02 và UX-01A/F01/F02 đã accepted; giữ nguyên Qwen fine-tuned và theme xanh lá. Không sửa FastAPI, inference, training, recommender, ranking hoặc session chat trong các milestone dưới đây. Các tính năng AI hiện có được giữ tương thích; không phải điều kiện để web cốt lõi dùng được.

**Trạng thái hiện hành:** M1-F06 đã **ACCEPTED**, đóng M1 trong phạm vi review tại `docs/reviews/M1-F06_REVIEW.md`. Theo yêu cầu chạy xuyên suốt mới, Gemini triển khai M2 → internal gate → M3, Codex nghiệm thu sau cả lượt. Prompt hiện hành `docs/prompts/M2_M3_AUTONOMOUS_GEMINI_PROMPT.md`; không làm AI và không gọi internal gate là Codex acceptance. Quy tắc dừng giữa M2/M3 phía dưới được cập nhật này thay thế.

## M1 — Tài khoản và thư viện cá nhân đáng tin cậy

Gộp AUTH-01 + LIB-01 + LIB-02 thành một kết quả sản phẩm. Spring auth/watchlist/rating đã có; nâng cấp luồng hiện tại. Favorite mới có local state, cần persistence theo tài khoản nếu chưa có backend thực tế.

Kết quả: guest có thể lưu trên thiết bị với nhãn rõ; người đăng nhập lưu/xóa watchlist, thích/bỏ thích và chấm điểm trên backend; tải lại vẫn đúng; A/logout/B không thấy dữ liệu nhau. Không tạo phiên giả, không báo saved khi request thất bại, không nhét phim mẫu vào thư viện người mới. Không tự merge guest vào account.

Phạm vi gồm frontend auth/library/consumers và phần Spring identity/library cần thiết; chỉ kết nối catalog theo ID hiện có để thư viện hiển thị đúng. Catalog search redesign, ETL và hạ tầng mới nằm ngoài M1.

Gate: auth success/error/unavailable, session/race tests; ownership backend; read/mutation/reload library; guest/account separation; duplicate click và retry; frontend checks, Spring tests với DB test, walkthrough browser. Prompt thực thi: `docs/prompts/M1_ACCOUNT_LIBRARY_GEMINI_PROMPT.md`.

## M2 — Kho hoạt hình và tìm kiếm dùng dữ liệu nghiệp vụ

Nối Home/Search/Detail/Profile vào catalog Spring, thay nguồn local trong luồng production. Giữ ID và đường dẫn cũ tương thích bằng lookup/mapping có căn cứ, không đoán ID theo tiêu đề. Catalog animation thực, filters kết hợp, search có debounce/cancel, sort và paging ổn định, URL giữ query và back navigation. Filter theo năm/thời lượng chỉ triển khai khi có giá trị chuẩn hóa được; dữ liệu không biết phải được xử lý rõ.

Giữ API list cũ tương thích hoặc thêm endpoint paging riêng; không đổi envelope làm hỏng consumer AI đang có. Metadata thiếu, ảnh lỗi, 404, empty và backend unavailable có UI hữu ích. Không fallback từ API lỗi sang catalog giả rồi gọi là dữ liệu live. Giữ watchlist/rating hoạt động từ tất cả entry points của M1.

Gate: search + genre + sort + paging thực trên repository; Home chỉ dùng animation; deep link + reload + back đúng; list/detail/library cùng ID; loading/empty/error/404; catalog lỗi không làm mất library; mobile/keyboard. Seed/import fixture phải có xuất xứ, không bịa media hoặc nhãn cá nhân hóa. Prompt chi tiết chốt sau nghiệm thu M1 dựa trên diff/schema cuối cùng.

## M3 — Web nhẹ, dễ dùng và sẵn sàng vận hành

Hoàn thiện các hành trình M1/M2 ở mobile và keyboard, focus modal, thông báo lỗi, reduced motion, ảnh responsive/lazy loading, tránh fetch trùng, xử lý timeout và lỗi ảnh. Không autoplay audio/video. Đo bundle/network và hiệu năng trên một cấu hình ghi rõ; đặt budget từ baseline và kiểm tra lại sau tối ưu, không gọi tối ưu chỉ dựa vào build pass.

Tách dev/test/prod config và seed policy; demo accounts/interactions không tự sinh trong prod. CI frontend/Spring theo checks thực sự dùng được, smoke test với fixture/DB riêng, hướng dẫn chạy và rollback. Không tự deploy, sửa dữ liệu live hoặc public services. Giữ cấu hình serving AI đã nghiệm thu.

Gate: walkthrough guest → khám phá → đăng nhập → lưu/đánh giá → reload → logout; account switch; slow/down backend; viewport mobile/desktop; checks CI/local; bằng chứng đo trước/sau và runbook. Prompt chi tiết chốt sau M2.

## Bổ sung: Google Drive storage và playback trên Windows

Theo yêu cầu ngày 14/10/2026, bổ sung thiết kế dùng Google Drive mount trên Windows để lưu/phát video hoạt hình tại `docs/DRIVE_MEDIA_STORAGE_DESIGN.md`. Đang ở trạng thái design/backlog, không mở rộng vòng M3 đang triển khai. Sau nghiệm thu M3, giao prompt riêng cho Windows mount spike → asset mapping/HTTP Range → player thật và capacity tests; chốt thứ tự so với milestone AI khi giao việc. Chưa cài đặt, OAuth, mount, import DB live hoặc triển khai storage trong lượt thiết kế.

## Sau ba milestone

Codex kiểm tra lại nền sản phẩm rồi mới giao milestone AI/FastAPI riêng. Qwen đã fine-tune; không giao huấn luyện lại như prerequisite. Chất lượng AI sẽ được nghiệm thu bằng dữ liệu và đánh giá thực, không bằng UI labels hoặc predictions hard-code.

## Quy trình giao và nghiệm thu

Gemini làm tuần tự các bước trong milestone, tự chạy checks và sửa regression trong scope; không chờ Codex duyệt từng bước nhỏ. Có thể lưu patch theo từng bước để truy vết nhưng bàn giao một report tổng và patch milestone. Không tự chuyển milestone tiếp theo khi chưa được Codex nghiệm thu.

Codex review theo hành trình người dùng và contract/ownership, không chỉ số test pass. Nếu có findings thì giao một follow-up gom findings của milestone. Giữ mọi thay đổi đang có, không commit/push/reset. Nếu AUTH-01 đã bắt đầu, giữ phần đã làm và tích hợp vào M1; không làm lại hoặc ghi đè.
