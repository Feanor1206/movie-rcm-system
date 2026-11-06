# M1-F04 — Hai nhánh ordering và unknown outcome còn lại

Bạn là Gemini triển khai tại `D:\Class\movie-rcm-system`. Đọc `docs/reviews/M1-F03_REVIEW.md`, M1 contract và engineering rules. Làm một patch nhỏ H1/H2, không làm lại M1 hoặc chuyển M2. Giữ mọi fixes F03 đã pass.

## H1: Read không được xác nhận commit diễn ra sau khi nó bắt đầu

Sửa journal/read policy dựa trên revision có căn cứ: thời điểm operation start không đủ để xác định read authoritative. Track commit revision và read-start watermark hoặc invalidate/reread; read bắt đầu khi write pending phải giữ overlay nếu response về sau write commit. Chỉ prune operation khi có read có thể acknowledge kết quả đó. Thêm latest-read/session guard trước mọi success/error/state/loading/expiry outcome, không chỉ trông vào abort.

Test actual code các interleavings với fake backend snapshot/commit state:
- write starts → read captures old state → write commits → read old body arrives.
- read starts → write starts/commits → read body arrives.
- read mới đã commit state rồi read cũ về muộn.
- add/remove watchlist/favorites, rating update/remove; distinct concurrent items; failure rollback.

Giữ snapshot owner/session isolation, raw password và các repro F01/F02 đang đúng. Dùng structured metadata, không sửa test expected để nhận stale state.

## H2: Unknown outcome phải giữ intent và có retry an toàn

Không xóa operation metadata/desired intent rồi unlock như mutation chắc chắn kết thúc khi AbortError/TypeError/body loss có thể đã commit.

Có lifecycle rõ: submitting → confirmed hoặc uncertain/reconciling → resolved / needs verification. Network timeout hữu hạn vẫn phải kết thúc spinner; trạng thái uncertain không phải pending spinner vô hạn. Giữ action theo intent ban đầu và operation ID; chặn toggle tự động đảo intent khi người dùng nghĩ đang retry. Provide verify/retry cùng desired intent, có error feedback và retry chủ động sau reconcile thất bại. Chỉ cho opposite action như ý định mới khi trạng thái được xác nhận hoặc người dùng chọn rõ theo policy.

Expose status/API tối thiểu cho MovieCard/MovieDetail/Profile nếu cần để hiện “Chưa xác nhận lưu”, “Kiểm tra lại” hoặc thông báo tương đương. Retry có idempotency, không POST→DELETE chỉ vì optimistic entry còn trong state. Không retry loop tự động vô hạn, không gộp guest/account hoặc làm mất dữ liệu đã xác nhận.

Tests: add/delete/rate/remove đã commit nhưng response mất; reconciliation success/error/timeout; retry giữ intent; new session không nhận uncertain state cũ; pending/body timeout; opposite action sau xác nhận. Assertions cả request method/body, final fake backend và UI/provider status, không chỉ check có GET.

## Bằng chứng và bàn giao

Reviewer repro `docs/reviews/repro/M1_F03_runtime_repro.cjs` và output. Không sửa repro để che regression. Frontend tests chạy production code; checks TypeScript/build. Nếu backend không đổi, không cần rerun toàn backend suite, ghi rõ prior evidence. Browser walkthrough với fixture khi hỗ trợ; ghi đúng thiếu evidence, không gọi hook adapter là E2E.

Snapshot F04 bảo toàn dirty tree. Tạo `docs/reports/M1-F04_REPORT.md` và `docs/reports/M1-F04.patch`; update contract read acknowledgment/uncertain retry policy, acceptance matrix H1/H2 với commands/exit codes. Patch numstat/reverse check pass.

Không AI/FastAPI/Qwen, không catalog/ETL overhaul, framework upgrade, live DB, commit/push/reset. Hoàn tất cả hai nhóm rồi READY FOR REVIEW M1-F04 một lần; không tự chuyển M2.
