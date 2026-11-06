# M4-F02 — Unblock walkthrough đang chờ seek (diagnostic, chưa review checkpoint)

Người dùng gửi ảnh Antigravity tối14/10/2026. Codex chỉ đọc source/process metadata, không chạy thêm harness/build/test, không sửa application code hoặc dừng process Gemini. Chưa có F02 artifacts/freeze, không gọi đây là review hoàn tất.

Lúc22:56, node run_m4_media_walkthrough.cjs PID20912 khởi chạy16:26 vẫn tồn tại; child Spring fixture15472 và Next standalone20376. PID chỉ là snapshot, phải xác minh lại parent/command trước thao tác. Không đụng Java11156, node13244/Java2752 hoặc process/server khác. Automation đã tắt, không có Codex review nào chặn Gemini.

Đoạn scripts/run_m4_media_walkthrough.cjs~662 đợi evaluate(new Promise) chỉ resolve khi video phát seeked, không reject/timeout. cdp() pendingRequests cũng không deadline. waitForCondition8000ms ở bên dưới không bảo vệ Promise đang kẹt ở phía trước. Timeline dùng value assignment + synthetic input/change; phải chứng minh actual production onChange chạy và video.seeking/seeked xảy ra, không giả định event dispatch đã tua thành công.

## Tiếp tục F02, không tạo ticket mới

1. Lấy log cuối/exit state của background harness đang sở hữu. Nếu đúng run bị treo, kết thúc có kiểm soát chính run và các child do run đó tạo, xác minh identity/parent; không kill theo tên node/java/chrome hoặc stop Antigravity. Không spawn thêm run khi run cũ vẫn giữ server/Chrome/ports. Báo command/error thật, không chờ task ID hết hạn lặp vô hạn.
2. Sửa harness CDP: mỗi command có deadline hữu hạn, timeout reject và xóa pending request/timer; WS close/error reject các requests đang chờ. Browser awaitPromise cho seek/frame callback cũng phải có timeout/reject và listener cleanup. Thiếu element/event => fail nonzero với diagnostics, không resolve latency0.
3. Điều khiển timeline bằng tương tác browser thật (CDP mouse/keyboard tới slider) hoặc phương pháp được kiểm chứng với controlled React input. Assert DOM slider value và production video.currentTime/seeking phản ánh target. Không tua trực tiếp video.currentTime để che lỗi control, không gọi play trong wait predicate để làm app pass. Trên timeout thu readyState/networkState/currentTime/duration/paused/seeking/slider value và media/network errors.
4. Đọc stack/request URL của Next TimeoutError riêng: hiện chỉ có stderr timeout chưa chứng minh đó là nguyên nhân seek. Nếu do external poster/image thì dùng ảnh fixture local cho browser test để tránh phụ thuộc mạng; không đổi app policy chỉ để bỏ lỗi. Không tăng wait lên hàng giờ hoặc loop rebuild.
5. Chạy lại một lần sau sửa/harness cleanup, negative control thiếu seek event phải exit nonzero trong thời gian hữu hạn và cleanup child processes. Sau đó hoàn tất F1/F2/F3 của prompt chính, artifacts F02 mới/freeze/ready_for_review. Còn lỗi thì báo cụ thể và bàn giao checkpoint, không fake pass.

Phạm vi vẫn M4-F02. Không sửa reviewer helpers/frozen artifacts, không AI/GPU/DB live/Drive install/mount/OS settings, không commit/push/reset. Bàn giao thủ công vì user đã tắt automation.
