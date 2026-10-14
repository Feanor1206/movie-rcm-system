# DRIVE-01 — Google Drive mounted storage, Windows, parallel agents

taskId: DRIVE-01
promptVersion: 1
branch: dev
baseline: 7c825b6 (M4 local ACCEPTED; verify current HEAD before work)
handoff: manual; no automation or polling

## Mục tiêu và phạm vi

Người dùng giao triển khai tiếp Google Drive để lưu/phát video hoạt hình từ máy Windows, yêu cầu nhiều agent song song. Ưu tiên phát/tua mượt và tránh hết ổ cứng; RAM/CPU không phải mục tiêu tiết kiệm. M4 local đã accepted, không mở lại như một checkpoint chưa đạt. Hoàn tất implementation đọc media từ mount, công cụ vận hành review được, tests và evidence; không chỉ viết thêm thiết kế hoặc dừng ở câu “thiếu rclone”. Drive thật là gate riêng nếu thiếu prerequisites/user OAuth/test folder.

Đọc trước: docs/reviews/M4_F03_REVIEW.md, docs/contracts/M4_MEDIA_PLAYBACK_CONTRACT.md, docs/DRIVE_MEDIA_STORAGE_DESIGN.md, docs/STORAGE_PERFORMANCE_DECISION.md, docs/runbooks/MEDIA_STORAGE_RUNBOOK.md, adapter/interface/controller/service hiện có. Tài liệu cũ mô tả trước M4 hoặc stub là lịch sử; source hiện tại và review accepted là baseline. Không sửa frozen M4 reports/patches/manifests/screenshots hoặc reviewer files để làm tests pass.

Topology được chọn: rclone + WinFsp read-only Windows mount -> Spring native cùng account/session -> API descriptor/GET/HEAD/Range hiện có -> production player. Không thêm Direct Drive API data plane thứ hai, không biến Drive share URL thành video src, không đưa Google token cho browser. Không thêm HLS/transcode/episodes/AI hoặc sửa giao diện không liên quan.

## Điều phối bắt buộc: ba subagents thực, ownership riêng

Agent chính khảo sát working tree trước, chốt contracts/config/error semantics và file ownership trước khi dispatch. Giữ nguyên thay đổi có sẵn, đặc biệt backend/fastapi/.env.example ngoài scope. Sau đó cho A/B/C chạy song song; không để cả ba chờ nhau hoặc sửa cùng file. Nếu tool chỉ cho ít agent hơn, chạy theo slots thực và ghi rõ; không bịa IDs/delegation. Không spawn agents chỉ để đốt quota. Thu kết quả trước tích hợp; agent chính sở hữu final artifacts.

