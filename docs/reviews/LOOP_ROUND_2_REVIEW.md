# Vòng 2 — Backend fixes và catalog client

Ngày 14/10/2026, Asia/Bangkok. roundId=2, promptVersion=2, runId=`run-round2-20261014-0315`.

Verdict: **CHANGES REQUESTED — tiếp tục vòng 3 sửa boundary client và genre whitespace**. M2 chưa accepted; chưa chuyển M3.

## Freeze/checks

- Manifest 5/5 own files khớp SHA256 trước và sau review; status/runId ready_for_review không đổi. Control reviewing trong checks.
- Patch numstat/reverse --check exit 0, 5 files đúng scope.
- Maven wrapper, JDK 25.0.3, test profile với H2 in-memory riêng `codex_round2_review`: 16 tests pass (8 auth/library + 8 catalog), 0 skipped/failures/errors, exit 0, 12,283s.
- Frontend catalog suite: 4/4 pass, exit 0; TypeScript noEmit exit 0. Không build/UI walkthrough vì client mới chưa gắn UI; không chạy lại M1 suite không đổi. Không DB live/GPU/commit hoặc application edits.
- R2 round1 search consistency đã sửa qua shared title/description predicate. R1 near-match và wildcard escape đã cải thiện, nhưng chưa normalize whitespace tổng quát (C3). Contract status/video example đã sửa.

## C1 — P2: Timeout/caller cancellation chỉ bao phủ headers

catalogService fetchWithTimeout finally clear timer và remove external abort listener trước trả Response. browseCatalog/getCatalogMovieById sau đó mới await res.json(). Body chậm không còn timer, caller abort sau headers không được truyền tới request/body. Trái claim unified timeout trong report. Test timeout hiện chỉ treo fetch headers, không body.

Repro actual module headers success/body deferred → caller abort: activeTimers=0 và transportAborted=false; body vẫn resolve thành success. Cần request+parse cùng lifecycle, cleanup cuối cùng, classify timeout và caller cancellation riêng để UI không báo lỗi mạng cho request intentionally canceled.

## C2 — P2: Malformed payload biến thành empty/phantom data; detail không verify ID

normalizeCatalogMovie chỉ kiểm tra object rồi String-coerce fields. `{}` thành id='', title placeholder, year=0/rating=0. browse success với data={} thành page empty thành công (size=0,totalPages=1), che server contract error thành no-results. getCatalogMovieById('requested-movie') nhận response id='other-movie' và trả Other; downstream library có thể lưu nhầm phim.

Validate required ID/title, field types và paginated envelope/metadata trước success. Missing required data phải lỗi; nullable media vẫn unknown, không bịa numeric zero để đại diện thiếu year/rating. Detail requested/response IDs phải khớp. HTTP 404 phải phân biệt với network/malformed success; hiện parse JSON trước 404 nên HTML/empty 404 bị exception thay vì null, cần policy/test rõ. Search/query precedence client dùng ?? nên blank query chặn search dù controller blank query fallback search; giữ contract consistent.

Repro actual catalog TS module: `docs/reviews/repro/ROUND_2_catalog_client_repro.cjs`, output cùng tên `_output.json`. No network hoặc copied client implementation.

## C3 — P2: Genre whitespace vẫn hard-code một dấu cách

MovieService buildGenreTokenPredicate liệt kê patterns một space quanh dấu phẩy và cb.trim toàn chuỗi chỉ dùng equality cho single token. CSV `Animation,  Family` hoặc `  Animation,Family` sau DTO trim có tokens Animation/Family, nhưng query Family/animationOnly không match một số vị trí. Contract trim token cho phép whitespace được normalize, không giới hạn một space. Tabs/repeated whitespace cũng chưa covered.

Cần normalization token boundary có policy rõ, bảo toàn internal spaces của token tên dài và case-insensitive exact match. Giữ DB filtering/paging, không fetch-all memory filter, không mutate DB live. Test repeated/outer whitespace, null genres, named token có internal spaces, near-match và literal wildcard để đóng R1.

## Vòng 3

Ưu tiên C1–C3 và behavior regression. Khi boundary checks xanh và còn thời gian có thể bắt đầu Search catalog slice; chưa cần cả Home/Detail trong một vòng, không mount client đang có C1/C2 vào production flows. Prompt version 3 và control work roundId 3 chỉ publish sau xác minh source freeze.
