# Gemini code / Codex review theo vòng 30 phút

**Cập nhật mới nhất 14/10/2026:** Người dùng đã yêu cầu tắt theo dõi tự động. Automation `theo-d-i-gemini-m2-m3` đã PAUSED. Chuyển về bàn giao/review thủ công: Gemini hoàn tất nhiệm vụ rồi kết thúc lượt; người dùng gửi báo cáo để Codex review. Không polling/chờ heartbeat để tiếp tục. Các hướng dẫn heartbeat/vòng chờ bên dưới là lịch sử. Prompt vòng 4 vẫn giữ làm scope nhiệm vụ tiếp theo.

Quyết định hiện hành của người dùng ngày 14/10/2026. Thay thế quy trình Gemini tự đi xuyên M2/M3 mà không chờ review. Scope sản phẩm vẫn giữ tại `docs/prompts/M2_M3_AUTONOMOUS_GEMINI_PROMPT.md`; file đó không còn là quyền vượt gate review.

## Hai bên và file giao tiếp

- Codex sở hữu `docs/prompts/GEMINI_CURRENT_TASK.md` và `GEMINI_REVIEW_CONTROL.json`.
- Gemini chỉ đọc hai files đó; sở hữu `docs/reports/M2_M3_STATUS.json`, worklog và artifacts của vòng triển khai.
- Mỗi vòng có roundId tăng dần, promptVersion và runId. Chỉ một bên sửa application source tại một thời điểm: Gemini; Codex review/read/check và viết tài liệu, không tự code app.

## Vòng triển khai

1. Gemini đọc control và prompt. Chỉ bắt đầu nếu command=work, targetRoundId lớn hơn vòng đã bàn giao, và promptVersion khớp.
2. Ghi working status với roundId/runId/promptVersion, giờ bắt đầu và mục tiêu. Snapshot riêng bảo toàn dirty tree.
3. Làm lát cắt được giao trong khoảng tối đa 30 phút. Đến mốc đó ngừng thêm tính năng; hoàn tất thao tác đang dang dở để có checkpoint review được, không kill compiler hoặc command tùy tiện. Ghi thời gian vượt mốc nếu có.
4. Chạy kiểm tra có ý nghĩa cho lát cắt, ghi failures chưa sửa thay vì bịa pass. Chốt diff/patch, report và source manifest SHA256 của own changed/new app/test/config files, include Git status và deletion entries nếu có.
5. Ghi artifacts trước, publish status `ready_for_review` cuối cùng với roundId/runId/promptVersion, milestone, manifest/report/patch paths và next-step đề xuất. Sau đó **ngừng sửa source**, không tự sang vòng sau.
6. Trong phiên agent còn hoạt động, chờ và đọc lại control mỗi khoảng 60 giây bằng công cụ có sẵn, không busy loop hoặc poll toàn repo. Không coi thời gian trôi qua là approval. Chỉ resume khi nhận command=work cho targetRoundId mới và version prompt khớp. command=stop thì dừng.

## Vòng review

Codex heartbeat mỗi 30 phút đọc status. Nếu working/validating/missing/không đổi thì giữ im lặng, không tests trên source đang viết. Khi ready_for_review, xác minh manifest, roundId và artifacts ổn định; nếu source drift thì không accepted, yêu cầu checkpoint mới.

Codex publish control command=reviewing cho round đang xét, chạy review/checks phù hợp và đối chiếu source hashes trước/sau. Viết review `docs/reviews/LOOP_ROUND_<roundId>_REVIEW.md`. Findings chỉ trong scope, có bằng chứng. Checkpoint chưa hoàn tất milestone có thể được chấp nhận để tiếp tục mà không gọi milestone accepted.

Sau review, Codex cập nhật GEMINI_CURRENT_TASK.md với mục tiêu vòng kế, findings cần sửa, files scope và gate rõ. Sau khi file prompt đã ghi xong, publish control command=work với targetRoundId tiếp theo và promptVersion mới. Không overwrite status/report Gemini; không tự gửi chat Antigravity. Khi M2 thật sự đạt gate mới giao phần M3; khi cả M2/M3 đạt thì command=stop, báo tổng kết và pause automation.

## Giới hạn thực thi

File protocol truyền chỉ dẫn trong workspace, không phải API khởi động agent. Nếu Antigravity kết thúc lượt, quota/app/permission/OS ngắt agent hoặc Gemini không còn chạy vòng chờ, thay đổi file không tự đánh thức nó. Người dùng cần resume chat bằng chỉ dẫn đọc control/current task; checkpoint vẫn cho phép tiếp tục đúng vòng. Không tạo process watchdog hoặc đổi OS/app permissions để né giới hạn.

Không AI/GPU/DB live, commit/push/reset/deploy; không dừng process người khác. Máy và apps cần chạy để hai bên thực thi. Nếu source đã thay đổi sau bàn giao, review phải dừng để tránh nghiệm thu nhầm revision.
