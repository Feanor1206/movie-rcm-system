# M4 — Xem video thật, tua mượt và nền tảng storage Windows

Bạn là kỹ sư triển khai Gemini tại D:\Class\movie-rcm-system, branch dev. Codex giữ vai trò kỹ sư trưởng và nghiệm thu. M1/M2/M3 đã accepted; đọc docs/reviews/LOOP_ROUND_13_REVIEW.md. Đây là milestone mới được giao thủ công, không phải Round14 và không khởi động lại automation M2/M3.

## Kết quả dành cho người dùng

Người xem mở tác phẩm có asset thật, bấm xem, phát được video, tua đầu/giữa/cuối, pause/resume, fullscreen và biết cách thử lại khi nguồn gián đoạn. Tác phẩm chỉ có trailer tiếp tục được gọi đúng là trailer; thiếu feature thì không bịa nút xem phim. Theme xanh lá dịu, mobile dễ chạm; giữ thư viện/account/search đã nghiệm thu. AI để sau.

Milestone gồm một luồng hoàn chỉnh storage adapter -> ranged HTTP -> player -> benchmark. Không dựng thêm microservice/queue/transcoder chỉ để chia kiến trúc. Module media trong Spring Boot hiện hữu, frontend dùng client riêng gọn. Hoàn tất phần tự làm được; Drive thật chưa có điều kiện không chặn local delivery/player, nhưng ghi rõ gate Drive chưa đạt. Không gọi fixture benchmark là nghiệm thu Drive hoặc mạng người xem.

## Đọc và kiểm tra baseline

Đọc docs/prompts/GEMINI_ENGINEERING_RULES.md, docs/USER_EXPERIENCE_BLUEPRINT.md, docs/DRIVE_MEDIA_STORAGE_DESIGN.md và docs/STORAGE_PERFORMANCE_DECISION.md. Quyết định mới hơn trong STORAGE_PERFORMANCE_DECISION được ưu tiên: người dùng muốn mượt tối đa, không lo RAM/CPU/GPU, có thể thêm SSD nếu số đo chứng minh cần; không tự bật cache xuống ổ hoặc mua gì trước khi đo.

Đọc source MovieDetail/player, catalog client/contracts, Spring Movie/Security/auth/config/migrations và test harness trước khi thiết kế. git status/diff baseline, snapshot own scope; không đụng backend/fastapi/.env.example ngoài scope. Không hỏi lại các quyết định đã chốt. Kiểm kê read-only rclone/WinFsp/mount nhìn thấy được, ffmpeg/browser và free disk hiện tại; không dump remote config/token hay scan kho Drive. ffmpeg đã thấy trên PATH ở lượt giao prompt nhưng phải kiểm tra lại.

## 1. Contract và assets có thật

Viết docs/contracts/M4_MEDIA_PLAYBACK_CONTRACT.md trước implementation: endpoints/payload/errors, feature/trailer, availability, HTTP range policy, player states, quyền truy cập và cấu hình MEDIA_ROOT. Giữ canonical movie IDs và dữ liệu M1. Asset mapping tối thiểu: assetId/movieId/kind/provider/relativePath/version/mimeType/byteLength; duration chỉ có khi thực sự probe được.

Chọn persistence theo pattern hiện hữu, migration additive và bootstrap đồng bộ khi thêm bảng; DB tests riêng, không live migration. Không tự import catalog/media live hoặc dựng trang admin/upload ngoài scope. Cung cấp fixture registration/preview rõ để kiểm thử và runbook mapping thủ công an toàn. Không lộ path Windows/Drive file credentials cho client.

M4 baseline: guest được xem assets được đánh dấu công khai; descriptor và stream áp cùng policy. Nếu dùng private assets thì giải pháp auth phải chạy được với native video/Range, không giả định localStorage Bearer tự xuất hiện ở video src. Không mở toàn bộ filesystem hoặc nới SecurityConfig /** để media chạy. Không tự xây subscription/billing. Chốt public-fixture/private-unavailable rõ thay vì auth giả hoặc biến trailer thành feature.

## 2. Storage adapter và HTTP streaming thật

- Read-only adapter resolve asset đã đăng ký dưới MEDIA_ROOT cấu hình. Test path traversal, absolute-path injection và symlink/reparse escape; không nhận path/URL tùy ý từ browser, không directory listing.
- GET/HEAD: MIME, Content-Length, Accept-Ranges, full200, single byte-range206/Content-Range, suffix/open-ended và416 với bytes */length. Quy định malformed/multi-range rõ, không trả sai bytes. Conditional behavior nếu hỗ trợ phải nhất quán, không mở thêm caching layer phức tạp.
- Không readAllBytes/toByteArray toàn video hoặc copy file ra temp trước khi phát. Đọc bounded, backpressure và đóng tài nguyên khi browser cancel/đóng player. Giới hạn concurrency/timeouts; remote filesystem có thể block: mô tả giới hạn và tránh executor/queue vô hạn, không hứa interrupt luôn hủy được mọi OS read.
- Unknown asset404 khác storage unavailable503. Sau headers/body đã gửi thì không đổi status giả: dừng stream, ghi lý do sạch, player retry. Media health tách catalog health; mount offline không làm mất catalog/library.
- Root test dùng temporary fixtures riêng. Có MP4 synthetic ngắn, nhỏ do ffmpeg tạo vào temp/evidence folder có giới hạn; không tải phim/ngốn disk. Dùng byte fixture kiểm tra integrity không thay được playable MP4 browser evidence.

## 3. Player trải nghiệm hoàn chỉnh

