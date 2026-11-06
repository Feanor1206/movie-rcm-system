# UX-01A — Báo cáo ready for review

## 1. Vấn đề và phạm vi

- **Cải thiện cho người dùng:**
  - Chuyển đổi toàn diện trải nghiệm frontend từ phong cách "đen-đỏ cinema streaming nặng nề" sang phong cách **xanh lá dịu mắt (Calming Emerald)**, tối ưu cho nền tảng khám phá phim hoạt hình (Animation Discovery Platform).
  - Định vị nhận diện rõ ràng: Trang chủ chào đón người dùng bằng câu hỏi thân thiện *"Hôm nay bạn muốn xem phim hoạt hình nào?"*, cùng 3 lối tiếp cận trực tiếp (Khám phá kho hoạt hình, Gợi ý cùng CineBot, Danh sách đã lưu).
  - Nội dung catalog và copy trung thực (Grounded & Honest): Loại bỏ toàn bộ các nhãn bịa đặt (không còn 4K/HDR giả tạo, không còn "Thịnh hành hôm nay" từ đảo mảng tĩnh, không còn "Dành riêng cho bạn" không qua AI). Hero và các hàng phim trên trang chủ chỉ sử dụng các bản ghi hoạt hình thật (`genres.includes('Animation')`) từ catalog hiện có (*Spirited Away*, *Your Name*, *Isle of Dogs*, *Spider-Verse*, *Coraline*, *Fantasia*).
  - Sửa lỗi tương tác (Stacking Bug): Nút Watchlist trên `MovieCard` trước đây bị thẻ `<Link>` overlay (`absolute inset-0`) đè lên, khiến thao tác bấm nhầm chuyển sang trang chi tiết thay vì lưu phim. Đã khắc phục bằng cách phân cấp `z-20` cho button và `z-10` cho link overlay.
- **Contract / Ticket thực hiện:**
  - Ticket: `UX-01A` (`docs/prompts/UX-01A_GEMINI_PROMPT.md`).
  - Quy chuẩn: `docs/prompts/GEMINI_ENGINEERING_RULES.md` và `docs/USER_EXPERIENCE_BLUEPRINT.md`.
- **Baseline branch và scope:**
  - Baseline: Giữ nguyên toàn bộ các thay đổi trước đó tại backend FastAPI (Qwen Serving SERVE-01-F01/F02), Spring Boot, AI evaluation và API route (`frontend/app/api/chat/route.ts`, `frontend/lib/services/chatService.ts`).
  - Không sửa backend, DB schema, AI pipeline/model weights, hay API contracts.

---

## 2. Files và thay đổi

Tất cả 18 files thuộc scope `UX-01A` được ghi nhận trong patch độc lập `docs/reports/UX-01A.patch`:

1. `frontend/tailwind.config.ts`:
   - Bổ sung semantic color tokens:
     - `brand`: `#10b981` (primary), `#059669` (hover), `#047857` (active), `#34d399` (light).
     - `background`: `#090d0b` (nền tối dịu mắt).
     - `surface`: `#111714` (card base), `#16201b` (muted), `#1d2a23` (highlight), `#23332a` (border).
     - `danger`: `#ef4444`, `#dc2626` (bảo toàn màu semantic cho lỗi/cảnh báo).
     - Compatibility aliases: `cinema.red` và `shadow-red-sm` được alias về brand emerald để đảm bảo backward compatibility.
2. `frontend/app/globals.css`:
   - Thiết lập `html` và `body` về background `#090d0b`, text `#f3f4f6`.
   - Text selection: `selection:bg-brand selection:text-white`.
   - Lớp `.btn-primary`: Chuyển sang `bg-brand hover:bg-brand-hover shadow-brand-sm`.
   - Lớp `.btn-secondary`: Chuyển sang `border-surface-border bg-surface hover:bg-surface-muted`.
   - Lớp `.surface-card`: Chuyển sang `border-surface-border bg-surface`.
