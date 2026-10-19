# SNAPSHOT-02 — budget đạt, cần một sửa nhỏ và xác nhận UI dữ liệu thật

Ngày19/10/2026, baseline2f205a4. Review mức usable_preview, không mở thêm tính năng hoặc matrix nghiệm thu production.

## Đã xác minh mới

- Node20.20.2:83 frontend tests PASS; production build/TypeScript PASS.
- compute_build_bytes.cjs nguyên trạng: /movies/[id]141307 gzip bytes, dư2053 so với143360. Khớp báo cáo. Chưa có run Linux CI mới được reviewer xác minh; không cam kết con số local bảo đảm mọi runner.
- Maven offline với profile test/H2, JDK25.0.3: DrivePathSecurityTest và MediaStreamingIntegrationTest tổng28 tests PASS.
- data/catalog.jadoo_all.json validate VALID; package pkg_dippie_jadoo_all rev2 có99 episodes. Contract5 files giống từng byte ZIP gốc.
- Không chạy collector tác giả vì nó gọi các services, model/Drive hiện tại; đọc raw JSON và code để xác định đúng loại bằng chứng. Một số summary PASS/metrics trong collector hardcode; không xem chúng là assertion tự động độc lập.

## S1 — P1: sửa prefix đưa metadata I/O Drive trở lại caller ngoài timeout

StorageKeyConfig.resolvePath mới gọi Files.exists(resolved) với **mọi Drive path**, rồi có thể Files.exists(alt), trước khi check containment và trước khi chuyển sang bounded Drive adapter.

MediaStreamService.getMediaResource/getResourceLength/openMediaChannel đều gọi resolvePath trực tiếp, sau đó mới gọi driveStorageAdapter.*ForPath. Vì vậy stat có thể chờ mount/network trước khi executeMetadata/deadline có hiệu lực. Source comment phía dưới vẫn nói Drive I/O chỉ nằm trong adapter, không còn đúng.

Đây là source regression của ranh giới timeout đã có, chưa tái hiện treo trên Drive thật trong review. Các28 tests hiện hành không bao phủ đoạn mới này. Không đề nghị thêm queue hoặc đổi kiến trúc.

Sửa nhỏ nhất: bỏ exists/fallback khỏi StorageKeyConfig, giữ normalize+containment không I/O. Chuẩn hóa prefix trong bản JSON cục bộ ngoài Git như scope cho phép; hoặc thực hiện fallback trong bounded metadata path thực sự được *ForPath sử dụng. Giữ schema/JSON gốc Drive/containment nguyên vẹn. Không chỉ chuyển sang adapter.resolvePath vì đường storage-key hiện gọi *ForPath.

## S2 — P2: chưa chứng minh chọn và phát đúng tập từ UI với catalog này

Đã có bằng chứng tiến bộ: API import/outbox READY/search, production HTTP HEAD/Range và FFprobe đọc frames của asset_jadoo_s01_v0001. Không phủ nhận video qua HTTP đọc/giải mã được.

Nhưng collector không mở browser, không import/search/click kết quả qua UI. FFprobe -read_intervals60/120 bắt đầu từ keyframe58.8/118.44 là probe độc lập, không browser currentTime/frame advance hoặc proof nút chọn tập trỏ đúng file. Evidence browser F08 dùng fixture khác, không thay cho catalog Jadoo99 tập này.

Chỉ cần một lượt ngắn với dữ liệu đã nhập: web search Jadoo → chọn một episode → xác nhận episodeId/assetId/currentSrc → decoded frame/time advance → seek một mốc và video tiếp tục. Chọn thêm một tập khác nếu có thể để bắt mapping nhầm. Không thêm suite lớn, không yêu cầu thêm3 seeks/codec/load test.

## Đường dẫn dữ liệu và vận hành

Report chưa ghi rõ DB preview/state path dùng cho catalog thật. Launcher hiện dùng profile dev và default data paths; reviewer không tự ghi live DB hoặc mount lại để suy đoán. Khi bàn giao bổ sung đúng path DB/index và cách mở lại, giữ dữ liệu đã nhập ngoài Git.

## Kết luận

Budget và JSON validation đạt. Chốt bằng cách sửa S1 gọn và chạy đúng một luồng UI Jadoo S2. Không cần quay lại catalog architecture/model hoặc mở tính năng mới. Chưa commit/push trong review.

Không sửa application, không thay runtime state/DB, không mount hoặc chạy model; chỉ thêm review và evidence reviewer. Không chạy CLI agent/automation.
