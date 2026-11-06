# Prompt Gemini — CTX-01: API ngữ cảnh thời tiết và giờ địa phương

Sao chép nội dung từ phần dưới để giao cho agent code. Ticket này triển khai nền dữ liệu cho tính năng context, chưa tích hợp ranking hoặc UI. Codex chỉ lập kế hoạch và review.

---

Bạn là agent triển khai ticket CTX-01 trong repo `D:\Class\movie-rcm-system`.

## Mục tiêu người dùng

Tôi muốn chọn thành phố để website biết giờ địa phương và lấy thông tin thời tiết khi tôi bật tính năng đó. Tôi có thể dùng riêng ngữ cảnh thời gian. Khi weather provider lỗi, website không tạo thời tiết giả và vẫn tính được giờ nếu biết timezone.

Hãy triển khai Spring Boot API nhỏ, có contract rõ và kiểm thử bằng fixture. Ticket đầu tiên chỉ cung cấp context chuẩn hóa. UI, truyền context sang FastAPI, đề xuất tone theo thời tiết, forecast cho giờ xem tương lai và ngân sách giờ kết thúc sẽ làm ở các ticket tiếp theo.

## Đọc repo trước khi sửa

- Đọc `AGENTS.md` áp dụng nếu có, `ANIMATION_DISCOVERY_PROJECT_BIBLE.md`, phần 6.9 của `docs/PRODUCT_FEATURE_PLAN.md`.
- Kiểm tra `git status` và diff ban đầu: repo có thay đổi chưa commit của người khác. Giữ nguyên các thay đổi đó, không reset, không tự commit hoặc push.
- Đọc `backend/springboot/pom.xml`, `dto/ApiResponse.java`, `config/SecurityConfig.java`, `controller/HealthController.java`, `application.yml` và Maven wrapper.
- Package hiện tại là `com.dippie.moviercm`, Java 17, Spring Boot 3.3.3. Dùng cấu trúc controller/service/DTO/config của repo; không nâng framework cho ticket này.
- Chỉ thay đổi module context, test, cấu hình cần thiết, security matcher chính xác cho API mới và tài liệu liên quan. Không sửa auth nghiệp vụ, DB schema/seed, frontend, FastAPI hoặc AI artifacts.

## Nguồn dữ liệu

Provider ban đầu: Open-Meteo qua adapter riêng để có thể thay thế sau.

- Geocoding docs: https://open-meteo.com/en/docs/geocoding-api
- Weather docs: https://open-meteo.com/en/docs
- Search location: `https://geocoding-api.open-meteo.com/v1/search` với `name`, `count=5`, `language=vi`, `format=json`.
- Resolve location by ID: `https://geocoding-api.open-meteo.com/v1/get?id=...`.
- Weather: `https://api.open-meteo.com/v1/forecast`, tọa độ lấy từ location metadata, `current=temperature_2m,weather_code,precipitation,is_day`, `timeformat=unixtime`. Chuẩn hóa timestamp về UTC instant.
- Các giá trị current của provider là dữ liệu mô hình, không gọi là quan trắc từ trạm. Ghi nguồn và đường dẫn attribution trong response/tài liệu.
- Base URL chỉ lấy từ cấu hình phía server. Request người dùng không được quyết định URL gọi ra ngoài. Không hard-code secrets hoặc gắn business logic vào raw response provider.

## Hai endpoint cần triển khai

### 1. `GET /api/context/locations?q=...`

- Guest dùng được. Trim q; hợp lệ từ 2 đến 80 ký tự; không giới hạn tên thành ASCII.
- Trả tối đa 5 location: `id`, `name`, `admin1` nếu có, `countryCode`, `country`, `timezone` IANA.
- Không tự chọn location đầu tiên khi trùng tên. Kết quả rỗng là HTTP 200 với danh sách rỗng.
- Trường tùy chọn thiếu không làm lỗi toàn bộ response. Location thiếu timezone hợp lệ không được dùng làm một lựa chọn có context đầy đủ; loại khỏi kết quả chọn được hoặc đánh dấu rõ theo contract đã ghi trong tài liệu.
- Dùng `ApiResponse` hiện hữu làm envelope. Dữ liệu chính có thể là `data.locations` để thêm metadata sau này.

