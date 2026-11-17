# Viết truy vấn đánh giá tìm kiếm

Điền một dòng cho mỗi truy vấn tự viết trong `search_queries_v1.csv`, giữ tên cột và lưu UTF-8. Viết theo trí nhớ hoặc sau khi xem tập phim. Chốt cách diễn đạt và nhãn trước khi xem kết quả tìm kiếm, mô tả ảnh hoặc lời thoại máy sinh. Giữ dấu tiếng Việt như khi nhập câu hỏi.

| Cột | Nội dung |
| --- | --- |
| `query` | Câu tìm kiếm về cảnh, nhân vật hoặc lời thoại. Ô có dấu phẩy cần được trình soạn CSV bọc trong dấu nháy kép. |
| `episode_id` | ID tập đúng trong danh sách tập thử nghiệm. |
| `start_ms`, `end_ms` | Mốc thời gian đã kiểm tra, tính bằng số nguyên mili giây. Có thể để trống `end_ms`; nếu chỉ chắc về tập, để trống cả hai mốc. |
| `writer` | Tên hoặc mã người viết. |
| `notes` | Ghi chú giúp kiểm tra lại nhãn. |

Giữ nguyên bản nhãn đã chốt cho cả bốn cấu hình. Tệp mẫu hiện chỉ có tên cột. Xem [lệnh đánh giá](../../evaluation/README.md).
