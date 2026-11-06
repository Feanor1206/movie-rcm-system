# M1-F01 — Khắc phục tổng hợp findings nghiệm thu M1

Bạn là Gemini, kỹ sư triển khai tại `D:\Class\movie-rcm-system`. Đọc `docs/reviews/M1_ACCOUNT_LIBRARY_REVIEW.md`, `docs/prompts/M1_ACCOUNT_LIBRARY_GEMINI_PROMPT.md`, engineering rules và contract M1. Thực hiện trọn follow-up R1–R8 rồi bàn giao một lần, không chờ duyệt từng finding. M1 hiện CHANGES REQUESTED; không chuyển M2.

## Scope và baseline

Giữ mọi thay đổi đang có và các phần đã đúng: bỏ mock auth, raw password, guest namespace, favorite persistence, theme xanh lá/contrast/card stacking. Không làm lại M1 từ đầu. Snapshot trước F01 bằng script/file thao tác có kiểm tra; không lồng pwsh -Command double quotes làm mất biến. Patch F01 chỉ chứa changes lượt này.

Được sửa frontend auth/library/consumers, Spring library/catalog lookup tối thiểu và tests liên quan. Không sửa FastAPI/Qwen/AI, bulk catalog/ETL, framework versions hoặc hạ tầng mới. Codex là reviewer; bạn triển khai.

## Những lỗi cần sửa

### R1: Auth guard xuyên suốt request

- verify/login/register kiểm tra generation và cancellation sau mọi await, ngay trước mọi commit state/storage/modal/result.
- Timeout bao gồm fetch headers và body parsing; cleanup trong finally. Logout/account switch/unmount vô hiệu hóa request cũ.
- Deferred body test: headers xong → logout/login B → body A về phải không phục hồi A.
- Runtime validate token string không rỗng, ID theo backend type/range, required username/email/role; không authenticated chỉ vì token/id truthy. Không tự thêm role/default identity để che malformed response.

### R2: Actor isolation cho toàn bộ mutations

- Capture actor/session generation và operation identity cho mỗi write, abort khi actor đổi.
- Success/catch/finally/rollback/toast/pending chỉ áp dụng nếu operation còn thuộc actor hiện hành. Không dựa riêng vào AbortController vì response có thể đã về.
- State được gắn actor để render khi chuyển tài khoản không hiện library cũ trước effect cleanup.
- Test A write deferred → logout → B loaded → A reject/resolve; B UI/storage/pending/toasts không bị ảnh hưởng. Áp dụng watchlist/favorites/ratings/removeRating.

### R3: Consistency, timeout và duplicate writes

- Pending lock đồng bộ, không chỉ React state stale trước render. Hai calls cùng actor/movie/action trong một tick không gửi hai writes.
- Rollback theo operation/item hoặc reconcile backend; X fail không làm mất Y đã success. Xử lý read-refresh và writes về sai thứ tự.
- Timeout hữu hạn cho writes/body; state thoát pending. Với unknown outcome, read reconcile hoặc retry idempotent, không khẳng định DB chưa ghi.
- Validate HTTP + success envelope/payload; 200 với success=false/malformed không được toast saved.

### R4: Auth/library states và errors trung thực

- Guest thật mới được ghi guest storage. checking/unavailable không tự fallback thành guest; UI nói rõ chưa xác minh và cho retry hoặc logout/chọn guest chủ động.
- Library 401 phối hợp auth invalidation/reverification. 403 phân biệt quyền bị cấm và session invalid theo contract, không invalidate mù quáng mọi forbidden.
- Same-actor refresh lỗi giữ snapshot đã xác nhận; actor change vẫn clear/ẩn snapshot cũ.
- Payload list malformed là error, không empty thành công; response empty hợp lệ vẫn replace đúng.
- Corrupt storage kiểm tra types/IDs/rating range; storage write fail không báo đã lưu bền vững.

### R5: Catalog validation và metadata chuẩn

- Watchlist/favorite/rating thêm hoặc cập nhật phải kiểm tra movieId tồn tại, trả status/envelope có cấu trúc khi invalid.
- Title/poster chuẩn lấy từ catalog; giữ request fields nếu cần compatibility nhưng không tin client metadata.
- Vẫn cho xóa legacy orphan; không drop DB hoặc tự xóa lịch sử.
- Tests seed Movie fixtures rõ, invalid ID và forged metadata. Không dùng movie-1 không tồn tại rồi expect add success. Không đoán mapping ID theo title hoặc bịa phim để pass.

### R6: Concurrent idempotency

- Sửa check-then-insert race bằng cơ chế transaction/upsert/locking/recovery đúng stack. UNIQUE chỉ ngăn duplicate rows, không tự đảm bảo response không 500.
- Recovery tránh transaction đã rollback-only. Giữ compatibility H2 tests/PostgreSQL runtime; ghi policy concurrent rating updates.
- Kiểm tra actual concurrent requests/transactions bằng barrier cho watchlist/favorite/rating, final count và outcomes; không chỉ gọi tuần tự.

### R7: Profile hydration và remove rating

- Library metadata lookup qua API catalog theo ID cho records ngoài local fixture. Network/5xx không gắn nhãn đã bị gỡ; 404 có empty/orphan state đúng.
- Thêm removeRating trong context/consumer gọi DELETE ratings đúng, có pending/error/actor guard. Xóa rating không gọi toggleWatchlist.
- Nút xóa orphan ở mọi tab chống duplicate và có feedback. Không chuyển toàn bộ Home/Search sang backend trong F01.

### R8: Kiểm thử actual application và báo cáo đúng

- Thay simulation suite bằng tests import/chạy production code. Dùng mocked fetch/storage, deferred responses/body và fake timers; không copy state machine vào tests.
- Có thể tách logic dùng chung ra module production và test module đó kèm provider wiring, hoặc dùng React harness tối thiểu. Không nâng framework.
- Regression tests phải thất bại trên baseline M1 với R1/R2/R3; ghi command/evidence, không yêu cầu giữ source baseline lỗi trong working tree.
- Reviewer repro `docs/reviews/repro/M1_runtime_repro.cjs` là minh họa, không thay suite React/application hoàn chỉnh và không phải acceptance oracle cần sửa để xanh.
- Bao phủ original M1 acceptance cùng R1–R7. Chạy TypeScript/build, Spring tests DB test riêng và browser walkthrough khi môi trường cho phép. Nếu chưa browser verify phải ghi needs evidence, không nói đã kiểm tra UI.

## Bàn giao

Tạo `docs/reports/M1-F01_REPORT.md`, `docs/reports/M1-F01.patch`; cập nhật contract/report M1 những claims sai mà giữ lịch sử minh bạch. Ma trận R1–R8: changed source, test gọi code nào, interleaving/input, expected/actual và lệnh exit code thực.

Patch numstat/reverse --check pass từ snapshot F01, không sửa tay hunk headers. Ghi migration/compatibility và limitations, không mô tả DROP favorites table là rollback không mất dữ liệu. Không commit/push/reset; không DB live, tạo live account hoặc GPU process. Kết thúc READY FOR REVIEW M1-F01 khi hoàn tất cả nhóm.
