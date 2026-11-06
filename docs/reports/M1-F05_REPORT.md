# M1-F05 Engineering Implementation & Verification Report

> **Milestone Ticket:** M1-F05 (Follow-up to M1-F04)  
> **Repository:** `D:\Class\movie-rcm-system`  
> **Branch:** `chore/taicautruc`  
> **Status:** READY FOR REVIEW M1-F05  
> **Implementation Engineer:** Antigravity (Gemini)  
> **Lead Reviewer:** Codex  

---

## 1. Executive Summary

Milestone **M1-F05** resolves the final remaining P2 finding identified in Codex's independent review (`docs/reviews/M1-F04_REVIEW.md`):
- **Vấn đề cốt lõi (Core Finding):** Trong M1-F04, trạng thái bất định (`status: 'uncertain'`) và bảo toàn ý định retry (`desiredValue`) đã được hiện thực hóa ở tầng `WatchlistContext` và vượt qua các bài kiểm tra logic vận chuyển (transport/provider). Tuy nhiên, các consumers giao diện (`MovieCard`, `MovieDetail`, `ProfileOverview`) chưa trực tiếp tiêu thụ các bộ chọn trạng thái này, dẫn đến việc giao diện hiển thị nhãn theo trạng thái lạc quan (ví dụ: hiển thị "Xóa" nhưng click lại retry `POST`, hoặc hiển thị "Thêm" nhưng click lại retry `DELETE`).
- **Phạm vi giải quyết trọn vẹn tại M1-F05:**
  1. Mở rộng `WatchlistContext` với các helper selectors: `getActionIntent(id, action)` và `getUnconfirmedRating(id)` nhằm cung cấp cho UI consumers ý định thực sự của thao tác đang bất định (`'add' | 'remove' | 'rate' | 'remove_rating'`).
  2. Nối trực tiếp `isActionUnconfirmed` và `getActionIntent` vào `MovieCard`, `MovieDetail`, và `ProfileOverview`.
  3. Hiển thị huy hiệu trực quan bền vững `"Chưa xác nhận"` (`data-testid="unconfirmed-badge"`), tone màu cảnh báo hổ phách (`amber-400 / amber-500`), và biểu tượng xoay `<RefreshCw>`.
  4. Chuẩn hóa nhãn nút, `aria-label`, thuộc tính `title`, và handler click:
     - Tuyệt đối không hiển thị "Xóa" khi click sẽ retry `POST` (hiển thị `"Chưa xác nhận lưu • Thử lưu lại"`).
     - Tuyệt đối không hiển thị "Thêm" khi click sẽ retry `DELETE` (hiển thị `"Chưa xác nhận xóa • Thử xóa lại"`).
  5. Khu vực đánh giá (`MovieDetail`): Tách biệt rõ ràng giữa việc bấm thử lại điểm số đang bất định (banner `"Chưa xác nhận điểm X/10 ★"` kèm nút riêng `"Thử lưu lại"`) với việc người dùng chủ động chọn một ngôi sao mới.
  6. Trang cá nhân (`ProfileOverview`): Khi xảy ra lỗi nạp/hòa giải thư viện (`libraryError`), hiển thị banner cảnh báo bền vững `<div data-testid="library-error-banner">` ở phía trên kèm nút `"Thử tải lại"`, giữ nguyên vẹn dữ liệu thư viện bên dưới để người dùng tiếp tục xem và tương tác retry từng mục orphan/chưa xác nhận.
  7. Trở lại trạng thái toggle bình thường ngay khi thao tác retry được server xác nhận thành công hoặc background reconcile hòa giải xong.

Toàn bộ 24 bài kiểm thử hành vi frontend (bao gồm 4 bài kiểm thử actual consumer components mới), build production Next.js, kiểm tra kiểu dữ liệu TypeScript, và repro Codex F03 đều đạt kết quả 100% PASS.

---

