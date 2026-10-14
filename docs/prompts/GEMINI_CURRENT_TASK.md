# M4-F02 — Khép3findings local media còn lại

taskId: M4-F02
promptVersion: 2
reviewedCheckpoint: M4-F01-CHECKPOINT-01

Bạn là Gemini tại D:\Class\movie-rcm-system,branch dev. Đọc docs/reviews/M4_F01_REVIEW.md và docs/M4_GEMINI_CODEX_HANDOFF.md. R1/public-private,R2/Node20,R5/root,R6/runbook cùng route/focus fixes đã đạt: không làm lại. M4 còn đúng F1/F2/F3 dưới đây. Không mở features hoặc cài/mount Drive/AI. Loop M2/M3 vẫn đóng.

## F1 — Media descriptor loading/error/retry trung thực

Không set hasFeature=false chỉ vì lookup500/timeout/malformed. Tách loading/error/ready; retry rõ trên MovieDetail. Legacy trailer có thể giữ riêng như preview nhưng không che lỗi feature lookup. MovieId/asset identity và validation tối thiểu phải ngăn data sai/stale thành thành công. Abort/route change im lặng và cancel. Test production component503->visibleerror->retry->200feature; browser fault/recovery. Không refresh cả trang để giả retry hoặc bịa feature.

## F2 — Bounded local streams và observable cleanup

Controller64KiB/request chưa có media admission policy. Thêm configurable stream concurrency bound/overload response, close+release finally và queue/deadline behavior rõ; tránh worker/executor queue vô hạn. Test slow/gated read hoặc controlled slow client để giữ stream thật active, thử overload, cancel, verify counters/resources về baseline. Counter test phải gắn handler thật, không fake health200=no-leak. Không cần expose debug endpoint production; test-only hook/bean instrumentation được.

Định nghĩa blocking filesystem cancellation limits trung thực; không hứa interrupt luôn ngắt IO remote. Drive vẫn stub, không viết remote adapter/circuit breaker mới. Chọn configurable baseline có bằng chứng, không đóng đinh low limit vì giả định thiếu RAM/CPU. Không tạo tải nặng lên services người dùng. Preserve GET/HEAD/range/private/availability semantics và resource byte integrity.

## F3 — Browser controls và benchmark evidence không tự giúp app

Giữ isolated Spring actual origin+Next production+small playable MP4. Wrapper/benchmark phải output F02 riêng. Retry assertion chỉ quan sát: bỏ v.play() hoặc sửa currentTime giúp handler bên trong wait predicate. Click actual play/pause/timeline controls để kiểm chứng UX; native APIs dùng riêng cho setup/fault phải label. Có network/media fault có kiểm soát ngoài synthetic Event(error), chứng minh retry giữ vị trí và resume do app.

Mobile375px: assert44px/visibility/layout cho các controls thực và timeline, không chỉ close>=40px rồi true. Tiếp tục desktop+focus close, metadata/volume không giật focus,Tab slider giữ hành vi.

Đo raw browser startup/seek theo events/frame callbacks khi hỗ trợ,>=3runs với conditions rõ; không gọi HTTP TTFB là video startup/seek-to-frame. waiting/stall/memory nếu không đo được thì unavailable/unknown, không fake0/false. HTTP TTFB/1+3request throughput có thể giữ với label đúng, không gọi3HTTP downloads là3concurrent viewers.

Cleanup dùng F2 observable counters+gated read cho active/cancel/drain, không dùng health200 suy zero socket/thread leak. Disk evidence snapshot trước/sau file list+sizes/hash trong test root và temp scope theo dõi; không giả định .mp4 không thể bị ghi hoặc không có filename mới là0writes. Không có OS-wide measurement thì giới hạn claim, không hứa no-leak/zero-write toàn hệ thống. Bỏ stale throughput>100MB/s statement khi raw data không support. Không có real Drive thì không đề xuất fixed cache/SSD hoặc phát mượt mạng ngoài.

## Checks và scope

Scope: MovieDetail/media client/component tests; media controller/service/config/test-only server+integration tests cho admission/cleanup; walkthrough scripts/raw evidence/report/contract nếu cần. Không rewrite catalog/auth/library/theme hoặc add player features mới. Bundle hiện Detail143342/143360bytes chỉ còn18bytes: giữ budget bằng lazy-load/refactor gọn cần thiết, không tăng ngân sách/đổi framework hoặc bỏ tests để pass.

Hai lệnh Maven bare/exactCI với DB fixture riêng; npm test Node20/current;tsc/build/dynamic guard;actualHTTP+browser tests F1/F2/F3. Chỉ rõ old passed scope và failures thật. Không sửa reviewer repro/artifacts,không app/source writes sau freeze. Không restart service user/DBlive,kill process người khác hoặc modelGPU/AI.

Tạo docs/reports/M4_F02_REPORT.md,M4_F02.patch,M4_F02_MANIFEST.json và M4_F02_STATUS.json có taskId/runId/promptVersion2/status ready_for_review/sourceFrozen. Manifest mọi own changed/new/deleted files+artifacts cuối,patch Git tooling từ snapshot baseline thật;numstat/reverse check,hash stable. Report/data F01 và originalM4 giữ nguyên. Drive gate blocked riêng.

Sau freeze làm theo M4_REVIEW_CONTROL.json: reviewing/await thì không sửa source;work cho task/version mới thì đọc prompt;stop thì dừng. Không tự accepted,tạo nhánh/commit/push/reset hoặc mở milestone mới. Codex review và xử lý checkpoint trực tiếp dev. Nếu agent kết thúc thì file không tự khởi động lại; không tạo watchdog.
