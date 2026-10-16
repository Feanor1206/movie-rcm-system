# Trạng thái bản chụp catalog ngày 17/10/2026

Bản chụp hiện tại lưu tiến độ importer, hàng đợi đồng bộ, tìm kiếm và trình phát. **Chưa được nghiệm thu để vận hành ổn định hoặc triển khai.**

Các lỗi đã tái hiện ở checkpoint CATALOG-01-F03:

- Java và Python băm JSON theo hai cách khác nhau; request đồng bộ của worker bị trả HTTP400.
- Request sai hash hoặc conflict409 vẫn có thể thay catalog đang phục vụ trước khi bị từ chối.
- Tua scene dùng file timestamp nhưng lại chuyển đổi lần nữa; ví dụ90 giây thành150 giây. Mapping chưa biết vẫn bị đoán thành0.
- Player chưa có đường xác thực phù hợp để đọc video authenticated/private. Một số thao tác resolve/real containment trên Drive còn nằm ngoài deadline.

Xem `docs/reviews/CATALOG_01_F03_REVIEW.md`, các repro và evidence tương ứng. Các nhãn COMPLETE/PASS trong báo cáo triển khai được giữ như lịch sử bàn giao, không thay thế kết luận review.

109 hash checkpoint đã được đối chiếu, contract vẫn giống ZIP gốc và reverse patch check qua. Chưa xác minh độc lập full CI, browser end-to-end hoặc Drive thật cho checkpoint này.

Mục tiêu tiếp theo là một rehearsal trên DB và media riêng: import → worker HTTP sync → tìm kiếm → decoder phát/tua đúng video → restart → lặp lại. Không thay schema, không dùng dữ liệu hư cấu như catalog thật và không ghi live DB để minh họa.