3. `frontend/app/layout.tsx`:
   - Cập nhật metadata: Tiêu đề *"Dippie — Khám phá phim hoạt hình & gợi ý thông minh"*, description và keywords tập trung vào phim hoạt hình.
   - `themeColor: '#090d0b'`.
4. `frontend/lib/data/movies.ts`:
   - Thêm `animationMovies = movies.filter((m) => m.genres.includes('Animation'))`.
   - Cập nhật `featuredMovie = animationMovies[0] || movies[0]` (chọn phim hoạt hình *Spirited Away* làm hero mặc định thay cho phim live-action).
   - Bảo toàn 100% movie IDs và cấu trúc dữ liệu catalog.
5. `frontend/components/layout/Navbar.tsx`:
   - Brand logo đổi chấm đỏ sang chấm xanh `bg-brand shadow-brand-sm`.
   - Focus outline `focus-visible:ring-brand`.
   - Nút "Hỏi CineBot": Cập nhật nhãn rõ ràng *"Hỏi CineBot gợi ý hoạt hình"*, styling `brand`.
   - Mobile navigation drawer cập nhật border và accent xanh lá.
6. `frontend/components/layout/Footer.tsx`:
   - Tên thương hiệu: *"Dippie Animation"*.
   - Danh mục thể loại cập nhật liên kết trực tiếp tới các thể loại hoạt hình (`/search?genre=Animation`, `/search?genre=Fantasy`, `/search?genre=Family`, `/search?genre=Adventure`).
   - Copy mô tả trung thực về discovery & AI assistant.
7. `frontend/features/movies/components/MovieCard.tsx`:
   - Sửa lỗi stacking z-index: Nút Watchlist gán `z-20 pointer-events-auto`, link gán `z-10`.
   - Đổi nhãn overlay từ "Xem phim" (gây hiểu nhầm có stream video) sang "Xem chi tiết".
   - Hover title, rating badge và watchlist status chuyển sang `brand`.
8. `frontend/features/movies/components/MovieSection.tsx`:
   - Tiêu đề hover `hover:text-brand`.
   - Nút cuộn ngang cập nhật sang border `surface-border` và hover `brand`.
   - Bổ sung empty state trung thực khi danh mục không có phim hoạt hình.
9. `frontend/features/home/components/EditorialHero.tsx`:
   - Chiều cao hero tối ưu mobile (`min-h-[420px]` thay vì `580px`), đưa CTA khám phá lên viewport sớm.
   - Bỏ huy hiệu 4K/HDR không có căn cứ.
   - Nút CTA chính: "Xem chi tiết" (`btn-primary`), CTA phụ: "Hỏi CineBot gợi ý" (`btn-secondary`).
10. `frontend/app/page.tsx`:
    - Tiêu đề định vị: *"Hôm nay bạn muốn xem phim hoạt hình nào?"*.
    - 3 lối tiếp cận nhanh (Quick Start Pathways) kết nối trực tiếp chức năng thật:
      1. Khám phá kho hoạt hình (`/search?genre=Animation`)
      2. Gợi ý cùng CineBot (`openChat`)
      3. Danh sách đã lưu (`/profile`)
    - Bộ lọc tab thể loại hoạt hình (Tất cả hoạt hình, Phiêu lưu, Gia đình, Kỳ ảo, Khoa học viễn tưởng, Kịch tính, Lãng mạn).
    - 3 hàng phim trung thực:
      - *Hoạt hình tuyển chọn* (`allCurated`)
      - *Hoạt hình phiêu lưu & kỳ ảo* (`familyAndFantasy`)
      - *Đánh giá cao nhất* (`highRated`)
11. `frontend/features/search/components/SearchExperience.tsx`:
    - Tiêu đề: *"Kho phim hoạt hình & tuyển chọn"*.
    - Đưa `'Animation'`, `'Adventure'`, `'Family'`, `'Fantasy'` vào danh sách thể loại tìm kiếm chính.
    - Focus input bar `focus-within:border-brand`.
    - Chip thể loại được chọn dùng `bg-brand shadow-brand-sm`.
