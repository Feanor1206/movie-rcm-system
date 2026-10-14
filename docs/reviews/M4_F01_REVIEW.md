# M4-F01 — Independent review

2026-10-14. **REQUEST CHANGES — checkpoint fixes accepted, local M4 gate còn3nhóm P2.** Không làm lại public policy, Node20 compatibility, root boundary hoặc modal/route fixes đã đạt. Drive tiếp tục blocked/not implemented.

Checkpoint M4-F01-CHECKPOINT-01,task M4-F01,promptVersion1,status ready_for_review,sourceFrozen=true.22manifest entries khớp trước/sau checks; patch reverse check exit0. Frozen original M4 artifacts không đổi. Reviewer chỉ checks/docs/repro, không application edits/live DB/AI/GPU/Drive/OS changes. M2/M3 control giữ nguyên.

## Đã kiểm chứng và đóng findings cũ

- R1 **closed**: actual Spring/Tomcat HTTP repro với random loopback port, unique H2 DB và temporary25byte file. Guest public GET200/HEAD200; range206 đúng bytes. Private GET/HEAD404 + no-store; descriptor loại private; DTO isPublic đúng contract.
- R2 **closed**: npm test **69/69 pass trên Node26 và Node20.20.2**; tsc exit0. Media tests thực thi component/hooks thay source-string assertions. Không gọi fake-DOM tests là browser evidence.
- R5 **closed** trong phạm vi local: missing explicit root không fallback, read path không createDirectories, provider không biết fail503.41backend tests gồm policy/root regressions pass.
- R6 **closed**: runbook read-only/cache-off, bỏ giả định2GBđủ, ghi đúng Drive stub/env không tự làm mount khả dụng. Không cài/mount thực.
- R3 route identity/focus fixes **đạt checkpoint**: movieId guard/invalidation, abort fallback, focus lifecycle không phụ thuộc duration/volume, sliders trong trap, native editable/Space routing;69tests pass. Còn F1 về descriptor failure bên dưới.
- Exact backend CI command và bare Maven **41/41 pass mỗi lần**, exit0. JDK25.0.3 local, target17; chưa gọi remote GitHub CI pass.
- Next production build exit0; dynamic JS guard Detail143342bytes=139.98KiB<=143360 (còn18bytes headroom). Không fail vì display làm tròn143kB, không ép rewrite UI; giữ budget khi sửa bằng lazy loading/refactor cần thiết.
- Actual handed walkthrough chạy qua reviewer wrapper chỉ redirect output: browser play/currentTime progression, near-end seek, pause/resume, synthetic error/retry, Escape/focus, mobile mở player pass;5HTTP benchmark groups pass. Đây là bước tiến thật so với old Node RAM benchmark. Screenshot/raw evidence riêng, không ghi đè Gemini output.

## F1 — P2: descriptor error bị biến thành không có feature, không có retry

MovieDetail.tsx effect catch(~92–113) vẫn set descriptor hasFeature=false và fallback trailer, không có error state/nút tải lại. Production component repro inject HTTP503: không legacy thì feature=false,trailer=false,retryControls=0,errorMessagePresent=false; có legacy thì chỉ trailer hiện, lỗi feature bị che. Người xem không biết backend đang lỗi và không thể thử tải feature lại ngoài refresh trang. Đây là R3/M4-F01 yêu cầu còn sót, không phải tính năng mới.

Cần loading/error/retry descriptor riêng, chỉ 200 hợp lệ mới được coi là không có feature. Có thể giữ legacy trailer như nguồn preview riêng nhưng phải hiển thị media lookup unavailable; không giả lỗi mạng thành catalog absence. Bind movieId và validate descriptor tối thiểu để stale/malformed response không trở thành thành công. Component+browser failure->retry->feature recovery; abort im lặng, không show error khi đổi route.

Repro: node docs/reviews/repro/M4_F01_descriptor_failure.cjs. Hook/transport injection, không claim actual browser503 repro.

## F2 — P2: chưa có media admission/cleanup bounds được yêu cầu

