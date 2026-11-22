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

## Mốc kiểm thử 100.000 tập

Phép đo dùng MySQL 8.0.46 cục bộ trên schema riêng, với 100.000 tập giả lập, 1.000 bộ, 100.000 liên kết tập–tệp và khoảng 7,7% tập nháp. Mỗi trường hợp gọi API qua TestClient, chạy 2 lần làm nóng rồi lấy trung vị của 7 lần đo. Bản đối chiếu là commit `539ac26`. Các số đo tập trung vào API đọc MySQL, với bước tải chỉ mục CineBot được tách khỏi phép thử.

| Truy vấn ở 100.000 tập | Trước | Sau | Số bản ghi phim được nạp sau |
| --- | ---: | ---: | ---: |
| Duyệt kho hoạt hình, trang 12 kết quả | 2.864 ms | 1.642 ms | 12 |
| Duyệt kho theo thể loại, trang 12 kết quả | 2.710 ms | 1.782 ms | 12 |
| Tìm theo một tiêu đề tập | 2.768 ms | 1.940 ms | 1 |
| Lấy tập và danh sách tệp theo mã | 6,2 ms | 6,4 ms | Không tải bảng `movies` |

Truy vấn chỉ mục tập–tệp ổn định cả ở 10.000 và 100.000 tập. Duyệt kho sắp xếp ở MySQL và đọc theo lô các cột cần lọc. Cách này giảm dữ liệu được nạp thành đối tượng nhưng bộ lọc chuỗi và số kết quả chính xác vẫn phải duyệt các dòng đủ điều kiện. Kết quả là phép đo một người dùng với dữ liệu giả lập.

Ở mốc 100.000 tập, giao dịch thêm 1.000 tập cùng 1.000 liên kết mất khoảng 1,06 giây. Nhập lại gói trả kết quả cũ trong khoảng 0,19 giây. Gói có quan hệ sai bị chặn, tổng sau thử nghiệm là 101.000 tập và 101.000 liên kết. Thời gian này đo phần ghi database, gồm kiểm tra và commit, trước khi đồng bộ chỉ mục.

Ngày 23/11/2026, FastAPI đồng bộ và khôi phục thành công chỉ mục từ khóa của 100.000 tập trong bản thử riêng. Dữ liệu gồm 755 tập thật và 99.245 tập giả lập. Đồng bộ qua API mất 30,59 giây, khôi phục sau khởi động lại mất 30,08 giây. Trung vị ba truy vấn tiêu đề mẫu là 86,74 ms với một tập có thật và 320,70 ms với một tập giả lập. Các số đo dùng chế độ `light` và một người gọi API.

## Nhập danh mục thật

Chạy thử trên bản sao MySQL sau khi áp dụng migration. Chia nội dung thành gói tự chứa theo bộ hoặc nhóm mùa, giữ nguyên mã của bản ghi đã có và tăng `revision` khi sửa. Dùng `--report` để biết phần metadata còn thiếu trước khi nhập.

Sau mỗi gói, đối chiếu số tập và phiên bản gói trong lịch sử nhập. Kiểm tra trạng thái `catalog_snapshots`, một truy vấn lấy tập theo mã và một vài nguồn phát mẫu. Đo lại độ trễ theo hình dạng dữ liệu thật, mức truy cập đồng thời và thời gian đồng bộ chỉ mục trước khi đưa toàn bộ kho vào sử dụng.
