# Vòng 8 — Chốt bằng chứng M2, không mở tính năng mới

promptVersion: 8
targetRoundId: 8
milestone: M2
reviewMode: manual
reviewedRunId: run-round7-20261014-0852

Đọc docs/reviews/LOOP_ROUND_7_REVIEW.md. D1–D3 source checkpoint accepted. Không làm lại fixes, M1, Search hoặc AI. Mục tiêu duy nhất là khép verification gate còn thiếu, bàn giao một lần để Codex đóng M2 nếu đạt.

1. Sửa/bổ sung journey test chạy production Hero click lưu, MovieDetail click chấm điểm, production WatchlistProvider và persisted fixture transport; remount/reload provider rồi Profile hiển thị cùng canonical ID ngoài local fixture và điểm thật đã lưu. Không thay click bằng gọi trực tiếp context methods rồi gọi đó là E2E. Assert IDs, POST bodies và read sau reload. Test Hero uncertain ADD/DELETE với provider thực: commit mất response, reconcile lỗi, click đúng retry, confirmed trở lại toggle.

2. Browser walkthrough desktop/mobile qua fixture transport/API riêng: Home→Detail→save/rate→reload Profile; Search deep link và back; empty/backend down/404 khác nhau; Hero retry label; keyboard tiếp cận controls. Dùng công cụ browser có sẵn; không account/DB live hoặc model. Lưu screenshots và command/fixture/viewport/observations. Không dùng build pass hoặc mocked Next Image tree làm browser evidence. Nếu browser tool bị lỗi, ghi bằng chứng blocker cụ thể, không tự cài browser khổng lồ/đổi OS settings, không giả pass. Có thể tạo fixture server/browser harness phục vụ tests, không trộn vào production.

3. Sửa mô tả runbook/report để gọi preview đúng là so với hardcoded baseline/fixture input, không live catalog hoặc importer. Giữ fixture provenance repository_unverified, media chưa kiểm chứng null. Không tự import hoặc sửa DB live.

Scope app source giữ nguyên trừ lỗi thực tế có repro phát hiện trong walkthrough, báo rõ nếu cần sửa. Ưu tiên tests/harness/docs. Bốn frontend suites + TypeScript; build lại nếu đổi source/config hoặc harness runtime cần build mới, ghi kết quả vừa chạy khác prior evidence. Không chạy diagnostic Round 6 assert lỗi tồn tại để lấy pass.

Snapshot riêng, ROUND_8_REPORT.md/patch/manifest own changed/new/deleted SHA256, patch numstat/reverse check và status roundId=8/promptVersion=8/runId mới. Khoảng 30 phút chốt checkpoint trung thực. Không polling, không tự M3, không AI/GPU/FastAPI/DB live/deploy; bàn giao rồi kết thúc lượt.

Người dùng đã cho phép Codex commit/push GitHub. Bạn vẫn không tự commit/push/reset hoặc sửa Git index. Giữ toàn bộ thay đổi ngoài scope và theme xanh lá.
