# Vòng 3 — Catalog boundary fixes

Ngày 14/10/2026, Asia/Bangkok. roundId=3, promptVersion=3, runId=`run-round3-20261014-0615`.

Verdict: **CHECKPOINT ACCEPTED để triển khai Search/Browse ở vòng 4**. Không phải nghiệm thu toàn M2; Home/Detail/Profile cutover và journey/browser gates còn phía sau.

## Freeze và kiểm tra độc lập

- Manifest 5/5 own files SHA256 khớp trước và sau checks. Status/runId ready_for_review ổn định. Control reviewing khi kiểm tra.
- Patch numstat/reverse --check exit 0, 5 files đúng scope.
- Maven wrapper với JDK 25.0.3, profile test và H2 in-memory riêng `codex_round3_review`: 17/17 pass (8 auth/library + 9 catalog), 0 skipped/failures/errors, exit 0, 12,879s.
- Catalog service actual-source suite: 9/9 pass, exit 0; TypeScript noEmit exit 0. Chưa build/UI test vì client chưa mount vào Search/Home trong checkpoint này. M1 suite không đổi, không rerun chỉ để tăng pass count.
- Không app code edits, DB live/GPU hoặc commit/push trong review.

## Findings vòng 2

- C1: executeWithLifecycle giữ timeout/caller abort qua cả fetch và body, cleanup trong finally; tests body timeout/external abort/pre-aborted pass. UI vòng 4 phải xử lý cancellation và generation guard, không hiển thị caller cancel thành network error.
- C2: malformed page/movie bị reject, không còn phantom empty/id/numeric zero; required fields được validate. Detail other-movie bị reject; HTML/empty HTTP 404 trả null trước parse. Blank query fallback search tương ứng backend. Việc literal case-sensitive ID equality chưa được test (source dùng lowercase comparison); trước nối Detail hãy giữ canonical ID đúng contract, không coi đổi case là mapping.
- C3: REGEXP_LIKE token boundaries xử lý repeated/outer whitespace và tabs, giữ multi-word genres; search shared predicate và DB pagination vẫn còn. Compose dùng PostgreSQL 16, khớp SQL function mà patch chọn. Runtime PostgreSQL chưa chạy, chỉ H2 mode evidence; không gọi đó là live production SQL verification.

## Vòng 4

Triển khai Search/Browse UI một lát cắt đầy đủ: URL source of truth, animationOnly, query+genres/year+sort/page, debounce/cancellation/stale response guards, loading/empty/error/retry và M1 card actions. Giữ shared client và backend đã kiểm tra. Không mount local fixture fallback để che API lỗi. Cần tests actual production Search/client, canonical link IDs, URL reload/back và async response ordering.

Chưa yêu cầu đổi Home/Detail/Profile cùng vòng để giữ checkpoint kiểm tra được. Nếu có thời gian chỉ chuẩn bị kế hoạch cutover tiếp, không tự chuyển M3. UI media thiếu cần placeholder không crash, không bịa metadata hoặc ảnh phim khác.