| Owner | Công việc và file sở hữu |
| --- | --- |
| Agent A — storage boundary | DriveMediaStorageAdapter.java; helper/classes mới dưới service/storage nếu cần; tests mới DriveMediaStorageAdapterTest.java. Thay stub bằng reader read-only root chính xác, path boundary, availability/error semantics; không tự sửa controller/service/interface/config chung. |
| Agent B — Windows operations | scripts/drive/*.ps1 và tests tooling riêng; docs/runbooks/GOOGLE_DRIVE_WINDOWS_RUNBOOK.md mới; template cấu hình không secrets. Preflight, mount command generator/launcher explicit, status và stop-owned-process; không chạy install/mount/OAuth trong lượt code. Không sửa adapter/backend/harness của C. |
| Agent C — verification | scripts/run_drive_media_walkthrough.cjs mới; test-only DriveWalkthroughServer.java và DriveMediaStreamingIntegrationTest.java mới; fixture/evidence generator riêng. Test provider=drive qua production Spring HTTP và production browser; không dùng local provider rồi gắn nhãn Drive. Không sửa application source của A hoặc scripts M4 đã accepted. |
| Parent — contract/integration | MediaStorageAdapter.java nếu cần; MediaStreamService.java, MediaStreamController.java, shared streaming/deadline helpers/config/exception mapping, application YAML, package/CI nếu cần; docs/contracts/DRIVE_STORAGE_CONTRACT.md; current design/runbook links; final artifacts. Chỉ parent tích hợp cross-cutting, sau khi thông báo contract cho A/C. |

Đường dẫn Java có prefix backend/springboot/src/main/java/com/dippie/moviercm/ hoặc src/test/java/com/dippie/moviercm/. Nếu cần đổi ownership, parent thông báo trước rồi mới chuyển; không có concurrent writers. Không sửa MovieDetail/mediaService/frontend features trừ khi integration chứng minh regression cần sửa; parent ghi lý do và thu hồi owner trước. Existing83 frontend và43 backend là baseline, không hardcode tổng khi thêm tests.

## Contract backend và IO cần chốt trước code

1. Dùng app.media.drive-mount / APP_MEDIA_DRIVE_MOUNT đã có, mặc định trống=disabled/unavailable. Root bắt buộc explicit, không fallback local root/working directory/parent drive, không mkdir hay ghi cache/media. Không auto-detect tùy tiện toàn Drive. Provider drive đọc đúng configured root; local behavior giữ nguyên.
2. Relative path chỉ từ asset đã đăng ký. Reject absolute/drive-relative/UNC/device paths, traversal cả separators Windows, NUL/alternate data streams, reparse/symlink escape. Resolve real root/target containment; thử junction/symlink Windows thực nếu quyền cho phép, nếu không ghi limitation. Không lộ Windows path/token trong lỗi public. Không tự scan toàn kho hay sửa is_public/is_available hàng loạt.
3. Availability phải nhất quán giữa probe/descriptor/stream: cấu hình trống/mount unavailable/read denied -> lỗi503 có thể retry; asset không đăng ký/private vẫn404; missing file trong root healthy phân biệt rõ404; source disconnect không giả thành catalog movie404. Không advertise ready từ Files.exists(root) đơn thuần khi adapter còn không đọc được. Không cache “healthy” vô hạn hoặc tạo HEAD/probe tải video đầy đủ. Health Drive tách catalog/local và có bounded work.
4. Quan trọng cho remote seek: controller hiện dùng InputStream.skip(start). Không giả định skip luôn là remote random access hoặc tua cuối không đọc bỏ cả file. Chốt abstraction ranged reader phù hợp (SeekableByteChannel/FileChannel position hoặc equivalent thực tế), mở tại requested offset, bounded buffer; kiểm chứng thực tế. Không đọc toàn phim vào heap/tempfile; không thêm bộ shared RAM cache phức tạp khi chưa có measurement. Preserve Range bytes/open-ended/suffix/416, GET/HEAD/content length/MIME, asset version/ETag, cancellation và admission429.
5. Mất mount/đọc chậm: finite configured deadlines cho metadata/open/read, bounded concurrency/queue và fail-fast circuit khi nguồn lỗi. Không claim Future.cancel(true) hoặc servlet timeout chắc chắn ngắt WinFsp/filesystem IO. Nếu dùng worker bị block, chỉ release actual worker capacity khi IO thật kết thúc; client timeout không cho phép tạo worker mới vô hạn. Tránh executor unbounded, task-per-chunk overhead hoặc timeout treo toàn Spring/local. Giới hạn read-only command/child process probes nếu dùng. Report chính xác soft deadline vs hard cancellation và OS IO limitation.
6. Lỗi trước commit ->503/no-store/retry policy hợp lý; sau response bắt đầu thì đóng stream, log sanitized và player retry hiện có; không thể sửa status sau commit. Không swallow/trả truncated body như success trong test. Stream close/disconnect phải đóng channel và permits. Preserve M4 private streams không public, descriptor terminal handling, identity/focus và retry currentTime.
7. Không tự ghi live DB. Tạo mapping manifest mẫu bằng canonical IDs + assetId/provider=drive/relativePath/version/verified size; preview validate-only, conflict/idempotency report và test DB apply riêng nếu cần. Không hardcode phim bất kỳ vào live catalog, không mặc định bật public cho video thật. Đăng ký live là bước review cụ thể sau.

## Windows toolkit: hoàn chỉnh và an toàn để vận hành

Preflight read-only: Windows version, rclone executable/version, WinFsp detection đáng tin cậy (không chỉ tìm service có chữ WinFsp), drive letters/path collision, backend account/session visibility, free disk/RAM. Không dump rclone.conf, env secrets hoặc config show có token; không scan Drive. Cho phép paths có space/Unicode, dùng LiteralPath và argument arrays, không shell-string injection.

Scripts có parameter Remote/RemoteSubpath/MountPoint/ConfigPath, config path ngoài repo. Không chốt M:/X: hoặc tên remote đoán là của người dùng. Default chạy plan/preflight/-WhatIf; mount chỉ khi explicit -Execute sau khi remote/folder và credentials được người dùng cấu hình. Block target đã chiếm dụng, không mount chồng local folder chứa dữ liệu. Kiểm tra kết quả root backend đọc được rồi mới báo healthy; chạy cùng account/session, không tự elevate/global-mount/firewall/registry/startup task/service.

Baseline --read-only --vfs-cache-mode off. RAM buffer32M/file và chunk8M tăng32M chỉ là candidate baseline; validate flags theo rclone version/official docs, kiểm tra ảnh hưởng parallel chunk streams trước kết luận. RAM budget theo active streams, không nạp cả phim trước Play. Không tạo RAM disk, đổi pagefile, mirror/sync/copy toàn kho. Logs có rotation/size bound, config/token ngoài repo. Tắt disk cache không đồng nghĩa toàn OS/browser0writes.

Start helper nếu chạy background dùng Start-Process -WindowStyle Hidden; lưu PID+start time+executable+mount identity trong state file riêng không secrets. Stop chỉ process do helper tạo, revalidate identity để tránh PID reuse, không kill theo tên rclone/node/java/chrome, không dừng mount/user process khác. Rollback stop owned mount + revert session env, không xóa video/config/remote. Không tự cài WinFsp/rclone hoặc thực hiện OAuth chỉ vì script đã được viết; cung cấp lệnh chính thức cụ thể cho bước setup sau review. Không tạo polling/watchdog chờ người dùng hàng giờ.

Người dùng cho phép cân nhắc SSD thêm nhưng chưa yêu cầu mua. Cache-off trước. Không tự bật full cache; nếu cần đề xuất disk cache, giải thích bằng đo before/after, working-set/peak/free-space reserve và dung lượng cần. --vfs-cache-max-size không phải hard cap tuyệt đối khi file đang dùng; đừng hứa giới hạn2GB cố định.

## Verification và gate tách bạch

G1 IMPLEMENTATION: adapter thật + scripts + docs + isolated tests pass. G2 MOUNTED_DRIVE: WinFsp/rclone thật, remote/folder thật do user chọn, backend thấy mount, actual Drive reads. G3 BROWSER_DRIVE: Spring provider drive + browser decoder play/seek/retry trên file thật. Không nghiệm thu G2/G3 bằng temp local directory hay CDP fake responses.

- Unit/integration production code với root temp nhỏ, H2 riêng: traversal/reparse/error classification/disabled/healthy/missing/read denied; HEAD+full/range đầu/giữa/cuối/open-ended/suffix/416 byte integrity, private404, ETag/size; startup/offline/recovery và no root creation. Fault injection blocking reader để chứng minh bounded workers/queue/circuit và cancellation accounting; ghi rõ simulation. Existing backend full bare và profile test, frontend suites trên Node20 và current runtime, tsc/build/dynamic JS<=143360B. Không tăng budget cho tính năng storage backend.
- Toolkit tests command arguments/cache-off/read-only/collision/dry-run/no secret leakage/owned stop identity; mock process launch không mount hoặc kill máy thật để test.
- Actual Spring HTTP + production browser fixture provider=drive: decoded frames/time advance,3 UI seeks gồm gần cuối, pause/play/cancel/retry, source unavailable->error->recovery; no stale movie state. Timeouts hữu hạn cả CDP/seek; isolated free ports, không chiếm/dừng services đang chạy. Không bypass auth/private policy để test dễ. Output DRIVE_01 riêng; không ghi đè M4 evidence. Fixture phải nhỏ và tổng disk evidence có bound, không tạo video GB để benchmark.
- Nếu chưa có prerequisites/OAuth/folder: vẫn hoàn tất G1/fixture checks, publish G2/G3=BLOCKED_EXTERNAL_INPUT kèm input/setup chính xác; không dừng coding từ đầu và không gắn nhãn full Drive acceptance. Chỉ cần user thao tác OAuth/permissions/chọn test folder; không yêu cầu gửi token vào chat. Không claim agent tự resume sau khi kết thúc.
- Nếu có mount hợp lệ đã được user giao: chỉ test file/folder explicit read-only, không upload/delete hoặc scan khác. Đo cold/warm startup, seeks p50/p95 + sample count, stall duration/ratio,1/2 rồi3/5 sessions nếu baseline ổn; ghi bitrate/upstream requests/bytes nếu đo được, memory/disk before-after, cancel resources. Chọn profile bằng so sánh thực, không hứa “mượt nhất” từ loopback hoặc1sample. Không giả vờ revoke token/disconnect mount người dùng để fault test; dùng isolated owned mount hoặc simulated reader ghi đúng provenance. Không benchmark WAN nếu chỉ dùng localhost.

## Bàn giao có giới hạn, không tự lặp vô hạn

Làm một checkpoint có nghĩa trong khoảng45–60phút; nếu toàn scope cần lâu hơn, hoàn tất phần coherent, ghi remaining rõ rồi freeze thay vì để polling/build loop. Parent chạy shared build/server tests tuần tự khi agents đã bàn giao; không3builds tranh cùng target/.next. Ghi agent IDs/tasks/files/commands/result thực tế; không coi self-report là evidence độc lập.

Artifacts mới: docs/reports/DRIVE_01_REPORT.md, DRIVE_01_STATUS.json, DRIVE_01.patch, DRIVE_01_MANIFEST.json, DRIVE_01_WORKLOG.md; evidence dưới docs/reports/drive/DRIVE_01/. Status có taskId/runId/checkpointId/promptVersion1, state=ready_for_review,sourceFrozen=true,gateResults(G1/G2/G3),blockers và baseline commit. Ready_for_review nghĩa sẵn sàng Codex review, không nghĩa Drive accepted. Patch generated bằng Git tooling, actual baseline, reverse check; manifest SHA256+bytes final source/artifacts, finalize patch trước hash. Không include Codex-owned prompt/control/review như implementation, không re-hash frozen M4 artifacts. Giữ secrets/real config/state/log nhạy cảm ngoài Git, screenshots redact account info.

Codex sở hữu docs/prompts/GEMINI_CURRENT_TASK.md, DRIVE_REVIEW_CONTROL.json, M4_REVIEW_CONTROL.json và reviews. Gemini chỉ đọc chúng; không tự publish reviewing/accepted hoặc sửa prompt tiếp. M4 control vẫn stop; DRIVE control mới là assignment này. Source freeze xong kết thúc lượt, bàn giao thủ công. Không tự commit/push/reset/create branch/deploy; Codex xử lý Git dev sau review theo quyền user. Không AI/FastAPI/Qwen/GPU/model, live DB, OS settings hoặc tự chạy installer/OAuth/mount trong coding checkpoint.

## Primary references cần đối chiếu version

- https://rclone.org/commands/rclone_mount/ — Windows/WinFsp, account visibility, VFS buffers/cache/chunked reads, cache limits.
- https://rclone.org/drive/ — Drive OAuth read-only scope, remote configuration/limitations; không assume scope number cố định.
- https://winfsp.dev/ — official Windows prerequisite/install reference.

Ghi version/flags thực khi vận hành. Đây là user-assigned implementation; quy định “chưa triển khai” trong tài liệu thiết kế cũ không cấm làm source/scripts của task này. User-interactive credentials và tác động máy thật vẫn là deployment gate riêng, chuẩn bị xong kết quả review được trước khi cần người dùng thao tác.
