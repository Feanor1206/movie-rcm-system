# Docker và Nginx

Cấu hình chạy MySQL 8.0, Redis, Next.js và backend Java hoặc Python.

Đặt `APP_JWT_SECRET` và thông tin cơ sở dữ liệu theo [hướng dẫn FastAPI](../backend/fastapi/README.md#2-cấu-hình-biến-môi-trường) trước khi chạy Compose.

| Tệp | Công dụng |
| --- | --- |
| `docker-compose.yml` | Bản Java: Spring Boot cổng 8080, FastAPI cổng 8000, Next.js cổng 3000, MySQL cổng 3306, Redis cổng 6379 và Nginx cổng 80. |
| `docker-compose.python-main.yml` | Ghi đè cấu hình để FastAPI làm backend chính. |
| `docker-compose.dev.yml` | Bật dữ liệu và tài khoản demo cho môi trường thử nghiệm riêng. |
| `nginx/default.conf` | Chuyển API nghiệp vụ sang Spring Boot, gợi ý phim sang FastAPI. |
| `nginx/python-main.conf` | Chuyển API nghiệp vụ sang FastAPI ở bản Python. |

Ở cả hai bản, `/api/chat` đi qua bộ chuyển tiếp Next.js trước khi gọi FastAPI. Nginx mở cổng 80 ra máy; các dịch vụ web phía sau dùng cổng nội bộ.

Từ thư mục `infrastructure`, chạy bản Java:

```powershell
docker compose up -d
```

Chạy bản Python:

```powershell
docker compose -f docker-compose.yml -f docker-compose.python-main.yml up -d nginx frontend fastapi mysql redis
```

Cấu hình FastAPI trong Compose yêu cầu GPU NVIDIA. Chuẩn bị driver và môi trường Docker hỗ trợ GPU trước khi khởi chạy toàn bộ dịch vụ.