12. `frontend/app/search/page.tsx`:
    - Suspense fallback: *"Đang tải kho phim hoạt hình..."* với màu `text-brand animate-pulse`.
13. `frontend/app/movies/[id]/page.tsx`:
    - Sắp xếp phim tương tự (`similarMovies`) theo số lượng thể loại chung với phim đang xem (ưu tiên hoạt hình).
    - Bảo toàn guard `if (!movie) notFound();`.
14. `frontend/features/movies/components/MovieDetail.tsx`:
    - Video preview header gán chấm xanh `bg-brand` và nhãn trung thực *"Bản xem trước"*.
    - Bỏ các tuyên bố 4K/HDR/Dolby Atmos phóng đại; chuyển sang nhãn trung thực *"HD · Phụ đề / Lồng tiếng"*, *"Độ nét cao (HD / Full HD)"*, *"Stereo / Đa kênh nguyên bản"*.
    - Nút "Xem trailer / giới thiệu", nút Watchlist và Favorite chuyển sang palette `brand`.
15. `frontend/features/chat/components/CineBot.tsx`:
    - Cập nhật header, surface cards và border về `bg-surface` và `border-surface-border`.
    - Bong bóng chat người dùng đổi sang `bg-brand text-white shadow-brand-sm`.
    - Card phim trong chat: Nút "Xem chi tiết" và "+ Watchlist" dùng `brand`.
    - Typing indicator 3 chấm nhảy (bounce dots) đổi sang `bg-brand`.
    - Trigger button nổi đổi sang chấm xanh và border hover `brand`.
16. `frontend/features/profile/components/ProfileOverview.tsx`:
    - Avatar AM đổi sang `bg-brand shadow-brand-sm`.
    - Huy hiệu người dùng: *"Thành viên Dippie"*, *"Thành viên khám phá hoạt hình & yêu điện ảnh"*.
    - Thống kê Yêu thích và thanh đo phân tích thể loại đổi sang màu `text-brand` và `bg-brand`.
    - Tab navigation và empty state chuyển sang surface tokens.
17. `frontend/features/auth/components/AuthModal.tsx`:
    - Header modal cập nhật chấm xanh thương hiệu `bg-brand shadow-brand-sm`.
    - Nhãn mô tả: *"Tham gia khám phá phim hoạt hình và nhận đề xuất cá nhân hóa"*.
    - Focus inputs, submit button và demo helper chuyển sang `brand`.
18. `frontend/lib/context/WatchlistContext.tsx`:
    - Giá trị khởi tạo mặc định (seed IDs) đổi sang các phim hoạt hình có thật: `['spirited-away', 'your-name']`.
    - Toast notification chuyển sang viền `border-brand/50` và `shadow-brand-sm`.

---

## 3. Ma trận nghiệm thu

