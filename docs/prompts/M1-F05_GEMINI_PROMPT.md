# M1-F05 — Nối uncertain/retry vào giao diện người dùng

Bạn là Gemini triển khai tại `D:\Class\movie-rcm-system`. Đọc `docs/reviews/M1-F04_REVIEW.md` và engineering rules. Chỉ hoàn thiện phần UI còn thiếu của H2, không làm lại H1/lifecycle/backend đã pass, không chuyển M2.

## Kết quả

Khi lưu/xóa/thích/chấm điểm chưa được xác nhận do response lost/timeout và reconciliation lỗi, người dùng phải nhìn thấy trạng thái đó và biết rõ verify/retry sẽ làm gì. Nút không được ghi “Xóa” nhưng click gửi POST retry, hoặc ghi “Thêm” nhưng click gửi DELETE retry.

## Triển khai

- Wire `isActionUnconfirmed` hoặc status API tương đương vào MovieCard, MovieDetail và Profile actions/orphan actions. Không chỉ expose selector trong context/tests.
- Feedback persistent cho uncertain: “Chưa xác nhận”, “Kiểm tra lại”, “Thử lưu lại” hoặc “Thử xóa lại” đúng desired intent. Label/aria/text/icon và handler phải đồng nhất.
- Distinguish pending spinner hữu hạn, uncertain/reconcile error và confirmed. Không ghi đã saved khi chưa xác nhận; không spinner vô hạn, không retry loop tự động.
- Explicit verify/retry giữ operation intent và idempotency đã có. Nếu cần context expose desired action/minimal retry helper, chỉ thêm phần cần cho UI, giữ tests H1/H2 đang pass. Rating update/remove không thay intent do optimistic data; user chọn ý định mới phải được phân biệt rõ với retry.
- Confirmed/reconciled rồi trở lại toggle bình thường. Account đổi phải clear/ẩn trạng thái cũ, không callbacks/notification stale.
- Giữ theme xanh lá, contrast, responsive, keyboard và card overlay stacking.

## Kiểm tra

Tests chạy actual consumer/component/helper mà production dùng, không assert string source hoặc copy UI implementation. Mock provider/transport để render uncertain add/delete/favorite/rating/remove/orphan; click verify/retry chứng minh đúng method/body/intent; resolve/reject rồi status/labels/pending chính xác. Giữ 20 tests context đang pass; TypeScript/build. Nếu không backend changes thì không cần rerun backend, ghi prior evidence.

Browser walkthrough trên fixture/test account nếu môi trường hỗ trợ; không account/DB live và không GPU. Ghi rõ rendered/component tests vs browser evidence; không tự gọi mock hooks là E2E.

## Bàn giao

Snapshot riêng F05 giữ dirty tree. Tạo `docs/reports/M1-F05_REPORT.md` và `docs/reports/M1-F05.patch`; matrix actual consumer/state/label/action/result, commands/exit codes và limitations. Numstat/reverse check pass; không sửa tay hunk headers. Không AI/FastAPI/Qwen, bulk catalog, framework upgrade, live DB, commit/push/reset.

Bàn giao một lần READY FOR REVIEW M1-F05. Đây là completion UI của H2, không mở thêm tính năng.
