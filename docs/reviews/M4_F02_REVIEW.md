# M4-F02 — Independent review

2026-10-14. **REQUEST CHANGES: còn1nhóm P2 descriptor terminal failures.** F2/bounded local streams,F3/browser harness và F1/HTTP503 retry đạt checkpoint. Không làm lại backend/streaming,modal,storage hoặc benchmark đã đạt. M4 local chưa accepted; Drive vẫn blocked/not implemented.

Checkpoint M4-F02-CHECKPOINT-01/taskM4-F02/version2/frozen khớp.21manifest entries khớp trước/sau checks; reverse patch check exit0. Không application edits,AI/GPU/liveDB/Drive/OS changes hoặc stop process Gemini/user. Automation vẫn paused/manual. User muốn Gemini đa agent từ prompt kế tiếp.

## Đã đạt độc lập

- Backend bare và exact CI equivalent: **43/43 pass mỗi run**, exit0,JDK25.0.3/target17,H2 riêng. Không gọi local pass là remote GitHub/JDK17 result.
- Frontend **70/70 pass cả Node26 và Node20.20.2**,tsc/build exit0. Component hooks/source checks được phân biệt với browser.
- Dynamic JS Detail143249bytes=139.89KiB<=143360;111bytes headroom. Các routes khác pass; không tăng budget để né sửa.
- Reviewer actual handed walkthrough qua wrapper chỉ redirect output sang temp riêng: exit0. Spring fixture unique in-memory DB/random loopback port; Next production+Chrome decoded playback,time progression,UI timeline3seeks,UI pause/retry,close/focus,mobile controls44px/no collisions đạt. CDP/request/seek deadlines đã có; không còn chờ seeked vô hạn trong run kiểm chứng.
- Stream admission/cleanup: configurable counter-based limit (AtomicInteger trong source; report gọi Semaphore chưa chính xác nhưng không làm sai behavior). Through actual HTTP/gated handler: baseline0->active1->overload429->client disconnect/gate release->active0;health200 riêng. Finally releases on completed/error requests. Đây là permit/handler cleanup evidence, không phải OS-wide socket/thread leak audit. Blocking filesystem IO vẫn có limitations; Drive chưa implement.
- Snapshot before/after3fixture MP4 trong test-media root khớp file count,size,hash. Claim giới hạn monitored root, không OS-wide0writes. Memory unavailable ghi đúng. HTTP TTFB khác browser seek timing; loopback fixture không chứng minh người xem WAN/multi-hour playback.
- R1/public-private,R2/Node20,R5/root,R6/runbook từ F01 giữ fixes; R3route/focus regressions và503 retry có tests. No new finding ở các phần đã chốt.

## T1 — P2: timeout/malformed descriptor không kết thúc loading bằng lỗi có thể retry

frontend/lib/services/mediaService.ts abort controller riêng khi hết6000ms. Fetch rejection là AbortError, nhưng MovieDetail.tsx effect catch(~103) bỏ qua mọi err.name==='AbortError', kể cả timeout nội bộ khi external/route signal chưa abort. Vì thế descriptorLoading không vềfalse, không role=alert hoặc retry. Route cancellation cần im lặng nhưng request deadline cần thông báo lỗi.

Actual production service+component source-execution repro dùng timeout20ms và transport reject theo abort signal cho output:

    serviceError: AbortError
    alertPresent: false
    retryPresent: false

Service còn normalize payload200{} bằng cách bịa movieId từ request và Boolean(undefined)=false, coi malformed là valid empty. Nếu backend trả movieId khác, component .then bỏ qua mà không kết thúc loading/error. Cả hai ca repro không có alert/retry. Đây là cùng1nhóm terminal-state handling còn sót từ F1, không phải feature mới.

Cần phân loại external cancellation vs timeout; validate required shape/movieId/flags/asset-stream fields trước khi coi ready. Chỉ valid response mới được coi hasFeature=false. Timeout,malformed,mismatch phải có terminal error+retry; canceled old request không chạm movie mới. Test pending headers và pending body,route abort,503,200valid-empty,timeout/malformed/mismatch rồi retryrecover200. Không giảm timeout thành timeout=không có video hoặc xóa loading indicator để lấy pass.

Repro reviewer: node docs/reviews/repro/M4_F02_descriptor_timeout.cjs; uses production service20ms timeout+production TSX via handed fake-DOM hooks, không gọi browser fault test. Existing70tests chỉ cover HTTP503 recovery, chưa cover3failure cases trên.

## Evidence / provenance

docs/reviews/evidence/M4_F02: Maven logs,Node20/26,build/budget,browser run,reviewer_benchmark.json,timeout repro và snapshots của Codex-owned files trước handoff. Actual browser output: C:\Users\Admin\AppData\Local\Temp\codex-m4-f02-browser-yR1Y6s. Không ghi đè frozen Gemini evidence. Reviewer đã kiểm tra21hashes stable trước khi sửa control/current prompt cho follow-up.

Manifest F02 include GEMINI_CURRENT_TASK.md,M4_REVIEW_CONTROL.json và M4_GEMINI_CODEX_HANDOFF.md là Codex-owned coordination files. Gemini đã ghi control=reviewing; đây là boundary quy trình cần giữ từ F03: chỉ Codex sửa control/current prompt, Gemini chỉ reports/status. Snapshot pre-review được lưu để phân biệt planned Codex handoff updates với source drift; không sửa/re-hash frozen F02manifest sau review.

## Next

M4-F03 chỉ T1, chia3agents Gemini sở hữu file riêng theo yêu cầu người dùng, agent chính tích hợp regression/budget/artifacts. Control manual/work taskM4-F03/version3 sau khi prompt hoàn tất và checkpoint Git an toàn. Không mở lại automation; không claim agent tự chạy tiếp. Checkpoint push dev không đồng nghĩa accepted/deploy.
