# Sao lưu và khôi phục MySQL

## Tạo bản sao lưu

Đặt `$dippieClientOptions` là đường dẫn tới tệp cấu hình MySQL của tài khoản cài đặt, nằm ngoài Git. Tệp giữ tên tài khoản, thông tin kết nối và mật khẩu. Chọn đúng schema trước khi chạy. `--single-transaction` lấy ảnh chụp nhất quán của các bảng InnoDB. Giữ lược đồ ổn định trong thời gian dump. [Cách dùng mysqldump](https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html)

```powershell
$sourceSchema = 'movie_rcm_db'
$backupDirectory = 'D:/Dippie-backups'
New-Item -ItemType Directory -Force -Path $backupDirectory | Out-Null
$dump = Join-Path $backupDirectory ('dippie-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.sql')
mysqldump "--defaults-extra-file=$dippieClientOptions" --default-character-set=utf8mb4 --single-transaction --quick --routines --triggers --events --no-tablespaces --set-gtid-purged=OFF "--result-file=$dump" $sourceSchema
if ($LASTEXITCODE -ne 0) { throw 'Sao lưu MySQL thất bại.' }
Get-FileHash -LiteralPath $dump -Algorithm SHA256
```

Chỉ định một schema làm đối số thường của `mysqldump` để file có thể nạp sang schema khác. Bản dump chứa các bảng và các đối tượng trong schema. Cấu hình tài khoản MySQL thuộc quy trình cấp quyền riêng. Video, phụ đề rời và chỉ mục AI cần được sao lưu cùng phiên bản gói ở nơi chúng được lưu.

## Nạp vào schema mới

Mở MySQL CLI bằng cấu hình đã chuẩn bị. Tạo schema mới, chọn schema đó, rồi chạy `SOURCE` với đúng đường dẫn mà lệnh sao lưu đã in. Nếu chuyển máy chủ, kiểm tra tài khoản `DEFINER` của view và trigger. Trên máy chủ mới, dùng bộ nạp đối tượng và tài khoản theo cấu hình mới sau khi nạp dump.

```sql
CREATE DATABASE dippie_restore CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE dippie_restore;
SOURCE D:/Dippie-backups/dippie-20261124-193000-000.sql;
```

Chạy đoạn sau trên cả schema nguồn và schema khôi phục. So từng `row_count` theo tên bảng. Truy vấn đếm trực tiếp từng bảng.

```sql
SET SESSION group_concat_max_len = 32768;
SELECT GROUP_CONCAT(
    CONCAT('SELECT ', QUOTE(table_name), ' AS table_name, COUNT(*) AS row_count FROM `',
           REPLACE(table_name, '`', '``'), '`')
    ORDER BY table_name SEPARATOR ' UNION ALL '
) INTO @dippie_counts
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE';
SET @dippie_counts = CONCAT(@dippie_counts, ' ORDER BY table_name');
PREPARE dippie_restore_counts FROM @dippie_counts;
EXECUTE dippie_restore_counts;
DEALLOCATE PREPARE dippie_restore_counts;

SELECT COUNT(*) FROM v_published_episodes;
SELECT DISTINCT table_schema FROM information_schema.view_table_usage WHERE view_schema = DATABASE();
```

View sau phục hồi phải đọc bảng của schema đích. Đếm số view, routine và trigger qua `information_schema.views`, `information_schema.routines` và `information_schema.triggers`.

## Kết quả chạy thật

Thử ngày 24/11/2026 trên MySQL **8.0.46** cục bộ. Dựng schema sạch theo thứ tự `01_init.sql`, đối tượng, quyền và hai tệp seed. FastAPI kết nối bằng `dippie_app`. `GET /api/health` trả 200 với trạng thái `UP`. API quản trị nhập `data/catalog-by-series/catalog.larva.json`, ghi **104 tập**, 92 phân đoạn và 66 track. Chỉ mục chế độ `light` trả `READY`. API gợi ý trả 5 kết quả và có tập thuộc gói vừa nhập.

Chạy `mysqldump` từ schema vừa nhập và khôi phục vào schema mới trên cùng máy chủ thử. **29/29 bảng** khớp số dòng. View tham chiếu đúng schema khôi phục. Tổng **4 view, 5 routine và 4 trigger** được giữ.

| Bảng hoặc view | Nguồn | Sau khôi phục |
| --- | ---: | ---: |
| `users` | 52 | 52 |
| `movies` | 118 | 118 |
| `watchlist_items` | 13 | 13 |
| `movie_ratings` | 30 | 30 |
| `catalog_episodes` | 104 | 104 |
| `catalog_segments` | 92 | 92 |
| `catalog_text_tracks` | 66 | 66 |
| `catalog_episode_characters` | 193 | 193 |
| `catalog_episode_genres` | 312 | 312 |
| `v_published_episodes` | 104 | 104 |

Dump thử có 1.066.344 byte. SHA-256 là `0c44cf50dbb7f5ea850ca98b736239eb8143478054a21831db0225e16bad937c`. Mốc phục hồi này dùng schema sạch với Larva. Phép đo 100.000 tập nằm trong tài liệu truy vấn. [Kết quả tối ưu truy vấn](../../database/queries/README.md)
