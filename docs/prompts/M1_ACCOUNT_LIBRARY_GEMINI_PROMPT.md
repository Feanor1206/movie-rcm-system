# M1 — Tài khoản thật và thư viện cá nhân hoàn chỉnh

Bạn là Gemini, kỹ sư triển khai tại `D:\Class\movie-rcm-system`. Codex là kỹ sư trưởng lập kế hoạch và nghiệm thu. Thực hiện trọn milestone M1, gồm AUTH-01/LIB-01/LIB-02, không dừng sau mỗi ticket nhỏ. Bàn giao một kết quả ready for review; không chuyển M2, commit hoặc push.

## Đọc và xác định baseline

Đọc AGENTS.md áp dụng nếu có, `docs/prompts/GEMINI_ENGINEERING_RULES.md`, `docs/PRODUCT_MILESTONES.md`, `docs/USER_EXPERIENCE_BLUEPRINT.md`, review UX-01A-F02 và prompt AUTH-01 cho yêu cầu auth chi tiết. M1 này mở rộng scope AUTH-01 sang library và backend nghiệp vụ cần thiết; quy tắc giao một ticket được hiểu là một milestone, không phải dừng giữa AUTH/LIB.

Ghi git status/branch và snapshot riêng trước khi sửa. Nếu AUTH-01 đã có thay đổi, đối chiếu và kế thừa, không viết lại mù quáng. Source trọng tâm:

- Frontend AuthContext, AuthModal, WatchlistContext, Navbar, MovieCard/MovieDetail, ProfileOverview, provider composition và catalog lookup hiện tại.
- Spring controller/service/repository/entity/DTO/security của auth, watchlist, rating; schema/config seed và test setup liên quan.

Backend đã có `/api/auth/login`, `/api/auth/register`, `/api/auth/me`, `/api/users/watchlist`, `/api/users/ratings`. Frontend còn mock login/register trong catch, thư viện seeded/shared localStorage, sync chỉ lúc mount, fire-and-forget writes và favorites local-only. Kiểm tra source thực tế trước khi sửa; không coi tất cả module là chưa xây.

## Kết quả người dùng cần đạt

Guest khám phá và lưu riêng trên thiết bị. Người đăng nhập có thư viện riêng trên backend, thao tác lưu/thích/chấm điểm phản ánh kết quả thật và còn đúng sau reload. Chuyển A → logout → B không thấy dữ liệu A; phản hồi cũ không cập nhật B. Giữ theme xanh lá, contrast và card stacking đã nghiệm thu.

## Thực hiện tuần tự, không xin nghiệm thu giữa các bước

### 1. Chốt contract nhỏ và sửa auth

Viết `docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md` dựa trên DTO hiện hữu: auth/session states, IDs, rating scale, list/mutation responses và error mapping. Giữ compatibility endpoints. Không tự tạo lại JWT/provider.

Thực hiện các yêu cầu AUTH-01: bỏ mock user/token, password nguyên văn, payload validation, verify stored session, 401/403 clear, network/5xx unavailable có retry, timeout hữu hạn, pending/duplicate prevention. Logout/account switch vô hiệu hóa mọi request cũ, gồm restore/login/register. Cached user không được coi đã xác minh. Token và identity phải cùng phiên.

### 2. Tách actor và đọc thư viện đúng

Library lấy verified identity từ AuthContext, không chỉ đọc token localStorage. Các trạng thái guest/checking/authenticated/unavailable có hành vi rõ. Xóa dữ liệu tài khoản khỏi UI ngay khi actor đổi; response/read/write cũ không được mutate state hoặc storage actor mới.

Guest storage có namespace/version riêng và nhãn “Lưu trên thiết bị này”. Account backend là nguồn chuẩn; cache nếu dùng phải theo userId, không hiện dữ liệu account khi chưa verify. Không tự merge guest/account. Keys legacy chung không có ownership đáng tin: không tự nhận là dữ liệu của user đang login; giữ nguyên để migration rõ, không xóa hàng loạt hoặc gán sang B.

Bỏ các default afterlight/quiet-places/the-last-orbit khỏi production library. Account list rỗng phải thay state bằng rỗng, không union để giữ dữ liệu mẫu/guest. Corrupt storage phải xử lý an toàn. Watchlist, favorites, ratings đều phải đọc và khôi phục theo actor; không chỉ sync watchlist.

### 3. Hoàn thiện persistence nghiệp vụ

Tái sử dụng watchlist/rating backend; bổ sung favorite persistence tối thiểu nếu xác nhận chưa có. Được thêm entity/repository/service/controller/DTO và schema/migration cần thiết cho favorites; không tách thêm service hoặc đổi auth provider. Dùng principal của request làm owner, không tin userId client gửi. Đọc response DTO chỉ chứa fields cần thiết, không expose entity user/password/hash.

