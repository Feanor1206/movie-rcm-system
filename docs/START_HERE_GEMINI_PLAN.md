# Bắt đầu triển khai: kỹ sư trưởng, Gemini và nghiệm thu

**Cập nhật hiện hành 14/10/2026:** Người dùng đã hủy theo dõi tự động, automation PAUSED. Gemini thực hiện prompt hiện hành vòng 4, bàn giao rồi kết thúc; người dùng gửi report để Codex review thủ công. Không vòng chờ/polling hoặc tự đợi heartbeat.

**Quy trình mới nhất:** Gemini code theo vòng khoảng 30 phút → freeze checkpoint → Codex review → Codex cập nhật `docs/prompts/GEMINI_CURRENT_TASK.md` và publish `GEMINI_REVIEW_CONTROL.json` cho vòng kế. Protocol tại `docs/GEMINI_CODEX_REVIEW_LOOP.md`; scope M2/M3 giữ nguyên, các quyền tự vượt milestone gate cũ được thay thế.

**Gate mới nhất (14/10/2026):** M1-F06 đã ACCEPTED tại `docs/reviews/M1-F06_REVIEW.md`. Người dùng cho phép prompt triển khai liên tục M2/M3; Gemini tự kiểm tra/sửa trong scope, Codex nghiệm thu sau. Prompt hiện hành `docs/prompts/M2_M3_AUTONOMOUS_GEMINI_PROMPT.md`, thay các yêu cầu dừng xin duyệt giữa M2/M3. AI để sau.

**Cập nhật ưu tiên mới nhất:** Giao theo milestone lớn; phần AI để sau. Tài liệu điều phối hiện hành là `docs/PRODUCT_MILESTONES.md`. Giao Gemini **M1 — Account & Library** bằng `docs/prompts/M1_ACCOUNT_LIBRARY_GEMINI_PROMPT.md`, gộp AUTH-01/LIB-01/LIB-02; không dừng bàn giao ở từng ticket con. Nếu AUTH-01 đã bắt đầu thì kế thừa trong M1. Các đoạn “ticket tiếp theo AUTH-01” bên dưới là lịch sử và được cập nhật này thay thế.

Ngày: 13/10/2026. Chỉ lập kế hoạch, prompt và tiêu chí nghiệm thu. Codex không sửa mã ứng dụng trong quy trình này; Gemini là người triển khai. Bạn quyết định sản phẩm và nhận kết quả review.

**Trạng thái hiện hành:** Hệ thống đã có frontend, Spring Boot nghiệp vụ, FastAPI discovery pipeline và Qwen fine-tuned. Đây là kế hoạch cải tiến trên hệ thống hiện hữu, không phải danh sách phần chưa xây. SERVE-01-F02 đã accepted. UX-01A cùng F01/F02 đã **accepted**, review cuối tại `docs/reviews/UX-01A-F02_REVIEW.md`. Ticket giao tiếp theo là **AUTH-01** theo `docs/prompts/AUTH-01_GEMINI_PROMPT.md`, sửa frontend auth hiện có. Không làm lại serving, theme hoặc Spring auth. Snapshot và bảng roadmap bên dưới là lịch sử đề xuất, không thay thế trạng thái hiện hành này.

## 1. Quyết định đã chốt

- Website khám phá phim hoạt hình, giao diện tone xanh lá, nhẹ nhàng, mobile dễ dùng.
- Người dùng khám phá được khi chưa đăng nhập; lưu/đồng bộ theo tài khoản thật.
- Chọn phim tối nay, tìm lại phim, reference similarity, personalization và refinement là các hành trình chính.
- Không spoil mặc định; có nguồn/unknown cho metadata và content facets; không tự gán nhãn phù hợp trẻ em.
- Spring Boot sở hữu nghiệp vụ/catalog/identity/library; FastAPI sở hữu engine AI và artifacts dẫn xuất.
- Qwen3-4B + LoRA đã fine-tune; giữ full serving policy, không tải/huấn luyện lại cho các ticket nền.
- Recommender và ranking được xây, giải thích, đánh giá độc lập với LLM.
- Phạm vi hiện hữu là discovery. Chưa mở rộng thành hệ thống hosting/playback toàn bộ phim.

## 2. Snapshot sau khi đọc lại mã

Đã kiểm tra lại working tree, code frontend/backend/AI, seeds, proxy, Docker, tests và tài liệu. Branch quan sát: `chore/taicautruc`; có nhiều thay đổi tracked/untracked chưa commit. Không coi toàn bộ diff đang có là patch mới của Gemini.

