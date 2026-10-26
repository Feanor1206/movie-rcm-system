# Vận hành bản xem trước có dữ liệu thật

## Dữ liệu nào là nguồn chính

Catalog đi từ tệp JSON cục bộ qua API Spring Boot, được ghi vào cơ sở dữ liệu SQL H2. Cơ sở dữ liệu là nguồn dữ liệu chính. Tệp snapshot JSON được Spring Boot tạo sau lần nhập để dùng cho đồng bộ; FastAPI không thay thế cơ sở dữ liệu. Google Drive chỉ phục vụ byte media khi một tài nguyên cần đến Drive.

Với cấu hình preview mặc định, dữ liệu nằm tại:

- SQL H2: `D:\Class\movie-rcm-system\backend\springboot\data\preview\preview_db.mv.db`
- Catalog snapshot: `D:\Class\movie-rcm-system\backend\springboot\data\preview\committed_catalog_snapshot.json`
- Trạng thái launcher: `D:\Class\movie-rcm-system\target\preview_stack.json` (trường `DataDirectory` ghi lại thư mục SQL đang dùng)

Không xóa hoặc đổi tên các tệp trong thư mục dữ liệu để “làm mới” preview. Dùng lệnh restore ở dưới nếu cần quay lại một bản sao lưu.

## Khởi động lần đầu và nhập catalog

Mở PowerShell tại `D:\Class\movie-rcm-system`. Khởi động mặc định tắt FastAPI/Qwen, chỉ chạy Spring Boot và giao diện. Thêm `-MountDrive` để xem video trên Drive đã cấu hình:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\start_preview_stack.ps1 -Background -MountDrive
```

Nhập đúng tệp catalog đã có trong repo làm việc. Lệnh đăng nhập vào API loopback, gọi `/api/admin/catalog/validate`, rồi chỉ khi hợp lệ và không có conflict mới gọi `/api/admin/catalog/import`:

```powershell
.\scripts\import_preview_catalog.ps1 -CatalogPath data\catalog.jadoo_all.json
```

Nếu chưa truyền thông tin đăng nhập, script hỏi tên tài khoản và mật khẩu; mật khẩu được hỏi ở chế độ ẩn. Có thể truyền `-Username` và `-Password` dưới dạng `SecureString`, hoặc đặt `PREVIEW_ADMIN_USERNAME` và `PREVIEW_ADMIN_PASSWORD` trong process environment hiện tại. Script không in hoặc lưu mật khẩu/JWT. API quyết định quyền, revision và idempotency; script không đổi quyền, sửa revision hay chính sách public/private. Gói local hiện tại là `pkg_dippie_jadoo_all` revision 3; các cờ public/private của video và audio được giữ nguyên như trong gói.

Kết quả hiển thị package ID, revision, import ID, counts và `indexStatus` do API trả về. `success` xác nhận dữ liệu đã được nhập vào SQL. Nếu `indexStatus` là `PENDING` hoặc `BLOCKED`, index chưa sẵn sàng; ở chế độ mặc định `ModelMode off`, đồng bộ index được để lại cho lần bật FastAPI phù hợp, không gọi tiến trình khác trên cổng 8000. Không hiểu `PENDING` là index đã đồng bộ.

## Dừng và khởi động lại

Dừng preview bằng launcher để nó xác minh PID và danh tính tiến trình:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\stop_preview_stack.ps1
```

Khởi động lại bằng cùng lệnh `start_preview_stack.ps1 -Background -MountDrive` ở trên. Spring Boot mở lại cùng `preview_db.mv.db`; catalog đã nhập vẫn còn trong SQL. Không chạy thao tác sao lưu/khôi phục khi launcher hoặc backend đang hoạt động.

## Sao lưu và khôi phục

Trước sao lưu, dừng preview. Chọn một tên thư mục mới dưới `target\preview_backups`; lệnh từ chối ghi đè một thư mục đã tồn tại:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\backup_preview_data.ps1 -BackupDirectory target\preview_backups\jadoo-before-change-20261027
```

Bản sao chỉ chứa hai tệp đã biết: `preview_db.mv.db` và `committed_catalog_snapshot.json`, cùng `manifest.json` có độ dài và SHA-256 của từng tệp. Script kiểm tra PID/danh tính launcher, listener Spring Boot và mở khóa tệp H2 độc quyền trước khi đọc; nó giữ khóa trong lúc sao chép cơ sở dữ liệu. Giữ stack dừng cho đến khi lệnh kết thúc. Đổi tên ví dụ ngày ở trên cho mỗi lần chạy.

Khôi phục cũng cần stack đã dừng và giữ dừng cho đến khi lệnh kết thúc. Script xác minh manifest và hash trước mọi thay đổi, tạo recovery backup của dữ liệu hiện tại, kiểm tra lại launcher/listener và khóa H2 ngay trước khi thay đúng hai tệp preview:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\restore_preview_data.ps1 -BackupDirectory target\preview_backups\jadoo-before-change-20261027
```

Đường dẫn recovery hiện ra trong output và nằm dưới `target\preview_backups\recovery-*`. Nếu backup thiếu manifest, sai hash, chứa tên đường dẫn ngoài danh sách hoặc đang có service dùng dữ liệu, thao tác dừng an toàn. Các lệnh này không xóa thư mục đệ quy, không đọc `user tempdata`, và không dùng copy nóng trực tiếp từ H2.

Các lệnh này chỉ sao lưu/khôi phục thư mục preview mặc định. Chúng không sao lưu media bên ngoài thư mục này, cấu hình Drive, log, model, hoặc index FastAPI.

Không bật `-ModelMode full` khi GPU còn dùng cho công việc khác. Khi chưa bật FastAPI, tìm kiếm catalog SQL và phát video vẫn dùng được; CineBot báo dịch vụ tạm nghỉ. Tài khoản demo chỉ dùng trên loopback, chưa dùng cấu hình này để công khai Internet.

## Khi chuẩn bị dùng Cloudflare Tunnel

Trình duyệt gọi API cùng nguồn tại `/api`. Next.js chuyển tiếp tới Spring Boot ở loopback; `/api/chat` vẫn là gateway riêng. Chỉ cần hướng Tunnel vào `http://127.0.0.1:3000`; không đưa trực tiếp cổng SQL, 8080 hay 8000 lên Internet.

Trước khi chia sẻ ra ngoài, cần đổi tài khoản/secret demo và cấu hình đúng origin HTTPS bằng `APP_CORS_ALLOWED_ORIGINS`, rồi khởi động lại. Ví dụ giá trị là `https://ten-mien-cua-ban.example`, không dùng `*`. Milestone này chưa nghiệm thu truy cập Internet hoặc triển khai công khai; người dùng sẽ setup Tunnel sau.

Với PostgreSQL có sẵn, migration `database/migrations/05_add_watch_progress.sql` bổ sung bảng tiến độ. Không tự đổi database preview đang dùng sang PostgreSQL chỉ để demo. Luôn backup trước khi áp dụng thay đổi dữ liệu.