Các mutation nhận movieId tồn tại trong catalog nghiệp vụ, không lấy title/poster client làm nguồn chuẩn. Giữ ID ổn định. Không tự đoán mapping từ title để lưu nhầm phim. Phần thiếu catalog cần báo rõ và lookup theo ID/API hiện có; không triển khai catalog ETL hoặc redesign search trong M1.

Watchlist/favorite thêm trùng không sinh duplicate; remove lặp có kết quả ổn định. Rating theo thang contract hiện hữu (UI /10): kiểm tra biên cả client/server, cùng user/movie cập nhật một bản ghi. Dùng constraints/transaction phù hợp để request đồng thời không tạo duplicate. Mọi schema change phải giữ dữ liệu cũ và có hướng dẫn migration; không drop/recreate DB người dùng.

### 4. Mutation và UI phản ánh sự thật

Mỗi thao tác có pending và kết quả xác nhận. Có thể dùng optimistic update nhưng phải rollback/reconcile và thông báo lỗi khi thất bại; không hiện toast “Đã lưu” trước thành công backend. Ngăn duplicate click theo movie/action và xử lý kết quả về sai thứ tự. Không retry mù quáng writes có thể đã thành công; read reconcile hoặc retry idempotent theo contract.

401/403 khi library request phải đưa UI về trạng thái phù hợp qua auth contract; phân biệt cấm truy cập với mất kết nối. Network/5xx giữ dữ liệu đã xác nhận và hiển thị thất bại/retry, không success giả. Trong session unavailable không gửi mutation account bằng cached token dưới danh nghĩa authenticated.

Profile hiển thị watchlist/favorites/ratings đúng, count đúng, có loading/empty/error và khả năng thử lại. Tham chiếu movieId thiếu catalog hiển thị bản ghi không còn khả dụng, cho xóa khỏi thư viện khi hợp lệ; không bỏ âm thầm hoặc tạo phim giả. Hydrate qua catalog ID hiện có, không bắt buộc chuyển toàn bộ Home/Search sang backend trong M1.

Giữ guest dùng được; không tự ép guest đăng nhập cho mọi thao tác. Không tự import guest sau login. Không đổi chat/CineBot inference để làm thư viện.

## Nghiệm thu bắt buộc

Test behavior với mocked API và backend test DB riêng; không chỉ test tìm chuỗi source:

1. Login/register thành công, sai thông tin, server down/500, malformed success; password có spaces gửi nguyên văn.
2. Saved session valid/expired/forbidden/unavailable; retry và timeout; logout khi restore hoặc login/register đang chờ, không resurrect.
3. Guest mới không có phim mẫu; guest reload còn dữ liệu đã tự lưu; account không nhận guest tự động.
4. A → logout → B và phản hồi A về muộn: mọi watchlist/favorites/ratings/count đều theo B. Mutation A về sau không đổi UI/cache B.
5. Read rỗng xóa stale state; storage malformed; lỗi list có retry; refresh khôi phục dữ liệu backend đã xác nhận.
6. Thêm/xóa watchlist, thích/bỏ thích, tạo/cập nhật rating; pending/double click; failure rollback; timeout kết quả không chắc được reconcile.
7. Backend ownership cho hai users, request không auth, invalid movie/rating; concurrent/duplicate mutation; không trả sensitive user fields.
8. Library item không còn catalog vẫn được giải thích và xử lý, không crash/phantom movie.
9. TypeScript/build; Spring tests qua Maven wrapper với DB riêng, không khởi động vào H2 file dữ liệu người dùng. Browser walkthrough mobile/desktop, keyboard modal, không mất contrast/card click.

Không load/download/train model, không gọi GPU inference hoặc chạy process model thứ hai. Không đổi FastAPI/Qwen, recommendation/chat APIs, framework versions, catalog bulk data hoặc hạ tầng deployment. Không tự tạo tài khoản trên môi trường live để lấy bằng chứng; dùng fixture/server/DB test tách biệt.

## Bàn giao một lần cho M1

Tạo `docs/reports/M1_ACCOUNT_LIBRARY_REPORT.md` theo template nghiệm thu: baseline, changed files, contract/state decisions, schema/migration, acceptance matrix từng hành trình, lệnh/interpreter/exit code thực, ảnh/walkthrough, limitations. Không gọi mock API tests là live integration evidence; ghi rõ thiếu bằng chứng nào.

Tạo `docs/reports/M1_ACCOUNT_LIBRARY.patch` từ snapshot trước milestone, chỉ chứa thay đổi thuộc lượt này; có thể kèm patches từng bước để truy vết. Chạy `git apply --numstat` và `git apply --reverse --check`; không sửa tay hunk header. Giữ mọi thay đổi người khác. Kết thúc **ready for review M1** sau khi hoàn tất cả auth + isolation + persistence + UI, không dừng riêng AUTH-01. Nếu có blocker thật ngoài scope, báo cụ thể và hoàn tất phần độc lập, không nới scope sang AI hoặc M2.