Tái dùng modal accessibility M3. Lazy-load phần player nếu cần để giữ ngân sách140KiB; chưa có video thì không tải media. preload metadata/none có lý do, không auto-download cả phim từ Home/Profile. Không ép autoplay khi browser chặn; hiện nút play dễ hiểu.

Phân biệt loading/playing/paused/seeking/buffering/error/ended. Retry giữ vị trí hợp lệ và không tự phát lại từ0 ngoài ý người xem; hủy request/session cũ khi đổi movie/asset hoặc unmount. Controls native là baseline hợp lệ, không viết lại tất cả controls nếu không cần. Fullscreen, volume, seek, keyboard và touch>=44px có thực; không chặn phím khi đang gõ form/chat. Không bịa nhãn độ phân giải/lồng tiếng/phụ đề khi metadata thiếu.

Giữ trailer path backward compatible và actor isolation/pending/uncertain của M1; không sửa auth/library vì tiện tích hợp media. Continue-watching đồng bộ tài khoản, episode/season, HLS/ABR, encoding hàng loạt, CDN và AI ngoài scope milestone này.

## 4. Đo trước khi chọn RAM/cache/SSD

Tạo benchmark/runbook có raw results: startup đến loadeddata/playing/frame đầu khi API hỗ trợ; seek request -> seeked và resumed frame; stall count/time, transferred bytes, peak active streams, cancel cleanup, memory và disk growth. Định nghĩa metrics, observation window và unavailable; không dùng sleep cố định hoặc response200 để kết luận phát được. Chứng minh currentTime tiến lên và tua gần cuối clip thật.

Baseline local adapter: tối thiểu1stream và3streams, lặp>=3lần startup/seek với clip nhỏ đủ dài;5streams nếu phù hợp. Tách browser cache/local OS cache/remote cache có thể kiểm soát và phần không reset được; không gọi mọi lần đầu là cold. Nếu đo long playback chưa đủ thời gian ghi limitation, không suy ra ổn định nhiều giờ từ clip ngắn.

Drive gate riêng: chỉ dùng mount test đã được người dùng cấu hình/chọn nếu thực sự sẵn có. Thiếu rclone/WinFsp/mount/test asset thì ghi BLOCKED_EXTERNAL_INPUT cho Drive, kèm chính xác cần người dùng làm gì và runbook/commands review được. Không tự cài, OAuth, mount, upload/download cả kho, mở firewall/startup/đổi OS settings. Không gọi local fixture là Drive pass.

Khi có đủ điều kiện Drive sau này, so RAM/no-content-disk-cache với bounded SSD cache bằng cùng clip/workload và mạng thực. Hiện chưa có quyền ghi cache lớn xuống disk: chuẩn bị opt-in harness/config, không chạy disk-cache benchmark chỉ vì có free space. Chỉ đề xuất SSD dựa working set, headroom và lợi ích startup/seek/stall đo được; không kết luận mua ổ lớn tự khắc phục uplink/quota. Không tự xây hai data planes hoặc RAM cache phức tạp trước bottleneck.

## 5. Nghiệm thu và evidence

- Backend production media handlers với DB fixture riêng: byte integrity full/range/suffix/open-ended/HEAD/416, unknown vs unavailable, path boundary, policy, concurrency/cancel và resource cleanup. Test qua HTTP thật ít nhất các ca streaming quan trọng, không chỉ mock service.
- Browser dùng Spring media origin test thật + frontend production, clip MP4 playable, không fixture server trả success giả cho đường media chính. Assert play/time progression/seek/retry/close, desktop+375px, không console/runtime errors. Mock fault injection hợp lệ nhưng ghi rõ. Screenshots không thay network/decoded playback evidence.
- npm test,tsc,production build,dynamic JS guard; cả mvnw.cmd test và mvnw.cmd test -Dspring.profiles.active=test. Thêm tests phù hợp media, bảo toàn57frontend/25backend baseline; không cần chạy AI. Không sửa reviewer tests/artifacts cũ để lấy pass.
- Report tách Core local playback READY_FOR_REVIEW / Drive integration NOT_RUN hoặc blocked / actual measured. Chưa chạy remote viewer thì không hứa concurrency public hoặc tối ưu tối đa.

## Scope, checkpoint và bàn giao

Files dự kiến: Spring media controller/service/storage/entity/repository/DTO/config/tests và SQL additive cần thiết; frontend media client/player + MovieDetail/types tích hợp tối thiểu; scripts benchmark/browser fixture/runbook; CI chỉ nối tests/guard liên quan. Không refactor catalog/auth/library/theme toàn dự án, không nâng framework, không thêm hạ tầng hay dependency lớn khi có sẵn cách làm.

Làm milestone liền mạch. Khi cần dừng phiên, bàn giao checkpoint đầy đủ những phần đã thực thi thay vì tự gọi accepted; không tự triển khai phần phụ thuộc vượt gate. Dùng M4_MEDIA_STATUS.json/report/worklog riêng, không sửa status/control của M2/M3 đã đóng. Nếu một external input thiếu, hoàn tất phần độc lập trước và nêu blocker cụ thể.

Artifacts: docs/reports/M4_MEDIA_PLAYBACK_REPORT.md, patch riêng từ baseline, manifest SHA256 own source/test/config + evidence, contract và runbook. Ghi commands/interpreters/exitcodes, test DB/topology, size fixtures/disk deltas, cases pass/fail/skip; numstat/reverse check. Freeze source rồi publish ready_for_review cuối. Dừng lượt, không polling hoặc tự sang milestone khác.

Không AI/FastAPI/Qwen/GPU/model, DB live, deploy, install/mount/OAuth/OS changes hoặc kill process người khác. Không tự tạo nhánh/commit/push/reset. Codex review và xử lý Git trực tiếp dev theo quyền người dùng.