## 2. Consumer Wiring & Interaction Matrix

| Consumer Component | Trạng thái / Trigger | Giao diện & Styling | Nhãn chữ, Icon & ARIA Attributes | Hành động mạng thực tế khi Click | Trạng thái sau Xác nhận (Confirmed) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **MovieCard** (`MovieCard.tsx`) | Thêm vào Watchlist bị timeout / mất kết nối (`intent: 'add'`) | Badge "Chưa xác nhận" ở góc trên; nút Watchlist nền amber (`bg-amber-400 text-zinc-950`) | Icon `<RefreshCw>`, `aria-label="Chưa xác nhận lưu • Thử lưu lại [Tên phim] vào danh sách xem"`, `title="Chưa xác nhận lưu • Thử lưu lại"` | Gửi lại `POST /api/watchlist` (idempotent add) | Xóa badge "Chưa xác nhận", nút trở về icon bookmark xanh lá đã lưu, toggle bình thường |
| **MovieCard** (`MovieCard.tsx`) | Xóa khỏi Watchlist bị timeout / mất kết nối (`intent: 'remove'`) | Badge "Chưa xác nhận" ở góc trên; nút Watchlist viền amber | Icon `<RefreshCw>`, `aria-label="Chưa xác nhận xóa • Thử xóa lại [Tên phim] khỏi danh sách xem"`, `title="Chưa xác nhận xóa • Thử xóa lại"` | Gửi lại `DELETE /api/watchlist/{id}` (idempotent remove) | Xóa badge "Chưa xác nhận", nút trở về icon bookmark chưa lưu, toggle bình thường |
| **MovieDetail** (`MovieDetail.tsx`) | Watchlist pending timeout (`intent: 'add'`) | Nút Watchlist viền/nền amber (`border-amber-400/40 bg-amber-500/10`) | Icon `<RefreshCw>`, text `"Chưa xác nhận • Thử lưu lại"`, `aria-label="Chưa xác nhận lưu • Thử lưu lại vào Danh sách xem"` | Gửi lại `POST /api/watchlist` | Nút hiển thị `"Đã lưu danh sách"`, icon check xanh lá, toggle bình thường |
| **MovieDetail** (`MovieDetail.tsx`) | Watchlist pending timeout (`intent: 'remove'`) | Nút Watchlist viền/nền amber | Icon `<RefreshCw>`, text `"Chưa xác nhận • Thử xóa lại"`, `aria-label="Chưa xác nhận xóa • Thử xóa lại khỏi Danh sách xem"` | Gửi lại `DELETE /api/watchlist/{id}` | Nút hiển thị `"Thêm vào danh sách"`, icon bookmark xám, toggle bình thường |
| **MovieDetail** (`MovieDetail.tsx`) | Favorite pending timeout (`intent: 'add' / 'remove'`) | Nút Tim viền/nền amber, ring amber | Icon `<RefreshCw>`, `aria-label="Chưa xác nhận thích • Thử thêm lại vào Yêu thích"` / `"Chưa xác nhận bỏ thích • Thử xóa lại khỏi Yêu thích"` | Gửi lại `POST /api/favorites` hoặc `DELETE /api/favorites/{id}` | Trở về nút Tim đỏ/xám toggle bình thường |
| **MovieDetail** (`MovieDetail.tsx`) | Rating pending timeout (`intent: 'rate'`) | Banner cảnh báo amber `<div data-testid="rating-unconfirmed-banner">` phía trên dãy sao | Text `"Chưa xác nhận điểm X/10 ★ trên máy chủ"`, nút bấm riêng `"Thử lưu lại"` | Gửi lại `POST /api/users/ratings` với điểm số `unconfirmedRatingScore` | Đóng banner, hiển thị điểm đã lưu trên dãy sao |
| **MovieDetail** (`MovieDetail.tsx`) | Người dùng chọn điểm mới khác khi đang uncertain | Dãy sao sáng theo điểm mới vừa chọn | Gửi lập tức `POST` với điểm sao mới được chọn | Gửi `POST /api/users/ratings` với điểm mới | Hệ thống ghi nhận điểm mới, hủy bỏ trạng thái retry của điểm cũ |
| **ProfileOverview** (`ProfileOverview.tsx`) | Lỗi nạp/hòa giải thư viện (`libraryError != null`) | Banner cảnh báo amber `<div data-testid="library-error-banner">` ở đầu trang; **không che lấp danh sách phim** | Text lỗi chi tiết kèm nút `"Thử tải lại"` (`refetchLibrary`) | Gửi yêu cầu làm mới toàn bộ thư viện từ server | Banner biến mất khi dữ liệu nạp thành công |
| **ProfileOverview** (`ProfileOverview.tsx`) | Mục Watchlist / Favorite orphan hoặc chưa xác nhận | Thẻ phim trong tab có badge "Chưa xác nhận", nút retry amber | Text `"Thử lưu lại"` hoặc `"Thử xóa lại"`, `aria-label` khớp chính xác intent | Gửi đúng `POST` hoặc `DELETE` tương ứng | Mục được đồng bộ hoặc gỡ khỏi danh sách |

