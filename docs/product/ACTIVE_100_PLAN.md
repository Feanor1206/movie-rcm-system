# Mục tiêu sản phẩm: hoạt hình cho 100 người dùng/ngày

Ngày chốt phạm vi: 27/10/2026. Đây là kế hoạch nghiệm thu, chưa phải báo cáo đạt tải.

## Người dùng và dữ liệu

- 100 người dùng hoạt động mỗi ngày, khoảng 10–20 người dùng đồng thời.
- Nội dung là hoạt hình theo bộ, mùa, tập, tiểu phẩm và phân cảnh. Không xây trải nghiệm phim điện ảnh hoặc gợi ý dữ liệu mẫu không có trong kho thật.
- SQL là nguồn dữ liệu chính. Spring Boot quản lý nghiệp vụ, quyền và streaming; FastAPI giữ vai trò index/tìm kiếm/ngôn ngữ. JSON chỉ nhập/xuất và phục hồi; video lưu trên Drive. Không đổi schema catalog hay trọng số model.
- Qwen tạm tắt theo yêu cầu. Không chiếm GPU hoặc dừng công việc khác để nghiệm thu sản phẩm.

## Thứ tự bàn giao

| Đợt | Nhu cầu thực tế | Kết quả phải nhìn thấy |
|---|---|---|
| 1 | Mở lại web vẫn có đúng dữ liệu | Một lệnh chạy không cần Qwen; SQL riêng bền vững; import có preview; backup/restore; sau restart khách tìm và phát đúng tập |
| 2 | Không bị lạc giữa các tập/mùa | Trang chủ/kho chỉ dùng catalog bộ hoạt hình thật; chọn mùa, tìm tập trong bộ; deep link đúng asset và thời gian |
| 3 | Quay lại xem thuận tiện | Tiếp tục xem, lịch sử và trạng thái đã xem; khách lưu cục bộ, tài khoản lưu SQL; xử lý đăng xuất/đổi tài khoản và ghi trễ không rò dữ liệu |
| 4 | Xem nhiều tập liên tục | Tập tiếp theo đúng thứ tự trong mùa; đếm ngược có hủy, cho phép tắt tự động; không tự nhảy mùa hoặc giành quyền điều khiển người xem |
| 5 | Người thật dùng an toàn | Origin/secret cấu hình rõ; quản trị có quyền; giới hạn đăng nhập/API/import; video public/private đúng; lỗi dễ hiểu, không lộ token/path/stack |
| 6 | Có bằng chứng chịu tải | Đo 10 rồi 20 phiên hỗn hợp trong thời gian hữu hạn; đo riêng số video đồng thời, throughput, lỗi, p95 API, buffering, CPU/RAM/IO; thử seek và retry khi tải cao |

Mỗi đợt được review và kiểm tra trước commit. Không coi test fixture thay thế video Drive thật, không tăng queue/worker/stream limit để che lỗi. Những tính năng có sẵn như watchlist/rating được giữ và kiểm tra, không viết lại chỉ để đổi giao diện.

## Tiêu chí trải nghiệm đề xuất

- Không yêu cầu đăng nhập để xem asset public; tài khoản dùng cho đồng bộ dữ liệu cá nhân.
- Bộ → mùa → tập luôn rõ; tập cùng số ở nhiều mùa không trộn vào một danh sách mặc định.
- Player giải mã được và thời gian/frame tiếp tục tăng sau pause/resume/seek; giữ mốc khi lỗi có thể phục hồi.
- Ghi tiến độ theo nhịp hợp lý và các mốc pause/đổi tập, không ghi SQL cho từng frame. Bản ghi thuộc đúng người dùng và tập, không dùng thời gian client để ghi đè vô điều kiện.
- Import lỗi không đổi dữ liệu đang phục vụ; người quản trị nhìn được package/revision, số bản ghi, SQL đang dùng, snapshot và tình trạng index riêng biệt.
- Backup phải khôi phục được vào database test độc lập; có hash, không copy file H2 đang mở như một bản backup hợp lệ.

Ngưỡng latency và số stream cụ thể được chốt sau baseline trên môi trường triển khai thật. 20 người dùng đồng thời không mặc nhiên được báo cáo là 20 video 1080p đồng thời. Hai kịch bản phải đo và công bố riêng. Khả năng đường truyền và Drive phải được tính vào kết quả.

## Các việc cần trước khi mở ra Internet

Người dùng đã chọn máy Windows hiện tại làm máy phục vụ. Cần chốt truy cập LAN hay Internet, hostname/TLS, đường truyền và SQL PostgreSQL cùng backup của môi trường đó. Chưa triển khai ra ngoài hoặc thay cấu hình OS toàn cục khi chưa có các thông tin này. Các tài khoản demo, H2 console và secret mặc định chỉ phù hợp thử nghiệm loopback.

Giới hạn tài nguyên được xem là một phần của an toàn API theo [OWASP API4](https://api-security.owasp.org/editions/2023/en/0xa4-unrestricted-resource-consumption/). Kiểm tra streaming tiếp tục giữ đúng [HTTP Range](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests) để tua/đọc từng phần thay vì tải trọn video.

## Mốc bàn giao trước khi làm tiếp

Theo yêu cầu mới, chốt `ANIMATION-PREVIEW-01` rồi commit/push trước. Chuẩn chất lượng là đồ án hoàn chỉnh, có thể trình bày bằng kiến thức Java, Python, cơ sở dữ liệu, công nghệ phần mềm và nhập môn trí tuệ nhân tạo. Cloudflare Tunnel do người dùng thiết lập sau; không mở cổng hay cài thêm nền tảng triển khai trong milestone này.