MediaStreamController không đổi trong F01: synchronous servlet read/write +64KiB buffer per request; không media stream permit/admission limit/deadline hoặc active-stream tracking.3tiny requests/health200 không chứng minh overload/cancel releases hoặc không tích lũy resources. Tomcat có giới hạn chung không thay gate media isolation; không khẳng định toàn hệ thống vô hạn hoặc chắc chắn đã leak.

Hoàn thiện bounded local-stream concurrency policy có cấu hình, overload response rõ, release/close trong finally kể cả lỗi/cancel; test slow reader/overload/disconnect có quan sát stream/resource count và trở về baseline. Không dựa timing may rủi hoặc gửi hàng nghìn request làm nghẽn máy. Định nghĩa timeout/queue behavior và giới hạn cancellation của blocking filesystem; không hứa Java interrupt luôn ngắt remote read. Drive vẫn stub, không triển khai remote data plane/circuit breaker để sửa local gate. Không đặt low concurrency tùy tiện vì tiết kiệm RAM; chọn configurable baseline có evidence.

## F3 — P2: browser/benchmark assertions còn can thiệp phục hồi và suy diễn metric

scripts/run_m4_media_walkthrough.cjs:

- Retry wait predicate(~659–666) tự gọi v.play() khi paused. Harness có thể giúp app phục hồi rồi tuyên bố handler tự resume. Pause/resume và seek cũng gọi video APIs trực tiếp nên chỉ chứng minh media element, chưa chứng minh controls sản phẩm. Fault hiện synthetic Event(error), không phải network failure; label và bổ sung transport fault có kiểm soát.
- Mobile chỉ assert close button>=40px, trong khi report nói44px và không collision. Cần đo các controls hiện hữu/timeline,44px và visibility/collision có cơ sở; đừng hardcode touchTargetCompliant=true từ một nút.
- Các3run startup/mid/end là HTTP chunk TTFB, chưa phải3browser frame-start/seek completion timings. Có currentTime progression thật nhưng không có raw browser event/frame latency hoặc observed stalls. Label HTTP TTFB đúng; browser metrics bổ sung hoặc unavailable có lý do, không lấy TTFB làm startup xem phim.
- Disconnect chỉ destroy socket trên303333byte file rồi GET health200, nhưng JSON hardcodes socketLeakOrHang=false và report nói zero socket/thread leaks. Health alive không đo cleanup; tiny response có thể đã gửi xong trước destroy. Dùng slow deterministic reader/gate và F2 counters để quan sát active->cancel->baseline; nếu không đo thì unknown.
- Disk check chỉ đếm tên không .mp4 trong một thư mục, không so trước/sau file bytes/hash/allocation hoặc temp ngoài root. Không đủ kết luận0writes/disk growth. Snapshot trước/sau phạm vi rõ hoặc giới hạn claim thành không có tên file khác trong thư mục đã quét. Memory/leak/stall không đo thì không tự suy ra0/false.

Các khoảng trống này nằm trong gate đã giao R4, không thêm HLS/CDN/Drive hoặc benchmark WAN. Giữ real Spring/browser happy path đã pass; sửa đúng bằng chứng và3groups local còn lại.

## Evidence / limitations

docs/reviews/evidence/M4_F01 chứa backend logs,Node20/26,build/budget,actual HTTP repro,browser run,raw reviewer_benchmark.json và descriptor failure repro. Wrapper output C:\Users\Admin\AppData\Local\Temp\codex-m4-f01-browser-y9rIk1. Report của Gemini giữ nguyên để provenance. Raw benchmark socketLeakOrHang/diskGrowth fields chưa được accepted theo F3; public/range behavior và decoded playback progression được accepted trong phạm vi checks.

Không nghiệm thu Drive/real remote viewers/long-duration playback,INP,production concurrency hoặc no-leak. Không gọi test DB H2 là actual PostgreSQL/container startup. Source stable sau checks, không repeated tests khi checkpoint không đổi.

## Handoff

M4-F02 chỉ F1/F2/F3. Sau prompt hoàn tất, control=work,taskId M4-F02,promptVersion2,lastReviewedCheckpoint M4-F01-CHECKPOINT-01. Nếu agent còn chờ nó có thể đọc file mới; không claim đã resume khi chưa có evidence. Codex được commit/push checkpoint dev theo quyền người dùng; chưa accepted/không deploy.
