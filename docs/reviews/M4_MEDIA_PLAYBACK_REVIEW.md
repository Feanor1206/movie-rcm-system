# M4 — Independent review

2026-10-14. **REQUEST CHANGES. M4 local playback chưa accepted; Drive vẫn BLOCKED_EXTERNAL_INPUT.** Không yêu cầu cài/mount để sửa những findings local dưới đây. M1/M2/M3 acceptance giữ nguyên.

## Checkpoint and checks

Manifest gồm35entries:34hash khớp trước/sau checks, riêng M4_MEDIA.patch đã sai từ lúc nhận. Expected f684e9780e7d2e6ea0537466c9f5ddf820bec5cd32096d89743b56a3c16abcbf, actual b6afe5abe2d3ec292a45b79f65b432a476af4bcc3f193dd78c43edbbc6109f4a. Reverse apply vẫn pass; validity của patch không chứng minh manifest khớp. Source/test/config không drift trong review. Không tự sửa manifest/status của Gemini.

- Exact CI backend command và bare Maven: **37/37 pass mỗi lần**, exit0 trên JDK25.0.3; DB tests H2 riêng, không live DB.
- npm test trên Node26: **64/64 pass**, tsc/build exit0. Media suite gồm3client checks và4source-string assertions, không thực thi player controls/lifecycle. Các old component harness không chạy media effect. Không gọi64tests là64browser/behavior tests.
- Current dynamic JS guard pass: Detail142976gzipbytes=139.63KiB<143360, dù Next display142kB. Các routes khác trong budget; không flag rounding làm lỗi bundle.
- **Node20.20.2**, cùng major CI: new media test module exits1 với ERR_UNKNOWN_FILE_EXTENSION cho mediaService.ts. Xem R2.
- Reviewer production HTTP repro: actual Spring/Tomcat random loopback port + unique in-memory H2 + temporary25byte fixture. Public full/range byte integrity pass; private exposure/root fallback confirmed. Đây không phải MP4 decoder/browser benchmark.
- Reviewer executes actual MovieDetail TSX qua transpilation với hook/fake-DOM harness: route/content và focus regressions confirmed. Không gọi fake-DOM repro là browser evidence. Logs/repro tại docs/reviews/evidence/M4 và docs/reviews/repro/M4_*.

## R1 — P1: private assets được phát công khai và cache public

