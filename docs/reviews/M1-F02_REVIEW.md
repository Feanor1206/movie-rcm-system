# M1-F02 — Review độc lập

Ngày: 14/10/2026 (Asia/Bangkok). Verdict: **CHANGES REQUESTED**. Chưa đóng M1 hoặc chuyển M2. Giữ các fixes F02 đã đạt, chỉ khắc phục 3 nhóm còn lại qua M1-F03.

## Đã đạt và checks thực tế

- Frontend actual-source suite 11/11 pass, exit 0, 808ms; TypeScript noEmit và production build exit 0. Suite hook adapter chưa mô phỏng React DOM/browser và chưa kiểm tra boot auth→library phối hợp.
- Spring integration 8/8 pass, 0 skipped/errors, exit 0, 12,038s; JDK 25.0.3, test profile, H2 in-memory riêng `codex_m1_f02_review`. Concurrent favorites đã thêm; backend recovery không còn trả unsaved item khi không tìm thấy persisted row.
- F02 patch numstat/reverse --check exit 0, 9 files khớp working tree. Reverse check không tự chứng minh mọi snapshot SHA256 claim.
- Chạy lại reviewer repro F01: old A 401 expiryCalls=0; first B render watchlist=[]; same-actor refresh/mutation hết pending; B duplicate writes=1; timer 7000ms còn active trong body parsing. Các fixes này được giữ.
- Không sửa application code, commit/push hoặc chạy GPU/live DB. Chưa browser walkthrough; report đã ghi giới hạn này.

## Bằng chứng regression mới

`node docs/reviews/repro/M1_F02_runtime_repro.cjs`, output `docs/reviews/repro/M1_F02_runtime_repro_output.json`. Repro chạy production WatchlistContext TSX với deterministic hook adapter và mocked transport; không copy library implementation. Đây là source execution, không phải browser E2E.

## G1 — P1: Tài khoản vừa xác minh không tải được library đã lưu

`frontend/lib/context/WatchlistContext.tsx:383`: authoritative read updater trả prev nếu `prev.ownerKey !== thisActorKey`. Snapshot ban đầu thường có owner status:checking; khi auth xác minh xong hoặc guest login, snapshot không được chuyển owner sang user trước read. Vì vậy response hợp lệ của actor mới bị bỏ qua, sau đó loading=false/error=null. Optimistic mutation cũng return prev khi owner khác, nên gửi backend thành công nhưng không hiện trong library.

Repro checking → authenticated A, backend watchlist `[A-saved-film]`: UI `[]`, loading=false, error=null. Repro A→B với backend B `[B-saved-film]` cũng `[]`. Test F2 hiện chỉ assert first B render rỗng, không assert B load xong nhận dữ liệu thật; tests khác khởi tạo provider đã authenticated nên bỏ qua boot transition.

Cần snapshot lifecycle cho actor hiện hành: render vẫn ẩn A ngay lập tức, nhưng response verified của B phải tạo snapshot owner B sau guard current session/read; không đòi snapshot đã mang owner B trước khi có read. Acceptance bao gồm checking→guest, checking→A, guest→A, A→logout→B, retry unavailable→authenticated và reload.

## G2 — P2: Reconciliation refresh chưa bảo toàn mutation hoàn tất hoặc xóa/cập nhật

WatchlistContext 383–407 chỉ merge các locks còn active khi response read commit. Khi mutation đã success và unlock trước old read về, dữ liệu read cũ overwrite kết quả mới. Logic pending watchlist/favorite chỉ giữ additions, không giữ removals; rating chỉ giữ nếu backend không có rating, không giữ updated value khi backend trả điểm cũ.

Repro read body snapshot cũ pending → add X success → read body empty về: `[X]` thành `[]`. Repro delete X pending → refresh vẫn chứa X → delete success: UI vẫn `[X]`. Đây là các interleavings đã yêu cầu ở F02, không scope mới.

Cần read snapshot/version và per-item operation journal/overlay hoặc policy invalidation/re-read có căn cứ; không dùng mỗi pending-lock set để quyết định dữ liệu còn mới. Bao phủ add/remove watchlist/favorites, rating update/remove, completed operation trước old read commit, concurrent distinct items và failure rollback. Không append phần tử dựa trên tách lock string dễ sai với movie IDs có dấu hai chấm; giữ operation metadata có cấu trúc.

## G3 — P2: Background reconcile và session outcome còn thiếu guard/timeout

WatchlistContext 224–261: reconcileAuthoritativeLibrary so targetActorKey với getActorKey(status,user,token) từ closure cũ, không so sessionGenRef/current actor sau await. Reads không có timeout/signal/read generation. setSnapshot thay toàn bộ library, bỏ qua ordering/operation policy của foreground reads. Actor key chỉ userId cũng không phân biệt A→B→A hoặc hai phiên cùng account.

Mutation catches chỉ reconcile AbortError, không network error/lost response thông thường có thể đã commit. Pending được giải phóng trước khi reconciliation xác nhận; reconciliation lỗi bị nuốt, không unknown outcome/error/retry state cho người dùng. Mutation success branches vẫn return true ngoài isStillCurrentSession guard, trái claim stale outcome bị hủy.

Cần một read/reconcile path dùng chung có current-session guard, finite timeout qua body, cancellation/unmount, response validation và ordering policy G2. Unknown outcome do abort/network/body loss phải được biểu diễn rõ, reconciled có giới hạn trước unsafe toggle retry. Response stale không trả success; lock cleanup phải gắn operation/session, không chỉ userId/action. Test response lost sau DB commit, reconciliation down/slow body, actor A→B→A và late stale success/finally.

## Kết luận

Các lỗi auth core/backend đã được cải thiện, nhưng chưa thể nghiệm thu library nếu login/reload trả empty giả hoặc read cũ đảo kết quả mutation. Không làm lại toàn milestone. Prompt hiện hành `docs/prompts/M1-F03_GEMINI_PROMPT.md` gom G1–G3.