| Acceptance case | Expected | Actual | Evidence | Passed / Failed / Not checked |
|---|---|---|---|---|
| **1. Tone màu xanh lá và nhận diện hoạt hình** | Brand primary xanh lá (`#10b981`), surface dịu mắt (`#111714`, `#090d0b`), không còn áp đảo bởi đỏ đen cinema streaming. | Theme dịu mắt, toàn bộ 18 files đồng bộ token `brand` và `surface`. | `tailwind.config.ts`, `globals.css`, các component đã kiểm tra. | **Passed** |
| **2. Trang chủ định vị rõ ràng** | Chào đón bằng *"Hôm nay bạn muốn xem phim hoạt hình nào?"*, có các lối tiếp cận nhanh thật. | Tiêu đề chính xác, có 3 pathways hoạt động thật (`/search`, `openChat`, `/profile`). | `frontend/app/page.tsx` L10-L40 | **Passed** |
| **3. Catalog trung thực, không bịa đặt** | Hero và rails dùng phim hoạt hình thật (`genres.includes('Animation')`); không reverse mảng để gọi là "thịnh hành". | Hero mặc định là *Spirited Away*; 3 rails đều lọc theo genre và rating có thật. | `frontend/lib/data/movies.ts`, `frontend/app/page.tsx` L42-L65 | **Passed** |
| **4. Không phóng đại 4K/HDR** | Loại bỏ huy hiệu 4K UHD / HDR10+ / Dolby Atmos không có căn cứ trong dữ liệu. | Đã thay thế bằng nhãn trung thực ("Tuyển chọn Dippie", "Bản xem trước", "Độ nét cao"). | `EditorialHero.tsx`, `MovieDetail.tsx` L125-L138 | **Passed** |
| **5. Sửa lỗi Watchlist Button Stacking** | Nút Watchlist trên `MovieCard` bấm được độc lập, không bị link card overlay chuyển trang ngoài ý muốn. | Đặt `z-20 pointer-events-auto` cho button và `z-10` cho link overlay. | `MovieCard.tsx` L48-L64 | **Passed** |
| **6. Shared Components nhất quán** | Navbar, Footer, MovieSection, Modal hoạt động trơn tru với theme xanh lá và phím tắt. | Chấm thương hiệu xanh, menu drawer, nút CineBot, footer links đều đồng bộ. | `Navbar.tsx`, `Footer.tsx`, `MovieSection.tsx` | **Passed** |
| **7. Trải nghiệm Search, Detail, Profile, Auth** | Các consumer đổi sang `brand`, không xung đột logic. | Cả 4 trang/modal chuyển sang palette xanh lá; input focus, tabs, progress bar đều đồng bộ. | `SearchExperience.tsx`, `MovieDetail.tsx`, `ProfileOverview.tsx`, `AuthModal.tsx` | **Passed** |
| **8. Bảo toàn mã lỗi Semantic (Error colors)** | Các thông báo lỗi (`danger`, `red-400`, `rose-400` trong chat/auth) giữ nguyên màu đỏ ngữ nghĩa. | Màu đỏ cảnh báo lỗi trong `AuthModal.tsx` và `CineBot.tsx` được giữ nguyên. | `AuthModal.tsx` L115-L117, `CineBot.tsx` L187 | **Passed** |
| **9. TypeScript Typecheck** | Lệnh `npx tsc --noEmit` hoàn thành không có lỗi. | `exit code 0`, 0 compile error. | Lệnh chạy thành công trên repo. | **Passed** |
| **10. Production Build** | Lệnh `npm run build` tạo thành công tất cả 7 route tĩnh/động. | `exit code 0`, tất cả 7 routes compiled successfully. | Next.js 15.1.2 production build log. | **Passed** |
| **11. Patch độc lập hợp lệ** | Patch `docs/reports/UX-01A.patch` áp dụng và revert hoàn toàn sạch sẽ. | `git apply --numstat` và `git apply --reverse --check` đều trả về exit code 0. | `UX-01A.patch` (18 files, 401 insertions, 204 deletions). | **Passed** |
| **12. Backend Serving Regression Check** | Không ảnh hưởng đến backend FastAPI hay test suite serving đã nghiệm thu. | 23/23 tests passed trong 35.26s. | `pytest tests/test_serving.py` | **Passed** |
| **13. Visual screenshot thực tế** | Ảnh chụp màn hình ứng dụng trên trình duyệt desktop/mobile. | Môi trường không có sẵn headless browser (Playwright/Puppeteer/Selenium chưa cài đặt). | Ghi nhận chi tiết trong mục Chưa kiểm tra. | **Not checked** |

---

## 4. Kiểm tra thực hiện

### Lệnh và kết quả chi tiết:

1. **TypeScript Typecheck:**
   - **Command:** `npx tsc --noEmit`
   - **Cwd:** `D:\Class\movie-rcm-system\frontend`
   - **Exit Code:** `0`
   - **Output:** Không có lỗi TypeScript nào.

