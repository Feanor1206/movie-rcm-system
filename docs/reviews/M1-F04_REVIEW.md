# M1-F04 — Review độc lập

Ngày 14/10/2026 (Asia/Bangkok). Verdict: **CHANGES REQUESTED — còn 1 finding P2 về consumer UI của H2**. H1 watermark và hai repro H1/H2 đã đạt; giữ fixes, không làm lại lifecycle hoặc backend.

## Checks đã chạy

- Actual-source frontend suite: 20/20 pass, 0 skipped, exit 0, 1187ms. TypeScript noEmit và Next production build: exit 0.
- Patch numstat/reverse --check: exit 0, chỉ contract, context, tests (3 files).
- Chạy reviewer repro F03: old read sau commit giữ `[X]`; unknown add + failed reconcile + retry gửi `[POST,POST]`, final backend `[X]`.
- H1 now tracks committedAtReadVersion và read acknowledgement. H2 có uncertain status, selector isActionUnconfirmed và retry giữ add/delete intent trong context. Test coverage đã cải thiện.
- Backend không đổi trong patch; không rerun backend cho patch này. 8/8 ở F02 là bằng chứng trước đó, không gọi là tests mới. Không model/GPU/live DB hoặc sửa mã ứng dụng. Hook adapter không phải browser E2E; chưa walkthrough UI.

## P2 — Uncertain lifecycle chưa được consumers hiển thị

`rg -n isActionUnconfirmed frontend` chỉ tìm context và tests. MovieCard, MovieDetail, ProfileOverview không dùng selector này hoặc một status tương đương. MovieCard derives inWatchlist và isPending, label/icon theo optimistic state; detail và các nút xóa orphan cũng chỉ theo membership/pending. Generic toast timeout không đủ duy trì trạng thái xác nhận sau khi toast biến mất.

Khi add đã commit nhưng response lost + reconcile down, UI hiện bookmark đã lưu và action xóa; context tiếp nhận click đó như retry POST. Khi delete chưa xác nhận, UI hiện thao tác thêm nhưng context retry DELETE. User không biết dữ liệu đang uncertain hoặc nút sẽ làm gì. Báo cáo đúng ở transport/provider nhưng chưa hoàn thành yêu cầu H2 “expose status/API cho consumers”, feedback và retry có nhãn rõ trong prompt F04.

Yêu cầu cuối: wired uncertain/reconciling/confirmed feedback tại MovieCard, MovieDetail và Profile actions, labels/aria đúng với actual request, explicit verify/retry giữ intent. Không spinner vô hạn; không giả saved hoặc cho opposite toggle dưới nhãn retry. Giữ xanh lá/contrast/z-index và các selectors/actions hiện đã pass.

Regression UI/component phải chạy actual consumer và chứng minh render uncertain + click retry → đúng method/desired state; retry confirm rồi mới trở lại toggle bình thường. Bao phủ add/delete, favorites, rating/remove và orphan actions. Walkthrough fixture khi browser khả dụng hoặc ghi thiếu evidence đúng.

## Bàn giao

Giao một follow-up **M1-F05** theo `docs/prompts/M1-F05_GEMINI_PROMPT.md`, chỉ nối consumer feedback/actions và tests. Không giao lại H1/backend, không chuyển M2 trước khi hành trình lưu/thử lại trung thực.
