# Bàn giao cho Luna — hoàn tất cleanup Google Drive

Làm tại D:\Class\movie-rcm-system, nhánh dev. Người dùng chọn Luna tiếp tục công việc; ba agent Codex trước đã bị dừng theo yêu cầu. Đây là nhiệm vụ triển khai, không chỉ review hoặc viết kế hoạch. Giữ automation tắt.

## Trạng thái thật

- F04 đã bị Codex yêu cầu sửa, dù báo cáo Gemini ghi PASS. Đọc docs/reviews/DRIVE_01_F04_REVIEW.md, docs/prompts/DRIVE_01_F05_GEMINI_PROMPT.md và repro docs/reviews/repro/DRIVE_F04_shutdown_close.java.
- Có thay đổi CHƯA kiểm thử hoàn chỉnh của các agent Codex trong DriveIoExecutor.java, DriveResourceReservation.java, DriveSeekableByteChannel.java và DriveMediaStorageAdapter.java. Kiểm tra git diff hiện tại trước; không reset, không ghi đè mù, không coi phần đang dở đã đúng.
- F04 report/manifest/patch là bằng chứng lịch sử đóng băng; sau sửa source sẽ không còn khớp manifest cũ. Không cập nhật hash cũ để che thay đổi; xuất bằng chứng mới cho phần Luna hoàn tất.
- G1 chưa accepted. Chưa mount Drive hoặc test video thật. rclone/WinFsp đã cài, remote cinema-drive đã OAuth drive.readonly, VideoDieppie có videoplayback.mp4 29,209,556 bytes. Không cần cài/đăng nhập/upload lại.

## Mục tiêu

Khép kín ownership tài nguyên khi cleanup quá tải, timeout, shutdown, rejection hoặc close ném lỗi. Không gọi native close trên caller, không drain cleanup inline trên shutdown caller, không mất handle, không giải phóng quota trước physical close, không queue/thread vô hạn. Bảo toàn deadlines và local-provider isolation.

Hướng thiết kế đang tích hợp: shutdown ngừng admission mới nhưng giữ cleanup lane nhận các reservation đã cấp; chỉ shutdown cleanup lane khi hết obligation. Chuyển active reservation sang pending một cách atomic trong cùng capacity budget. Rejection giữ lại owner/reservation; close lỗi giữ bounded failed obligation để retry có kiểm soát, không báo disposed giả. Kiểm tra phần code đang dở có thực hiện đúng không; có thể sửa thiết kế nếu chứng minh tốt hơn. Chú ý adapter timeout không được release reservation khi open worker/late handle còn sống. Mọi metadata/open timeout và channel worker-finally phải giữ chủ sở hữu vật lý rõ ràng.

## Đa agent và kiểm tra chéo

Nếu môi trường hỗ trợ, dùng ba subagent Luna có file ownership độc lập: A executor/reservation/helper; B channel/adapter; C test đối kháng độc lập. Parent điều phối và chạy build duy nhất, tránh nhiều Maven cùng ghi target. Không tự nhận đã tạo agent nếu tool không hỗ trợ. A/B thống nhất contract trước sửa; C review A/B, A/B review compatibility; parent đóng mọi finding và kiểm tra final diff. Ghi hash revision cuối được review. Không mở agent thứ hai ghi cùng file; không tự khởi động lại Gemini.

## Bằng chứng bắt buộc

1. Repro shutdown của reviewer phải hết callerBlocked khi close latch vẫn giữ; handle đang mở phải được tính ownership/capacity. Sau thả latch đóng đúng một lần và về baseline.
2. Test deterministic shutdown-before-close, race shutdown/submission, cleanup rejection, blocked queued shutdown, close lỗi trước physical disposal, open/metadata timeout, caller interrupt và >=300 admission attempts. Không thả latch trước rồi suy ra caller không block. Tất cả test có timeout/finally/join và fixture nhỏ.
3. Chạy targeted tests trước, sau đó toàn bộ backend test profile H2 riêng một lần khi đã tích hợp; fix failures thật, không sửa assertion chỉ để xanh. Không truy cập DB live. Kiểm tra JDK/command từ repo; không cài runtime mới tùy tiện.
4. Xuất docs/reports/LUNA_DRIVE_CLEANUP_REPORT.md và bằng chứng mới có commands, exit codes, hashes, pass/fail và giới hạn thật. Không tuyên bố accepted chỉ vì tự test xanh; bàn giao Codex review.

Không thay đổi AI/FastAPI/Qwen/GPU, backend/fastapi/.env.example ngoài scope, credentials, OS settings hoặc dữ liệu Drive. Không branch mới/reset/force/deploy. Chưa commit/push phần chưa được kiểm tra. Dừng trước mount: Codex sẽ nghiệm thu G1 rồi thực hiện mount chỉ đọc/cache-off và test video thật theo quyền người dùng đã cấp. Nếu agent khác còn ghi các path này, dừng phần ghi bị trùng và báo rõ thay vì ghi đè.
