# FastAPI

Backend Python xử lý tài khoản, danh mục, thư viện và phát video. Khi chạy cùng Spring Boot, dịch vụ này cung cấp tìm kiếm, gợi ý phim và hội thoại CineBot.

## Cài đặt

### 1. Thư viện

Chạy từ thư mục gốc:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/fastapi/requirements.txt
```

### 2. Cấu hình biến môi trường

`APP_JWT_SECRET` phải là Base64 của ít nhất 32 byte ngẫu nhiên. Dùng cùng khóa với Spring Boot khi chạy cả hai dịch vụ:

```powershell
python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Lưu khóa qua biến môi trường hoặc hệ thống quản lý bí mật. Giữ khóa ngoài Git. Đổi khóa sẽ làm các phiên đăng nhập và quyền phát cũ hết hiệu lực.

JWT đăng nhập và quyền phát phải có chủ thể cùng thời điểm tạo, hết hạn. Mật khẩu đăng ký dài ít nhất 6 ký tự, tối đa 72 byte UTF-8. Cùng một địa chỉ kết nối và tên đăng nhập được thử xác thực tối đa 30 lần mỗi phút trên một tiến trình.

Python dừng nếu không kết nối được cơ sở dữ liệu đã cấu hình. SQLite cần được chọn rõ bằng `DATABASE_URL`. `GET /api/health` kiểm tra kết nối dữ liệu, còn `GET /ready` kiểm tra thêm chỉ mục tìm kiếm.

Để tạo quản trị viên đầu tiên trên cơ sở dữ liệu mới, đặt `APP_BOOTSTRAP_ADMIN_USERNAME`, `APP_BOOTSTRAP_ADMIN_EMAIL` và `APP_BOOTSTRAP_ADMIN_PASSWORD`. Mật khẩu cần ít nhất 16 ký tự, tối đa 72 byte. Gỡ các biến này sau khi tạo xong. Hệ thống giữ mật khẩu riêng của quản trị viên hiện có và chỉ tạo tài khoản khi chưa có quản trị viên.

Khi nâng cấp cơ sở dữ liệu có quản trị viên dùng mật khẩu demo `password123`, ứng dụng dừng khởi động. Đặt `APP_BOOTSTRAP_ADMIN_USERNAME` đúng tài khoản và `APP_BOOTSTRAP_ADMIN_PASSWORD` mới để đổi mật khẩu; không cần email. Nếu còn nhiều quản trị viên dùng mật khẩu mặc định, cần đổi từng tài khoản bằng công cụ quản trị cơ sở dữ liệu trước khi chạy lại.

Tài khoản demo `user@dippie.com` còn dùng mật khẩu mặc định sẽ được đổi sang mật khẩu ngẫu nhiên; dữ liệu được giữ. Kiểm tra cả bản Java nếu hai dịch vụ dùng chung cơ sở dữ liệu.

`APP_DEMO_MODE=true` tạo tài khoản có mật khẩu công khai, chỉ dùng trong môi trường thử nghiệm riêng. Script chạy cục bộ tạo khóa JWT tạm nếu chưa có; khi script tạo khóa mới, phiên cũ hết hiệu lực. Compose yêu cầu cung cấp khóa và bản `docker-compose.dev.yml` bật dữ liệu demo.

Các biến tùy chọn:

