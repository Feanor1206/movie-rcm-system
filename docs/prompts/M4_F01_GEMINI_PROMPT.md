# M4-F01 — Fix local media boundaries, player lifecycle and real evidence

Bạn là Gemini triển khai tại D:\Class\movie-rcm-system, branch dev. Đọc docs/reviews/M4_MEDIA_PLAYBACK_REVIEW.md, M4_MEDIA_PLAYBACK_GEMINI_PROMPT.md và docs/prompts/GEMINI_ENGINEERING_RULES.md. M4 chưa accepted. Đây là follow-up trọn gói cho6nhóm findings, không chia thành nhiều ticket text/CSS hoặc thêm feature. M2/M3 loop vẫn stop/manual.

## R1 — Public policy phải enforced ở server

Guest chỉ xem public assets. Private chưa có entitlement: fail closed/không advertise trong descriptor, kể cả caller đã login; không tự dựng billing/signed URL system. GET/HEAD direct access không lộ private bytes/metadata và không cache-public lỗi/private content. DTO public/isPublic thống nhất contract. Tests qua HTTP thật public+private+descriptor, không chỉ mock/ẩn nút.

## R2 — Test chạy trên Node20 CI

media_playback_suite.mjs đang import TS trực tiếp, Node20 ERR_UNKNOWN_FILE_EXTENSION. Tái dùng transpilation harness/dependency TypeScript hiện có; không nâng Node major/framework để né lỗi. Chạy npm test với Node20 và runtime đang dùng, ghi phiên bản/commands. Thay source-string assertions của player bằng tests thực thi production component/events; browser evidence riêng ở R4.

## R3 — Đúng movie/session và focus không giật

Descriptor/session gắn movieId/asset/version. Route A->B clear/invalidate media state ngay, cancel fetch/stream cũ; lúcBpending không còn nút/video từA. External cancel phải hoạt động, không phụ thuộc duy nhất AbortSignal.any. Validate descriptor movieId/payload đủ để không chơi nhầm; network error có retry trạng thái rõ, không giả thành không có feature hoặc silent fallback che lỗi.

Tách modal open/close focus trap, scroll lock và restore khỏi volume/mute/duration state. Metadata/volume/seek không đưa focus về opener khi player còn mở. Trap bao gồm timeline/volume sliders; keyboard chỉ trong player context, không lấy Space/Arrows của textbox/native controls. Callback/state không stale. Retry chờ metadata+seek hợp lệ rồi resume; autoplay rejection có nút Play, không spinner/error sai. Regression test route swap, slow descriptor, rejected play, retry currentTime, focus sau metadata/volume, Tab qua sliders và close restore. Giữ hành vi thư viện M1-F06/theme xanh.

## R4 — Benchmark thật qua Spring và browser

Không dùng Node Buffer server làm bằng chứng production playback. Dựng test topology riêng: Spring actual app/media handlers với unique in-memory DB và MEDIA_ROOT temp, ffmpeg synthetic MP4 nhỏ đủ dài, Next production với endpoint đúng. Không dùng DB file/live backend hiện tại. Loopback ports riêng, preflight không chiếm service của người dùng; dọn process mình sở hữu trong finally.

Browser asserts play,currentTime tăng,seek gần cuối rồi frame/time tiếp tục,pause/resume,retry khôi phục vị trí,close/cancel,mobile375px. Network check206+actual byte integrity backend, không chỉ nút/ảnh/time gán bằng JS. Đo startup/seek theo actual events/frame callback khi hỗ trợ, raw arrays>=3runs;1/3player concurrency phù hợp; waiting/stall thật hoặc unavailable, không hằng2300ms. Disk growth/memory/active stream+cleanup evidence hoặc limitation cụ thể. Kiểm thử admission/concurrency bounds, overload response, client disconnect cleanup/deadlines không leak.64KiB buffer không được gọi zero heap overflow hoặc RAM benchmark.

Old synthetic HTTP benchmark có thể giữ như transport simulation, label đúng; không overwrite kết quả frozen cũ. Repro reviewer dùng temporary25byte fixture xác minh server policy/integrity, không thay playable-video gate. Không cần chạy Drive/mạng ngoài để chứng minh local path.

## R5 — Storage root chính xác, read-only và availability

Không tự fallback từ configured missing root sang ../../media hoặc ../media. Không Files.createDirectories/write từ GET/HEAD/read path. Missing/unreadable/offline root503,unknown asset404 và known asset missing file theo contract nhất quán. Unknown storageProvider không tự thành local. Test root invalid không đọc kho khác/không tạo folder,provider boundary,symlink/realpath,path traversal,byte ranges integrity,HEAD không body. Giữ bounded streaming và fail có nghĩa khi partial body đã bắt đầu.

## R6 — Runbook và báo cáo trung thực

Baseline Drive tương lai read-only/cache-off; full-cache/bounded SSD chỉ opt-in sau số đo/headroom, không bật hoặc hứa2GBđủ mượt. Không cài/mount/OAuth/sync hay thay settings. APP_MEDIA_DRIVE_MOUNT hiện chưa được wire và Drive adapter là always-unavailable stub: ghi đúng, không hứa cấu hình env làm nó chạy. Có thể wire config/test để doc nhất quán nhưng không cần implement actual Drive trong follow-up local. Drive giữ BLOCKED_EXTERNAL_INPUT/NOT_IMPLEMENTED chính xác. Không PRODUCTION_READY/100%/0stall hoặc tốc độ decoder suy ra từ Node RAM transport.

## Scope/checks/bàn giao

Sửa trong module media backend/frontend/test/scripts/contract/runbook/CI liên quan. Không rewrite auth/catalog/library/theme, thêm episode/HLS/CDN/AI, đổi framework, thêm hạ tầng, động DB live hoặc services người khác. Giữ fixtures nhỏ/temp; không tải phim/copy kho.

Chạy cả mvnw.cmd test và mvnw.cmd test -Dspring.profiles.active=test (DB fixture); npm test dưới Node20/current,tsc,production build,dynamic JS guard <=140KiB; production HTTP và browser playback evidence thật như trên. Old37backend/64frontend là baseline đếm, không giữ tests yếu chỉ để đủ số. Pass/fail/skip rõ, không sửa reviewer repro để lấy pass.

Artifacts F01 riêng: docs/reports/M4_F01_REPORT.md, M4_F01.patch, M4_F01_MANIFEST.json, screenshots/raw metrics/logs và status M4 mới cuối cùng. Không ghi đè artifacts M4 frozen để chữa provenance; report hash mismatch patch cũ và baselinecommit thật. Snapshot own scope trước sửa, patch tạo bằng Git tooling; finalize patch trước hash manifest, không đổi patch sau hashing. Numstat/reverse check và mọi SHA256 entry khớp bytes cuối.

Làm toàn bộ phần độc lập, còn external Drive input thì báo rõ; freeze và dừng ở ready_for_review để Codex nghiệm thu. Không polling,tự accepted/chuyển milestone,tạo nhánh/commit/push/reset. Codex xử lý checkpoint trực tiếp dev theo quyền người dùng. Không AI/FastAPI/Qwen/GPU/model,deploy/OS settings,Drive install/mount/OAuth hoặc DB live.
