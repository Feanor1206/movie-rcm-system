# M1-F02 — Hoàn thiện lifecycle và tính đúng đắn của M1

Bạn là Gemini tại `D:\Class\movie-rcm-system`. Đọc `docs/reviews/M1-F01_REVIEW.md` và engineering rules. Triển khai một follow-up tổng hợp F1–F5, không làm lại các phần F01 đã đúng và không chuyển M2. Codex review; bạn code.

## 1. Session/operation ownership xuyên suốt

Mutation capture session identity và operation ID. Guard ngay sau mỗi await, trước mọi effect: handleSessionExpired/401, success/catch/rollback/toast, pending state và sync lock deletion, return success. Closure user/status cũ không phải current identity. Response A không logout B; finally A không xóa lock B dù cùng movie/action. Track và abort mutation controllers khi session đổi/unmount; stale response không return success.

## 2. State có owner, không expose data A ở render B

Gắn owner/session vào library snapshot; derive watchlist/favorites/ratings/selectors/counts/visible pending theo actor hiện tại ngay khi render. Không dựa riêng useEffect clear state sau render. A→B, A→guest trước passive effects phải không expose A. Không mutation bằng closure của actor cũ. Guest state vẫn được đọc/lưu riêng, không merge account.

## 3. Tách read generation khỏi session generation

Same-actor refetch không được invalidate mutation đang chạy hoặc làm pending kẹt. Tách session lifecycle, read request cancellation/version, mutation operation identity. Refresh kết thúc trước/sau write không overwrite commit mới bằng snapshot cũ. Chọn reconciliation policy rõ, pending được giải phóng bởi đúng operation mà không unlock operation mới.

## 4. Timeout qua body và reconcile unknown outcome

List/mutation timeout bao gồm headers + JSON body, cleanup trong finally; kiểm tra cancellation khi body đã resolve. Profile hydration có timeout, abort/unmount cleanup, bounded retry user action và validate response ID/required data trước found. Không giữ loading/pending vô hạn.

Write response lost/timeout có thể đã commit: biểu diễn chưa xác nhận và reconcile backend với giới hạn; retry phải idempotent và không đảo toggle đã thành công. Giữ actor isolation và operation ordering, không retry loop vô hạn. Giữ snapshot đã xác nhận khi read lỗi.

## 5. Backend recovery chỉ trả dữ liệu đã lưu

Watchlist/Favorite catch DataIntegrityViolationException không dùng orElse(unsavedItem) rồi trả 200 success. Chỉ duplicate recovery khi tìm thấy persisted row đúng owner/movie. Không có row thì trả lỗi phù hợp hoặc recovery có giới hạn, không success giả. Rating handling cũng phân biệt insert collision thật với lỗi khác. Giữ REQUIRES_NEW khi phù hợp, không sử dụng transaction rollback-only.

## Tests và evidence bắt buộc

Tests gọi actual production source, không copy implementation. Bổ sung các ca:

- A write trả 401 sau B login: B không logout/open auth modal.
- A finally về trong lúc B write cùng key: lock B còn, không gửi duplicate.
- Render chuyển actor trước flush effects: không expose library/counts A.
- Same-actor refresh trong lúc add/delete/rate/remove pending: hết pending đúng, final state khớp backend.
- Refresh snapshot cũ về sau successful write không overwrite kết quả mới.
- Headers về nhưng body chậm: fake timer thực sự fire và abort body; timeout kết thúc pending/loading.
- Backend đã commit nhưng write response mất: reconcile cho thấy state thật, retry không đảo hành động.
- Profile network/404/timeout/retry không bị gán removed nhầm.
- Backend insert integrity failure + no persisted row không trả success; duplicate recovery trả persisted ID. Concurrent favorites cùng watchlist/rating.

Repro Codex: `docs/reviews/repro/M1_F01_runtime_repro.cjs` và output là bằng chứng tham khảo, không sửa để che lỗi. Có thể refactor context thành common request/operation helpers để tránh nhân lỗi trong bốn mutations; chỉ trong scope M1. Không nâng frameworks.

Chạy frontend suite, TypeScript/build và Spring tests DB in-memory riêng. Ghi rõ hook adapter vs React/browser evidence. Khi có trình duyệt hỗ trợ, walkthrough guest/auth/profile/save/remove/reload/account switch bằng test fixture, không account live. Nếu thiếu evidence UI thì ghi đúng chưa kiểm tra.

## Bàn giao

Snapshot baseline F02 giữ mọi thay đổi người khác. Tạo `docs/reports/M1-F02_REPORT.md`, `docs/reports/M1-F02.patch`, cập nhật contract policy/session/read/write outcomes. Ma trận F1–F5 có nguồn/test/interleaving/expected/actual và lệnh/exit code. Patch numstat/reverse check pass, không sửa tay hunk header.

Không AI/FastAPI/Qwen, không GPU/model, không ETL/catalog overhaul, không DB live/deploy/commit/push/reset. Bàn giao một lần READY FOR REVIEW M1-F02 sau khi hoàn tất cả nhóm; chưa M2.
