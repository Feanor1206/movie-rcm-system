# Dippie

Dippie là web xem phim hoạt hình, có danh mục phim, danh sách đã lưu, đánh giá và lịch sử xem. Video được phát từ thư mục cục bộ hoặc Google Drive đã gắn vào máy. Phần tìm kiếm hỗ trợ văn bản, ảnh chụp cảnh phim và hội thoại qua CineBot.

## Yêu cầu

- Node.js 20 và Python 3.11.
- MySQL 8.0; có thể chạy bằng Docker Compose.
- JDK 17 trở lên nếu chạy bản Java.

## Cài đặt

Chạy các lệnh từ thư mục gốc của dự án trên PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/fastapi/requirements.txt
cd frontend
npm ci
cd ..
```

Tạo khóa JWT và đặt mật khẩu MySQL trước khi chạy dịch vụ:

```powershell
$env:APP_JWT_SECRET = python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
$env:MYSQL_PASSWORD = "mat-khau-mysql-cua-ban"
cd infrastructure
docker compose up -d mysql
cd ..
```

Dùng cùng khóa JWT cho hai backend. Thay mật khẩu mẫu bằng mật khẩu MySQL của bạn. Xem [cấu hình tài khoản và mô hình](backend/fastapi/README.md#2-cấu-hình-biến-môi-trường) trước khi dùng dữ liệu thật.

## Chạy ứng dụng

Chọn một trong hai bản:

| Bản | Backend chính | Tìm kiếm và hội thoại |
| --- | --- | --- |
| Java | Spring Boot tại cổng 8080 | FastAPI tại cổng 8000 |
| Python | FastAPI tại cổng 8000 | Cùng dịch vụ FastAPI |

Bản Java:

```powershell
.\start-java-main.ps1 -Background
```

Bản Python:

```powershell
.\start-python-main.ps1 -Background
```

Mở [localhost:3000](http://localhost:3000). Script Java bật tài khoản demo có mật khẩu công khai `password123`, chỉ dùng trong môi trường thử nghiệm riêng. Với bản Python, đặt `APP_DEMO_MODE=true` khi cần tài khoản demo, hoặc dùng các biến bootstrap trong hướng dẫn backend để tạo quản trị viên.

Python có thể chuyển sang SQLite tại `data/python_main.db` tính từ thư mục chạy backend nếu kết nối MySQL thất bại. Java có profile `test` dùng H2 để kiểm thử.

Để phát từ Google Drive, đặt `APP_MEDIA_DRIVE_MOUNT` trỏ tới thư mục hoặc ổ đĩa đã gắn Drive.

Dừng dịch vụ:

```powershell
.\scripts\stop_preview_stack.ps1
```

## Kiểm thử

Chạy từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m pytest tests backend/fastapi/tests -q
cd backend/springboot
.\mvnw.cmd test "-Dspring.profiles.active=test"
cd ../../frontend
npm test
npm run typecheck
npm run build
```

## Tài liệu

- [Spring Boot](https://github.com/Feanor1206/movie-rcm-system/tree/java-main/backend/springboot): API tài khoản, danh mục, thư viện và phát video.
- [FastAPI](backend/fastapi/README.md): cấu hình, API nghiệp vụ và tìm kiếm.
- [Giao diện](frontend/README.md): chạy và kiểm tra Next.js.
- [Docker và Nginx](infrastructure/README.md): cấu hình dịch vụ.
- [Xử lý dữ liệu phim](ai/README.md): tạo chỉ mục và đánh giá tìm kiếm.

Các nhánh `main`, `dev` và `java-main` chứa cả hai bản. Nhánh `python-main` lược bỏ `backend/springboot`; bỏ qua các lệnh chạy và kiểm thử Java khi dùng nhánh này.
