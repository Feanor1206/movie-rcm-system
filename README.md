# Dippie

Dippie là web xem phim hoạt hình. FastAPI phục vụ giao diện, tài khoản, kho phim, phát video, gợi ý và CineBot. Node.js chỉ cần khi build hoặc sửa giao diện.

## Chạy trên Windows

Cần Python 3.11, MySQL 8.0 và Node.js 22.12 trở lên để build. Chạy từ thư mục gốc.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/fastapi/requirements.txt
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
```

Cấu hình MySQL và `APP_JWT_SECRET`, rồi khởi động Dippie. [Biến môi trường](backend/fastapi/README.md#2-cấu-hình-biến-môi-trường)

```powershell
.\start-python-main.ps1 -Production -Background
```

Mở [Dippie](http://localhost:3000/). Để dùng cổng khác, truyền `-Port`. Log và trạng thái mặc định nằm trong `target/`.

## Gợi ý và CineBot

Trang chủ gợi ý tập chưa xem từ lịch sử, phim yêu thích và điểm đánh giá. Khách dùng lịch sử trên thiết bị. CineBot tìm trong danh mục và dẫn đến tập hoặc cảnh phù hợp.

Để bật DeepSeek, dừng bản đang chạy, nhập khóa qua `& './scripts/configure_llm.ps1'` rồi khởi động với `-ModelMode cloud`. [Cấu hình DeepSeek](backend/fastapi/README.md#deepseek)

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest tests backend/fastapi/tests -q
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
node scripts/compute_build_bytes.cjs
```

Dừng Dippie bằng `.\scripts\stop_preview_stack.ps1`. Xem thêm [chạy với Docker](infrastructure/README.md), [sửa giao diện](frontend/README.md) và [xử lý dữ liệu phim](ai/README.md).
