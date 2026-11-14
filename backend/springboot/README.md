# Spring Boot Auth & User Service

Dịch vụ Backend chính phụ trách quản lý tài khoản người dùng, xác thực bảo mật qua JWT và lưu trữ Watchlist / Đánh giá phim.

---

## 🚀 Hướng dẫn khởi chạy

### Yêu cầu
- **Java 17** hoặc **Java 21**
- **Maven** (hoặc dùng Maven Wrapper)

### 1. Chạy với profile `dev` / `prod` (MySQL 8.0 Database)

Khởi chạy container MySQL 8.0 từ thư mục `infrastructure/`:
```bash
cd ../../infrastructure
docker compose up -d mysql
```

Build và khởi chạy ứng dụng Spring Boot:
```bash
cd ../backend/springboot
./mvnw clean package -DskipTests
./mvnw spring-boot:run
```

- Server chạy tại: [http://localhost:8080](http://localhost:8080)
- Cơ sở dữ liệu mặc định: `jdbc:mysql://localhost:3306/movie_rcm_db`

Đặt `APP_MEDIA_DRIVE_MOUNT` thành thư mục hoặc ổ đĩa đã gắn Google Drive để phát video. Giới hạn mặc định là 10 kết nối HTTP phát Drive, chỉnh qua `APP_MEDIA_MAX_CONCURRENT_DRIVE_STREAMS`. Khi tua, trình duyệt có thể mở kết nối mới trước khi đóng kết nối cũ.

---

### 2. Chạy kiểm thử tự động với profile `test` (H2 In-Memory ở chế độ tương thích MySQL)

```bash
cd backend/springboot
./mvnw test -Dspring.profiles.active=test
```

---

## 📡 Danh sách API Endpoints

### 1. Xác thực & Tài khoản (`/api/auth`)
- `POST /api/auth/register`: Đăng ký tài khoản mới.
  ```json
  {
    "username": "alex",
    "email": "alex@example.com",
    "password": "password123",
    "fullName": "Alex Morgan"
  }
  ```
- `POST /api/auth/login`: Đăng nhập lấy Bearer JWT Token.
  ```json
  {
    "usernameOrEmail": "alex",
    "password": "password123"
  }
  ```
- `GET /api/auth/me`: Lấy thông tin user hiện tại (cần Header `Authorization: Bearer <token>`).

### 2. Quản lý Danh sách xem (`/api/users/watchlist`) - Cần JWT
- `GET /api/users/watchlist`: Lấy danh sách phim đã lưu.
- `POST /api/users/watchlist`: Thêm phim vào watchlist.
  ```json
  {
    "movieId": "the-last-orbit",
    "movieTitle": "The Last Orbit",
    "posterUrl": "https://..."
  }
  ```
- `DELETE /api/users/watchlist/{movieId}`: Xóa phim khỏi watchlist.

### 3. Đánh giá phim (`/api/users/ratings`) - Cần JWT
- `GET /api/users/ratings`: Lấy danh sách phim đã chấm điểm.
- `POST /api/users/ratings`: Chấm điểm phim (1 đến 10 sao).
  ```json
  {
    "movieId": "the-last-orbit",
    "rating": 9
  }
  ```
