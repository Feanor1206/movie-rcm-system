# UX-01A — Giao diện xanh lá và trang chủ khám phá hoạt hình

Áp dụng `docs/prompts/GEMINI_ENGINEERING_RULES.md`. SERVE-01-F02 đã accepted; không làm lại serving. Chỉ thực hiện UX-01A rồi bàn giao Codex review.

## 1. Mục tiêu người dùng

Cải tiến frontend đã có thành website khám phá hoạt hình tone xanh lá, nhẹ nhàng, dễ bắt đầu và có nội dung trung thực. Giữ các luồng hiện hữu hoạt động. Đây là ticket visual/copy/navigation của bản hiện tại; không xây lại frontend, backend, catalog hoặc recommender.

## 2. Đọc source trước khi sửa

- `docs/USER_EXPERIENCE_BLUEPRINT.md`, `docs/ENGINEERING_EXECUTION_PLAN.md`.
- `frontend/package.json`, `tailwind.config.ts`, `app/globals.css`, `app/layout.tsx`, `app/page.tsx`.
- `frontend/components/layout/Navbar.tsx`, `Footer.tsx`.
- `frontend/features/home/components/EditorialHero.tsx`.
- `frontend/features/movies/components/MovieCard.tsx`, `MovieSection.tsx`.
- Current catalog `frontend/lib/data/movies.ts`; hiện có cả demo cinema và phim animation. Kiểm tra actual records trước khi chọn home content.
- Các consumers của color tokens trong search/detail/profile/auth/chat, cùng handlers navigation hiện hữu.

Ghi baseline branch/status, giữ changes có sẵn. Không nhận các changes serving/frontend trước đó là patch của lượt này.

## 3. Phạm vi

- Design tokens, styling, typography, spacing, metadata/copy nhận diện animation.
- Home layout và shared Navbar/Footer/MovieCard/MovieSection/Hero.
- Styling consumers trên các trang/modal hiện có chỉ khi cần để theme mới nhất quán; không đổi business handlers/state/API.
- Có thể thêm component nhỏ thuộc home để giữ code dễ đọc.
- `docs/reports/UX-01A_REPORT.md`, ảnh evidence nếu môi trường cho phép và patch riêng có baseline.

Không sửa FastAPI/Spring/database/AI artifacts. Không đổi auth/storage/API contracts, không cài framework/design library mới, không thêm media hosting/player mới, không sửa records catalog để bịa metadata. Không mở rộng UX-01A thành cả discovery/onboarding/library implementation.

## 4. Yêu cầu giao diện

### Màu và độ dễ đọc

- Xanh lá là brand primary; nền trung tính dịu, surface và typography có hierarchy rõ. Chọn palette thống nhất và ghi tokens/hex trong report.
- Primary/hover/selected/focus states dùng xanh lá; error/warning vẫn có semantic color/label riêng.
- Giảm cách trình bày đen/đỏ cinema hiện hữu, tránh neon/glow mạnh và trang trí gây phân tâm.
- Dùng semantic tokens `brand`, `background`, `surface`, `foreground`, `muted`, `border`, `danger` hoặc tương đương; không replace mọi màu đỏ thành xanh vì đỏ lỗi có ý nghĩa riêng.
- Có thể giữ alias cinema-red trong giai đoạn chuyển đổi để compatibility, nhưng các components đã sửa dùng tên token có ngữ nghĩa mới. Không để một phần brand đỏ một phần xanh trên cùng flow.
- Giữ focus-visible, reduced-motion và text contrast dễ đọc. Không đổi font/dependency chỉ vì sở thích cá nhân.

### Home và định vị animation

