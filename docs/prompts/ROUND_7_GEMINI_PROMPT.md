# Vòng 7 — Gom sửa D1–D3 và hoàn thiện bằng chứng gate M2

promptVersion: 7
targetRoundId: 7
milestone: M2
reviewMode: manual
reviewedRunId: run-round6-20261014-0826

Bạn là Gemini triển khai tại D:\Class\movie-rcm-system. Đọc docs/reviews/LOOP_ROUND_6_REVIEW.md và contract M1/M2 hiện hành. Codex giữ vai trò nghiệm thu; bạn sửa application code. M2 chưa accepted; không sang M3 hoặc AI. Review thủ công: hoàn tất checkpoint rồi kết thúc lượt, không polling/chờ control trong background.

## Làm chung trong lượt này theo thứ tự

1. **D1: Main detail hiển thị ngay khi lookup chính thành công.** Tách vòng đời similar rail khỏi loading/error/404 chính. Similar chậm/thất bại không được chặn các hành động lưu/đánh giá của phim đã load. Giữ cancellation và guard ở các async boundary, không cho callback cũ đổi trạng thái của request mới/unmounted. Không cần làm lại router. Test production component: main 200 + similar pending vẫn thấy đúng movie và actions; similar reject/timeout không biến main thành error/404; main404/network vẫn đúng.

2. **D2: Hero dùng đầy đủ M1 pending/uncertain intent.** Watchlist ADD chưa xác nhận hiện thử lưu lại; DELETE chưa xác nhận hiện thử xóa lại; nhãn chữ/aria/badge và request cùng ý định. Pending có feedback/chống submit trùng; confirmed trở về toggle bình thường. Dùng selectors hiện có, không sửa journal/actor isolation của WatchlistProvider nếu không thật cần. Tests Hero thực với production provider + fixture transport tái hiện POST/DELETE commit nhưng mất response, reconcile lỗi, click retry; xác nhận method và dữ liệu backend fixture.

3. **D3: TTL và giới hạn metadata Profile có hiệu lực.** Loại bỏ đường vòng remoteMovies found tồn tại vô thời hạn. Đặc tả trigger revalidation rõ, tối thiểu item được truy cập lại sau TTL hoặc refresh phù hợp. Không tạo timer polling nền. Cả cache/state có giới hạn hoặc cleanup IDs không còn cần; dedupe watchlist/favorites/ratings và cleanup abort an toàn. Fake clock >5 phút: remove/re-add/refetch X phải đọc metadata mới; kiểm tra 200→404 và 200→network error. 404 khác unavailable; không xóa library vì metadata lỗi; giữ M1-F06 rating retry.

4. **Khép phần evidence M2 còn thiếu, không mở dự án ETL.** Bổ sung journey dùng production components/provider, fake persisted transport và canonical ID ngoài local fixture: khám phá→lưu/chấm điểm→remount/reload provider→Profile đọc đúng IDs/điểm. Ghi rõ mock/component và browser evidence khác nhau. Nếu công cụ browser có sẵn, walkthrough desktop/mobile qua fixture API riêng; ảnh và quan sát ghi vào report, không đụng tài khoản/DB live. Nếu chưa làm được ghi đúng giới hạn và phần còn lại, không coi build pass là visual acceptance.

5. **Catalog data handoff nhỏ, review được.** Chuẩn bị fixture JSON + preview/dry-run từ animation records có sẵn trong repository, ghi provenance chính xác là repository fixture chưa xác minh bên ngoài. Giữ IDs hiện có, không fuzzy match hay overwrite conflict. Không copy video giả hoặc stock photo làm media đúng tác phẩm: bỏ/null media không có căn cứ. Preview phải nêu add/skip/conflict và policy additive/idempotent, kiểm thử trên file/fixture/test DB riêng; chạy lần hai không nhân đôi, existing record khác metadata phải báo conflict. Không tự apply DB live, không tự seed production, không tải media. Có thể chỉ tạo công cụ preview an toàn và runbook; không cần endpoint import công khai.

## Phạm vi

frontend/app/movies/[id]/page.tsx; frontend/features/home/components/EditorialHero.tsx; frontend/features/profile/components/ProfileOverview.tsx; components phụ nhỏ nếu cần; frontend/tests/m2_journey_suite.mjs và tests liên quan; docs/contracts/M2_CATALOG_CONTRACT.md; fixture/preview script được đặt rõ dưới scripts hoặc docs/fixtures. Không sửa backend nghiệp vụ đã accepted nếu không cần cho preview; không sửa source AI/FastAPI/Qwen hoặc dữ liệu live. Không làm lại Search/M1/theme, không nâng framework/tách service mới. Giữ tone xanh lá, contrast, responsive, media nullable và canonical IDs.

## Kiểm tra và bàn giao

Chạy toàn bộ 4 frontend suites, TypeScript, production build và Search repro. Nếu backend không đổi ghi prior evidence 17/17, không gọi là vừa chạy. Tests mới assert hành vi đúng, không copy implementation. ROUND_6_cutover_repro.cjs là diagnostic hiện tại assert lỗi tồn tại; không sửa artifact reviewer và không dùng exit 0 đó làm acceptance sau fix.

Chốt checkpoint nhất quán khoảng 30 phút, ưu tiên hoàn tất ba fixes cùng regression trước. Nếu evidence/fixture chưa đủ, ghi phần còn lại trung thực, không tự đóng M2. Snapshot riêng bảo toàn dirty tree. Tạo docs/reports/ROUND_7_REPORT.md, ROUND_7.patch và ROUND_7_MANIFEST.json (SHA256 own changed/new/deleted files, git status); numstat/reverse check phải hợp lệ. Report tách lệnh vừa chạy khỏi prior evidence, browser khỏi component, trạng thái fixes khỏi milestone acceptance.

Freeze source rồi publish docs/reports/M2_M3_STATUS.json cuối cùng với ready_for_review, roundId=7, promptVersion=7, runId mới và paths artifacts. Không sửa file control/current prompt/review Codex. Không commit/push/reset/deploy, không GPU/model/AI/DB live, không dừng process người khác. Kết thúc lượt để người dùng gửi Codex nghiệm thu.
