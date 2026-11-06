# AUTH-01 — Xác thực thật và trạng thái tài khoản trung thực

Đây là ticket tiếp theo sau UX-01A đã được nghiệm thu tại `docs/reviews/UX-01A-F02_REVIEW.md`. Áp dụng `docs/prompts/GEMINI_ENGINEERING_RULES.md`. Sửa auth hiện hữu; không chờ hoặc xây lại contract/catalog/backend. Account library isolation được nghiệm thu riêng ở LIB-01.

## Vấn đề người dùng

Hiện frontend tạo mock token/user khi login/register mất kết nối và giữ user authenticated khi /auth/me lỗi. Người dùng tưởng đăng nhập thật, lưu dữ liệu thất bại và có thể thấy trạng thái không đúng.

## Source và phạm vi

- `frontend/lib/context/AuthContext.tsx`, `frontend/features/auth/components/AuthModal.tsx`.
- Consumers của useAuth trong Navbar/Profile và tests/config test tối thiểu khi cần.
- Đọc Spring AuthController/AuthService/UserDetails và DTO để giữ API hiện hữu tương thích.

Backend đã có `POST /api/auth/login`, `POST /api/auth/register` và `GET /api/auth/me`. Đối chiếu source DTO và envelope ApiResponse trước khi sửa frontend; giữ endpoints và payload hiện hữu. Không triển khai lại JWT hoặc auth backend.

Chỉ sửa frontend auth/consumers cần thiết và test harness tối thiểu. Không sửa Qwen/FastAPI, DB/seed, watchlist/rating implementation hoặc thêm auth provider. Tạo `docs/reports/AUTH-01_REPORT.md`.

## Hành vi phải thực hiện

1. Bỏ MOCK_50_USERS, random IDs, mock_jwt và offline registration/login success. Network/backend/invalid payload trả trạng thái lỗi nhìn thấy được; không mutate user/token sang tài khoản mới.
2. Login/register thành công chỉ sau response hợp lệ từ backend; validate required user/token fields. Không trust success=true nếu payload thiếu token/identity.
3. Password được gửi nguyên văn như người dùng nhập, không trim/lowercase. Username/email có normalization theo backend contract; không thay semantics auth ngoài scope.
4. Boot: session saved cần kiểm chứng /auth/me; trong thời gian đó trạng thái checking, không coi verified authenticated. Token invalid/expired hoặc /me 401/403 xóa session và đưa về unauthenticated.
5. /me network error/5xx phân biệt unavailable với invalid credentials. Không tạo user/token hoặc gọi verified authenticated từ dữ liệu local. Có thể giữ session material để retry theo policy đã ghi, nhưng private actions phải phản ánh chưa xác minh.
6. Logout hoặc login B trong lúc /me A đang chờ: response A về muộn không được restore A. Dùng cancellation/generation guard; mount/unmount không tạo stale update.
7. Failed login không làm hỏng phiên đã xác thực hợp lệ nếu UI cho phép đổi account; transition phải rõ. Không lưu plaintext password.
8. Modal pending/error/validation: message tiếng Việt bình tĩnh, không technical stack trace, không duplicate submits. Giữ responsive/keyboard và theme xanh lá đã nghiệm thu, bao gồm foreground tối trên brand trong Navbar. Không redesign toàn site trong ticket này.
9. Request có timeout hữu hạn và retry do người dùng chủ động khi session unavailable. Không vòng retry tự động vô hạn; không giữ checking/pending vô thời hạn. Áp dụng guard cho cả restore lẫn login/register: kết quả thành công về sau logout không được tạo lại phiên.

Thể hiện rõ các trạng thái guest, checking, authenticated, unavailable (hoặc tên tương đương). `isAuthenticated` chỉ đúng khi verified. Consumers Navbar/Profile không hiển thị tài khoản như đã xác minh khi checking/unavailable; người dùng được thấy thông báo ngắn và cách thử lại. Dữ liệu identity hiện ra phải cùng phiên với token, không trộn cached user A và response B.

## Acceptance

- Login/register valid và invalid; server down; 500; malformed success payload.
- Password có spaces đi nguyên văn tới mock backend.
- Stored session valid, expired, /me forbidden và /me unavailable.
- Logout/login B trong lúc A đang restore; không stale identity resurrection.
- Login/register đang chờ rồi logout; response thành công về trễ không ghi user/token/storage. Timeout đưa UI khỏi pending và cho phép thử lại.
- UI không còn message mật khẩu demo hoặc signed-in giả; button pending/error đúng.
- Private consumers không dùng cached user snapshot như identity verified.
- TypeScript check và checks frontend phù hợp pass; test actual auth transitions với mocked API, không test string search thay behavior.

Nếu cần thêm test runner nhỏ cho behavior tests, giới hạn dependency và giải thích. Không nâng Next/React. Báo rõ backend live checks có/không thực hiện; tests mock không chứng minh server auth thật đang hoạt động.

Không tuyên bố đã sửa account library isolation: LIB-01 còn phải làm state/storage, fetch cancellation và sync riêng theo actor. Bàn giao ready for review.

## Bàn giao

Snapshot baseline trước khi sửa; tạo patch độc lập `docs/reports/AUTH-01.patch` chỉ gồm thay đổi lượt này. Kiểm tra `git apply --numstat` và `git apply --reverse --check` trước khi bàn giao, không sửa tay hunk headers. Báo cáo phải ghi changed files, state transition policy, test cases và lệnh/exit code thực tế, phần chưa kiểm tra và phạm vi library còn lại. Không commit/push hoặc tự chuyển LIB-01.
