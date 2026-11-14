# Spring Boot

Backend Java quản lý tài khoản, danh mục phim, thư viện, tiến độ xem và phát video. Xác thực dùng JWT; tìm kiếm và hội thoại được chuyển sang FastAPI.

## Chạy

Cần JDK 17 trở lên và MySQL 8.0. Maven Wrapper có sẵn trong thư mục này.

Đặt khóa JWT và thông tin MySQL theo [README chính](../../README.md#cài-đặt). Từ thư mục gốc, chạy:

```powershell
.\start-java-main.ps1 -Background
```

API chạy tại [localhost:8080](http://localhost:8080). Cơ sở dữ liệu mặc định là `jdbc:mysql://localhost:3306/movie_rcm_db`.

Để chạy riêng Spring Boot:

```powershell
cd backend/springboot
.\mvnw.cmd spring-boot:run
```

Profile mặc định `dev` tạo tài khoản demo có mật khẩu công khai `password123`, chỉ dùng trong môi trường thử nghiệm riêng. Profile `prod` tắt dữ liệu demo, yêu cầu `APP_JWT_SECRET`, `SPRING_DATASOURCE_PASSWORD` và lược đồ cơ sở dữ liệu đã được chuẩn bị.

## Phát video từ Drive

Đặt `APP_MEDIA_DRIVE_MOUNT` trỏ tới thư mục hoặc ổ đĩa đã gắn Google Drive. Giới hạn mặc định là 10 kết nối HTTP phát Drive, chỉnh bằng `APP_MEDIA_MAX_CONCURRENT_DRIVE_STREAMS`. Khi tua, trình duyệt có thể mở kết nối mới trước khi đóng kết nối cũ.

## API tài khoản và thư viện

Các API cá nhân cần header `Authorization: Bearer <token>`.

| Đường dẫn | Chức năng |
| --- | --- |
| `POST /api/auth/register` | Đăng ký với `username`, `email`, `password`, `fullName`. |
| `POST /api/auth/login` | Đăng nhập bằng `usernameOrEmail` và `password`, nhận JWT. |
| `GET /api/auth/me` | Thông tin tài khoản hiện tại. |
| `GET /api/users/watchlist` | Danh sách phim đã lưu. |
| `POST /api/users/watchlist` | Lưu phim theo `movieId`. |
| `DELETE /api/users/watchlist/{movieId}` | Bỏ phim đã lưu. |
| `GET /api/users/ratings` | Danh sách đánh giá của tài khoản. |
| `POST /api/users/ratings` | Đánh giá theo `movieId` và `rating` từ 1 đến 10. |

## Kiểm thử

Chạy từ thư mục gốc. Profile `test` dùng H2 ở chế độ tương thích MySQL:

```powershell
cd backend/springboot
.\mvnw.cmd test "-Dspring.profiles.active=test"
```
