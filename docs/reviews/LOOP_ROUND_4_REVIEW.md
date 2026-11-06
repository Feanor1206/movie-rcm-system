# Vòng 4 — Search/Browse UI

Ngày 14/10/2026, Asia/Bangkok. roundId=4, promptVersion=4, runId=`run-round4-20261014-0750`. Chế độ review thủ công, automation vẫn tắt.

Verdict: **CHANGES REQUESTED — 4 nhóm P2 ở Search/coverage**. Giữ API cutover, animationOnly và Card poster placeholder đã đúng; chưa chuyển Home/Detail hoặc M3 trước khi Search đạt.

## Freeze và checks

- 3/3 own file SHA256 khớp manifest trước/sau review; ready status/runId ổn định. Control reviewing trong kiểm tra.
- Patch numstat/reverse check exit 0, 3 files đúng scope.
- Chạy search/catalog/M1 suites chung: 40 tests pass, 0 skipped, exit 0. Trong đó 6 Search tests là simulation (S4), không có giá trị chứng minh production UI behavior. 9 catalog và 25 M1 tests tiếp tục pass.
- TypeScript noEmit và production build exit 0. 7/7 là prerender progress, không phải mọi route static (detail/API routes dynamic).
- Backend không đổi, không rerun. Prior 17/17 là review vòng 3. Không GPU/live DB/application edits/commit. Chưa browser walkthrough.

## Repro độc lập

`node docs/reviews/repro/ROUND_4_search_repro.cjs`; output `ROUND_4_search_repro_output.json`. Chạy actual SearchExperience.tsx qua transpilation với hook/navigation/transport adapter tối thiểu; không copy logic Search. Đây là source/component execution, không browser E2E.

## S1 — P2: URL update chậm ghi đè draft mới

SearchExperience dùng effect `setInputValue(urlQuery)` vô điều kiện khi URL query đổi. Với router navigation có latency: đang q=A → user gõ B → debounce push q=B → user tiếp tục gõ C trước khi B navigation hoàn tất → URL B commit → input C bị set về B. Repro before C / after B, ký tự mới mất.

Phân biệt own pending navigation acknowledgment với external back/forward/deep link. Chỉ sync draft khi external navigation hoặc draft chưa tiến xa hơn navigation đó; cancel/suppress stale own update. Test với router push chưa resolve ngay, không đồng bộ URL giả tức thì che race. Reset/clear và thay filter khi draft đang chờ cũng cần cùng policy.

## S2 — P2: Old empty data bị gắn nhãn theo query mới

Khi data của query cũ empty và query mới loading, render vẫn vào nhánh `data && data.items.length === 0`; empty copy lấy urlQuery mới. Repro q=old empty → q=new fetch pending: đồng thời có updating indicator và “Không có phim ... từ khóa new”. Chưa có response new mà đã khẳng định no-results new.

Gắn query key vào data snapshot/rendered status. Loading new query phải skeleton/updating phù hợp, chỉ empty khi response đúng query hiện hành hoàn tất. Nếu giữ previous results/counts, label chúng là snapshot query cũ và tránh click/pagination như thể thuộc query mới. Tests empty→pending, results→pending, pending→error/retry, response A/B sai thứ tự.

## S3 — P2: URL year/size không tham gia query

Prompt vòng 4 yêu cầu URL query/genres/year/sort/direction/page/size. Search không đọc yearMin/yearMax và hard-code urlSize=12. Repro URL `q=film&yearMin=2000&yearMax=2005&size=2` gửi yearMin=null/yearMax=null/size=12, silently bỏ filter và page size.

Đọc/validate/forward year bounds và size theo backend contract, giữ qua paging/back/reload, reset/clear filters đúng và có controls/summary đủ để user thấy filter active. Invalid year range/page/size có normalization/error policy rõ, không parseInt biến page=1.5 thành 1 mà vẫn gọi canonical. Không cần thêm runtime filter chưa có data.

## S4 — P2: 6 Search tests không chạy source được bàn giao

Suite có `Helper replicating` URL parser/serializer, mockFetch tự viết generation guard, deriveUiState/getPosterConfig implementation riêng; animation test chỉ assert object literal true. Không import/call actual SearchExperience hoặc helpers production. Bỏ generation guard/animationOnly khỏi app vẫn có thể giữ 6/6 xanh. Lặp lại hạn chế simulation đã sửa ở M1, trái prompt vòng 4.

Thay bằng tests actual production component/helper mà component dùng. Mock router với delayed navigation và back/forward, transport deferred/fake timer; cover S1–S3, cancellation/unmount và MovieCard placeholder/href/actions thực. Không chỉ đổi tên suite/report. Report rõ simulation cũ vs evidence mới, không gọi hook adapter browser test.

## Tiếp theo

Prompt vòng 5 sửa tổng hợp S1–S4, scope Search/helper/tests và Card tests cần thiết. Backend/client/M1 giữ nguyên. Kết thúc lượt sau bàn giao, không polling/chờ tự động. M2 chưa accepted; sau Search gate đạt sẽ giao Home/Detail/Profile cutover.
