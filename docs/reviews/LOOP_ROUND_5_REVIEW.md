# Vòng 5 — Search fixes

Ngày 14/10/2026, Asia/Bangkok. roundId=5, promptVersion=5, runId=`run-round5-20261014-0805`. Review thủ công, không automation.

Verdict: **CHECKPOINT ACCEPTED để tiếp tục catalog UI cutover vòng 6**. Không nghiệm thu toàn M2; Home/Detail/Profile vẫn cần API cutover và journey tests.

## Bằng chứng độc lập

- Manifest 2/2 own file SHA256 khớp trước/sau review, status/runId ready_for_review không đổi. Patch numstat/reverse --check exit 0, 2 files.
- Frontend combined suites: 46/46 pass, 0 skipped, exit 0 (12 Search component + 9 catalog + 25 M1). Search suite đã thay replication helpers bằng execution actual Search/MovieCard với mocked hooks/navigation/transport.
- TypeScript noEmit và production build exit 0. Không gọi progress prerender 7/7 là mọi route static.
- Reviewer actual-component repro ROUND_4_search_repro: own URL B về sau draft C giữ C; old empty/new pending không hiện no-results new; yearMin/yearMax/size được forward đúng (2000/2005/2).
- Source có snapshot query key, API animationOnly và invalid-year-range state; Card missing poster placeholder và M1 uncertain actions vẫn giữ.
- Backend không đổi, không rerun. Prior evidence 17/17 review vòng 3. Không app code edits/live DB/GPU/commit.

## Giới hạn và việc còn lại của M2

Hook adapter/component execution không phải React DOM/browser E2E. Chưa walkthrough production UI với test backend hoặc PostgreSQL live. Acceptance ở đây là checkpoint đã giao, không chứng nhận mọi race/navigation edge case hoặc toàn bộ sản phẩm.

URL integer parsing vẫn dùng parseInt nên malformed numeric prefixes có thể thành giá trị khác thay vì explicit validation. Trước final M2 gate, normalize/validate full numeric strings và canonical policy rõ (fractional/non-numeric không silently thành filter khác). Detail client nên so canonical ID literal theo contract, không lowercase để coi đổi case là mapping. Hai cleanup boundary này có thể ghép vòng cutover, không cần làm lại Search lifecycle.

## Vòng 6

Thực hiện Home/Detail/Profile API cutover thành một hành trình cùng canonical IDs: Home animation-only/empty/error, detail 200/404/unavailable và missing media, Profile shared client bỏ local production lookup, giữ M1 save/uncertain retry/ownership. Bổ sung actual-source journey tests và browser evidence nếu tools hỗ trợ. Không M3 đến khi các gate M2 đạt; chưa sửa AI.
