# Round 7 — Codex independent review

2026-10-14. **SOURCE CHECKPOINT ACCEPTED; full M2 acceptance còn chờ runtime/UI gate.**

roundId=7, promptVersion=7, runId=run-round7-20261014-0852. Own source manifest verified trước/sau kiểm tra, patch reverse check thành công. Không sửa application code hoặc dữ liệu live.

## D1–D3

- D1 closed: main lookup thành công render MovieDetail ngay, similar promise độc lập; isCurrent/cancellation guard ngăn callback sau cleanup. Actual route test xác nhận main visible trong lúc similar pending và vẫn visible khi similar lỗi.
- D2 closed ở source/component layer: Hero dùng pending/uncertain/action intent, nhãn ADD/DELETE retry đúng và pending disabled. Context selectors dùng action=watchlist đúng. Test 4 thực thi Hero với context mock; provider retry semantics đã được kiểm tra ở M1. Chưa có test tích hợp Hero uncertain + production provider trong Round 7.
- D3 closed cho policy được giao: cả public Map và remote found có expiry; cleanup removed IDs; remove/re-add sau 6 phút đọc lại API, 404 khác lỗi mạng. Focus listener revalidate expired found; không polling. Actual Profile fake-clock test đã pass.

## Kiểm tra Codex vừa chạy

- Bốn frontend suites: **53/53 pass**, exit 0.
- TypeScript: exit 0. Production build: exit 0, generated 7/7.
- Preview script --test: 3 assertions ADD/SKIP/CONFLICT pass; default preview ADD=6/SKIP=0/CONFLICT=0; không ghi DB.
- ROUND_7.patch reverse check: exit 0. SHA256 own manifest khớp trước/sau.
- Backend không đổi trong Round 7; 17/17 là prior evidence Round 3, không phải lượt chạy mới.

## Gate còn thiếu trước khi đóng milestone

Không có code finding P1/P2 mới được xác nhận trong scope D1–D3. Tuy nhiên **test 7 không phải E2E UI**: gọi trực tiếp provider.toggleWatchlist/rateMovie rồi remount provider, cuối cùng render Profile. Không render/click Home Hero hoặc Detail rating trong test này; ID spirited-away còn là ID fixture local. Test 6 vẫn render ba harness độc lập. Vì vậy lời báo cáo Home→Detail→Profile E2E vượt bằng chứng thực tế.

Cần một lượt chốt bằng chứng tập trung: dùng canonical ID ngoài local fixture, click Hero lưu và Detail chấm điểm qua production provider/persisted test transport, reload rồi xác minh Profile; thêm Hero uncertain ADD/DELETE transport integration. Desktop/mobile browser walkthrough với fixture API/server riêng cho loading/empty/error/404, back navigation và keyboard. Không dùng account/DB live. Nếu công cụ không chạy được, ghi blocker cụ thể; không gọi component adapter là browser E2E.

Fixture provenance repository-unverified và media null phù hợp handoff. Preview default chỉ so với mảng baseline hardcoded trong script; không phải đối chiếu catalog live, không phải importer và chưa áp dụng dữ liệu. Khi viết hướng dẫn phải nói rõ giới hạn này. Không có yêu cầu chạy import live để đạt gate.

Không tự chuyển M3 trước gate M2; vòng 8 chỉ hoàn thiện verification/evidence, không thêm feature hoặc thay kiến trúc. Automation vẫn tắt.
