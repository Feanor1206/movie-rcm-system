# M1-F03 — Snapshot lifecycle và read/write reconciliation

Bạn là Gemini triển khai tại `D:\Class\movie-rcm-system`. Đọc `docs/reviews/M1-F02_REVIEW.md` và engineering rules. Thực hiện tổng hợp G1–G3, giữ fixes auth/actor isolation/backend của F02. Không chuyển M2, không làm lại theme hoặc mở scope AI.

## G1 — Login/reload phải khôi phục library thật

Sửa lifecycle owner snapshot để verified response của actor hiện hành có thể khởi tạo snapshot mới dù previous owner là checking/guest/A. Guard bằng session/read identity hiện hành trước commit; render B vẫn không expose A. Không nhận response cũ chỉ vì userId khớp. Mutation không được báo success rồi UI không đổi do owner mismatch.

Test actual provider composition hoặc một harness phối hợp AuthProvider→WatchlistProvider, không chỉ bắt đầu authenticated. Kiểm tra checking→guest, stored token→verified A, guest login A, A→logout→B, unavailable retry→verified và reload. Mỗi tài khoản có nonempty fixtures riêng cả watchlist/favorites/ratings; B load xong phải đúng B chứ không chỉ assert render đầu empty.

## G2 — Read cũ không đảo mutation mới

Thiết kế một chính sách read/write ordering có cấu trúc và tài liệu ngắn trước khi triển khai. Tách session epoch, read version và per-item operation identity/desired state/confirmed state. Có thể dùng journal/overlay hoặc invalidate read cũ và bounded authoritative reread; không chỉ merge locks còn active.

Giữ được cả add và remove watchlist/favorite, rating update và remove; successful operation đã unlock vẫn phải được bảo vệ trước read cũ. X failure không làm mất Y success. Read/refresh giữa write pending hoặc sau commit không làm pending kẹt. Dùng structured operation metadata thay split lock string để suy ra movie IDs.

Regression: old read empty về sau add success; old read có X về sau delete success; rating cũ 5 về sau update 9; old rating về sau remove; concurrent distinct items; failure rollback. Test fake backend có committed state và snapshots, không mặc định mọi GET empty.

## G3 — Reconciliation dùng chung lifecycle, có unknown outcome rõ

Hợp nhất foreground read và background reconcile qua một path có guard current session/ref sau mỗi await, read version, timeout cả body, AbortController/cancellation, payload validation và G2 ordering. Không kiểm tra current actor bằng closure status/user/token cũ. Session epoch phải phân biệt A→logout→A và token/phiên thay đổi cùng user.

Abort/network/body lost sau gửi write có thể đã commit. Biểu diễn outcome chưa xác nhận, bounded reconcile và cách retry an toàn; không nuốt reconcile lỗi rồi cho toggle retry ngược hành động đã thành công. Không vòng retry tự động vô hạn.

Return success chỉ cho operation còn current và kết quả hợp lệ. Cleanup lock/controller/pending kiểm tra operation/session identity; stale finally không unlock operation phiên mới cùng account/movie/action. Chặn stale callbacks trước mọi side effect; account data vẫn cách ly.

Test committed write + response lost; reconcile error/timeout/slow body; A→B→A khi reconcile pending; stale success/finally; unavailable→retry. Không thêm mock success, guest auto merge hoặc changes AI.

## Kiểm thử và bàn giao

Repro Codex: `docs/reviews/repro/M1_F02_runtime_repro.cjs` và output. Không sửa repro để che regression. Giữ các tests/repros F01/F02 đang đạt và thêm cases G1–G3 gọi actual production code. Nếu tách helpers/state machine, production phải dùng chính module tested; không copy logic cho test.

Chạy frontend behavior suite, TypeScript/build và backend regression phù hợp. DB test riêng; không start vào DB người dùng hoặc tạo account live. Walkthrough bằng browser test fixture khi môi trường hỗ trợ; ghi rõ hook adapter vs React/browser evidence và phần chưa kiểm tra.

Tạo `docs/reports/M1-F03_REPORT.md` và `docs/reports/M1-F03.patch` từ snapshot trước lượt này; matrix G1–G3 và policy read/write/unknown outcome, lệnh/exit code thực. Numstat/reverse check pass, không sửa tay hunk headers. Không commit/push/reset hoặc sửa AI/Qwen/FastAPI, bulk catalog hay framework. Kết thúc một lần READY FOR REVIEW M1-F03.