- Heading rõ như “Hôm nay bạn muốn xem phim hoạt hình nào?”; nội dung tiếng Việt thân thiện, ngắn và không đưa tên model/pipeline lên user flow.
- Hero không chiếm phần lớn màn hình mobile khiến người dùng phải cuộn mới bắt đầu được; khu vực khám phá/CTA phải thấy sớm.
- CTA dẫn đến chức năng hiện có: khám phá catalog/search hoặc mở CineBot hiện hữu. Kiểm tra path/handler thật; không thêm nút mood/compare/onboarding không hoạt động.
- Có thể trình bày tối đa vài lối bắt đầu: khám phá hoạt hình, tìm qua mô tả bằng CineBot, xem danh sách đã lưu. Chỉ dùng nhãn phản ánh capability thực; không tuyên bố tìm đúng title/personalization đã nghiệm thu nếu chưa có bằng chứng.
- Home animation sections lấy các records `genres` chứa Animation từ catalog hiện hữu. Giữ ID để detail/watchlist tiếp tục hoạt động. Không dùng phim demo không phải animation làm hero của bản animation.
- Không gọi reverse(movies) là “dành riêng cho bạn”, không gọi static catalog là “thịnh hành hôm nay”. Đổi thành nhãn thật như “Khám phá hoạt hình” hoặc “Điểm nguồn hiện có”; thiếu rating source thì đừng tạo tên nguồn/vote count. Rails phải có mục đích khác nhau và hạn chế lặp khi catalog đủ.
- Bỏ các nhãn 4K/HDR/Dolby trong hero/shared copy nếu dữ liệu không có. Link đi tới detail dùng “Xem chi tiết”, không ngụ ý đang cung cấp full movie playback.
- Không thêm autoplay audio/video hoặc tự gửi query/load AI khi vào home. Poster dùng assets hiện có; missing ảnh có fallback trung thực, không bịa poster/trailer mới.

### Tương tác và khả năng dùng

- Watchlist button trên card không bị link overlay che; hoạt động bằng pointer/keyboard. Nếu cần sửa stacking/z-index của shared card trong scope UI, ghi rõ.
- Navbar/search/navigation/modal triggers hiện hữu tiếp tục hoạt động; keyboard focus thấy được và icon-only buttons có accessible name.
- Không phụ thuộc hover để người dùng mobile tìm được hành động chính.
- Layout không horizontal overflow tại khoảng 360px, 768px và desktop 1440px.
- Empty animation list xử lý thật, không tự fallback sang fiction demo và gọi là animation.

## 5. Tiêu chí nghiệm thu

1. Home nhận diện hoạt hình và xanh lá rõ; palette/token hierarchy nhất quán ở shared components và các consumers đã chỉnh.
2. Guest vào trang có đường khám phá hoạt động, không bị ép login hoặc tự gọi AI.
3. Home sử dụng animation records thực trong catalog hiện hữu; detail IDs/watchlist handlers không bị đổi.
4. Không còn personalized/trending/4K claims giả trong phần home/shared UI đã sửa.
5. Primary action thấy sớm trên mobile; card CTA và watchlist có thể thao tác bằng touch/keyboard.
6. Navigation/search/chat/auth/profile hiện hữu không bị regression do theme; error color còn phân biệt đúng.
7. TypeScript check pass. Production build được kiểm tra nếu môi trường cho phép; ghi đúng lỗi baseline/environment nếu không chạy được, không báo pass giả.
8. Có evidence desktop/mobile, keyboard walkthrough và reduced-motion kiểm tra. Nếu chưa visual-verify, ghi chưa kiểm tra; không nhận UX đã accepted chỉ vì TypeScript pass.

Không viết tests chỉ để assert CSS classes hoặc text literal. Dùng meaningful behavior checks hoặc walkthrough cho các thay đổi tương tác, cùng visual QA.

## 6. Bàn giao

- Before/after summary và files/hunks thực của lượt này.
- Palette tokens và lý do bố cục phục vụ nhu cầu người dùng.
- Screenshots mobile/desktop khi có công cụ; không dựng ảnh giả làm screenshot ứng dụng.
- Exact commands/results, navigation/card/modal walkthrough và limitations.
- `docs/reports/UX-01A_REPORT.md` và patch độc lập hợp lệ khi có before snapshot.
- Không commit/push, không chuyển ticket tiếp theo; dừng ready for review.

Codex nghiệm thu UI/source/evidence. Ticket này chỉ cải tiến UX hiện có; không tuyên bố đã hoàn thành các AI capabilities hoặc library fixes ngoài phạm vi.
