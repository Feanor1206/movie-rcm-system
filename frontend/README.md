# Giao diện Dippie

React và TypeScript được Vite build thành tệp tĩnh trong `dist/`. FastAPI phục vụ các tệp này cùng API.

## Làm việc trên giao diện

Chạy FastAPI ở cổng 8000 với [cấu hình cơ sở dữ liệu](../backend/fastapi/README.md#2-cấu-hình-biến-môi-trường). Từ thư mục `frontend`, chạy các lệnh sau và mở [Dippie](http://localhost:3000/).

```powershell
npm ci
npm run dev
```

Vite chuyển `/api` tới cổng 8000. Có thể đặt `BACKEND_INTERNAL_URL` để dùng cổng khác.

## Kiểm thử và build

```powershell
npm test
npm run typecheck
npm run build
node ../scripts/compute_build_bytes.cjs
```
