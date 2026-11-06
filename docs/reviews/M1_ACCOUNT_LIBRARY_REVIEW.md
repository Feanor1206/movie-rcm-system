# M1 — Review độc lập

Ngày: 13/10/2026. Verdict: **CHANGES REQUESTED**. Chưa nghiệm thu M1; chưa chuyển M2. Có 2 findings P1 và 6 nhóm P2 dưới đây. Codex chỉ tạo tài liệu/repro, không sửa mã ứng dụng.

## Kiểm tra đã chạy

- Patch numstat và reverse --check: exit 0, 21 files; artifact parse được và khớp current tree.
- TypeScript check: exit 0. Production build: exit 0, compile/type validation/prerender hoàn tất; 7/7 là progress prerender, không phải mọi route đều static.
- `node --test tests/m1_behavior_suite.mjs`: 9 pass, exit 0, nhưng suite không import hoặc chạy code ứng dụng (R8).
- Spring Maven wrapper, JAVA_HOME `C:\Program Files\Java\jdk-25.0.3`, profile test, datasource override `jdbc:h2:mem:codex_m1_review`: 6 tests pass, 0 skipped/errors, exit 0, 20,891s. Không sử dụng DB file người dùng.
- Repro độc lập chạy actual TSX providers qua TypeScript transpilation và hook adapter tối thiểu: `node docs/reviews/repro/M1_runtime_repro.cjs`. Output lưu tại `docs/reviews/repro/M1_runtime_repro_output.json`. Không copy implementation auth/library vào test, không network/DB. Đây là deterministic source execution, không phải React DOM/browser integration; cần suite React thực tế ở lượt sửa.
- Không chạy GPU/FastAPI hoặc live browser login. Chưa có bằng chứng walkthrough UI; không cần mở rộng kiểm tra hình thức để bỏ qua các blockers đã tái hiện.

## R1 — P1: Auth vẫn hồi sinh sau logout trong lúc đọc body

`frontend/lib/context/AuthContext.tsx:245–259`, tương tự verifySession 96–105 và register 348–361: generation được kiểm tra sau fetch nhưng trước `await res.json()`. Khi logout/đổi account diễn ra trong lúc body đang đọc, response cũ vẫn commit user/token/storage vì không kiểm tra lại sau await. Timer cũng bị clear ngay khi có headers nên body chậm có thể chờ vô hạn.

Repro actual login: headers nhận → JSON deferred → logout → JSON resolve. Kết quả `status=authenticated`, stored token tồn tại. Phải guard mọi commit sau async boundary, timeout bao gồm body; cleanup/unmount cũng invalidates request generation.

## R2 — P1: Mutation trễ của A ghi state vào B

`frontend/lib/context/WatchlistContext.tsx:332–338`, favorites 413–419, ratings 473–479: mutations không capture/check actor hoặc generation, không có abort controller. Generation guard chỉ tồn tại ở list reads. Catch rollback dùng snapshot A và finally/success toast vẫn tác động actor mới.

Repro: A có A-private-film → A add đang chờ → B load B-film → A request reject. Watchlist B biến thành `[A-private-film]`. Đây là vi phạm ownership trực tiếp, trái báo cáo zero leakage. Guard cả success/catch/finally/toast và pending state; state hiển thị phải gắn actor để không lộ snapshot cũ ở render chuyển tài khoản.

## R3 — P2: Mutation thiếu timeout, rollback làm mất thao tác khác

Watchlist 267–338 và các mutations còn lại: pending lock chỉ dựa trên React state của render; fetch không timeout/signal; success chỉ kiểm tra HTTP ok; rollback thay cả collection bằng snapshot cũ.

Repro: X pending → Y thành công → X fail: danh sách từ `[X,Y]` thành `[]`, mất Y dù backend đã lưu. Gọi cùng callback hai lần trước rerender gửi 2 writes. Request chưa resolve giữ pending với không timer hoạt động. Cần lock đồng bộ theo actor/movie/action, operation-aware rollback/reconcile, finite timeout và validation envelope; request timeout chưa rõ outcome không được coi chắc chắn chưa ghi DB.

## R4 — P2: Unverified bị coi là guest; library lỗi không cập nhật auth

WatchlistContext 130–143, 274–290, 355–371, 437–446 và isGuestMode: `!isAuthenticated` bao gồm checking/unavailable. Mutation trong session chưa xác minh được ghi vào guest storage và báo lưu, dù người dùng chưa chọn guest. Repro unavailable tạo guest entry account-click.