MediaStreamService.java:37–83 chỉ lọc isAvailable, không isPublic. SecurityConfig cho guest GET/HEAD /api/media/**; controller luôn cachePublic. Qua HTTP thật không Authorization: asset isPublic=false trả GET200/full25bytes,HEAD200 và public max-age3600. Descriptor công khai còn trả feature=codex-private. Do đó biết assetId là đủ đọc nội dung bị đánh dấu private.

Giữ guest public playback; deny/filter private nhất quán ở descriptor, GET và HEAD. Chưa có entitlement thì private không available cho mọi caller, không tự thêm subscription/auth system. Test public/private direct requests, headers/cache và descriptor; không chỉ ẩn nút UI. DTO hiện serialize field public thay vì contract isPublic cũng cần khớp khi sửa boundary này.

## R2 — P1: frontend CI Node20 không chạy được suite mới

frontend/tests/media_playback_suite.mjs:11 import trực tiếp ../lib/services/mediaService.ts có interface/type annotations. Local Node26 strip TS, CI node-version20 không hỗ trợ. Reviewer chạy npm exec --yes --package=node@20 -- node --test tests/media_playback_suite.mjs: exit1 ERR_UNKNOWN_FILE_EXTENSION,0tests pass. Không đổi framework/runtime cả dự án chỉ để né test. Dùng TypeScript transpilation harness như suites hiện hữu, hoặc runner tương thích được khai báo/khóa rõ. Chạy npm test bằng Node20 thực tế và Node hiện tại.

## R3 — P1: stale descriptor mở nhầm phim; P2: focus bị phục hồi trong lúc player đang mở

MovieDetail.tsx:72–108 không reset/key descriptor hay đóng active stream khi movie.id đổi. Reuse component A->B, B descriptor còn pending, feature củaA vẫn hiển thị. Source-execution repro click trênB trả videoSrc=https://fixture.invalid/feature-A.mp4. Mounted boolean chỉ chặn response cũ, không ngăn data đã lưu củaA được dùng choB. Giữ movie/asset version identity cho descriptor và session; invalidation/cancel ngay khi route đổi.

Effect modal tại~178–295 phụ thuộc isMuted,volume,duration; cleanup luôn gọi opener.focus(). Metadata/volume update sẽ cleanup khi modal còn mở. Repro loadedMetadata(duration120) cho playerStillOpen=true nhưng openerFocusCallsDuringMetadata=1. Trap query cũng bỏ input[type=range]; custom keyboard handler bắt toàn window, chặn Space/Arrow kể cả focused control/text input. Tách open/close focus lifecycle khỏi changing playback state; include controls, respect editable targets và native activation/range keys. Kiểm thử actual component và browser: Tab/ShiftTab timeline, metadata/volume không mất focus, close restore đúng, route change không còn stream cũ. Retry/autoplay phải chờ metadata, handle rejected play với state/action đúng; source includes không chứng minh phục hồi currentTime.

## R4 — P1: benchmark/player gate chưa chạy trên production media path

scripts/benchmark_media_playback.cjs dựng createBenchmarkServer(), đọc toàn fixture vào RAM bằng fs.readFileSync, phục vụ Buffer.subarray từ Node giả lập. Không gọi Spring adapter/controller và không có browser/video decoding. startup là roundtrip chunk64KiB; seek là request tới byte offset, không video.seeked/resumed frame. stall là so duration với hằng2300ms, không waiting/playing thực. Concurrency là tiny HTTP requests, không nhiều player đang xem. Kết quả này không chứng minh latency/stalls/heap/disk của app, càng không chứng minh SSD2GB đủ cho Drive.

Prompt M4 đã yêu cầu actual Spring origin + frontend production + playable MP4 browser evidence. Bổ sung harness riêng isolated DB/media root/server-owned ports, assert time progression, seek gần cuối, pause/resume, retry giữ vị trí, close/cancel, mobile. Thu raw observations3runs/start/seek,1/3streams khi thích hợp; unavailable thay fake0. HTTP transport benchmark có thể giữ nhưng label simulation rõ. Thiếu cancellation/limit/resource tests cần hoàn thiện: controller hiện synchronous read/write không có media admission/deadline riêng;64KiB buffer không chứng minh không có thread/resource accumulation hoặc zero heap overflow. Implement bounded behavior có cơ sở cho local path và ghi limitations của blocked filesystem, không xây Drive plane mới.

## R5 — P2: explicit root bị fallback sang kho khác; read request tự tạo root

LocalMediaStorageAdapter.java:40–52 nếu configured root không tồn tại sẽ chọn ../../media hoặc ../media. HTTP repro configuredRoot=temp/explicit-root-does-not-exist nhưng actualRoot=D:\Class\movie-rcm-system\media. Đây là silent switch storage boundary; root cấu hình sai/offline phải unavailable, không phục vụ kho mặc định. resolveValidatedPath:77–83 còn Files.createDirectories trong read path; missing root có thể bị biến thành folder rỗng và404 thay503. Không fallback khi explicit config mất, không tạo directories khi đọc. Test missing/offline root503 và không write/mutate, missing asset/file404 rõ; provider không biết phải fail rõ thay mặc định local. Giữ canonical/realpath boundary tests.

## R6 — P2: runbook trái quyết định disk/cache và mô tả Drive chưa thực thi

MEDIA_STORAGE_RUNBOOK.md:85–98 gợi ý --vfs-cache-mode full không --read-only, không bounded disk budget. Report kết luận cache2GB đủ mượt khi chưa đo Drive; bỏ kết luận này. User chỉ đồng ý cân nhắc SSD sau benchmark, không cho tự bật full-cache. Baseline read-only/cache-off; SSD comparison là opt-in có headroom/capacity limits, chưa chạy thì ghi chưa chạy.

Runbook APP_MEDIA_DRIVE_MOUNT không được nối bằng placeholder trong YAML; DriveMediaStorageAdapter hiện luôn throw ngay cả khi mount tồn tại. Giữ Drive gate blocked và ghi rõ đây là stub/chưa implement, không hứa chỉ cài mount/env là dùng được. Chưa cần triển khai Drive adapter thật để khép local fixes. Bỏ PRODUCTION_READY/100%/Zero Heap Overflow không có bằng chứng. Sửa reports qua artifacts F01 mới, không ghi đè frozen originals.

## Next gate

Một follow-up M4-F01 giải quyết đồng thời6nhóm trên, không mở tính năng mới. Tạo fresh patch/manifest đúng byte cuối sau khi artifacts hoàn tất. Drive external blocker không làm giảm gate local/browser. Không sửa AI/theme/library, không mount/install/live DB/deploy. Codex chỉ review/docs và push checkpoint dev theo quyền người dùng; checkpoint chưa accepted không phải production release.