| Biến | Công dụng |
| --- | --- |
| `APP_MEDIA_DRIVE_MOUNT` | Thư mục hoặc ổ đĩa đã gắn Google Drive. Danh mục có thể giữ tiền tố `VideoDieppie/` khi gắn trực tiếp thư mục đó. |
| `APP_MEDIA_CACHE_ROOT` | Bản lưu video Drive trên máy, giữ nguyên đường dẫn tương đối trong danh mục. Chỉ dùng tệp đủ kích thước đã khai báo. Tệp thiếu hoặc sai kích thước được đọc từ Drive. |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT` | Số kết nối MySQL thường trực, kết nối bổ sung và thời gian chờ lấy kết nối. Mặc định 20, 10 và 10 giây. |
| `DB_CONNECT_TIMEOUT`, `DB_READ_TIMEOUT`, `DB_WRITE_TIMEOUT` | Thời gian chờ kết nối, đọc và ghi MySQL. Mặc định 3, 15 và 15 giây. |
| `MODEL_MODE` | `light`: tìm kiếm và trả lời theo mẫu; `cloud`: bật dịch vụ LLM đã cấu hình. |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | Địa chỉ, tên mô hình và khóa của API tương thích OpenAI. Cũng nhận các biến `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `DEEPSEEK_API_KEY`. |
| `ALLOW_FULL_CATALOG_GROUNDING=1` | Cho CineBot dùng bằng chứng trong toàn bộ danh mục, ngoài nhóm tập thử nghiệm. |
| `TEXT_ENCODER_PATH` | Thư mục mô hình mã hóa văn bản ONNX. |
| `RERANKER_MODEL_PATH` | Thư mục mô hình xếp hạng lại TorchScript. |
| `SCORE_CALIBRATION_PATH` | Tệp JSON hiệu chuẩn điểm tìm kiếm. |
| `FRAME_INDEX_PATH` | Thư mục chứa `keyframes.json` cho tìm kiếm bằng ảnh. |

LLM có thể chạy trên máy qua `http://127.0.0.1` hoặc `http://localhost`, hoặc qua dịch vụ HTTPS như DeepSeek. Khóa API có thể bỏ trống với máy chủ HTTP cục bộ. Ví dụ địa chỉ: `https://api.deepseek.com`, `http://127.0.0.1:11434/v1`.

## Chạy

Từ thư mục gốc:

```powershell
.\start-python-main.ps1 -Background
```

Để dùng bản build, đặt `BACKEND_INTERNAL_URL` đúng cổng FastAPI trước khi chạy `npm run build` trong `frontend`, rồi thêm `-Production` vào lệnh khởi động. Chế độ này yêu cầu `APP_JWT_SECRET` đã cấu hình. Tệp trạng thái chỉ chuyển sang `READY` sau khi API và MySQL trả lời.

Mỗi dịch vụ FastAPI chạy một tiến trình để giữ chỉ mục và trạng thái tác vụ nhất quán. Khởi động lại phục hồi danh mục từ bản lưu hoặc cơ sở dữ liệu. Trạng thái đồng bộ là `PENDING`, `BUILDING`, `READY`, `BLOCKED` hoặc `SYNC_FAILED`. Sau khi chuẩn bị cache, có thể thử lại bản dữ liệu mới nhất trong trang quản trị.

Dữ liệu cũ có bản JSON gốc hợp lệ được sửa đúng loại tệp và MIME khi khởi động, không cần nhập lại danh mục.

Chỉ đặt video từ nguồn đã kiểm tra trong thư mục cache. Kiểm tra kích thước xác nhận bản sao đầy đủ ở mức số byte.

Cách chạy cùng Spring Boot nằm trong [README chính](../../README.md).

## API tìm kiếm và hội thoại

| Đường dẫn | Chức năng |
| --- | --- |
| `POST /api/index/sync` | Nhận toàn bộ bản danh mục từ Spring Boot và cập nhật nguyên tử. |
| `POST /v1/search`, `POST /v1/discover` | Tìm phim, tập, cảnh và lời thoại. Kết hợp BM25 với vector khi đã cấu hình mô hình. |
| `POST /api/chat` | Hội thoại SSE với các sự kiện `metadata`, `token`, `done`; trả bằng chứng và câu hỏi tiếp theo trong `followUps`. |
| `POST /api/recommend`, `POST /v1/recommend` | Gợi ý theo `likedMovieIds`, `genres` và `mood`. |
| `POST /v1/frame-search` | Tìm tập và mốc thời gian từ ảnh JPEG, PNG hoặc WebP. |
| `GET /health`, `GET /ready` | Trạng thái dịch vụ và từng tính năng. |

## Kiểm thử

Từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m pytest tests backend/fastapi/tests -q
```