| Quan sát hiện tại | Nguồn chính | Việc cần xử lý |
|---|---|---|
| Theme đen/đỏ, metadata nói điện ảnh chung | frontend/tailwind.config.ts, app/globals.css, app/layout.tsx | Tokens xanh lá và nội dung animation |
| Home dùng movies local; personalized rail đảo danh sách; trending chưa có đo usage | frontend/app/page.tsx | Catalog thật và nhãn danh sách trung thực |
| Detail/hero gắn 4K/HDR/Dolby và đường video dự đoán | frontend/features/movies/components/MovieDetail.tsx; home/EditorialHero.tsx | Chỉ hiện capability/media có dữ liệu |
| Auth lỗi kết nối tạo mock user/token; invalid me chưa xóa state | frontend/lib/context/AuthContext.tsx | AUTH-01 |
| Library dùng khóa storage chung, default phim mẫu, sync lúc mount và nuốt lỗi lưu | frontend/lib/context/WatchlistContext.tsx | LIB-01 và LIB-02 |
| Client chat bỏ sessionId; catch ở CineBot chỉ console, thiếu lỗi nhìn thấy được | frontend/lib/services/chatService.ts; features/chat/components/CineBot.tsx | Gateway/session/error UX |
| Next route và Nginx đều chuyển chat trực tiếp FastAPI | frontend/app/api/chat/route.ts; infrastructure/nginx/default.conf | DISC-02 cutover có compatibility |
| Movie API search/genre xử lý else-if, không kết hợp; không paging | backend/springboot/controller/MovieController.java | CAT-01 |
| Runtime string, genres CSV; catalog seed Spring khác frontend/AI | Java entity/DTO, SQL seeds, frontend/lib/data/movies.ts, DEFAULT_MOVIES | Contract, DATA-01, CAT-01 |
| DataInitializer không có profile guard và tạo demo accounts/interactions | backend/springboot/config/DataInitializer.java | FND-01 môi trường/seed |
| FastAPI default session dùng chung, memory dictionary không TTL, history chưa vào full-model prompt | backend/fastapi/schemas.py, ai_pipeline.py, qwen_service.py | DISC-02/03 và AI-NLU |
| Retrieval dùng word overlap; recommender lấy 8 phim; matchPercentage clamp 75–99 | backend/fastapi/services/ai_pipeline.py | AI-01/02 và DISC-01 |
| Recommend endpoint dùng DEFAULT_MOVIES khi kết quả rỗng | backend/fastapi/main.py | DISC-01: không phá constraints/no-results |
| Metadata health full+GGUF fallback vẫn ghi Qwen3-4B | backend/fastapi/services/qwen_service.py | SERVE-01-F01 |
| Train recommender/ranker chỉ ghi config; benchmark predictions cố định | ai/training, ai/evaluation/evaluate_metrics.py | AI-01 rồi CF/MF/hybrid thật |
| CI chỉ TypeScript, trigger main/master/develop | .github/workflows/ci.yml | FND-02: Python/Java/TS và branch policy rõ |

Các số liệu test/live health trong review trước là bằng chứng lịch sử. Lượt lập kế hoạch này đọc mã, chưa rerun build/tests hoặc inference. Gemini phải ghi đúng môi trường và kết quả thực của từng ticket.

## 3. Cách giao việc

1. Dùng `docs/prompts/GEMINI_ENGINEERING_RULES.md` làm hướng dẫn chung cho Gemini.
2. Giao đúng một ticket; mỗi ticket có prompt, phạm vi và acceptance riêng.
3. Gemini đọc source trước, ghi baseline, triển khai phần được giao và kiểm tra phù hợp.
4. Gemini trả changed files, diff riêng của lượt làm, lệnh/kết quả, limitations và report tồn tại thật.
5. Codex review source/diff, chạy lại kiểm tra cần thiết và kết luận accepted / changes requested / needs evidence.
6. Nếu cần sửa, Codex đưa prompt follow-up nhỏ. Chỉ chuyển ticket phụ thuộc sau khi gate liên quan đạt.

Không giao một prompt “làm toàn bộ web và AI”. Không tự commit/push/reset hoặc đổi branch. Không cần có thêm agent/service để bắt đầu.

## 4. Thứ tự bắt đầu

