# Viết truy vấn đánh giá tìm kiếm

Điền một dòng cho mỗi truy vấn bạn tự viết trong `search_queries_v1.csv`. Giữ
nguyên tên cột và lưu UTF-8. Viết câu tự nhiên theo trí nhớ hoặc sau khi xem tập.
Chọn cách diễn đạt và chốt nhãn trước khi xem kết quả tìm kiếm, caption hoặc lời
thoại đã sinh. Giữ nguyên dấu tiếng Việt khi đó là cách bạn sẽ nhập câu hỏi.

- `query` là câu bạn sẽ gõ vào ô tìm kiếm. Có thể dùng mô tả cảnh, nhân vật hoặc
  lời thoại bạn nhớ. Nếu câu chứa dấu phẩy, để trình soạn CSV bọc cả ô bằng dấu
  nháy kép.
- `episode_id` là ID catalog của tập pilot đúng. Đối chiếu ID từ danh sách pilot.
- `start_ms` là mốc bắt đầu bạn đã kiểm tra trong tập. `end_ms` có thể để trống.
  Dùng số nguyên mili giây trên timeline của tập. Nếu chỉ chắc chắn về tập, để
  trống cả hai mốc.
- `writer` là tên hoặc mã người viết. `notes` ghi chi tiết giúp đối chiếu nhãn
  nếu cần.

Giữ bản nhãn đã chốt để dùng cho cả bốn cấu hình. Mẫu CSV chỉ có header để bạn
tự điền nhãn. Lệnh chạy nằm trong [hướng dẫn đánh giá](../../evaluation/README.md).
