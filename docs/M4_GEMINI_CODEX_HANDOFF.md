# M4 — Theo dõi và giao prompt tiếp

Người dùng yêu cầu bật theo dõi lại ngày14/10/2026. Codex automation theo-d-i-gemini-m2-m3 được cập nhật thành Review Gemini M4 và giao prompt tiếp, mỗi10phút. Không mở lại M2/M3 đã accepted.

Codex sở hữu docs/prompts/M4_REVIEW_CONTROL.json và GEMINI_CURRENT_TASK.md. Gemini sở hữu reports/status/artifacts M4. Original M4 ready_for_review đã được review tại ecf8839, không phải handoff mới. Status cũ hoặc file build timestamp không đủ kết luận hoàn tất.

Gemini tiếp tục M4-F01 đang làm. Khi xong: hoàn tất report/patch/manifest đúng hashes, publish ready_for_review với taskId/runId/promptVersion hoặc checkpoint identity rõ, xác nhận freeze; ngừng mọi source writes. Nếu agent còn hoạt động, đọc M4_REVIEW_CONTROL mỗi khoảng60giây bằng công cụ hiện có, không busy loop hoặc chạy watchdog. Không tự sửa control hay tiếp tục source khi await_checkpoint/reviewing. Khi command=work với taskId/version MỚI, đọc GEMINI_CURRENT_TASK.md và đúng prompt mới rồi thực hiện. command=stop kết thúc.

Codex chỉ review khi checkpoint mới thực sự frozen, source/artifact hashes ổn định; checks dùng test DB/fixtures/temp riêng, không application edits/AI/live DB/Drive installation. Review có evidence và scope; nếu cần sửa, viết prompt kế trước rồi publish work/taskId/version mới. Không ghi đè Gemini reports/status, không auto-send chat Antigravity. Notifications chỉ review/prompt mới, blocker cần người dùng hoặc acceptance, giữ im lặng polls không đổi.

Nếu agent đã kết thúc lượt, file không tự khởi động lại nó. Người dùng cần bấm tiếp tục; không được claim tự thực thi hoặc đoán ended từ timestamp. Codex tiếp tục tự review checkpoint dù Gemini đã kết thúc. Sau local M4 acceptance, ghi rõ Drive gate riêng, stop và pause automation; không tự mở milestone mới.

Không đổi OS/app settings, cài/mount/OAuth, DB live, model/GPU, kill process người khác hoặc deploy. Codex giữ quyền checkpoint Git trực tiếp dev đã được người dùng giao; chỉ thao tác khi source frozen và không ghi đè working tree.
