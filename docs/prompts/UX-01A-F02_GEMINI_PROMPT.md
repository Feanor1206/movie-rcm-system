# UX-01A-F02 — Hoàn thiện contrast còn sót ở Navbar

Áp dụng GEMINI_ENGINEERING_RULES.md; đọc `docs/reviews/UX-01A-F01_REVIEW.md` và current Navbar. F01 đã đạt copy, scope restoration, empty-catalog rendering và contrast của các components đã sửa. Chỉ sửa Navbar consumer còn sót, không làm lại F01 hoặc theme.

## Scope

- `frontend/components/layout/Navbar.tsx`: styling foreground/hover liên quan.
- `docs/reports/UX-01A-F02_REPORT.md` và valid independent patch.
- Test/evidence component nếu cần; không thêm test framework lớn hoặc snapshot/CSS-class tests máy móc.

Không sửa AuthContext, WatchlistContext, login/logout handlers, API, catalog, backend, model hoặc global palette đã chốt.

## Sửa đúng bốn trạng thái

1. Guest mobile “Đăng nhập”: bg-brand có foreground on-brand tối, không text-white.
2. Authenticated mobile initials/profile link: foreground đúng trên brand.
3. Authenticated desktop initials: foreground đúng trên brand.
4. Guest desktop login: default nền tối/chữ sáng có thể giữ; hover:bg-brand phải đi cùng hover foreground on-brand đạt contrast.

Có thể dùng `text-brand-foreground` / `hover:text-brand-foreground` với token #09090b hiện có. Kiểm tra actual class cascade; không thay tên/action/handlers hoặc behavior của dropdown.

## Acceptance

- Các text chức năng trong bốn states đạt ≥4,5:1 khi enabled; ghi đúng foreground/background/ratio. Không tuyên bố toàn website đạt AAA.
- TypeScript/build pass; Navbar mobile menu/focus/navigation và auth modal trigger không regression.
- Browser computed style của guest mobile login sau sửa là on-brand tối trên xanh, kèm ảnh nếu có tools. Desktop hover và authenticated branches có source/fixture hoặc UI evidence rõ; không tạo login giả để test.
- Baseline snapshot và patch riêng F02 được tạo bằng Git tooling, numstat và reverse --check exit 0.
- Không clear/migrate storage; không chạy lại backend/GPU suite cho styling-only patch.

Báo cáo actual checks và limitations. Không commit/push; dừng ready for review để Codex đóng UX-01A khi criteria đạt.