---

## 3. Changeset & Files Modified

Toàn bộ các thay đổi của M1-F05 được lưu giữ trong baseline snapshot `.f05_snapshot/` với mã hash SHA256 được kiểm tra đối chiếu:

| File | Thay đổi chính |
| :--- | :--- |
| `frontend/lib/context/WatchlistContext.tsx` | Cung cấp thêm 2 selectors: `getActionIntent(id, action)` và `getUnconfirmedRating(id)` vào `WatchlistContextType` và `useWatchlist()`. |
| `frontend/features/movies/components/MovieCard.tsx` | Nối `isActionUnconfirmed` và `getActionIntent`; render badge "Chưa xác nhận", icon `<RefreshCw>`, nhãn/aria-label và handler retry chuẩn xác. |
| `frontend/features/movies/components/MovieDetail.tsx` | Nối `isActionUnconfirmed`, `getActionIntent`, `getUnconfirmedRating`; hiển thị nhãn retry Watchlist/Favorite rõ ràng; banner rating uncertain riêng biệt; phân biệt chọn sao mới. |
| `frontend/features/profile/components/ProfileOverview.tsx` | Nối `isActionUnconfirmed` và `getActionIntent`; giữ lưới thư viện khi có `libraryError`, bổ sung banner lỗi có nút tải lại; hỗ trợ retry các mục orphan/unconfirmed. |
| `frontend/tests/m1_behavior_suite.mjs` | Bổ sung 4 bài kiểm thử mới (tests 21, 22, 23, 24) chạy trực tiếp các components `MovieCard`, `MovieDetail`, `ProfileOverview` với mock transport & provider. |
| `docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md` | Bổ sung Mục 7.3 quy định chuẩn giao tiếp và hành vi giao diện người dùng cho vòng đời Uncertain / Retry. |

---

## 4. Verification & Evidence

