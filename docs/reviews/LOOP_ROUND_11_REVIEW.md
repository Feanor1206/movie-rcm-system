# Round 11 — Independent M3 review

2026-10-14. **REQUEST CHANGES — source/UI checkpoint đạt, M3 còn production bootstrap và performance measurement.** Không yêu cầu làm lại các fixes đã đạt.

Checkpoint round11/prompt11/run-round11-20261014-1140 khớp control/status. 31 manifest hashes stable trước/sau checks; patch reverse check exit0. Không sửa application code, không dùng live DB/AI/GPU hoặc service đang mở trên3100.

## Đã xác minh và chốt phạm vi đã đạt

- npm test **57/57 pass**: 54 executed component/provider behavior tests +3 source-structure assertions của modal_a11y_suite. Không gọi ba source includes tests là browser lifecycle tests. TypeScript exit0.
- Production build exit0: Next15.1.2, FirstLoad Home139kB/Detail140kB/Profile138kB/Search137kB hiển thị làm tròn. Claim mọi route<140kB chưa được chứng minh bằng exact-byte budget assertion; không tự diễn giải display làm fail/pass sát ngưỡng.
- Backend isolated H2 mem:codex_round11_review **21/21 pass**, exit0; log tại docs/reviews/evidence/ROUND_11/backend_test.log.
- Reviewer browser wrapper docs/reviews/repro/ROUND_11_browser_review.cjs chạy actual handed harness, outputtemp riêng. 14 steps/UI assertions và3runs×4routes kết thúc exit0. Auth failed submit/restore, player initial focus/Tab/Escape/restore, CineBot reduced-motion/restore, UI logout/loginB và isolation/reload đạt trong fixture. Mobile reviewer scroll0/200/400/600 không có trigger collisions. R1 CI names/dev trigger và R3 UX findings cũ **closed** trong phạm vi checks này.
- Rollback đã bỏ DROP TABLE, production demo seed mounts đã tách khỏi base compose. Giữ các thay đổi này; không cần rewrite.

## C1 — P1: Compose bootstrap dùng schema thiếu Favorite entity

infrastructure/docker-compose.yml vẫn mount **database/schema/01_init.sql** vào entrypoint postgres. File đó chỉ tạo users/movies/watchlist_items/movie_ratings, không có favorite_items. Production app dùng ddl-auto=validate và có FavoriteItem entity, nên một volume mới không thể startup thành công chỉ theo Compose hiện tại, kể cả đã cấp secrets. File docs/runbooks/db/schema_v1.sql có favorite_items nhưng không phải file bootstrap Compose dùng.

Codex đã chạy đúng database/schema/01_init.sql trên H2 in-memory PostgreSQL mode riêng: bốn bảng trên tồn tại, query FAVORITE_TABLE_COUNT trả **0**. Đây là bằng chứng thực thi SQL thiếu bảng; không giả là đã chạy PostgreSQL/container. Không có docker/podman/psql khả dụng trong shell review nên không startup DB production.

Cần một nguồn schema bootstrap nhất quán và test bootstrap→Hibernate validate với entities, không test create-drop rồi gọi đã validate DDL. Cho DB cũ: additive migration thêm Favorite table, không DROP hoặc ghi đè user data; runbook nói rõ bootstrap chỉ chạy trên volume mới. Policy test negative hiện ApplicationContextRunner chưa có positive-control load actual prod YAML+valid fixture secrets+test DB, và assert placeholder chung không chứng minh đúng secret nào; tăng độ đặc hiệu khi sửa bootstrap/config test. Kiểm tra Compose healthcheck với POSTGRES_USER/DB configurable thay vì hardcoded postgres/movie_rcm_db; bắt missing env từ config preflight nếu yêu cầu mandatory. Không dùng DB live để sửa/đo.

## C2 — P2: LCP/CLS/cold numbers chưa phải metric được tuyên bố

scripts/run_browser_walkthrough.cjs:1499–1538 đọc performance.getEntriesByType('largest-contentful-paint'/'layout-shift'), không dùng PerformanceObserver. Các entry types này không lấy được bằng getEntriesByType. Khi LCP array rỗng, code **gán FCP thành LCP**; CLS array rỗng cho0. Vì vậy LCP=FCP và CLS0 trong report không chứng minh LCP/CLS. Dùng observer buffered từ trước navigation/content render; không thu được thì null/unavailable, không thay bằng metric khác. [MDN getEntriesByType](https://developer.mozilla.org/en-US/docs/Web/API/Performance/getEntriesByType), [W3C LCP](https://www.w3.org/TR/largest-contentful-paint/).

Codex gắn observer độc lập từ new document, giữ nguyên phương pháp đo khác của harness để so:

| First run gắn nhãn cold | FCP và LCP harness | LCP observer | Static resources zero-transfer/cache |
| --- | --- | --- | --- |
| Home | 52ms | 108ms |17/17 |
| Search |64ms |80ms |17/17 |
| Detail |88ms |148ms |18/18 |
| Profile |56ms |84ms |17/17 |

Các con số trên chỉ là một lượt diagnostic, không thay kết quả benchmark chính thức. Observer còn nhận layout-shift entries trong cả4routes trong khi getEntriesByType luôn0. Review evidence/perf_measurements.json lưu raw observer samples và original metrics.

Không có clearBrowserCache/setCacheDisabled/new browser context trong loop. First run đã đi qua toàn walkthrough nên không cold; runIdx===1 không làm lạnh cache. Hơn300KB encoded static data có transferSize0 vì cache; API cross-origin cũng có thể thiếu timing exposure. Median6KB là con số ResourceTiming trong điều kiện đó, không phải toàn bộ byte cold load. Phân biệt transferred/encoded/decoded, cache hit và opaque timing; dùng CDP network bytes để đối chiếu, không cộng đếm trùng.

Sửa cold/warm protocol, lưu raw runs riêng và không trộn mediancold+warm. Chốt end condition app content/requests settled có deadline; document.readyState complete+600ms chưa bảo đảm catalog async đã render. LCP observation-window/finalization rõ, CLS session-window aggregation đúng hoặc label raw sum không gọi CLS chuẩn. Cần baseline/build identity, same conditions và actual before/after; nếu chưa tối ưu code thì gọi measurement baseline đúng tên. Không suy cần mua SSD từ phép đo web localhost này.

## Phần còn lại và giới hạn

M3 còn **hai nhóm C1/C2**; không mở AI/Drive hoặc thêm features khác. R1/R3 không mở lại trừ regression mới. Source includes tests có thể giữ như structural checks, browser assertions là lifecycle evidence. Tuyên bố "0% leak" chỉ áp dụng cases fixture đã test, không certification bảo mật toàn hệ thống.

Reviewer wrapper chỉ redirect outputs, thêm observer diagnostics và đo overlap vài vị trí scroll; không sửa production app. Artifact Gemini không bị ghi đè, source hashes31/31 stable. Round12 prompt tại docs/prompts/ROUND_12_GEMINI_PROMPT.md. Manual handoff, automation tắt. Git checkpoint nếu pushdev không đồng nghĩa deployment hoặc accepted M3.
