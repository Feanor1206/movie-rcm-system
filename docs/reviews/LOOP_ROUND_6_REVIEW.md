# Round 6 — Independent Codex review

Ngày review: 2026-10-14. **REQUEST CHANGES — chưa đóng M2, chưa giao M3.**

Checkpoint: roundId=6, promptVersion=6, runId=`run-round6-20261014-0826`. Status ready_for_review khớp control. SHA256 của cả 9 files trong ROUND_6_MANIFEST.json khớp trước và sau kiểm tra. Codex chỉ đọc/chạy checks và viết tài liệu/repro; không sửa application source.

## Phần đã đạt

Home, Detail và Profile đã dùng shared backend catalog client, bỏ local fixture làm nguồn production. Animation constraint ở Home/Search, literal detail ID comparison và strict numeric URL parsing được giữ. Placeholder cho media thiếu, 404 khác lỗi mạng, các consumer Detail/Profile của M1 vẫn qua regression tests.

## Findings cần xử lý chung trong vòng 7

### D1 — P2: Main detail bị chặn bởi request similar tùy chọn

`frontend/app/movies/[id]/page.tsx:41–73`: sau khi lookup chính trả valid movie, route chỉ gọi `setLoading(false)` sau `await browseCatalog` của similar rail. Render toàn trang dựa trên `loading`, nên cả tiêu đề, nút lưu và chấm điểm tiếp tục bị skeleton che dù dữ liệu chính đã có. Nếu similar service chậm, người xem phải chờ thêm đến timeout mặc định 7000ms. Catch không làm mất movie nhưng vẫn buộc người dùng chờ.

Actual production component repro: lookupResolved=true, mainDetailVisible=false trong khi similar promise pending; chỉ sau khi similar resolve mới có MovieDetail. Cho phép render nội dung chính ngay khi lookup chính thành công, quản lý loading/error của similar riêng; cancellation hoặc kết quả similar cũ không được đổi trạng thái request chính. Không cần sửa Next routing hay làm lại UI.

### D2 — P2: Hero chưa bảo toàn ngữ nghĩa uncertain/retry của M1

`frontend/features/home/components/EditorialHero.tsx:11–13,79–94`: nút chỉ dùng `isWatchlisted`, không đọc pending/uncertain/intent. Với ADD đã cập nhật lạc quan nhưng mất response, Hero hiện **Đã lưu Watchlist**, aria-label **Xóa khỏi Watchlist**. Provider thực tế bảo toàn ý định ADD và lần bấm tiếp sẽ retry POST. Như vậy nhãn hành động ngược với request và trạng thái chưa xác nhận lại bị trình bày như đã lưu xong. DELETE bất định gặp vấn đề tương ứng. Đây là entry point trong scope Home cutover và M2 yêu cầu giữ M1 tại cả Hero.

Áp dụng selectors và nhãn retry đúng ý định tương tự MovieCard, disable/pending feedback hợp lý; không thay đổi state machine WatchlistProvider. Test phải chạy Hero thực cùng provider hoặc transport thực giả lập, gồm ADD/DELETE mất response và trở lại toggle bình thường sau confirmed.

### D3 — P2: Profile có đường vòng bỏ qua TTL metadata

`frontend/features/profile/components/ProfileOverview.tsx:141–155`: Map công khai có expiresAt, nhưng `remoteMovies` lưu found không thời hạn. Missing check chỉ xét tồn tại key; resolveMovieItem trả remote found ngay cả khi Map đã hết hạn. Repro: hydrate X một lần; clock tiến 6 phút; bỏ X rồi thêm lại trong cùng component; API lần sau sẽ trả 404 nhưng không được gọi, UI vẫn hiện Old title, calls=1. Dữ liệu cũ có thể sống suốt phiên và không phát hiện phim đã gỡ. `remoteMovies` cũng giữ mọi ID từng nạp qua các thay đổi thư viện.

Làm policy expiry/invalidation có hiệu lực cho cả nơi đọc metadata; revalidate khi item được truy cập lại sau TTL hoặc trigger refresh được đặc tả. Có giới hạn/cleanup state metadata đã rời thư viện, tránh fetch loop; không yêu cầu polling nền hay xóa library IDs. Kiểm thử fake clock và 200→404/200→network error sau expiry; lỗi mạng không gỡ dữ liệu thư viện hoặc giả 404.

## Bằng chứng độc lập

- `node --test tests/search_experience_suite.mjs tests/catalog_service_suite.mjs tests/m1_behavior_suite.mjs tests/m2_journey_suite.mjs`: **51/51 pass**, exit 0.
- `frontend/node_modules/.bin/tsc.cmd --noEmit`: exit 0.
- `npm run build`: exit 0, generated 7/7; first-load JS Home 138kB, Detail 139kB, Profile 138kB, Search 137kB. Đây là output build, không phải benchmark trải nghiệm người xem.
- `node docs/reviews/repro/ROUND_4_search_repro.cjs`: 3 scenarios giữ kết quả đúng.
- `git apply --numstat docs/reports/ROUND_6.patch` và `git apply --reverse --check docs/reports/ROUND_6.patch`: exit 0, đúng 9 files.
- `node docs/reviews/repro/ROUND_6_cutover_repro.cjs`: tái hiện cả D1/D2/D3 bằng production TSX qua hook adapter. Exit 0 của script này nghĩa là **tái hiện được lỗi hiện tại**, không phải sản phẩm đạt. Không sửa script reviewer để lấy pass sau khi fix; thêm regression assertions mong đợi vào test suite sản phẩm.
- Backend không đổi trong patch, không rerun; 17/17 Spring tests là prior evidence từ Round 3, không phải kết quả chạy mới.

## Giới hạn và phần gate M2 chưa hoàn tất

Hook adapter/component tests có mock Next Image/router và API; không phải React DOM/browser/E2E. Không có walkthrough browser mới trong vòng review này. Không xác nhận runtime chuyển dynamic route A→B giữ cùng component; không dùng giả định này làm finding. D1 được xác nhận bằng chờ similar ngay trên một lần load detail, không phụ thuộc giả định remount.

Test journey số 5 hiện truyền cùng movie fixture vào ba harness riêng. Nó xác minh ID/metadata rendering, **chưa** chạy Home→save/rate→provider persist→reload Profile theo yêu cầu prompt. Cần bổ sung lát cắt đó bằng production provider và transport lưu trữ fixture riêng, cùng browser evidence desktop/mobile khi công cụ cho phép.

Chưa có animation import manifest/preview hoặc provenance bàn giao trong Round 6. Full M2 cần ghi gap catalog backend đang seed fiction và chuẩn bị additive/idempotent dry-run từ repository fixture; tuyệt đối không tự ghi DB live hoặc nhập các đường video giả/stock photo như media đúng tác phẩm. Đây là phần milestone còn lại, không phải yêu cầu xây ETL/microservice mới.

Automation vẫn tắt. Prompt vòng 7 được giao thủ công, không polling hoặc tự khởi động Antigravity.