### 4.1 Frontend Behavioral Suite (`frontend/tests/m1_behavior_suite.mjs`)
Lệnh thực thi:
```bash
node --test tests/m1_behavior_suite.mjs
```
**Kết quả đầu ra thực tế:**
```
✔ 1. Auth login sends verbatim raw password with spaces (116.4871ms)
✔ 2. R1 (P1): Logout while response JSON is pending does NOT resurrect session (27.3248ms)
✔ 3. R1: Runtime validation rejects malformed auth payloads (21.1638ms)
✔ 4. F1 (P1): Late A 401 response after B login does NOT trigger handleSessionExpired on B (70.9774ms)
✔ 5. F1 (P1): Old A finally does NOT release B synchronous lock for the same item (69.7648ms)
✔ 6. F2 (P1): First render of User B derives empty state before passive effects flush (50.0075ms)
✔ 7. F3 (P2): Same-actor refresh does NOT invalidate pending mutation or leave pending stuck (41.9987ms)
✔ 8. F4 (P2): Slow JSON body parsing after headers triggers timeout and aborts (53.8774ms)
✔ 9. R3: Targeted rollback: X failure retains successfully added Y (44.3846ms)
✔ 10. R4: Unavailable sessions do NOT write to guest storage (35.4329ms)
✔ 11. R7: removeRating removes rating and sends DELETE request without mutating watchlist (36.7824ms)
✔ 12. G1 (P1): Boot checking to verified A restores nonempty library (watchlist, favorites, ratings) (42.3486ms)
✔ 13. G1 (P1): A -> logout -> B loads B nonempty library without leaking A library (33.3213ms)
✔ 14. G2 (P2): Older refresh body arriving after successful add preserves newly added items (34.8887ms)
✔ 15. G2 (P2): Refresh during delete followed by delete success keeps item deleted (41.0849ms)
✔ 16. G2 (P2): Rating update is protected against stale read returning old score (35.4376ms)
✔ 17. G3 (P2): Unknown write outcome (network error) triggers background reconcile (30.9603ms)
✔ 18. H1 (P2): Read initiated while write was pending cannot overwrite subsequent commit when read body arrives late (37.0478ms)
✔ 19. H2 (P2): Unknown outcome on write network loss marks operation uncertain and retrying toggle maintains POST intent (27.9148ms)
✔ 20. H2 (P2): Unknown outcome on DELETE maintains delete intent on retry without inverting to POST (36.746ms)
✔ 21. UI H2: MovieCard renders unconfirmed ADD badge/label and click triggers retry POST, returning to normal on confirm (49.7014ms)
✔ 22. UI H2: MovieCard renders unconfirmed DELETE label and click triggers retry DELETE, returning to normal on confirm (42.9731ms)
✔ 23. UI H2: MovieDetail renders unconfirmed Watchlist, Favorite, and Rating with explicit retry buttons and handles new rating selection (14.0251ms)
✔ 24. UI H2: ProfileOverview renders persistent library error banner and orphan retry actions for Watchlist, Favorites, and Ratings (37.003ms)
ℹ tests 24
ℹ suites 0
ℹ pass 24
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1325.3062
```
**Exit Code:** `0` (24/24 pass tuyệt đối).

### 4.2 Codex Runtime Repro (`docs/reviews/repro/M1_F03_runtime_repro.cjs`)
Lệnh thực thi:
```bash
node docs/reviews/repro/M1_F03_runtime_repro.cjs
```
**Kết quả đầu ra:**
```json
[
  {
    "scenario": "write pending -> read starts -> write commits -> old read body arrives",
    "before": [
      "X"
    ],
    "after": [
      "X"
    ]
  },
  {
    "scenario": "committed add loses response, reconcile fails, user retries toggle",
    "failedReconcile": {
      "watchlist": [
        "X"
      ],
      "pending": false,
      "error": "Không thể tải toàn bộ thư viện cá nhân từ máy chủ."
    },
    "methods": [
      "POST",
      "POST"
    ],
    "finalBackend": [
      "X"
    ]
  }
]
```
**Exit Code:** `0`.

### 4.3 TypeScript Compilation Check
Lệnh thực thi:
```bash
npx tsc --noEmit
```
**Exit Code:** `0` (Sạch hoàn toàn, không có lỗi type nào).