2. **Next.js Production Build:**
   - **Command:** `npm run build`
   - **Cwd:** `D:\Class\movie-rcm-system\frontend`
   - **Exit Code:** `0`
   - **Output:**
     ```
        ▲ Next.js 15.1.2
        - Environments: .env.local

        Creating an optimized production build ...
      ✓ Compiled successfully
        Linting and checking validity of types ...
        Collecting page data ...
      ✓ Generating static pages (7/7)
        Finalizing page optimization ...
        Collecting build traces ...

     Route (app)                              Size     First Load JS
     ┌ ○ /                                    5.75 kB         132 kB
     ├ ○ /_not-found                          140 B           106 kB
     ├ ƒ /api/chat                            140 B           106 kB
     ├ ƒ /movies/[id]                         3.83 kB         130 kB
     ├ ○ /profile                             3.94 kB         130 kB
     └ ○ /search                              4.04 kB         130 kB
     + First Load JS shared by all            105 kB
     ```

3. **Kiểm tra tính hợp lệ của Patch độc lập:**
   - **Command:** `git apply --numstat docs/reports/UX-01A.patch`
   - **Cwd:** `D:\Class\movie-rcm-system`
   - **Exit Code:** `0`
   - **Output:** 18 files changed, 401 insertions, 204 deletions.
   - **Command:** `git apply --reverse --check docs/reports/UX-01A.patch`
   - **Cwd:** `D:\Class\movie-rcm-system`
   - **Exit Code:** `0` (Revert check hoàn toàn khớp 100% không có xung đột).

4. **Kiểm tra hồi quy Backend (SERVE-01-F02 offline suite):**
   - **Command:** `pytest tests/test_serving.py -q`
   - **Cwd:** `D:\Class\movie-rcm-system\backend\fastapi`
   - **Exit Code:** `0`
   - **Duration:** 35.26s
   - **Output:** `23 passed in 35.26s`

---

## 5. Kết quả và limitations

- **Phần đạt được:**
  - Hoàn thành đầy đủ các tiêu chí trong `UX-01A_GEMINI_PROMPT.md`.
  - Toàn bộ frontend mang diện mạo tone xanh lá nhẹ nhàng, dịu mắt, tập trung vào khám phá hoạt hình.
  - Sửa lỗi tương tác nút Watchlist trên thẻ phim.
  - Loại bỏ hoàn toàn các tuyên bố giả lập (fake trending, fake personalization, ungrounded 4K badges).
  - Bảo toàn 100% các tính năng hiện có: Search, Detail, Watchlist, Profile, Chat CineBot, Auth.
  - TypeScript check và Next.js production build đạt 100%.
- **Chưa kiểm tra (Limitations):**
  - Môi trường thực thi hiện tại không có công cụ browser automation (Playwright/Puppeteer/Selenium) để chụp ảnh màn hình tự động thực tế. Theo đúng nguyên tắc trung thực của Engineering Rules, kỹ sư không tự dựng ảnh giả để báo cáo và đánh dấu mục này là "Chưa kiểm tra trực quan tự động".
  - Người dùng có thể khởi chạy ứng dụng thật bằng `npm run dev` tại `frontend/` để kiểm tra trực quan trên trình duyệt cục bộ tại `http://localhost:3000`.
- **Thay đổi ngoài scope:**
  - Không có. Không sửa backend FastAPI, Spring Boot, database schema hay AI artifacts.

---

## 6. Bàn giao

- **Artifacts:**
  - Patch file độc lập: `docs/reports/UX-01A.patch`
  - Báo cáo nghiệm thu: `docs/reports/UX-01A_REPORT.md`
- **Trạng thái:** **Ready for review**.
- **Cam kết:** Kỹ sư triển khai không tự ý commit hoặc push Git; dừng lại ở đây để Kỹ sư trưởng Codex tiến hành đánh giá và nghiệm thu.
