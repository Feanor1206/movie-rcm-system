# Docker

Compose chạy FastAPI và MySQL 8.0. FastAPI phục vụ giao diện đã build tại cổng 3000.

Tạo `frontend/dist` bằng `npm ci` và `npm run build` trong `frontend`. Tạo `.env` từ `.env.example` rồi điền mật khẩu MySQL và khóa JWT. Giữ cùng tên dự án Compose khi dùng lại volume MySQL.

```powershell
cd infrastructure
docker compose up -d --build
```

Mở [Dippie](http://localhost:3000/). Dùng `docker compose up -d mysql` nếu chạy web bằng PowerShell ngoài Docker.