### 2. `GET /api/context/viewing`

Query parameters:

- Nhận đúng một trong `locationId` hoặc `timezone`; thiếu cả hai hoặc có cả hai là 400.
- `locationId` là số nguyên dương, resolve metadata phía server. Dùng timezone của location; browser không cung cấp tọa độ tùy ý cho weather request.
- `timezone` phải là IANA region ID hợp lệ bằng `ZoneId`; cho phép `UTC` rõ ràng. Không chấp nhận chuỗi offset tùy ý hoặc dùng timezone hệ điều hành làm fallback.
- `weatherEnabled` mặc định false. Nếu true nhưng chỉ có timezone, trả context thời gian và weather unavailable với reason `LOCATION_NOT_SELECTED`; không gọi forecast.
- Nếu false, không gọi forecast dù có locationId; weather status là `NOT_REQUESTED`.

Response `data` tối thiểu:

- `schemaVersion`: `viewing-context.v1`.
- `generatedAt`: UTC instant của lần tạo response.
- `location`: thông tin city đã chọn hoặc null.
- `time`: `timezone`, `localDateTime` ISO 8601 có offset, `dayOfWeek`, `dayPeriod`.
- `weather`: `status`, `reason` khi cần, `provider`, `dataKind`, `modelTime`, `fetchedAt`, `temperatureC`, `weatherCode`, `precipitationMm`, `isDay`, `attributionUrl`.
- `weather.status`: `AVAILABLE` / `NOT_REQUESTED` / `UNAVAILABLE`.
- `dataKind=MODEL_CURRENT` khi AVAILABLE. `modelTime` là valid time từ provider, không phải thời điểm quan trắc. `fetchedAt` khác `generatedAt` khi weather lấy từ cache.
- Khi weather không có: các giá trị thời tiết là null, không điền 0 hoặc sunny. Metadata provider chỉ có khi biết nguồn đang dùng; mọi status có mô tả rõ trong README.

Policy dayPeriod theo giờ địa phương, chỉ là phân đoạn thời gian hiển thị, không phải giả định sở thích:

- MORNING: [05:00, 12:00)
- AFTERNOON: [12:00, 18:00)
- EVENING: [18:00, 22:00)
- LATE_NIGHT: [22:00, 24:00) và [00:00, 05:00)

Không đưa `isWeekend`, holiday, inferred mood, runtime limit hoặc rank score vào ticket này. Không chuyển các khoảng thời gian trên thành ràng buộc phim.

## Failure behavior và security

- Validation đầu vào lỗi: 400. Location ID được provider xác nhận không tồn tại: 404. Geocoding lỗi/timeout không phải bằng chứng location không tồn tại: 503 với code rõ.
- Forecast lỗi/timeout/429/malformed data: trả 200 với time hợp lệ và `weather.status=UNAVAILABLE`; reason phân biệt TIMEOUT / UPSTREAM_ERROR / INVALID_DATA khi có đủ thông tin.
- Nếu toàn bộ weather payload không có các trường bắt buộc hoặc timestamp/units sai: unavailable, không coi null là 0. Định nghĩa trường bắt buộc và validation trong code/tài liệu.
- Giữ error envelope tương thích `ApiResponse`, `success=false`, message cho người dùng và `data.code` ổn định cho API mới; dùng exception handling có scope trong module context. Không đổi lỗi tất cả controller hiện hữu.
- Chỉ mở anonymous GET cho hai path mới trong `SecurityConfig`. Giữ nguyên bảo vệ ratings/watchlist và các method/path khác.
- Không lưu location vào hồ sơ/tài khoản ở ticket này; không gọi GPS/IP geolocation, không thêm dữ liệu cá nhân vào log.

## Reliability và cấu trúc

