# M1-F03 — Review độc lập

Ngày 14/10/2026, Asia/Bangkok. Verdict: **CHANGES REQUESTED — còn 2 findings P2 thuộc G2/G3**, không làm lại các phần đã đạt và chưa chuyển M2.

## Bằng chứng đạt

- Patch numstat/reverse --check exit 0, 3 files: contract, WatchlistContext và frontend suite. Không có thay đổi backend trong patch F03.
- Chạy độc lập frontend suite: 17/17 pass, 0 skipped, exit 0, 1044ms. TypeScript noEmit và production build exit 0.
- Chạy reviewer repro F01/F02: tất cả kịch bản cũ cho kết quả mong đợi, gồm checking→verified account và B nonempty library, stale A 401/lock isolation, delete/add/rating cơ bản.
- Backend 8/8 đã được rerun ở review F02; không chạy lại suite không đổi cho patch frontend này. Không gọi đây là backend test mới trong lượt F03.
- Không sửa app code, chạy AI/model, commit/push hoặc DB live. Browser walkthrough chưa có; hook adapter chạy source không thay thế React DOM/browser evidence.

## H1 — P2: Read bắt đầu trong lúc write pending vẫn đảo commit mới

WatchlistContext overlay dựa trên `op.readVersionAtStart >= thisReadVersion || op.status === 'pending'`; committed ops có start version nhỏ hơn read bị prune. Đó là thời điểm write bắt đầu, không phải thời điểm commit hoặc thời điểm read lấy snapshot backend.

Interleaving đã chạy: write X starts/pending (version 1) → refresh starts (version 2, captures empty backend) → write X success/committed → refresh body empty arrives. Lúc apply read, op committed và startVersion 1 < 2, nên không overlay, bị prune: UI `[X]` thành `[]` dù backend lưu thành công. Suite test 14 đặt read trước write nên chưa bao phủ thứ tự này.

Phải dùng commit revision/read-start watermark hoặc cơ chế invalidation có căn cứ. Read bắt đầu trước khi write được xác nhận không được coi là xác nhận commit, dù read bắt đầu sau write start. Prune chỉ khi read đủ mới để acknowledge operation. Guard latest read version trước mọi outcome/commit; cancellation không tự thay ordering guard. Kiểm tra cả add/remove watchlist/favorite, rating update/remove và nhiều reads/mutations.

## H2 — P2: Unknown outcome mất lock trước xác nhận, retry đảo hành động

Các catches xóa operation journal trước khi nhận diện TypeError/AbortError, gọi background reconcile không await; finally giải phóng pending lock dù chưa biết write outcome. Không có trạng thái unknown/reconciling/confirmation failed theo movie/action để consumer chặn toggle ngược.

Repro fake backend commit add X rồi mất response → reconcile GET 500: UI vẫn optimistic X, `isActionPending(X)=false`, có generic library error. Người dùng bấm lại nút lưu: request tiếp theo là **DELETE**, backend mất X. Đường retry đã đảo hành động ban đầu thay vì xác minh/đảm bảo add X. Đây là yêu cầu unknown outcome/retry an toàn của G3, không scope mới.

Cần giữ desired intent/operation identity khi outcome chưa rõ; có trạng thái chưa xác nhận và action verify/retry cùng intent, không spin pending vô hạn hoặc retry tự động vô hạn. Khi reconciliation lỗi, consumer vẫn cho người dùng xử lý rõ nhưng không tự toggle ngược từ optimistic state. Phân biệt thay đổi ý định mới sau xác nhận với retry hành động cũ.

## Repro và bàn giao tiếp theo

`node docs/reviews/repro/M1_F03_runtime_repro.cjs`, output `docs/reviews/repro/M1_F03_runtime_repro_output.json`: chạy actual production WatchlistContext qua deterministic hook adapter, không network/DB. Không copy implementation library vào repro.

Giao một patch **M1-F04** theo `docs/prompts/M1-F04_GEMINI_PROMPT.md`, chỉ H1/H2 và regression/consumer feedback cần thiết. Giữ G1 và các fixes auth/backend/actor/timeout đã đạt.
