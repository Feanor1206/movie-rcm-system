# Vòng 9 — Sửa browser harness và cung cấp bằng chứng M2 đúng thực tế

promptVersion: 9
targetRoundId: 9
milestone: M2
reviewMode: manual
reviewedRunId: run-round8-20261014-0925

Đọc docs/reviews/LOOP_ROUND_8_REVIEW.md trước khi làm. 54 component/provider tests đạt; ảnh browser vòng 8 không chứng minh nội dung report. Không làm lại production feature hoặc tuyên bố M2 accepted. Mục tiêu là sửa B1–B3 trong một lượt verification có thể tái chạy.

1. **Setup thật và cô lập:** chuẩn bị đúng Next production assets (standalone cần static/public đúng vị trí) hoặc dùng next start/test build phù hợp. Kiểm tra CSS/JS response và hydration; xác minh URL API thực tế từ bundle, không giả định NEXT_PUBLIC runtime env thay được build-time env. Fixture API + auth login/me/session riêng; đi qua production AuthProvider, xác nhận authenticated trước account writes. Bind loopback, chọn ports trống, preflight và fail rõ khi bận; không dùng lại/kill service người khác hoặc chạm live DB. Chỉ cleanup child processes/temp directories do lượt này tạo và kiểm tra absolute path trước recursive cleanup.

2. **Assertions thay observation cố định:** sau navigate chờ condition DOM/request cụ thể với timeout hữu hạn. Missing selector, runtime exception, chunk/CSS 404, sai actor hoặc postcondition phải fail exit nonzero. CDP evaluate kiểm tra exceptionDetails. Ghi JSON evidence theo từng bước: expected/actual/pass, URL, actor, relevant network method/path/status và fixture state (không token/password). Chỉ chụp trạng thái sau assertion đạt; fail có thể chụp diagnostic và ghi failed, không viết lời thành công. Chứng minh harness fail khi intentionally thiếu nút/asset hoặc sai postcondition bằng một negative self-check riêng.

3. **Hành trình account trên browser:** Home có Hero phim fixture → click lưu → Detail click chấm9 → reload → Profile watchlist đúng ID và tab Đánh giá hiển thị9. Kiểm tra requests/backend fixture state. Hero uncertain ADD/DELETE: commit mất response + reconcile500, badge/nhãn đúng → phục hồi → click retry đúng POST/DELETE → confirmed. Search deep link/back: assert URL/draft/results sau Back, không navigate lại để thay thế kết quả Back. Empty, catalog500 và detail404 có nội dung khác nhau được assert. Desktop/mobile và Tab focus được kiểm tra bằng DOM/computed style/activeElement, không gắn nhãn đạt accessibility chung chỉ từ một screenshot.

4. **Test data B3:** dùng canonical ID synthetic riêng không xuất hiện trong local fixture (ví dụ m2-browser-only-001), assert điều kiện đó. Không gọi the-last-orbit là ngoài fixture hoặc gán metadata thay thế rồi gọi backend data thật. Giữ component/provider click tests, mở tab ratings để assert Profile thực sự render9 sau provider reload. Không sửa local catalog để làm test claim đúng.

5. **Bằng chứng và bàn giao:** ảnh mới đặt docs/reports/screenshots/ROUND_9/; giữ ảnh/report vòng8 làm lịch sử, review Codex đã đánh dấu rejected. Report vòng9 chỉ nêu observations đã assert và trích log run; nếu fail/thiếu ghi trung thực. Không sửa report/manifest/status cũ nhằm che checkpoint. Không sửa review Codex. Chạy 4 frontend suites + tsc + browser harness và preview selftests; build đúng test runtime nếu cần. Bàn giao command/env không secret, exit codes, fixture setup, viewport, measured DOM/network assertions, screenshots và giới hạn mock vs Spring real.

Khoảng 30 phút chốt trạng thái thực tế; không cần đủ14 ảnh hình thức nếu ít ảnh nhưng đầy đủ assertions tốt hơn. Nếu còn fail thì ready_for_review với failure rõ, không ép all-pass. ROUND_9_REPORT.md/patch/manifest SHA256 own files + screenshots và status round9/prompt9/runId mới publish cuối sau freeze; patch numstat/reverse check hợp lệ. Không polling/M3/AI/GPU/DB live/deploy. Không tự commit/push/reset hoặc thay Git index. Giữ theme xanh lá và source ngoài scope. Kết thúc lượt để người dùng bàn giao Codex.
