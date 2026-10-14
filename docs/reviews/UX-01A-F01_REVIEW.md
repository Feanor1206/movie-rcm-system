# UX-01A-F01 — Review độc lập

Ngày: 13/10/2026. Verdict: **changes requested — còn một finding về contrast trong Navbar**. Không yêu cầu làm lại các phần F01 đã đạt; không sửa mã ứng dụng trong lượt review.

## Các phần đã xác nhận đạt

- TypeScript `frontend/node_modules/.bin/tsc.cmd --noEmit`: exit 0.
- `npm run build`: exit 0, compile/prerender thành công.
- F01 patch numstat và reverse --check: exit 0, 12 files khớp current source.
- Ratio tính độc lập cho #09090b trên brand states: default #10b981 = 7,84; hover #34d399 = 10,35; active #059669 = 5,28. Đạt AA 4,5 cho chữ nhỏ; active không đạt AAA 7,0, không diễn giải toàn bộ states đạt AAA.
- Source/copy đã bỏ HD/subtitle/audio assertions, family-tone guarantee và model/Phase23/five-stage UI labels theo findings.
- Ba default values trong WatchlistContext về baseline trước UX-01A; file movies/[id]/page.tsx khớp HEAD. Đây là scope restoration, không phải nghiệm thu library demo defaults.
- Empty fixture kiểm tra độc lập bằng TypeScript transpilation và React server rendering: actual movies module được thay initializer bằng một fiction-only fixture trong bộ nhớ, không thay source/data trên đĩa. animation count=0, featuredMovie=null, hero render calls=0, HomePage render thành công với empty message/discovery link.
- Browser production build review :3101 tại 360×800 xác nhận hero CTA màu chữ rgb(9,9,11), nền rgb(16,185,129), font 12px. Phần CTA đã sửa đúng.

## P2 — Navbar chưa áp dụng on-brand foreground

`frontend/components/layout/Navbar.tsx` không nằm trong patch F01 nhưng vẫn là consumer brand cần kiểm tra theo prompt F01:

- Line 175: guest mobile login là bg-brand/text-white, font 12px.
- Line 168: authenticated mobile initials tương tự.
- Line 106: authenticated desktop initials bg-brand/text-white, font 11px.
- Line 156: guest desktop login giữ text-white khi hover:bg-brand.

Browser computed style của nút “Đăng nhập” mobile: background rgb(16,185,129), foreground rgb(255,255,255), font 12px; contrast **2,54:1**. Finding này là phần còn thiếu của yêu cầu sửa login/brand consumers ở F01, không phải mở rộng chức năng mới.

Ảnh bằng chứng: `docs/reviews/screenshots/UX-01A-F01-navbar.jpg`; ảnh mobile đầy đủ: `UX-01A-F01-mobile.jpg`.

Yêu cầu: chỉnh on-brand foreground cho bốn trạng thái trên; desktop login default có thể giữ chữ sáng trên nền tối nhưng hover cần foreground tương ứng. Không sửa auth handlers hoặc user state.

## Giới hạn và bước tiếp theo

- Không login, gửi query Qwen, sửa storage hoặc chạy backend/GPU suite. Không audit toàn website để tuyên bố WCAG compliance.
- Trạng thái authenticated Navbar được xác định từ source; không đăng nhập giả chỉ để chụp UI. Regression fixture có thể kiểm tra riêng component.
- Server review :3101 có PID riêng được khởi tạo bởi Codex và dừng sau kiểm tra; tab đóng/viewport reset. Không tác động service đã có ở port :3100.
- Giao Gemini `docs/prompts/UX-01A-F02_GEMINI_PROMPT.md`, chỉ scope Navbar và report/patch. Các phần F01 đã đạt giữ nguyên.
