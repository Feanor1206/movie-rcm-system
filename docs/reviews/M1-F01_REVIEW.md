# M1-F01 — Review độc lập

Ngày: 13/10/2026. Verdict: **CHANGES REQUESTED**. Không chuyển M2. Các sửa đổi F01 có giá trị nhưng chưa đóng hoàn toàn R2/R3/R6; còn 5 nhóm findings, giao một lượt M1-F02.

## Đã xác nhận

- Chạy suite actual TSX: 10/10 pass, exit 0 (771ms). Suite đã bỏ implementation mô phỏng riêng và chạy production providers; hook adapter vẫn không phải React DOM/browser integration.
- TypeScript noEmit và production build: exit 0. 7/7 là progress prerender, không có nghĩa mọi route static.
- Spring wrapper với JDK 25.0.3, test profile và DB in-memory riêng `codex_m1_f01_review`: 8/8 pass, 0 skipped/errors, exit 0, 15,689s. Log quan sát actual unique collisions ở watchlist/rating, được recovery cho hai test hiện tại. Chưa có concurrent favorites test.
- F01 patch numstat/reverse --check: exit 0, 13 files khớp working tree hiện tại.
- Auth logout khi JSON pending đã được test chặn; raw password giữ nguyên. Library targeted rollback giữ Y khi X fail. Checking/unavailable không ghi guest; same-actor refresh lỗi giữ snapshot đã đọc. Backend catalog validation/canonical metadata và removeRating đã có. Migration rollback giữ favorite data.
- Report đã ghi rõ chưa browser walkthrough; không coi build/hook adapter là bằng chứng UI tương tác.

## Bằng chứng bổ sung

`node docs/reviews/repro/M1_F01_runtime_repro.cjs` chạy actual WatchlistContext qua transpilation và deterministic hook adapter, không network/DB. Output: `docs/reviews/repro/M1_F01_runtime_repro_output.json`. Không sửa source ứng dụng trong review. Các kết quả sau là source execution; cần tests React/application bổ sung phù hợp, không gọi là live browser.

## F1 — P1: Side effects của mutation cũ vẫn tác động phiên mới

WatchlistContext lines 393–395/425–427: xử lý 401 gọi `handleSessionExpired()` trước khi kiểm tra actor/generation. Favorites/rate/removeRating có cùng cấu trúc. Sau A write pending → B authenticated → A trả 401, repro ghi nhận expiry callback bị gọi 1 lần. Auth callback này logout và mở modal nên response của A có thể logout B.

Finally 455–459 luôn xóa key trong syncPendingKeysRef, rồi mới check generation để set React pending state. Nếu A và B có cùng movie/action, A finally xóa lock B. Repro B đang write X, A finally về, B gọi X lần nữa: **2 B writes**. Phải guard mọi side effect, kể cả expiry và lock ref, bằng session/operation ownership hiện hành. Abort mutations khi actor/unmount đổi và không return success cho response stale.

## F2 — P1: Render đầu của B vẫn trả library A

Actor/state clear chỉ ở loadLibraryForCurrentActor lines 157–169, được gọi từ useEffect. Provider return lines 881–886 trả raw watchlist/favorites/ratings mà không gắn owner của snapshot. Khi auth B render trước effect-driven update, context vẫn expose state A. Repro first B render trả `[A-private-film]`.

Không chỉ thêm cleanup effect: lưu owner/session của snapshot và derive visible values theo actor hiện tại ngay trong render, đồng thời khóa actions dùng closure cũ. Test render chuyển A→B và A→guest trước flush passive effects; counts và selectors cũng không được lộ A.

## F3 — P2: Refresh vô hiệu hóa mutation đang chạy và để pending kẹt

loadLibraryForCurrentActor line 148 tăng syncGenerationRef mỗi lần gọi, kể cả same-actor refresh. Mutations dùng cùng counter làm session generation; finally chỉ setPendingKeys khi generation còn khớp. Repro X write pending → refetchLibrary → X success: `isActionPending(X)=true`, watchlist `[]` dù backend đã nhận X. Refetch còn có thể overwrite optimistic state bởi snapshot cũ.

Cần tách actor/session lifecycle khỏi read-request generation và operation IDs. Refresh không invalidate operation cùng phiên. Read/write reconciliation không mất commit mới; pending của đúng operation luôn được giải phóng và không unlock operation khác.

## F4 — P2: Library timeout chưa bao phủ body, unknown outcome chưa reconcile

List read line 210 và các mutations lines 391/423/550/582/706/830 clear timer ngay sau fetch headers, trước res.json. Repro headers success + body deferred: pending true và **activeTimerMs=[]**. Request có thể chờ vô hạn. Profile hydration lines 77–119 không có timeout/cancellation nên loading cũng có thể kẹt.

Timer phải giữ qua body và được clear trong finally; abort/timeout không được commit success. Khi write timeout/network mất phản hồi sau DB commit, hiện code rollback rồi chỉ toast “kiểm tra trạng thái”, không đọc lại/reconcile hoặc biểu diễn outcome chưa xác nhận như prompt yêu cầu. Cần trạng thái unknown và cách reconcile có giới hạn, giữ đúng actor/operation; không để toggle retry tạo ngược thao tác đã thành công. Test server committed + response lost, slow body, refresh ordering và profile timeout/retry.

## F5 — P2: Recovery backend có thể trả thành công với item chưa lưu

WatchlistService/FavoriteService catch DataIntegrityViolationException dùng `findByUserIdAndMovieId(...).orElse(item)` (lines 63–66). Không tìm thấy persisted row vẫn trả object vừa build chưa có id. Controller bọc 200 success, trong khi insert đã thất bại. Exception có thể do constraint khác hoặc winning row bị xóa trước recovery; không được coi mọi DataIntegrityViolationException là duplicate.

Chỉ recover khi xác nhận existing persisted row của đúng owner/movie; không có row phải propagate/map lỗi phù hợp, không return unsaved item. Rating fallback tương tự phải xử lý rõ, không blanket swallow. Test unique duplicate và insert failure không có existing row. Bổ sung concurrent favorite case và verify persisted IDs/final rows, giữ migration/data.

## Kết luận

Auth core và catalog correctness đã cải thiện; suite thực thi source là tiến bộ. Tuy nhiên kết luận “R1–R8 triệt để” chưa đúng với các interleavings trên. Không làm lại F01 hoặc mở scope AI. Prompt tiếp theo: `docs/prompts/M1-F02_GEMINI_PROMPT.md`.
