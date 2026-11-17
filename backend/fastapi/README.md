# FastAPI

FastAPI phục vụ web, tài khoản, danh mục, thư viện, phát video, tìm kiếm, gợi ý phim và CineBot.

## Cài đặt

### 1. Thư viện

Chạy từ thư mục gốc:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/fastapi/requirements.txt
```

### 2. Cấu hình biến môi trường

`APP_JWT_SECRET` phải là Base64 của ít nhất 32 byte ngẫu nhiên.

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
| `ALLOW_FULL_CATALOG_GROUNDING=1` | Mở rộng nguồn DeepSeek sang các tập công khai trong gói danh mục được duyệt. Mặc định dùng nguồn thí điểm, tóm tắt Larva và Ori đã đối chiếu, cùng các tập trong `APPROVED_CLOUD_EPISODES`. |
| `TEXT_ENCODER_PATH` | Thư mục mô hình mã hóa văn bản ONNX. |
| `RERANKER_MODEL_PATH` | Thư mục mô hình xếp hạng lại TorchScript. |
| `SCORE_CALIBRATION_PATH` | Tệp JSON hiệu chuẩn điểm tìm kiếm. |
| `FRAME_INDEX_PATH` | Thư mục chứa `keyframes.json` cho tìm kiếm bằng ảnh. |

LLM có thể chạy trên máy qua `http://127.0.0.1` hoặc `http://localhost`, hoặc qua dịch vụ HTTPS như DeepSeek. Khóa API có thể bỏ trống với máy chủ HTTP cục bộ. Ví dụ địa chỉ: `https://api.deepseek.com`, `http://127.0.0.1:11434/v1`.

## DeepSeek

Chạy `& './scripts/configure_llm.ps1'` tại thư mục gốc. Giữ địa chỉ `https://api.deepseek.com` và mô hình `deepseek-flash` nếu dùng DeepSeek chính thức. Script kiểm tra kết nối rồi lưu khóa vào `.env.deepseek.local`, tệp được Git bỏ qua. Khởi động Python với `-ModelMode cloud`. Xem [API DeepSeek](https://api-docs.deepseek.com/api/create-chat-completion/) để đổi mô hình.

CineBot tìm bằng chỉ mục cục bộ. Với kết quả có trích đoạn đã duyệt, máy chủ gửi loại yêu cầu và tối đa ba trích đoạn đến DeepSeek trong một lượt gọi. Câu hỏi gốc, lịch sử chat và dữ liệu cá nhân được xử lý cục bộ. Liên kết phim và mốc phát lấy từ danh mục. Khi thiếu nguồn phù hợp hoặc mô hình gặp lỗi, CineBot vẫn trả lời từ kho phim.

Ở cấu hình mặc định, hỏi “Học tập trải nghiệm thú vị” để kiểm tra luồng DeepSeek. Phản hồi `done` ghi `pipelineStages.conversation` là `cloud` khi dùng câu trả lời đã kiểm tra từ nhà cung cấp hoặc `template` khi dùng nội dung cục bộ.

## Chạy

Build giao diện bằng `npm run build` trong `frontend`. Từ thư mục gốc, chạy ứng dụng với khóa JWT cố định.

```powershell
.\start-python-main.ps1 -Production -Background
```

Web và API dùng cổng 3000. FastAPI đọc giao diện tại `frontend/dist`. Biến `DIPPIE_WEB_DIST` chỉ định nơi lưu tệp build khi cần. Tệp trạng thái chuyển sang `READY` sau khi FastAPI kết nối được cơ sở dữ liệu.

Mỗi dịch vụ FastAPI chạy một tiến trình để giữ chỉ mục và trạng thái tác vụ nhất quán. Khởi động lại phục hồi danh mục từ bản lưu hoặc cơ sở dữ liệu. Trạng thái đồng bộ là `PENDING`, `BUILDING`, `READY`, `BLOCKED` hoặc `SYNC_FAILED`. Sau khi chuẩn bị cache, có thể thử lại bản dữ liệu mới nhất trong trang quản trị.

Dữ liệu cũ có bản JSON gốc hợp lệ được sửa đúng loại tệp và MIME khi khởi động, không cần nhập lại danh mục.

Chỉ đặt video từ nguồn đã kiểm tra trong thư mục cache. Kiểm tra kích thước xác nhận bản sao đầy đủ ở mức số byte.

## API tìm kiếm và hội thoại

| Đường dẫn | Chức năng |
| --- | --- |
| `POST /api/index/sync` | Nhận bản danh mục đã xác thực và cập nhật chỉ mục. |
| `POST /v1/search`, `POST /v1/discover` | Tìm phim, tập, cảnh và lời thoại. Kết hợp BM25 với vector khi đã cấu hình mô hình. |
| `POST /api/chat` | Hội thoại SSE với các sự kiện `metadata`, `token`, `done`; trả bằng chứng và câu hỏi tiếp theo trong `followUps`. |
| `POST /api/recommend`, `POST /v1/recommend` | Gợi ý theo `likedMovieIds`, `genres` và `mood`. Với token đăng nhập, dùng thêm phim yêu thích, điểm từ 8 và các tập đã xem. Trang chủ gửi mã những tập đã xem trên thiết bị khi dùng chế độ khách. |
| `POST /v1/frame-search` | Tìm tập và mốc thời gian từ ảnh JPEG, PNG hoặc WebP. |
| `GET /health`, `GET /ready` | Trạng thái dịch vụ và từng tính năng. |

## Kiểm thử

Từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m pytest tests backend/fastapi/tests -q
```