- Inject `Clock`; tính instant bằng clock và chuyển bằng `ZoneId`, không dùng giờ local máy chủ.
- HTTP client có connect timeout/read timeout cấu hình; mặc định 2 giây và 3 giây. Không retry tự động trong bản đầu.
- Cache search/metadata/weather riêng, TTL mặc định 1 giờ / 24 giờ / 10 phút. Mỗi cache tối đa 500 entries, có eviction thật; không dùng map tăng vô hạn.
- Cache theo query chuẩn hóa/ID thành phố, không theo user. Khi cache weather hết TTL và provider lỗi, trả unavailable; không dùng stale data trong ticket này.
- Không cache nguyên viewing response; giờ hiện tại phải được tính lại từng request.
- Giới hạn external calls đang thực hiện tối đa 8 cho mỗi instance; queue không tăng vô hạn; nếu hết capacity, xử lý reason/error rõ và giải phóng slot kể cả khi exception.
- Chặn việc nhiều request cùng refresh một cache key tạo nhiều external calls trùng nhau; kiểm thử concurrent behavior quan trọng.
- Dùng dependencies có sẵn nếu phù hợp. Nếu cần thêm thư viện cho bounded cache, giải thích lý do và chỉ thêm dependency nhỏ đúng mục đích. Không yêu cầu Redis hoặc service mới để chạy ticket này.
- Adapter provider, context service, controller, DTO và properties tách trách nhiệm. DTO provider không chính là DTO public.
- Merge cấu hình bổ sung vào `application.yml`, giữ nguyên thay đổi chưa commit hiện hữu. Không sửa môi trường hệ thống máy người dùng để chạy Maven.

## Kiểm thử bắt buộc, không gọi internet

1. Clock cố định: cùng instant nhưng Asia/Ho_Chi_Minh và America/New_York cho ngày/giờ địa phương đúng; có case ngày UTC khác local date.
2. Các biên 05:00, 12:00, 18:00, 22:00 và 00:00 đúng dayPeriod.
3. DST: kiểm tra hai instant hai phía của một lần đổi giờ ở America/New_York bằng timezone database; không dùng offset cố định.
4. Search không có kết quả trả 200; thiếu optional field không crash; Unicode tên khu vực xử lý đúng.
5. Thiếu/đồng thời hai locator, ID không hợp lệ hoặc timezone sai trả 400; location không tồn tại trả 404.
6. Weather disabled không gọi forecast. Timezone-only dù weatherEnabled=true cũng không gọi forecast.
7. Fixture provider hợp lệ được map đúng field, đơn vị, modelTime và fetchedAt. Fixture timeout/error/malformed trả trạng thái tương ứng, không bịa weather.
8. Cache hit không gọi provider thêm; hết TTL thì refresh; cache bị giới hạn; viewing time thay đổi theo clock dù weather cache còn hiệu lực.
9. Nhiều request cùng key không tạo refresh trùng; nhiều key vượt capacity không có queue vô hạn; lỗi không làm rò slot.
10. MockMvc với security đang hoạt động: guest truy cập được đúng API mới, endpoint thư viện vẫn yêu cầu auth. Không dùng tắt filter làm bằng chứng phân quyền.

Tests dùng fake/stub provider, fixed/mutable Clock và mock HTTP server hoặc công cụ sẵn có. Không tải model và không khởi động seed/H2 file DB thật để test controller/service context.

## Kết quả cần báo cáo

- Triển khai ticket, chạy kiểm tra phù hợp và sửa các lỗi trong phạm vi.
- README API có response fixture cho AVAILABLE, NOT_REQUESTED, UNAVAILABLE, validation error và cấu hình provider/TTL/timeout; ghi rõ đây là ví dụ giả lập, không phải thời tiết hiện tại.
- Báo danh sách file thay đổi, hành vi đã có, dependency mới nếu có, lệnh test và kết quả thực tế.
- Nếu Maven không chạy do JAVA_HOME/toolchain, xác định JDK có sẵn và có thể dùng cấu hình chỉ trong process chạy kiểm tra; không thay đổi env hệ thống. Nếu vẫn không chạy được, báo chính xác kiểm tra nào chưa thực hiện; không tuyên bố tests pass.
- Nêu giới hạn còn lại và những điểm cần review. Chưa tuyên bố tính năng gợi ý theo thời tiết hoàn tất: CTX-01 chỉ cung cấp API context. Dừng sau ticket này, không tự mở rộng sang frontend hoặc AI.
