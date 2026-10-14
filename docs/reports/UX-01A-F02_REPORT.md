# UX-01A-F02 — Báo cáo ready for review

## 1. Vấn đề và phạm vi

- **Người dùng được cải thiện điều gì?**
  - Khắc phục triệt để finding P2 duy nhất còn sót lại tại [Navbar.tsx](file:///D:/Class/movie-rcm-system/frontend/components/layout/Navbar.tsx) từ đợt review `UX-01A-F01`:
    1. **Guest mobile "Đăng nhập" button:** Trước đây sử dụng `bg-brand/text-white` (font 12px) với độ tương phản chỉ **2.54:1**. Đã chuyển sang `bg-brand text-zinc-950 font-bold` (`#09090b`), nâng tỷ lệ tương phản lên **7.84:1** (mặc định), **10.35:1** (hover) và **5.28:1** (active), hoàn toàn vượt chuẩn WCAG AA (≥ 4.5:1).
    2. **Authenticated mobile initials:** Trước đây là `bg-brand text-white` (font 12px), đã chuyển sang `bg-brand text-zinc-950 font-bold` (contrast **7.84:1**).
    3. **Authenticated desktop initials:** Trước đây là `bg-brand text-white` (font 11px), đã chuyển sang `bg-brand text-zinc-950 font-bold` (contrast **7.84:1**).
    4. **Guest desktop login button hover:** Nút đăng nhập desktop giữ nền tối/chữ sáng `text-zinc-100` ở trạng thái mặc định (contrast **15.20:1**), và khi hover chuyển sang `hover:bg-brand hover:text-zinc-950` (contrast **7.84:1**), không còn bị lỗi chữ trắng trên nền xanh khi rê chuột.
- **Contract / Ticket thực hiện:**
  - `UX-01A-F02` theo đúng yêu cầu tại [docs/prompts/UX-01A-F02_GEMINI_PROMPT.md](file:///D:/Class/movie-rcm-system/docs/prompts/UX-01A-F02_GEMINI_PROMPT.md) và [docs/reviews/UX-01A-F01_REVIEW.md](file:///D:/Class/movie-rcm-system/docs/reviews/UX-01A-F01_REVIEW.md).
- **Baseline branch và scope:**
  - Baseline là mã nguồn sau ticket `UX-01A-F01`.
  - Chỉ chỉnh sửa thuần túy styling class trong [Navbar.tsx](file:///D:/Class/movie-rcm-system/frontend/components/layout/Navbar.tsx).
  - Không sửa `AuthContext`, `WatchlistContext`, login/logout handlers, dropdown state, API, catalog, backend hay Qwen model. Không làm lại F01 hay theme đã chốt.

---

## 2. Files và thay đổi

Chỉ duy nhất 1 file được chỉnh sửa trong ticket này và được lưu tại patch độc lập **`docs/reports/UX-01A-F02.patch`**:

- `frontend/components/layout/Navbar.tsx` (4 insertions, 4 deletions):
  - **Line 106:** Đổi initials avatar desktop của user đã đăng nhập từ `text-white` sang `text-zinc-950 font-bold`.
  - **Line 156:** Nút đăng nhập desktop bổ sung `hover:text-zinc-950` đi kèm `hover:bg-brand`, và đổi default text thành `text-zinc-100`.
  - **Line 168:** Đổi initials avatar mobile của user đã đăng nhập từ `text-white` sang `text-zinc-950 font-bold`.
  - **Line 175:** Nút đăng nhập mobile đổi từ `text-white` sang `text-zinc-950 font-bold hover:bg-brand-hover active:bg-brand-active`.

---

## 3. Ma trận nghiệm thu

### Bảng kiểm tra tương phản 4 trạng thái Navbar (WCAG 2.2 Relative Luminance)

| Trạng thái Navbar | Nền (Background) | Chữ / Icon (Foreground) | Tỷ lệ tương phản | WCAG AA (≥ 4.5:1) | WCAG AAA (≥ 7.0:1) |
|---|---|---|---|---|---|
| **1. Guest mobile "Đăng nhập" (default)** | `bg-brand #10b981` | `text-zinc-950 #09090b` | **7.84:1** | **PASS** | **PASS** |
| **1. Guest mobile "Đăng nhập" (hover)** | `bg-brand-hover #34d399` | `text-zinc-950 #09090b` | **10.35:1** | **PASS** | **PASS** |
| **1. Guest mobile "Đăng nhập" (active)** | `bg-brand-active #059669` | `text-zinc-950 #09090b` | **5.28:1** | **PASS** | Gần đạt (5.28:1) |
| **2. Authenticated mobile initials** | `bg-brand #10b981` | `text-zinc-950 #09090b` | **7.84:1** | **PASS** | **PASS** |
| **3. Authenticated desktop initials** | `bg-brand #10b981` | `text-zinc-950 #09090b` | **7.84:1** | **PASS** | **PASS** |
| **4. Guest desktop login (default)** | `bg-surface #111714` | `text-zinc-100 #f4f4f5` | **15.20:1** | **PASS** | **PASS** |
| **4. Guest desktop login (hover)** | `hover:bg-brand #10b981` | `hover:text-zinc-950 #09090b` | **7.84:1** | **PASS** | **PASS** |

### Ma trận nghiệm thu theo tiêu chí kỹ thuật

| Acceptance case | Expected | Actual | Evidence | Status |
|---|---|---|---|---|
| **1. Guest mobile "Đăng nhập"** | Nền xanh lá có chữ on-brand tối, contrast ≥ 4.5:1, không text-white. | `bg-brand text-zinc-950 font-bold` (7.84:1 mặc định, 10.35:1 hover). | `Navbar.tsx` L175. | **Passed** |
| **2. Authenticated mobile initials** | Chữ viết tắt trên nền xanh lá đạt contrast ≥ 4.5:1. | `bg-brand text-zinc-950 font-bold` (7.84:1). | `Navbar.tsx` L168. | **Passed** |
| **3. Authenticated desktop initials** | Chữ viết tắt desktop trên nền xanh lá đạt contrast ≥ 4.5:1. | `bg-brand text-zinc-950 font-bold` (7.84:1). | `Navbar.tsx` L106. | **Passed** |
| **4. Guest desktop login hover** | Khi rê chuột sang nền xanh `hover:bg-brand`, màu chữ chuyển sang on-brand tối. | `hover:bg-brand hover:text-zinc-950` (7.84:1 khi hover, 15.20:1 khi default). | `Navbar.tsx` L156. | **Passed** |
| **5. Không tác động Auth logic** | Handlers `openAuthModal`, dropdown toggle, user session giữ nguyên. | Không thay đổi hàm xử lý, chỉ sửa class Tailwind. | `git diff Navbar.tsx`. | **Passed** |
| **6. TypeScript Typecheck** | `npx tsc --noEmit` hoàn thành không lỗi. | `exit code 0`, 0 compile errors. | Lệnh chạy thành công. | **Passed** |
| **7. Production Build** | `npm run build` biên dịch 7/7 static routes thành công. | `exit code 0`, compile/prerender thành công. | Next.js 15.1.2 production build log. | **Passed** |
| **8. Patch F02 hợp lệ** | Patch áp dụng và revert hoàn toàn sạch sẽ bằng Git tooling. | `git apply --numstat` và `--reverse --check` đều exit 0. | `UX-01A-F02.patch` (1 file). | **Passed** |

---

## 4. Kiểm tra thực hiện

### Lệnh và kết quả chi tiết:

1. **TypeScript Typecheck:**
   - **Command:** `npx tsc --noEmit`
   - **Cwd:** `D:\Class\movie-rcm-system\frontend`
   - **Exit Code:** `0`
   - **Duration:** 3.5s

2. **Next.js Production Build:**
   - **Command:** `npm run build`
   - **Cwd:** `D:\Class\movie-rcm-system\frontend`
   - **Exit Code:** `0`
   - **Duration:** 41.2s
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
     ┌ ○ /                                    5.88 kB         132 kB
     ├ ○ /_not-found                          140 B           106 kB
     ├ ƒ /api/chat                            140 B           106 kB
     ├ ƒ /movies/[id]                         3.78 kB         130 kB
     ├ ○ /profile                             3.95 kB         130 kB
     └ ○ /search                              4.04 kB         130 kB
     + First Load JS shared by all            105 kB
     ```

3. **Kiểm tra tính hợp lệ của Patch độc lập UX-01A-F02:**
   - **Command:** `git apply --numstat docs/reports/UX-01A-F02.patch`
   - **Cwd:** `D:\Class\movie-rcm-system`
   - **Exit Code:** `0`
   - **Output:** `4  4  frontend/components/layout/Navbar.tsx`
   - **Command:** `git apply --reverse --check docs/reports/UX-01A-F02.patch`
   - **Cwd:** `D:\Class\movie-rcm-system`
   - **Exit Code:** `0` (Revert check hoàn toàn sạch sẽ 100%).

---

## 5. Kết quả và limitations

- **Phần đạt được:**
  - Hoàn tất chỉnh sửa chính xác 4 trạng thái tương phản tại Navbar theo đúng yêu cầu của Codex.
  - Tỷ lệ tương phản của cả 4 trạng thái đều đạt chuẩn WCAG AA (từ 5.28:1 đến 15.20:1, trong đó trạng thái mặc định và hover đạt cả WCAG AAA ≥ 7.0:1).
  - Không gây regression lên giao diện, dropdown menu hay các luồng modal đăng nhập.
  - Toàn bộ production build và TypeScript typecheck đạt 100%.
- **Chưa kiểm tra (Limitations):**
  - Trạng thái `active` (khi nhấn giữ nút) đạt **5.28:1**, thỏa mãn chuẩn WCAG AA (≥ 4.5:1) nhưng chưa đạt AAA (≥ 7.0:1). Đúng như lưu ý của Codex tại review F01, báo cáo không tuyên bố toàn bộ trạng thái đạt AAA mà ghi nhận chính xác theo thực tế đo đạc.
  - Không chạy lại backend serving suite hay model GPU do patch này thuần túy là chỉnh sửa CSS class tại Navbar frontend.
  - Không tạo login giả lập hay thay đổi localStorage để test authenticated branch; các class authenticated đã được xác thực trực tiếp tại mã nguồn `Navbar.tsx`.

---

## 6. Bàn giao

- **Artifacts bàn giao:**
  - Patch độc lập: [docs/reports/UX-01A-F02.patch](file:///D:/Class/movie-rcm-system/docs/reports/UX-01A-F02.patch)
  - Báo cáo nghiệm thu: [docs/reports/UX-01A-F02_REPORT.md](file:///D:/Class/movie-rcm-system/docs/reports/UX-01A-F02_REPORT.md)
- **Trạng thái:** **Ready for review**.
- **Cam kết:** Kỹ sư triển khai không tự ý commit hoặc push Git; dừng lại để Kỹ sư trưởng Codex tiến hành nghiệm thu và đóng ticket UX-01A.
