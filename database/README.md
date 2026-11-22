# Cơ sở dữ liệu

Các tệp SQL cho MySQL:

- `schema/`: lược đồ khởi tạo, bắt đầu từ `01_init.sql`.
- `migrations/`: thay đổi bảng danh sách yêu thích, video, danh mục và tiến độ xem.
- `seeds/`: dữ liệu phim và tài khoản demo.

Compose nạp lược đồ khi tạo cơ sở dữ liệu mới. Bản `docker-compose.dev.yml` nạp thêm dữ liệu demo; chỉ dùng trong môi trường thử nghiệm riêng.

## Quan hệ danh mục

- Một tập thuộc một bộ. Nếu tập có mùa, khóa ngoại `(series_id, season_id)` yêu cầu mùa thuộc đúng bộ. Tập có thể để `season_id` là `NULL`. Muốn xóa hoặc đổi bộ của một mùa, xử lý các tập đang trỏ đến mùa đó trước.
- `catalog_episode_assets` nối mỗi tập với những tệp có phạm vi phát tương ứng. Khóa chính `(episode_id, media_asset_id)` giúp tra tệp theo tập và chống liên kết trùng. `coverage_json` giữ mốc thời gian, phạm vi và dữ liệu xuất gói.
- Xem trước và nhập kiểm tra tập, mùa và tập được tham chiếu trong phạm vi tệp. Khi nhập thành công, metadata và liên kết được lưu trong cùng giao dịch.

## Nâng cấp MySQL đang sử dụng

Tạm dừng FastAPI và các tiến trình ghi danh mục. Sao lưu schema ra ngoài thư mục Git trước khi nâng cấp. Ví dụ sau dùng bản demo MySQL cục bộ.

```powershell
$dippieBackup = Join-Path $env:USERPROFILE ('dippie-before-06-' + (Get-Date -Format yyyyMMdd-HHmmss) + '.sql')
mysqldump --host=127.0.0.1 --port=18306 --user=root --password --single-transaction --no-tablespaces --set-gtid-purged=OFF --result-file="$dippieBackup" dippie_release
if ($LASTEXITCODE -ne 0) { throw 'Sao lưu MySQL thất bại.' }
```

Trong MySQL Workbench, chọn đúng schema và kiểm tra các tập có mùa bị thiếu hoặc khác bộ.

```sql
SELECT e.id, e.series_id, e.season_id
FROM catalog_episodes AS e
LEFT JOIN catalog_seasons AS s ON s.id = e.season_id AND s.series_id = e.series_id
WHERE e.season_id IS NOT NULL AND s.id IS NULL;
```

Khi truy vấn trả về 0 dòng, chạy tệp [migration 06](migrations/06_catalog_integrity.sql) trên schema đó. Migration có thể chạy lại. Nếu MySQL báo lỗi liên kết, kiểm tra và sửa các mã ở truy vấn trên theo nguồn trước khi chạy lại.

Khởi động FastAPI để tạo lại liên kết tập–tệp từ `coverage_json`. FastAPI cập nhật các liên kết bị thiếu hoặc lệch và ghi log khi gặp JSON cũ không đọc được hoặc tham chiếu thiếu tập. Kiểm tra một tập có tệp và số liên kết trong bảng `catalog_episode_assets`.

Nếu cần quay lại phiên bản ứng dụng cũ, ứng dụng đó vẫn đọc được `coverage_json`. Nếu cần gỡ khóa ngoại mới trên MySQL, chạy `ALTER TABLE catalog_episodes DROP FOREIGN KEY fk_episode_season_same_series` trong thời gian bảo trì. Có thể giữ bảng nối và chỉ mục phụ. Bản SQLite đã tạo từ phiên bản cũ dùng kiểm tra ở bước nhập và tạo bảng nối khi khởi động. SQLite mới có khóa ngoại ghép ngay từ lúc tạo bảng.

## Kiểm tra độ phủ trước khi nhập

Chạy từ thư mục gốc của repo.

```powershell
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.jadoo_all.json --report
```

Kết quả đếm số tập có tóm tắt, từ khóa, nhân vật, nguồn phát được khai báo và mốc thời gian có bản ghi đã duyệt. Kiểm tra phát và đối chiếu nội dung dùng nguồn video thực tế.