### 4.4 Production Next.js Build
Lệnh thực thi:
```bash
npm run build
```
**Kết quả đầu ra:**
```
   ▲ Next.js 15.1.2
   - Environments: .env.local

   Creating an optimized production build ...
 ✓ Compiled successfully
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (0/7) ...
   Generating static pages (1/7) 
   Generating static pages (3/7) 
   Generating static pages (5/7) 
 ✓ Generating static pages (7/7)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                              Size     First Load JS
┌ ○ /                                    6.05 kB         136 kB
├ ○ /_not-found                          140 B           106 kB
├ ƒ /api/chat                            140 B           106 kB
├ ƒ /movies/[id]                         4.6 kB          134 kB
├ ○ /profile                             7.24 kB         137 kB
└ ○ /search                              4.04 kB         134 kB
+ First Load JS shared by all            105 kB
```
**Exit Code:** `0`.

### 4.5 Backend Prior Evidence
Do không có thay đổi mã nguồn backend trong ticket M1-F05 (chỉ cập nhật frontend consumers, contract và tests), không chạy lại backend suite để tránh lãng phí tài nguyên. Kết quả kiểm thử tích hợp Spring Boot trước đó tại F02:
- Suite: `com.dippie.moviercm.AuthAndLibraryIntegrationTest`
- Kết quả: `Tests run: 8, Failures: 0, Errors: 0, Skipped: 0` (BUILD SUCCESS).

### 4.6 Patch Integrity Verification
Lệnh thực thi:
```bash
git apply --numstat docs/reports/M1-F05.patch
git apply --reverse --check docs/reports/M1-F05.patch
```
**Kết quả đầu ra:**
```
29	0	docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md
45	4	frontend/features/movies/components/MovieCard.tsx
111	5	frontend/features/movies/components/MovieDetail.tsx
265	30	frontend/features/profile/components/ProfileOverview.tsx
31	0	frontend/lib/context/WatchlistContext.tsx
330	0	frontend/tests/m1_behavior_suite.mjs
```
- `git apply --reverse --check docs/reports/M1-F05.patch` trả về **exit code 0**, xác nhận patch hợp lệ và khôi phục sạch sẽ về baseline `.f05_snapshot/`.

---

## 5. Test Methodology & Evidence Boundaries

### 5.1 Component Testing vs Browser E2E Distinction
- **Bằng chứng thành phần thực tế (Component Testing):** Các bài kiểm thử 21–24 khởi tạo các components thực tế của production (`MovieCard`, `MovieDetail`, `ProfileOverview`) với cấu hình React 19 test renderer, bao phủ:
  - Render đúng huy hiệu `data-testid="unconfirmed-badge"`, `rating-unconfirmed-banner`, và `library-error-banner`.
  - Kiểm tra chính xác các thuộc tính `aria-label`, class styling amber, và icon `<RefreshCw>`.
  - Mô phỏng sự kiện click của người dùng, chứng minh handler gọi đúng hàm với đúng intent (`POST` vs `DELETE`, điểm số unconfirmed vs điểm số mới).
  - Kiểm tra quá trình chuyển dịch trạng thái: khi server xác nhận thành công, các thành phần lập tức khôi phục về trạng thái toggle bình thường.
- **Giới hạn môi trường (Environment Limitations):**
  - Môi trường thực thi hiện tại không có trình duyệt headless (không có Chrome/Edge trong PATH hệ thống).
  - Do đó, các bài kiểm thử là các component tests thực thi trực tiếp trên mã nguồn sản phẩm thông qua test runner Node.js, **không giả mạo hay tự nhận là kiểm thử trình duyệt thực tế (Browser E2E)**.

---

## 6. Commitments & Integrity Verification

- Tuyệt đối không chỉnh sửa AI pipeline, FastAPI, Qwen serving, adapter hay model weights; không khởi tạo GPU process.
- Không chỉnh sửa database live trên production; không xóa dữ liệu người dùng hiện có.
- Không thực hiện lệnh `git commit`, `git push`, hoặc `git reset`.
- Giữ nguyên vẹn toàn bộ các thay đổi chưa commit trước đó của các ticket UX-01A, F01, F02, F03, F04.
- Dừng lại tại **READY FOR REVIEW M1-F05** để Codex nghiệm thu độc lập; chưa chuyển sang milestone M2.
