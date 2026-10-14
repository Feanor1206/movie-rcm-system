# UX-01A-F01 — Sửa findings UX và khôi phục scope visual

Áp dụng `docs/prompts/GEMINI_ENGINEERING_RULES.md`. Đọc `docs/reviews/UX-01A_REVIEW.md`, prompt UX-01A và patch baseline `docs/reports/UX-01A.patch`. TypeScript/build/patch checks đã pass; phần theme/layout/card stacking được giữ. Chỉ sửa findings dưới đây rồi dừng Codex review.

## Scope

Frontend styles/copy/home guard và revert đúng behavior hunks ngoài scope; test/evidence/documentation liên quan. Không đổi backend/Qwen/API/auth/storage policy, không dựng tính năng AI mới hoặc sửa records catalog.

### 1. Contrast

- Giữ tone xanh lá. Chọn surface/foreground hoặc semantic on-brand token để small text chức năng đạt contrast ≥4,5:1 trong các trạng thái dùng thực.
- Kiểm tra btn-primary, selected chips, card overlay, login/submit buttons, rating badge có bg-brand và user chat bubbles. Error palette giữ nguyên semantic.
- Ghi contrast table dùng actual colors/default/hover/selected/active và screenshots. Không chỉ đổi hero button rồi để các consumer khác dùng cùng tổ hợp #10b981/text-white.
- Không tạo test chỉ assert CSS classes; color arithmetic/computed-style checks và visual walkthrough là evidence phù hợp.

### 2. Copy có căn cứ

- Xóa/ẩn các hard-coded HD/Full HD, phụ đề/lồng tiếng, stereo/đa kênh ở MovieDetail khi metadata không có. Nếu cần hiển thị trường, ghi “Chưa có thông tin”; không tự tạo edition/media data.
- Đổi home rail “ấm áp/phù hợp gia đình” sang nhãn trung tính phản ánh tập genre hiện có, như “Phiêu lưu & kỳ ảo”. Không làm classifier mới, không coi Family tag là safety guarantee.
- Pathway CineBot dùng copy phù hợp capability hiện hữu đã kiểm chứng; không hứa runtime/mood như constraint đã hỗ trợ đầy đủ.
- CineBot header/welcome dùng tên trợ lý và lời mời thân thiện, bỏ model/Phase23/five-stage và personalized claims thiếu bằng chứng khỏi user UI. Giữ nguyên payload/handlers/Qwen model.

### 3. Scope correction

- Revert đúng ba changes default watchlist/favorite/rating trong WatchlistContext về baseline trước UX-01A (dùng UX-01A.patch để xác định), giữ toast styling xanh lá.
- Revert local similarMovies sorting hunk trong app/movies/[id]/page.tsx về baseline trước UX-01A; không nhận thay đổi selection/ranking là visual.
- Không xóa localStorage, đổi saved keys, migrate/correct ratings đã lưu hoặc refactor account/library trong ticket này. Ghi existing demo defaults là limitation riêng của LIB-01, không gọi library đã production-ready.

### 4. Empty animation catalog

- featured animation không fallback sang movies[0] nếu item không phải Animation.
- Home render hero có guard và empty state hữu ích khi không có animation records; vẫn giữ navigation và CTA hiện hữu.
- Có behavior evidence với fixture không Animation; không sửa factual catalog/IDs để tạo test. Không cần thêm test framework lớn cho một guard.

## Acceptance và bàn giao

- TypeScript và production build pass; error/navigation/modal/card interactions hiện hữu không regression.
- Contrast table đạt; mobile 360px/768px và desktop 1440px được kiểm tra; không overflow.
- Empty-catalog case không fiction hero và không crash.
- Media/tone/family/capability copy không còn assertions unsupported trong các vùng đã sửa.
- Scope defaults/similarMovies về đúng baseline; không có storage migrations.
- Before/after snapshots cho patch riêng F01, `git apply --numstat` và reverse --check exit 0. Giữ các changes có sẵn.
- `docs/reports/UX-01A-F01_REPORT.md`, actual checks, screenshots nếu có browser tools; phần chưa visual-verify ghi đúng.
- Không chạy lại backend serving suite khi không sửa backend; không gọi model hoặc tạo GPU process.
- Không commit/push hoặc chuyển ticket; dừng ready for review.

Không làm lại theme/home từ đầu. Đây là patch chỉnh chất lượng và scope trên UI đã có.
