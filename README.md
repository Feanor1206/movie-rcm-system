# Dippie

Dippie là web xem phim hoạt hình. FastAPI phục vụ giao diện, tài khoản, kho phim, phát video, gợi ý và CineBot. Node.js chỉ cần khi build hoặc sửa giao diện.

## Chạy trên Windows

Cần Python 3.11 và Node.js 22.12 trở lên. Giao diện hiện tại nằm trên nhánh `dev`.

```powershell
git clone --branch dev https://github.com/Feanor1206/movie-rcm-system.git
cd movie-rcm-system
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/fastapi/requirements.txt
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
```

Nếu đã clone, cập nhật nhánh `dev` rồi chạy lại hai lệnh `npm.cmd` ở trên.

### Chạy thử với danh mục mẫu

Chạy từ thư mục gốc trong một cửa sổ PowerShell dành riêng cho bản thử. Bản thử dùng SQLite trong `target/dippie-demo/` và nhập sáu gói phim cùng một gói cập nhật metadata. Lần đầu, đặt mật khẩu cho tài khoản `dippie-admin` dài ít nhất 16 ký tự và tối đa 72 byte.

```powershell
$env:DATABASE_URL = 'sqlite:///../../target/dippie-demo/catalog.sqlite3'
$env:SYNC_STATE_PATH = '../../target/dippie-demo/catalog-sync.json'
$env:APP_DEMO_MODE = 'false'
$stateFile = Join-Path $PWD 'target/dippie-demo/stack.json'
$password = Read-Host 'Mật khẩu dippie-admin' -AsSecureString
$admin = [PSCredential]::new('dippie-admin', $password)
$env:APP_BOOTSTRAP_ADMIN_USERNAME = $admin.UserName
$env:APP_BOOTSTRAP_ADMIN_EMAIL = 'dippie-admin@example.invalid'
$env:APP_BOOTSTRAP_ADMIN_PASSWORD = $admin.GetNetworkCredential().Password
try {
    .\start-python-main.ps1 -Background -StateFile $stateFile
} finally {
    Remove-Item Env:APP_BOOTSTRAP_ADMIN_USERNAME, Env:APP_BOOTSTRAP_ADMIN_EMAIL, Env:APP_BOOTSTRAP_ADMIN_PASSWORD
}
foreach ($catalog in @('jadoo_all', 'larva', 'ori', 'doraemon', 'doraemon_s05_s11', 'trang_quynh', 'episode_metadata')) {
    .\scripts\import_preview_catalog.ps1 -CatalogPath "data/catalog.$catalog.json" -ApiBaseUrl 'http://127.0.0.1:3000/api' -Username $admin.UserName -Password $admin.Password
}
```

Mở trang chủ để xem mục **Gợi ý cho bạn**. [Dippie ở cổng 3000](http://localhost:3000/)

Dùng `.\scripts\stop_preview_stack.ps1 -StateFile $stateFile` để dừng. Lần chạy sau, đặt lại `DATABASE_URL`, `SYNC_STATE_PATH` và `$stateFile` như trên rồi chạy lệnh khởi động. Danh mục đã nhập nằm trong tệp SQLite.

### Chạy với MySQL

Mở một cửa sổ PowerShell riêng và cấu hình MySQL 8.0 cùng `APP_JWT_SECRET`. [Biến môi trường](backend/fastapi/README.md#2-cấu-hình-biến-môi-trường)

```powershell
.\start-python-main.ps1 -Production -Background
```

Mở [Dippie](http://localhost:3000/). Để dùng cổng khác, truyền `-Port`. Log và trạng thái mặc định nằm trong `target/`.

## Gợi ý và CineBot

Trang chủ gợi ý tập chưa xem từ lịch sử, phim yêu thích và điểm đánh giá. Khách dùng lịch sử trên thiết bị. CineBot tìm trong danh mục và dẫn đến tập hoặc cảnh phù hợp.

Để bật DeepSeek, dừng bản đang chạy, nhập khóa qua `& './scripts/configure_llm.ps1'` rồi khởi động với `-ModelMode cloud`. [Cấu hình DeepSeek](backend/fastapi/README.md#deepseek)

## Danh mục phim

Đăng nhập quản trị và nhập từng gói ở [trang Nhập dữ liệu](http://localhost:3000/admin/import). Jadoo phát từ tệp hoặc Google Drive. Larva, Ori, Doraemon và Trạng Quỳnh Thời Nhí Nhố dùng trình phát YouTube, kèm liên kết mở video gốc. [Danh mục và nguồn](data/README.md)

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest tests backend/fastapi/tests -q
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
node scripts/compute_build_bytes.cjs
```

Dừng Dippie bằng `.\scripts\stop_preview_stack.ps1`. Xem thêm [chạy với Docker](infrastructure/README.md), [sửa giao diện](frontend/README.md) và [xử lý dữ liệu phim](ai/README.md).
