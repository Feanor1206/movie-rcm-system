# Cơ sở dữ liệu

Các tệp SQL cho MySQL:

- `schema/`: lược đồ khởi tạo, bắt đầu từ `01_init.sql`.
- `migrations/`: thay đổi bảng danh sách yêu thích, video, danh mục và tiến độ xem.
- `seeds/`: dữ liệu phim và tài khoản demo.

Compose nạp lược đồ khi tạo cơ sở dữ liệu mới. Bản `docker-compose.dev.yml` nạp thêm dữ liệu demo; chỉ dùng trong môi trường thử nghiệm riêng.