| Thứ tự | Ticket | Kết quả | Nghiệm thu chính |
|---|---|---|---|
| 1 | SERVE-01-F01/F02 — accepted | Đã review/sửa và nghiệm thu, không làm lại | 23 tests pass, 2 skipped, valid F02 patch |
| 2 | CONTRACT-01 | Contract và fixtures cho catalog/discovery/library | Một ý nghĩa field xuyên 3 lớp; schemas/examples/error states đầy đủ |
| 3 | DATA-01 | ETL/validation và pilot animation catalog có nguồn | ID ổn định, runtime số, unknown rõ, no fabricated media/facets |
| 4 | FND-01 | Dev/prod/test baseline và seed policy | Không demo account/interactions ở prod; test DB tách data thật |
| 5 | CAT-01 | Catalog published thật, search/filter/detail và snapshot | Filters kết hợp, paging ổn định; DB/API/AI cùng ID/version |
| 6 | AUTH-01 | Auth thật và state xác thực đúng | Backend down không login giả; 401/403 clear; password không trim |
| 7 | LIB-01 | Guest/account isolation và sync read state | A→logout→B, response A về muộn không làm bẩn B |
| 8 | LIB-02 | Watchlist/rating/favorite/watched mutations | Idempotency, state saved thật, retry/rollback; không gộp guest tự động |
| 9 | UX-01 | UI xanh lá, animation catalog và lối chọn phim nhẹ | Mobile/keyboard, truthful labels/media, loading/empty/error |
| 10 | AI-01 | Evaluation framework và baseline thật | Metrics hand-check, splits freeze, không predictions hard-code |
| 11 | AI-02 | TF-IDF/cosine/content features và artifact | Toy tests, reproducible vectors, version tương thích |
| 12 | DISC-01 | Structured discovery không cần Qwen | Runtime/year/excludes đúng, evidence, no-results thật |
| 13 | DISC-02 | Gateway/session ownership và route cutover | UI→Spring→FastAPI, scope/versions/internal auth, errors đúng |
| 14 | UX-02 | Chọn tối nay → chips → ba kết quả → lưu | Một journey end-to-end với constraints và lỗi nhìn thấy được |
| 15 | AI-RETR / AI-NLU | Tìm lại/reference và Qwen follow-up | Identity metrics, history-aware patch, no shared default session |
| 16 | AI-PROFILE / AI-CF / AI-MF | Gu/cold-start/CF/MF thật | Profile ảnh hưởng thật; temporal split và baseline comparisons |
| 17 | AI-HYBRID / AI-EVIDENCE | Conditional ranker, MMR, reasons | Tuned weights, ablation, không phần trăm giả/claim thiếu evidence |
| 18 | UX-03 / SERVE-02 | Compare/choose, jobs/performance | Chọn phim dễ hơn; queue/deadline/cancel đúng; không nhân weights |
| 19 | EXT-01 | Group/context/why-not/counterfactual | Core stable, quyền và constraints đúng, evidence đủ |

Tickets 15–19 là nhóm cần tách nhỏ sau nghiệm thu vòng đầu; chưa giao như một ticket lớn. FND-02 CI bổ sung theo component từ đầu, không chờ hoàn thành AI.

UX-01 có thể thiết kế tokens/layout bằng fixtures contract sau bước 2 nếu cần thấy UI sớm, nhưng chỉ accepted cho luồng catalog thật sau CAT-01. Không ghi nhãn production hoặc personalization cho preview fixture.

Mốc đầu tiên có giá trị: web animation xanh lá với catalog thật, auth đúng và library riêng. Mốc thứ hai: chọn tối nay chạy end-to-end, không chờ full CF/MF mới dùng được.

## 5. Prompt sẵn dùng

**Ticket tiếp theo hiện hành: AUTH-01**. Gemini đọc `docs/prompts/AUTH-01_GEMINI_PROMPT.md` và sửa frontend auth đang có; Codex nghiệm thu độc lập. Không có prerequisite xây lại catalog/contract để sửa lỗi auth này.

UX-01A đã qua vòng review gốc và F01; các findings được khắc phục trong F01/F02. Các review cũ ghi trạng thái lịch sử, không phải lệnh giao lại.

F02 đã đóng finding Navbar: TypeScript/build, patch checks và browser mobile đều đạt. UX-01A đã đóng trong phạm vi được giao; auth và library production có nghiệm thu riêng.

- Hướng dẫn chung: `docs/prompts/GEMINI_ENGINEERING_RULES.md`.
- Ticket đầu tiên: `docs/prompts/SERVE-01-F01_GEMINI_PROMPT.md`.
- Ticket contract: `docs/prompts/CONTRACT-01_GEMINI_PROMPT.md`.
- Ticket data: `docs/prompts/DATA-01_GEMINI_PROMPT.md`.
- Ticket auth hiện hành: `docs/prompts/AUTH-01_GEMINI_PROMPT.md`.

Các prompt tiếp theo được Codex chốt dựa trên contract đã accepted và diff thực tế; tránh pre-generate implementation details trái schema mới.

## 6. Nghiệm thu bắt buộc

Ba lớp: đúng trải nghiệm → đúng nghiệp vụ → đúng kỹ thuật.

- UX: hành trình hoàn thành, tone xanh lá, mobile/keyboard, không misleading labels, có đường tiếp tục khi lỗi.
- Nghiệp vụ: identity/ownership, feedback scope, hard constraints, unknown, retry/idempotency, phiên bản.
- Kỹ thuật: giới hạn tài nguyên, meaningful tests, contract compatibility, artifact/migration và error behavior.

Một report “100% pass” không thay thế kiểm tra coverage và source. Không tính tests skipped là passed; không tính unit mock là benchmark inference thật. Không yêu cầu chạy GPU suite khi offline tests đủ cho patch.

Mẫu report Gemini: `docs/reports/<TICKET>_REPORT.md` theo `docs/prompts/ACCEPTANCE_REPORT_TEMPLATE.md`. Codex ghi kết luận riêng khi review, không sửa mã ứng dụng để làm thay Gemini.

Các findings SERVE-01-F01/F02 đã đóng. Trước mỗi ticket tiếp theo cần xác định chính xác phần còn thiếu so với code/runtime; không triển khai lại module đã có hoặc đồng loạt chạy các prompt phía sau.
