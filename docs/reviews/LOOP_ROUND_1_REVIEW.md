# Vòng 1 — M2 backend catalog

Ngày 14/10/2026, Asia/Bangkok. roundId=1, promptVersion=1, runId=`run-round1-20261014-0245`.

Verdict: **CHANGES REQUESTED cho backend contract/filter; cho phép tiếp tục vòng 2 để sửa trong scope**. Đây là checkpoint review, không nghiệm thu toàn milestone M2.

## Freeze và kiểm tra độc lập

- Status ready_for_review và manifest khớp 7/7 ownChangedFiles SHA256 trước review. Control đã chuyển reviewing trước checks.
- Patch numstat/reverse --check: exit 0, 7 files. Có browse DTO, JPA Specification executor, DB pagination, filter kết hợp/year, sort whitelist và id ASC tie-break.
- Maven wrapper, JAVA_HOME `C:\Program Files\Java\jdk-25.0.3`, profile test, datasource override `jdbc:h2:mem:codex_round1_review`: 15 tests pass, 0 skipped/failures/errors, exit 0, 13,235s. Gồm 8 auth/library và 7 catalog integration. Không DB file/live hoặc GPU.
- Kiểm tra lại manifest 7 hashes và ready_for_review/runId sau tests: không source drift. Frontend không thay đổi trong checkpoint nên không rerun frontend/build; số frontend checks của Gemini là report evidence, không phải kiểm tra mới của Codex vòng này.

## R1 — P2: Genre filters vẫn substring, trái token contract

MovieService lines 53, 142–154 và filterByGenre vẫn dùng LIKE `%genre%`. Browse `genre`, `genres`, `animationOnly` không match token CSV chính xác như contract: genre=Drama cũng khớp token Melodrama; genre=Animation/animationOnly có thể nhận token NonAnimation. Genre chứa wildcard `%` hoặc `_` mở rộng match ngoài intended literal input. Trim DTO output không sửa predicate query.

Cần một predicate token-match dùng chung, normalize spaces/case quanh tokens và escape pattern metacharacters hoặc giải pháp query phù hợp H2/PostgreSQL. Giữ DB pagination, không fetch-all rồi lọc memory. Genre đơn và multi AND cùng semantics; Animation constraint phải là token Animation thật. Test near-match tokens, whitespace/case, null genres, combined filter và literal wildcard.

## R2 — P2: Legacy search thay semantics tùy có genre

Contract ghi search trong title và description. getAllMovies(search,genre) khi cả hai dùng OR title/description nhưng search-only gọi searchMovies → findByTitleContainingIgnoreCase (line 80), bỏ description. Ví dụ “time” chỉ nằm description Your Name: `/api/movies?search=time` không có Your Name, thêm genre=Animation lại xuất hiện, trái tính chất filter chỉ thu hẹp kết quả.

Cần dùng shared search predicate semantics title/description cho search-only và combined/ browse, giữ list envelope/API compatibility. Test description-only search với/không genre và null description. Không mở rộng sang AI semantic search.

## Contract notes cho vòng kế

- Header APPROVED FOR IMPLEMENTATION do Gemini ghi chưa phải Codex approval; dùng draft/ready_for_review đến khi gate đạt.
- Ví dụ Spirited Away đang gắn videoUrl `/videos/the-last-orbit.mp4`; thay null/unknown để không đưa asset sai phim vào contract/client fixture.
- Ghi rõ search/query precedence; nullable/year/rating policy phải khớp schema thực và unknown behavior, không bịa giá trị để thỏa non-null. Tối thiểu không coi nullable media là valid image/video bắt buộc ở frontend.

## Vòng 2

Ưu tiên sửa R1/R2 và thêm regression tests. Sau backend tests đạt, nếu còn thời gian thì bắt đầu shared frontend catalog client và boundary tests; chưa chuyển toàn bộ Home/Search hoặc M3 trước backend semantics đúng. Prompt tiếp theo đã ghi trong GEMINI_CURRENT_TASK.md version 2, control publish work cho roundId 2. Chỉ M2 khi toàn journey/canonical IDs/URL/UI gates đạt mới giao M3.