Library read 172–175 và writes chỉ xử lý generic error cho 401/403, không báo cho auth để reverify/invalidate; repro 401 write vẫn giữ auth authenticated. Retry list bắt đầu bằng xóa toàn bộ state 124–126, nên lỗi refresh còn làm mất dữ liệu đã xác nhận. Malformed list success được coi là empty thay vì error.

Auth validation 259/361 chỉ yêu cầu token/id truthy: repro `{id:'bad-id',token:{unexpected:true}}` vẫn authenticated với thiếu username/email. Cần runtime validation required field types, phân biệt guest/checking/unavailable, giữ snapshot đã xác nhận cho same-actor refresh lỗi, phối hợp 401 và 403 theo contract (permission forbidden không tự đồng nghĩa token invalid). Không chuyển UI thành guest để nuốt lỗi xác minh.

## R5 — P2: Backend không kiểm tra catalog; tin metadata client

WatchlistService 38–63, FavoriteService 38–63 cho phép movieId bất kỳ: findById empty vẫn save, và client title/poster không rỗng thắng catalog. RatingService không truy vấn catalog. Contract nói ID phải tồn tại nhưng source không thực hiện; backend test còn dùng movie-1/movie-2/movie-3 không có fixture catalog rõ ràng và expect 200.

Cần reject ID không tồn tại bằng error có cấu trúc, lấy metadata chuẩn từ catalog khi thêm mới; giữ khả năng xóa orphan cũ. Test fixture seed movies riêng, invalid ID và forged title/poster. Không bịa mapping tiêu đề hoặc thêm phim giả để che gap catalog/frontend; nếu ID hiện hữu không khớp phải xử lý rõ trong UI và report.

## R6 — P2: Idempotency chỉ đúng request tuần tự

WatchlistService 33–35, FavoriteService 33–35 và RatingService 30–46 đều check-then-save. Hai transaction cùng thấy empty sẽ cùng insert: UNIQUE ngăn duplicate row nhưng request thua có thể constraint violation/500. Không có recovery/locking/upsert đảm bảo response ổn định. Các tests hiện chỉ gọi tuần tự, không chứng minh concurrent writes như milestone yêu cầu.

Chọn cơ chế transaction/idempotency hợp với H2 test và PostgreSQL runtime, xử lý race mà không reuse transaction đã rollback-only. Test thật hai request/transactions được đồng bộ barrier, verify responses và final row count; rating ordering policy rõ. Không yêu cầu chạy vào PostgreSQL live của người dùng.

## R7 — P2: Profile chưa lookup backend và thiếu xóa orphan rating

`frontend/features/profile/components/ProfileOverview.tsx:45–54` chỉ lookup mảng movies local, không hydrate qua API catalog. Movie có trong DB nhưng ngoài fixture local bị nói “có thể đã bị gỡ”. Rating orphan 350–371 không có action xóa; branch ratings trong handleRemoveMissingItem 77–85 lại gọi toggleWatchlist, không xóa rating. Endpoint DELETE rating mới chưa có context action/consumer.

Cần lookup backend theo ID và phân biệt 404 với network/error; chỉ xác nhận absent sau kết quả có căn cứ. Thêm removeRating đúng actor/pending/error; không mutate watchlist khi xóa rating. Các nút xóa orphan phải có pending/duplicate prevention. Không mở rộng M2 chuyển toàn bộ Home/Search.

## R8 — P2: Frontend suite tự mô phỏng và báo cáo quá coverage

`frontend/tests/m1_behavior_suite.mjs:23` mô tả simulation; cả 9 tests tự viết fetch/state/generation/rollback trong file, không import AuthContext/WatchlistContext hoặc module production. Bỏ production guard hay đưa mock login trở lại không làm suite fail. Các R1/R2/R3 tái hiện dù 9/9 pass.

Thay bằng tests gọi actual production provider/state module, mocked transport/storage và deferred promises/fake timers. Kiểm tra các interleavings và tất cả acceptance scenarios. Có thể tách logic production dùng chung để test hoặc dùng React test harness tối thiểu; không tạo implementation riêng chỉ cho test. Cập nhật report từ pass-count sang bằng chứng coverage thật và walkthrough chưa kiểm tra; tránh “ngăn chặn hoàn toàn/100% zero leakage”.

## Bàn giao tiếp theo

Một follow-up tổng hợp **M1-F01** theo `docs/prompts/M1-F01_GEMINI_PROMPT.md`, không tách thành tám lượt giao. Sau khi khắc phục và review lại đủ gates M1 mới giao M2.
