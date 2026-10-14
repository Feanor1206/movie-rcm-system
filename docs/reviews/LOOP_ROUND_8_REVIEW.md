# Round 8 — Independent Codex review

Ngày 2026-10-14. **REQUEST CHANGES: browser verification gate chưa đạt; chưa đóng M2, chưa M3.**

Checkpoint roundId=8 / promptVersion=8 / runId=run-round8-20261014-0925 khớp control/status. 18 SHA256 entries khớp trước/sau review. Patch numstat/reverse check exit 0. Không sửa application code; không chạy lại walkthrough đang ghi đè artifacts frozen.

## Phần được công nhận

Codex chạy bốn frontend suites: **54/54 PASS**, TypeScript exit 0, preview --test 3/3 PASS. Component click journey đã gọi Hero/MovieDetail onClick với production provider và kiểm tra POST bodies/reload provider. Hero uncertain ADD/DELETE integration dùng provider thực và transport lỗi/recovery đạt. Đây là component/provider integration qua hook adapter, không phải DOM/browser E2E. Preview docs đã phân biệt baseline hardcoded với live catalog/importer.

Không đổi application source vòng này, không build lại; prior production build pass từ Round 7. Không rerun backend; 17/17 vẫn là prior evidence.

## Findings

### B1 — P1: Browser evidence contradicts acceptance report; harness tự báo pass khi UI chưa hoạt động

Codex đã mở trực tiếp PNG 01,03,04,10. 01/10 chỉ có HTML chưa có styling, không có Hero/catalog. 03/04 chỉ có navbar/footer, không có nội dung phim, stars hoặc saved state. Báo cáo lại mô tả theme xanh lá, phim load, lưu/chấm điểm và uncertain badge thành công.

Các nhóm **byte-identical SHA256** từ manifest:

- 01_home_desktop = 09_catalog_error_desktop = 10_hero_uncertain_retry_desktop.
- 03_detail_desktop = 04_detail_saved_rated_desktop = 07_detail_404_desktop.
- 06_search_deep_link_back_desktop = 08_search_empty_desktop.

Hash giống nhau không tự chứng minh lỗi, nhưng ở đây ảnh trực tiếp không chứa trạng thái được mô tả. Các đoạn `observations.push({obs: ...})` trong scripts/run_browser_walkthrough.cjs gán mô tả thành công cố định, không đọc/assert DOM hoặc backend state. Dòng 469/471/546 chỉ `if (button) click()`: thiếu nút vẫn tiếp tục, cuối script vẫn in “captured and verified successfully”. `evaluate()` bỏ qua exceptionDetails; wait cố định không xác minh readiness. `history.back()` xong lại navigate mới trước chụp, không assert trạng thái sau Back.

Không dùng bộ 14 ảnh này làm bằng chứng nghiệm thu. Giữ artifact lịch sử và đánh dấu rejected; vòng sau chụp mới, không sửa ảnh bằng công cụ đồ họa. Walkthrough phải fail khi selector mất, CSS/JS không load, runtime exception, postcondition hoặc request/state không khớp; observations phải xuất từ assertions đã chạy, không từ ý định thao tác. Một ảnh chụp thành công không chứng minh tính năng chạy thành công.

### B2 — P2: Setup browser không đủ assets/auth để kiểm chứng luồng đã tuyên bố

`scripts/run_browser_walkthrough.cjs:250–280` khởi động `.next/standalone/server.js` nhưng không chuẩn bị `.next/static`/public cho standalone. Kiểm tra filesystem: frontend/.next/static tồn tại; frontend/.next/standalone/.next/static **không tồn tại**. Đây là nguyên nhân có khả năng cao khiến ảnh mất CSS/client hydration; cần kiểm chứng bằng response asset/network log trong lần chạy mới, không chỉ suy luận.

Fixture server hiện không có /api/auth/login hoặc /api/auth/me, script không thực hiện đăng nhập hay thiết lập session test. Ảnh còn hiển thị Đăng nhập và thư viện khách rỗng. Provider ở guest mode ghi local storage, không gửi account write tới fixture; cờ writeDrop/reconcileError không đủ tạo uncertain account mutation. Vì vậy browser account persist/reload/uncertain chưa được test.

Thêm fixture auth/verified session qua production AuthProvider và xác nhận actor authenticated trước thao tác account. Dùng API/ports/bundle đúng fixture, không dịch vụ live. NEXT_PUBLIC_* runtime env của standalone không bảo đảm đổi endpoint đã inline khi build: xác minh URL request thực tế hoặc chuẩn bị test build đúng cấu hình. Thiết lập assets đầy đủ, fail khi CSS/chunk 404 hoặc sai process/port. Không kill/reuse service người khác khi port bận.

### B3 — P2: Canonical-ID isolation claim sai và rating Profile chưa được assert ở UI

`frontend/tests/m2_journey_suite.mjs:1077` gọi the-last-orbit là ngoài local fixture, nhưng `frontend/lib/data/movies.ts:7` đã có chính ID này. Test thay metadata thành year2024/rating8.4/Animation, khác record repository year2026/rating8.7/Sci-Fi,Drama. Có thể dùng movie giả trong test, nhưng không được gọi đó là record backend thật hoặc ID ngoài fixture. Dùng ID riêng như m2-browser-only-001, assert ID không có trong local fixture, ghi rõ synthetic test fixture.

Test 7 xác nhận provider.getRating=9 và Profile card year, nhưng không mở tab Đánh giá/assert điểm 9 hiển thị trong Profile. Thêm click tab và assert score/action ở component/browser sau reload; giữ những integration assertions đã có.

## Giới hạn và kết luận

Không chạy script walkthrough vì output sẽ ghi đè các ảnh đang frozen và setup chưa bảo đảm isolation. Source/component changes tiến bộ, không có production application regression mới được xác nhận. Finding B1 là lỗi verification/report, không phải kết luận có chủ ý làm giả. Toàn bộ browser observations hiện bị bác bỏ cho gate M2 cho tới khi có assertions/log/ảnh đúng trạng thái.

Round 9 chỉ sửa harness/tests và bằng chứng, không đổi theme/kiến trúc/M1/AI. Tự động theo dõi tiếp tục tắt. Snapshot Git có thể push để lưu checkpoint nhưng không đồng nghĩa accepted/deployed.
