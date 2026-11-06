# Spring Boot Auth & User Service

Dịch vụ Backend chính phụ trách quản lý tài khoản người dùng, xác thực bảo mật qua JWT và lưu trữ Watchlist / Đánh giá phim.

---

## 🚀 Hướng dẫn khởi chạy

### Yêu cầu
- **Java 17** hoặc **Java 21**
- **Maven** (hoặc dùng Maven Wrapper)

### 1. Chạy với profile `dev` (Sử dụng H2 In-Memory Database - Chạy ngay không cần cài DB)

```bash
cd backend/springboot

# Build dự án
mvn clean package -DskipTests

# Khởi chạy ứng dụng
mvn spring-boot:run
```

- Server chạy tại: [http://localhost:8080](http://localhost:8080)
- H2 Database Console: [http://localhost:8080/h2-console](http://localhost:8080/h2-console)
  - JDBC URL: `jdbc:h2:mem:moviercm_db`
  - Username: `sa`
  - Password: *(để trống)*

---

### 2. Chạy với profile `prod` (PostgreSQL Database)

Chạy container PostgreSQL từ thư mục `infrastructure/`:
```bash
cd ../../infrastructure
docker compose up -d postgres
```

Khởi chạy Spring Boot với profile `prod`:
```bash
cd ../backend/springboot
mvn spring-boot:run -Dspring-boot.run.profiles=prod
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
