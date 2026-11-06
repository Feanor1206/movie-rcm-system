# UX-01A — Review source và giao diện thực tế

Ngày: 13/10/2026. Codex là kỹ sư trưởng review; không sửa mã ứng dụng. **Verdict: changes requested**, với bốn nhóm findings có scope sửa nhỏ tại `docs/prompts/UX-01A-F01_GEMINI_PROMPT.md`.

## 1. Bằng chứng đã kiểm tra độc lập

- `frontend/node_modules/.bin/tsc.cmd --noEmit`: exit 0.
- `npm run build` tại frontend: exit 0, Next 15.1.2 compile/prerender thành công.
- `git apply --numstat docs/reports/UX-01A.patch` và `git apply --reverse --check`: exit 0; patch 18 files khớp source.
- Khởi chạy frontend review tạm trên loopback :3100 bằng production build, không khởi chạy backend/model. Đã dừng process review và đóng tab sau kiểm tra.
- Browser kiểm tra home, Animation search, Spirited Away detail và mở CineBot, không gửi query/model inference hoặc login.
- Viewport 360×800 và 768×1024: document scrollWidth bằng clientWidth (354 và 762 do scrollbar); không horizontal overflow trên home. Detail tại 768 cũng không overflow.
- Desktop 1440×900: watchlist card Isle of Dogs thao tác bằng Enter; Fantasia bằng pointer; label/count cập nhật và URL vẫn ở home, không bị link overlay chuyển trang.
- Home heading nhu cầu ở y=509 tại mobile 360×800; đường khám phá hiện trong viewport đầu. Theme xanh lá và surface hierarchy đã thể hiện trong browser.
- Ảnh thật: `docs/reviews/screenshots/UX-01A-mobile.jpg`, `UX-01A-desktop.jpg`, `UX-01A-detail.jpg`.

Hai thao tác lưu diễn ra trên guest localStorage của origin review :3100, không có token/account và không ghi DB. Không xóa hoặc migrate dữ liệu tài khoản thật. Không chạy lại backend suite vì patch chỉ frontend và serving đã được nghiệm thu ở F02.

## 2. P2 — Foreground trắng trên brand xanh không đủ tương phản

`frontend/app/globals.css:78` sử dụng bg-brand/text-white cho button text-sm. Brand #10b981 có contrast với #ffffff khoảng **2,54:1**. Browser computed style trên hero CTA xác nhận rgb(16,185,129)/rgb(255,255,255), font 12px.

Đây là text chức năng nhỏ, thấp hơn 4,5:1 của [WCAG Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html). Small badges, selected chips/chat bubbles và card overlay cũng cần kiểm tra foreground trên brand tương tự. Giữ tone xanh lá; chỉnh button surface hoặc semantic on-brand color và đo default/hover/selected/active.

## 3. P2 — Copy thay tuyên bố thiếu dữ liệu bằng tuyên bố khác

- `frontend/features/movies/components/MovieDetail.tsx:135,298,303` hiển thị HD / phụ đề / lồng tiếng / đa kênh cho mọi phim. Movie type/catalog không có các fields edition/media tương ứng. Bỏ 4K rồi đổi sang HD không làm thông tin thành factual. Browser detail xác nhận những nhãn này đang hiển thị.
- `frontend/app/page.tsx:21–26,170–171` lấy mọi Animation có Family **hoặc** Fantasy **hoặc** Adventure rồi gọi là “ấm áp, phù hợp xem cùng người thân”. Tập hợp hiện bao gồm Coraline/Horror; genre không chứng minh tone ấm áp hoặc phù hợp mọi đối tượng. Đổi nhãn trung tính theo dữ liệu, không cần sửa engine phân loại.
- Quick pathway hứa tìm theo cảm xúc/thời lượng dù chưa có acceptance cho các facets đó. Dùng copy mô tả capabilities hiện có đã kiểm chứng (query/film reference/genres/year), không mở ticket xây facets trong patch này.
- Header CineBot vẫn đưa “Qwen Phase23 5-Stage Personalized Animation Discovery” và welcome Phase23 vào user flow. Thay bằng tên trợ lý và khả năng trung thực; giữ handlers/payload/pipeline nguyên vẹn.

## 4. P2 — Đổi defaults dữ liệu cá nhân ngoài phạm vi visual

`frontend/lib/context/WatchlistContext.tsx:52–58` đổi default watchlist/favorite/rating sang Spirited Away/Your Name, gồm rating 10. Patch đã thay behavior/state chứ không chỉ styling. Browser detail hiển thị “Bạn đã chấm ... 10/10” dù lượt review không chấm phim.

Yêu cầu UX-01A-F01: revert đúng ba changes defaults về baseline trước UX-01A, giữ theme toast. Không refactor library hoặc tự clear/migrate saved storage. Default demo data đã có từ trước là vấn đề riêng phải xử lý trong LIB-01; revert ở đây không đồng nghĩa nghiệm thu library truthfulness.

New similarMovies sorting tại app/movies/[id]/page.tsx cũng là thay đổi selection logic ngoài scope visual. Revert hunk này về baseline; cải tiến similarity được giao ticket riêng có criteria/metrics.

## 5. P2 — Empty animation catalog vẫn render fiction hero

`frontend/lib/data/movies.ts:153` dùng `animationMovies[0] || movies[0]`, trong khi home render EditorialHero vô điều kiện tại line 45. Nếu không còn Animation record nhưng còn demo cinema, hero vẫn gắn nhãn “Hoạt hình tiêu điểm” cho phim ngoài domain.

Trường hợp này được xác định từ source, chưa mutate live catalog để tái hiện. Cần render hero khi có animation item và empty state thực khi không có. Không fallback sang fiction/demo; navigation và CineBot trigger vẫn dùng được. Không thay IDs/records production để tạo fixture.

## 6. Limits của review

- Đã kiểm tra routes/card/keyboard focus theo walkthrough, không phải audit accessibility đầy đủ.
- Không kiểm tra đăng nhập, media playback, model responses, reduced-motion OS preference hoặc account synchronization. Không coi đó là accepted từ build pass.
- Không giữ server/tab review chạy sau lượt này. Ảnh chụp là trạng thái thực của frontend tại thời điểm review.
- UX-01A chưa accepted; chỉ thực hiện follow-up nhỏ, giữ phần xanh lá/layout/card stacking đã làm tốt.
