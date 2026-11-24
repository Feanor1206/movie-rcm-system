# Từ điển dữ liệu MySQL

Đối chiếu MySQL 8.0.46 dựng từ `01_init.sql`, gồm 29 bảng và 304 cột. Các cột chuỗi dùng utf8mb4. `movie_genre_terms.name` và `movie_genres.genre_name` dùng collation nhị phân cho tên thể loại đã chuẩn hóa. Các cột có mặc định SQL được ghi theo lược đồ.

PK là thành phần khóa chính. UNIQUE được liệt kê theo đúng nhóm cột. Trong cột Khóa và CHECK, FK ghi bảng/cột đích và hành động khi xóa. CHECK có tên để liên hệ với thông báo lỗi MySQL và phần biểu thức bên dưới bảng.

## `users`

Tài khoản và quyền trong ứng dụng.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `bigint` | Không | `AUTO_INCREMENT` | PK | Mã định danh của hàng trong bảng. |
| `username` | `varchar(50)` | Không | — | UNIQUE `username` | Tên đăng nhập duy nhất. |
| `email` | `varchar(100)` | Không | — | UNIQUE `email` | Địa chỉ email dùng cho tài khoản. |
| `password` | `varchar(255)` | Không | — | — | Dấu băm bcrypt của mật khẩu tài khoản ứng dụng. |
| `full_name` | `varchar(100)` | Có | `NULL` | — | Tên hiển thị của tài khoản. |
| `role` | `varchar(20)` | Không | `ROLE_USER` | `ck_user_role` | ROLE_USER hoặc ROLE_ADMIN của ứng dụng. Quyền MySQL cấp độc lập. |
| `created_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` | — | Thời điểm tạo bản ghi. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- UNIQUE `email` gồm `email`.
- UNIQUE `username` gồm `username`.
- `ck_user_role` kiểm tra `(hex(role) in (hex(_utf8mb4\'ROLE_USER\'),hex(_utf8mb4\'ROLE_ADMIN\')))`.

## `movies`

Phim ở API cũ, gồm cả các bản chiếu từ danh mục hoạt hình.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `title` | `varchar(255)` | Không | — | — | Tiêu đề của bản ghi. |
| `release_year` | `int` | Không | — | — | Năm hiển thị của phim ở API cũ. |
| `rating` | `double` | Không | — | `ck_movie_rating_bounds` | Điểm hiển thị sẵn của phim, trong miền 0 đến 10. |
| `runtime` | `varchar(20)` | Có | `NULL` | — | Thời lượng hiển thị dạng chuỗi trong API phim cũ. |
| `genres` | `longtext` | Có | `NULL` | — | Chuỗi thể loại phim phân tách bằng dấu phẩy, dùng cho API cũ. |
| `description` | `longtext` | Có | `NULL` | — | Mô tả bằng văn bản. |
| `poster` | `varchar(500)` | Có | `NULL` | — | Đường dẫn ảnh áp phích phim. |
| `backdrop` | `varchar(500)` | Có | `NULL` | — | Đường dẫn ảnh nền phim. |
| `video_url` | `varchar(500)` | Có | `NULL` | — | Đường dẫn phát phim trong API cũ. |
| `created_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` | — | Thời điểm tạo bản ghi. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- `ck_movie_rating_bounds` kiểm tra `(rating between 0 and 10)`.

## `watchlist_items`

Một mục xem sau của một người dùng.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `bigint` | Không | `AUTO_INCREMENT` | PK | Mã định danh của hàng trong bảng. |
| `user_id` | `bigint` | Không | — | UNIQUE `uq_user_movie_watchlist`, FK `fk_watchlist_user` tới `users(id)` khi xóa `CASCADE` | Mã tài khoản của thao tác. |
| `movie_id` | `varchar(100)` | Không | — | UNIQUE `uq_user_movie_watchlist`, FK `fk_watchlist_movie` tới `movies(id)` khi xóa `CASCADE` | Mã phim được liên kết. |
| `added_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` | — | Thời điểm người dùng thêm mục vào thư viện. |

- UNIQUE `uq_user_movie_watchlist` gồm `(user_id, movie_id)`.

## `favorite_items`

Một mục yêu thích của một người dùng.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `bigint` | Không | `AUTO_INCREMENT` | PK | Mã định danh của hàng trong bảng. |
| `user_id` | `bigint` | Không | — | UNIQUE `uq_user_movie_favorite`, FK `fk_favorite_user` tới `users(id)` khi xóa `CASCADE` | Mã tài khoản của thao tác. |
| `movie_id` | `varchar(100)` | Không | — | UNIQUE `uq_user_movie_favorite`, FK `fk_favorite_movie` tới `movies(id)` khi xóa `CASCADE` | Mã phim được liên kết. |
| `added_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` | — | Thời điểm người dùng thêm mục vào thư viện. |

- UNIQUE `uq_user_movie_favorite` gồm `(user_id, movie_id)`.

## `movie_ratings`

Điểm người dùng chấm cho một phim.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `bigint` | Không | `AUTO_INCREMENT` | PK | Mã định danh của hàng trong bảng. |
| `user_id` | `bigint` | Không | — | UNIQUE `uq_user_movie_rating`, FK `fk_rating_user` tới `users(id)` khi xóa `CASCADE` | Mã tài khoản của thao tác. |
| `movie_id` | `varchar(100)` | Không | — | UNIQUE `uq_user_movie_rating`, FK `fk_rating_movie` tới `movies(id)` khi xóa `CASCADE` | Mã phim được liên kết. |
| `rating` | `int` | Không | — | `ck_movie_rating_range` | Điểm nguyên 1 đến 10 mà tài khoản chấm cho phim. |
| `created_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` | — | Thời điểm tạo bản ghi. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- UNIQUE `uq_user_movie_rating` gồm `(user_id, movie_id)`.
- `ck_movie_rating_range` kiểm tra `((rating >= 1) and (rating <= 10))`.

## `media_assets`

Bản siêu dữ liệu video dùng cho API phát phim cũ.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(64)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `movie_id` | `varchar(100)` | Không | — | UNIQUE `uq_movie_kind_version`, FK `fk_media_movie` tới `movies(id)` khi xóa `CASCADE` | Mã phim được liên kết. |
| `kind` | `varchar(20)` | Không | — | UNIQUE `uq_movie_kind_version`, `ck_media_kind` | Công dụng của bản phát legacy, lấy cùng miền role của tệp danh mục. |
| `storage_provider` | `varchar(30)` | Không | `local` | — | Nhà cung cấp hoặc loại kho lưu trữ. |
| `storage_key` | `varchar(100)` | Có | `NULL` | — | Mã cấu hình gốc lưu trữ chứa tệp. |
| `relative_path` | `varchar(500)` | Không | — | — | Đường dẫn tương đối tới tệp trong kho lưu trữ. |
| `version` | `varchar(50)` | Không | `v1` | UNIQUE `uq_movie_kind_version` | Mã phiên bản. |
| `mime_type` | `varchar(100)` | Không | `video/mp4` | — | Kiểu nội dung khi FastAPI trả tệp legacy. |
| `byte_length` | `bigint` | Không | — | — | Số byte của tệp phát trong API cũ. |
| `duration_seconds` | `double` | Có | `NULL` | — | Thời lượng tệp legacy tính theo giây. |
| `is_public` | `tinyint(1)` | Không | `1` | — | Asset legacy được phép công khai. |
| `is_available` | `tinyint(1)` | Không | `1` | — | Asset legacy được đánh dấu khả dụng. |
| `created_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` | — | Thời điểm tạo bản ghi. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- UNIQUE `uq_movie_kind_version` gồm `(movie_id, kind, version)`.
- `ck_media_kind` kiểm tra `(hex(kind) in (hex(_utf8mb4\'feature\'),hex(_utf8mb4\'trailer\'),hex(_utf8mb4\'extra\'),hex(_utf8mb4\'opening\'),hex(_utf8mb4\'ending\'),hex(_utf8mb4\'dub\'),hex(_utf8mb4\'audio_description\')))`.

## `movie_genre_terms`

Từ vựng thể loại chuẩn hóa từ nhãn phim cũ.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `name` | `varchar(255)` | Không | — | PK | Nhãn thể loại đã viết thường và bỏ khoảng trắng đầu/cuối. |

## `movie_genres`

Liên kết nhiều–nhiều phim và từ vựng thể loại phim.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `movie_id` | `varchar(100)` | Không | — | PK, FK `fk_movie_genres_movie_id` tới `movies(id)` khi xóa `CASCADE` | Mã phim được liên kết. |
| `genre_name` | `varchar(255)` | Không | — | PK, FK `fk_movie_genres_genre_name` tới `movie_genre_terms(name)` khi xóa `CASCADE` | Nhãn thể loại phim đã chuẩn hóa. |


## `catalog_packages`

Sổ theo dõi gói danh mục được nhập.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `version` | `varchar(50)` | Không | — | — | Mã phiên bản. |
| `revision` | `int` | Không | — | — | Phiên bản nội dung của bản ghi hoặc gói. |
| `default_language` | `varchar(20)` | Không | — | — | Ngôn ngữ mặc định của gói. |
| `import_mode` | `varchar(50)` | Không | — | — | Chế độ áp dụng gói danh mục. |
| `reference_scope` | `varchar(50)` | Không | — | — | Phạm vi mã tham chiếu khi nhập gói. |
| `name` | `varchar(200)` | Có | `NULL` | — | Tên định danh hoặc tên hiển thị. |
| `description` | `longtext` | Có | `NULL` | — | Mô tả bằng văn bản. |
| `content_hash` | `varchar(100)` | Không | — | — | Dấu băm nhận diện nội dung gói hoặc snapshot. |
| `status` | `varchar(50)` | Không | — | `ck_catalog_package_status` | COMMITTED khi giao dịch nhập gói thành công. |
| `error_message` | `longtext` | Có | `NULL` | — | Thông tin lỗi của lần nhập hoặc dựng chỉ mục. |
| `opt_lock_version` | `bigint` | Có | `0` | — | Phiên bản số của hàng để kiểm tra cập nhật đồng thời. |
| `created_at` | `timestamp` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm tạo bản ghi. |
| `imported_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` | — | Thời điểm lần nhập gói được ghi. |

- `ck_catalog_package_status` kiểm tra `(hex(status) = hex(_utf8mb4\'COMMITTED\'))`.

## `catalog_snapshots`

Phiên bản xuất cho CineBot và gợi ý phim, cùng trạng thái tạo chỉ mục.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `snapshot_version` | `bigint` | Không | — | UNIQUE `uq_cat_snap_version` | Số thứ tự duy nhất của snapshot. |
| `content_hash` | `varchar(100)` | Không | — | — | Dấu băm nhận diện nội dung gói hoặc snapshot. |
| `total_items` | `int` | Không | — | — | Số mục trong phiên bản xuất chỉ mục. |
| `status` | `varchar(50)` | Không | — | `ck_catalog_snapshot_status` | Trạng thái pipeline gồm PENDING, BUILDING, READY, BLOCKED và SYNC_FAILED. |
| `retry_count` | `int` | Có | `0` | — | Số lần thử dựng lại chỉ mục. |
| `error_message` | `longtext` | Có | `NULL` | — | Thông tin lỗi của lần nhập hoặc dựng chỉ mục. |
| `created_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` | — | Thời điểm tạo bản ghi. |
| `completed_at` | `timestamp` | Có | `NULL` | — | Thời điểm tạo chỉ mục thành công. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- UNIQUE `uq_cat_snap_version` gồm `snapshot_version`.
- `ck_catalog_snapshot_status` kiểm tra `(hex(status) in (hex(_utf8mb4\'PENDING\'),hex(_utf8mb4\'BUILDING\'),hex(_utf8mb4\'READY\'),hex(_utf8mb4\'BLOCKED\'),hex(_utf8mb4\'SYNC_FAILED\')))`.

## `catalog_genres`

Thể loại có nhãn đa ngôn ngữ của catalog.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `labels_json` | `longtext` | Không | — | — | Các nhãn thể loại theo ngôn ngữ. |
| `aliases_json` | `longtext` | Có | `NULL` | — | Tên khác và loại của tên khác. |
| `description` | `longtext` | Có | `NULL` | — | Mô tả bằng văn bản. |
| `record_json` | `longtext` | Có | `NULL` | — | Trạng thái, phiên bản và thông tin kiểm chứng của bản ghi. |
| `raw_json` | `longtext` | Có | `NULL` | — | Bản gốc của thực thể khi nhập, dùng để truy vết và xuất gói. |
| `revision` | `int` | Không | `1` | — | Phiên bản nội dung của bản ghi hoặc gói. |
| `opt_lock_version` | `bigint` | Có | `0` | — | Phiên bản số của hàng để kiểm tra cập nhật đồng thời. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

## `catalog_attribute_scales`

Thang đo thuộc tính biên tập.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `name` | `varchar(255)` | Không | — | — | Tên định danh hoặc tên hiển thị. |
| `definition` | `longtext` | Có | `NULL` | — | Định nghĩa giá trị mà thang đo mô tả. |
| `minimum` | `double` | Không | — | `ck_catalog_scale_bounds` | Giá trị nhỏ nhất của thang đo. |
| `maximum` | `double` | Không | — | `ck_catalog_scale_bounds` | Giá trị lớn nhất của thang đo. |
| `levels_json` | `longtext` | Không | — | — | Các mức giá trị và diễn giải của thang đo. |
| `version` | `varchar(50)` | Có | `NULL` | — | Mã phiên bản. |
| `source_ids_json` | `longtext` | Có | `NULL` | — | Nguồn tham chiếu được khai báo trong gói gốc. |
| `record_json` | `longtext` | Có | `NULL` | — | Trạng thái, phiên bản và thông tin kiểm chứng của bản ghi. |
| `raw_json` | `longtext` | Có | `NULL` | — | Bản gốc của thực thể khi nhập, dùng để truy vết và xuất gói. |
| `revision` | `int` | Không | `1` | — | Phiên bản nội dung của bản ghi hoặc gói. |
| `opt_lock_version` | `bigint` | Có | `0` | — | Phiên bản số của hàng để kiểm tra cập nhật đồng thời. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- `ck_catalog_scale_bounds` kiểm tra `(minimum < maximum)`.

## `catalog_sources`

Nguồn của metadata, lời thoại hoặc kiểm chứng.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `kind` | `varchar(50)` | Không | — | `ck_catalog_source_kind` | Loại nguồn theo hợp đồng, như manual, official, subtitle hoặc model_output. |
| `title` | `varchar(255)` | Không | — | — | Tiêu đề của bản ghi. |
| `uri` | `varchar(1000)` | Có | `NULL` | — | Địa chỉ nguồn hoặc mã tài nguyên. |
| `note` | `longtext` | Có | `NULL` | — | Ghi chú về nguồn hoặc cách lấy dữ liệu. |
| `retrieved_at` | `datetime(6)` | Có | `NULL` | — | Thời điểm lấy nguồn lưu ở UTC, tới microgiây. |
| `record_json` | `longtext` | Có | `NULL` | — | Trạng thái, phiên bản và thông tin kiểm chứng của bản ghi. |
| `raw_json` | `longtext` | Có | `NULL` | — | Bản gốc của thực thể khi nhập, dùng để truy vết và xuất gói. |
| `revision` | `int` | Không | `1` | — | Phiên bản nội dung của bản ghi hoặc gói. |
| `opt_lock_version` | `bigint` | Có | `0` | — | Phiên bản số của hàng để kiểm tra cập nhật đồng thời. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- `ck_catalog_source_kind` kiểm tra `(hex(kind) in (hex(_utf8mb4\'manual\'),hex(_utf8mb4\'official\'),hex(_utf8mb4\'external_catalog\'),hex(_utf8mb4\'subtitle\'),hex(_utf8mb4\'transcript\'),hex(_utf8mb4\'video_observation\'),hex(_utf8mb4\'model_output\'),hex(_utf8mb4\'other\')))`.

## `catalog_series`

Bộ phim hoạt hình và siêu dữ liệu cấp bộ.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `title` | `varchar(255)` | Không | — | — | Tiêu đề của bản ghi. |
| `original_title` | `varchar(255)` | Có | `NULL` | — | Tên bộ theo ngôn ngữ nguyên bản. |
| `aliases_json` | `longtext` | Có | `NULL` | — | Tên khác và loại của tên khác. |
| `synopsis` | `longtext` | Có | `NULL` | — | Tóm tắt nội dung phim hoạt hình. |
| `translations_json` | `longtext` | Có | `NULL` | — | Các bản dịch tên, mô tả hoặc tóm tắt. |
| `genre_ids_json` | `longtext` | Có | `NULL` | — | Danh sách mã thể loại theo payload cũ. |
| `keywords_json` | `longtext` | Có | `NULL` | — | Từ khóa tìm kiếm của nội dung. |
| `themes_json` | `longtext` | Có | `NULL` | — | Các chủ đề của nội dung. |
| `origin_countries_json` | `longtext` | Có | `NULL` | — | Mã các quốc gia sản xuất. |
| `original_languages_json` | `longtext` | Có | `NULL` | — | Mã ngôn ngữ nguyên bản của bộ. |
| `release_year_start` | `int` | Có | `NULL` | `ck_catalog_series_years` | Năm phát hành đầu được biết của bộ. |
| `release_year_end` | `int` | Có | `NULL` | `ck_catalog_series_years` | Năm phát hành cuối được biết của bộ. |
| `release_status` | `varchar(50)` | Có | `NULL` | — | Tình trạng phát hành của bộ, khác với trạng thái biên tập tập. |
| `character_ids_json` | `longtext` | Có | `NULL` | — | Danh sách mã nhân vật của payload cũ. |
| `artworks_json` | `longtext` | Có | `NULL` | — | Ảnh minh họa với vai trò, đường dẫn và thông tin liên quan. |
| `attributes_json` | `longtext` | Có | `NULL` | — | Thuộc tính biên tập và giá trị theo thang đo. |
| `ratings_json` | `longtext` | Có | `NULL` | — | Điểm và nguồn đánh giá trong gói danh mục. |
| `advisories_json` | `longtext` | Có | `NULL` | — | Khuyến cáo nội dung hoặc giới hạn độ tuổi. |
| `credits_json` | `longtext` | Có | `NULL` | — | Thông tin người tham gia sản xuất và vai trò. |
| `external_ids_json` | `longtext` | Có | `NULL` | — | Mã nhận diện của bản ghi trong các danh mục ngoài. |
| `record_json` | `longtext` | Có | `NULL` | — | Trạng thái, phiên bản và thông tin kiểm chứng của bản ghi. |
| `raw_json` | `longtext` | Có | `NULL` | — | Bản gốc của thực thể khi nhập, dùng để truy vết và xuất gói. |
| `revision` | `int` | Không | `1` | — | Phiên bản nội dung của bản ghi hoặc gói. |
| `opt_lock_version` | `bigint` | Có | `0` | — | Phiên bản số của hàng để kiểm tra cập nhật đồng thời. |
| `created_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` | — | Thời điểm tạo bản ghi. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- `ck_catalog_series_years` kiểm tra `(release_year_start <= release_year_end)`.

## `catalog_seasons`

Mùa thuộc một bộ cụ thể.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK, UNIQUE `uq_cat_season_series_id` | Mã định danh của hàng trong bảng. |
| `series_id` | `varchar(100)` | Không | — | UNIQUE `uq_cat_season_series_id`, FK `fk_season_series` tới `catalog_series(id)` khi xóa `CASCADE` | Mã bộ được liên kết. |
| `number` | `int` | Có | `NULL` | — | Số thứ tự của mùa hoặc tập theo danh mục. |
| `title` | `varchar(255)` | Không | — | — | Tiêu đề của bản ghi. |
| `synopsis` | `longtext` | Có | `NULL` | — | Tóm tắt nội dung phim hoạt hình. |
| `kind` | `varchar(50)` | Có | `NULL` | `ck_catalog_season_kind` | Loại mùa gồm regular, specials, collection và unknown và có thể trống. |
| `translations_json` | `longtext` | Có | `NULL` | — | Các bản dịch tên, mô tả hoặc tóm tắt. |
| `release_date` | `date` | Có | `NULL` | — | Ngày phát hành đã biết, theo ngày lịch. |
| `artworks_json` | `longtext` | Có | `NULL` | — | Ảnh minh họa với vai trò, đường dẫn và thông tin liên quan. |
| `attributes_json` | `longtext` | Có | `NULL` | — | Thuộc tính biên tập và giá trị theo thang đo. |
| `record_json` | `longtext` | Có | `NULL` | — | Trạng thái, phiên bản và thông tin kiểm chứng của bản ghi. |
| `raw_json` | `longtext` | Có | `NULL` | — | Bản gốc của thực thể khi nhập, dùng để truy vết và xuất gói. |
| `revision` | `int` | Không | `1` | — | Phiên bản nội dung của bản ghi hoặc gói. |
| `opt_lock_version` | `bigint` | Có | `0` | — | Phiên bản số của hàng để kiểm tra cập nhật đồng thời. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- UNIQUE `uq_cat_season_series_id` gồm `(series_id, id)`.
- `ck_catalog_season_kind` kiểm tra `((kind is null) or (hex(kind) in (hex(_utf8mb4\'regular\'),hex(_utf8mb4\'specials\'),hex(_utf8mb4\'collection\'),hex(_utf8mb4\'unknown\'))))`.

## `catalog_episodes`

Tập hoạt hình, trạng thái xuất bản và siêu dữ liệu cấp tập.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `series_id` | `varchar(100)` | Không | — | FK `fk_episode_season_same_series` tới `catalog_seasons(series_id, id)` khi xóa `NO ACTION`, FK `fk_episode_series` tới `catalog_series(id)` khi xóa `CASCADE` | Mã bộ được liên kết. |
| `season_id` | `varchar(100)` | Có | `NULL` | FK `fk_episode_season_same_series` tới `catalog_seasons(series_id, id)` khi xóa `NO ACTION` | Mã mùa của tập, có thể chưa phân mùa. |
| `number` | `int` | Có | `NULL` | — | Số thứ tự của mùa hoặc tập theo danh mục. |
| `title` | `varchar(255)` | Không | — | — | Tiêu đề của bản ghi. |
| `aliases_json` | `longtext` | Có | `NULL` | — | Tên khác và loại của tên khác. |
| `synopsis` | `longtext` | Có | `NULL` | — | Tóm tắt nội dung phim hoạt hình. |
| `translations_json` | `longtext` | Có | `NULL` | — | Các bản dịch tên, mô tả hoặc tóm tắt. |
| `kind` | `varchar(50)` | Không | — | `ck_catalog_episode_kind` | Loại tập theo hợp đồng, như regular, special, recap, short hoặc movie. |
| `release_date` | `date` | Có | `NULL` | — | Ngày phát hành đã biết, theo ngày lịch. |
| `duration_ms` | `bigint` | Có | `NULL` | `ck_catalog_episode_duration` | Thời lượng nội dung tính theo mili giây. |
| `genre_ids_json` | `longtext` | Có | `NULL` | — | Danh sách mã thể loại theo payload cũ. |
| `primary_language` | `varchar(50)` | Có | `NULL` | — | Ngôn ngữ chính khai báo của nội dung. |
| `orders_json` | `longtext` | Có | `NULL` | — | Các thứ tự phát hoặc thứ tự trình bày của tập. |
| `links_json` | `longtext` | Có | `NULL` | — | Các liên kết kèm theo tập trong gói danh mục. |
| `character_ids_json` | `longtext` | Có | `NULL` | — | Danh sách mã nhân vật của payload cũ. |
| `plot_facts_json` | `longtext` | Có | `NULL` | — | Chi tiết tình tiết và bằng chứng có cấu trúc. |
| `keywords_json` | `longtext` | Có | `NULL` | — | Từ khóa tìm kiếm của nội dung. |
| `themes_json` | `longtext` | Có | `NULL` | — | Các chủ đề của nội dung. |
| `attributes_json` | `longtext` | Có | `NULL` | — | Thuộc tính biên tập và giá trị theo thang đo. |
| `ratings_json` | `longtext` | Có | `NULL` | — | Điểm và nguồn đánh giá trong gói danh mục. |
| `artworks_json` | `longtext` | Có | `NULL` | — | Ảnh minh họa với vai trò, đường dẫn và thông tin liên quan. |
| `credits_json` | `longtext` | Có | `NULL` | — | Thông tin người tham gia sản xuất và vai trò. |
| `record_json` | `longtext` | Có | `NULL` | — | Trạng thái, phiên bản và thông tin kiểm chứng của bản ghi. |
| `publication_status` | `varchar(16)` | Không | `draft` | `ck_catalog_episode_publication` | Trạng thái tập gồm draft, ready và archived. |
| `raw_json` | `longtext` | Có | `NULL` | — | Bản gốc của thực thể khi nhập, dùng để truy vết và xuất gói. |
| `revision` | `int` | Không | `1` | — | Phiên bản nội dung của bản ghi hoặc gói. |
| `opt_lock_version` | `bigint` | Có | `0` | — | Phiên bản số của hàng để kiểm tra cập nhật đồng thời. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- FK ghép `fk_episode_season_same_series` dùng `(series_id, season_id)`.
- `ck_catalog_episode_duration` kiểm tra `(duration_ms > 0)`.
- `ck_catalog_episode_kind` kiểm tra `(hex(kind) in (hex(_utf8mb4\'regular\'),hex(_utf8mb4\'special\'),hex(_utf8mb4\'ova\'),hex(_utf8mb4\'ona\'),hex(_utf8mb4\'recap\'),hex(_utf8mb4\'short\'),hex(_utf8mb4\'pilot\'),hex(_utf8mb4\'movie\'),hex(_utf8mb4\'unknown\')))`.
- `ck_catalog_episode_publication` kiểm tra `(hex(publication_status) in (hex(_utf8mb4\'draft\'),hex(_utf8mb4\'ready\'),hex(_utf8mb4\'archived\')))`.

## `catalog_segments`

Phân đoạn có thứ tự và mốc thời gian của tập.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `episode_id` | `varchar(100)` | Không | — | UNIQUE `uq_cat_segment_position`, FK `fk_segment_episode` tới `catalog_episodes(id)` khi xóa `CASCADE` | Mã tập được liên kết. |
| `position` | `int` | Không | — | UNIQUE `uq_cat_segment_position` | Vị trí của phân đoạn trong tập. |
| `title` | `varchar(255)` | Không | — | — | Tiêu đề của bản ghi. |
| `aliases_json` | `longtext` | Có | `NULL` | — | Tên khác và loại của tên khác. |
| `synopsis` | `longtext` | Có | `NULL` | — | Tóm tắt nội dung phim hoạt hình. |
| `translations_json` | `longtext` | Có | `NULL` | — | Các bản dịch tên, mô tả hoặc tóm tắt. |
| `primary_language` | `varchar(50)` | Có | `NULL` | — | Ngôn ngữ chính khai báo của nội dung. |
| `character_ids_json` | `longtext` | Có | `NULL` | — | Danh sách mã nhân vật của payload cũ. |
| `plot_facts_json` | `longtext` | Có | `NULL` | — | Chi tiết tình tiết và bằng chứng có cấu trúc. |
| `keywords_json` | `longtext` | Có | `NULL` | — | Từ khóa tìm kiếm của nội dung. |
| `themes_json` | `longtext` | Có | `NULL` | — | Các chủ đề của nội dung. |
| `attributes_json` | `longtext` | Có | `NULL` | — | Thuộc tính biên tập và giá trị theo thang đo. |
| `episode_start_ms` | `bigint` | Có | `NULL` | `ck_cat_segment_time_range` | Mốc đầu phân đoạn trong tập, tính theo mili giây. |
| `episode_end_ms` | `bigint` | Có | `NULL` | `ck_cat_segment_time_range` | Mốc cuối phân đoạn trong tập, tính theo mili giây. |
| `record_json` | `longtext` | Có | `NULL` | — | Trạng thái, phiên bản và thông tin kiểm chứng của bản ghi. |
| `raw_json` | `longtext` | Có | `NULL` | — | Bản gốc của thực thể khi nhập, dùng để truy vết và xuất gói. |
| `revision` | `int` | Không | `1` | — | Phiên bản nội dung của bản ghi hoặc gói. |
| `opt_lock_version` | `bigint` | Có | `0` | — | Phiên bản số của hàng để kiểm tra cập nhật đồng thời. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- UNIQUE `uq_cat_segment_position` gồm `(episode_id, position)`.
- `ck_cat_segment_time_range` kiểm tra `(((episode_start_ms is null) and (episode_end_ms is null)) or ((episode_start_ms is not null) and (episode_end_ms is not null) and (episode_start_ms >= 0) and (episode_end_ms > episode_start_ms)))`.

## `catalog_characters`

Hồ sơ nhân vật.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `series_ids_json` | `longtext` | Có | `NULL` | — | Danh sách mã bộ trong bản ghi nhân vật cũ. |
| `name` | `varchar(255)` | Không | — | — | Tên định danh hoặc tên hiển thị. |
| `aliases_json` | `longtext` | Có | `NULL` | — | Tên khác và loại của tên khác. |
| `description` | `longtext` | Có | `NULL` | — | Mô tả bằng văn bản. |
| `role` | `varchar(50)` | Có | `NULL` | — | Vai trò tự sự của nhân vật trong danh mục. |
| `traits_json` | `longtext` | Có | `NULL` | — | Đặc điểm nhân vật. |
| `relationships_json` | `longtext` | Có | `NULL` | — | Quan hệ nhân vật theo gói nhập. |
| `voice_credits_json` | `longtext` | Có | `NULL` | — | Thông tin diễn viên lồng tiếng trong gói. |
| `artworks_json` | `longtext` | Có | `NULL` | — | Ảnh minh họa với vai trò, đường dẫn và thông tin liên quan. |
| `record_json` | `longtext` | Có | `NULL` | — | Trạng thái, phiên bản và thông tin kiểm chứng của bản ghi. |
| `raw_json` | `longtext` | Có | `NULL` | — | Bản gốc của thực thể khi nhập, dùng để truy vết và xuất gói. |
| `revision` | `int` | Không | `1` | — | Phiên bản nội dung của bản ghi hoặc gói. |
| `opt_lock_version` | `bigint` | Có | `0` | — | Phiên bản số của hàng để kiểm tra cập nhật đồng thời. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

## `catalog_episode_characters`

Liên kết tập và nhân vật xuất hiện.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `episode_id` | `varchar(100)` | Không | — | PK, FK `catalog_episode_characters_ibfk_1` tới `catalog_episodes(id)` khi xóa `CASCADE` | Mã tập được liên kết. |
| `character_id` | `varchar(100)` | Không | — | PK, FK `catalog_episode_characters_ibfk_2` tới `catalog_characters(id)` khi xóa `CASCADE` | Mã hồ sơ nhân vật. |


## `catalog_episode_genres`

Liên kết tập và thể loại.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `episode_id` | `varchar(100)` | Không | — | PK, FK `catalog_episode_genres_ibfk_1` tới `catalog_episodes(id)` khi xóa `CASCADE` | Mã tập được liên kết. |
| `genre_id` | `varchar(100)` | Không | — | PK, FK `catalog_episode_genres_ibfk_2` tới `catalog_genres(id)` khi xóa `CASCADE` | Mã thể loại trong catalog. |


## `catalog_series_characters`

Liên kết bộ và nhân vật được giới thiệu ở cấp bộ.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `series_id` | `varchar(100)` | Không | — | PK, FK `fk_catalog_series_characters_series_id` tới `catalog_series(id)` khi xóa `CASCADE` | Mã bộ được liên kết. |
| `character_id` | `varchar(100)` | Không | — | PK, FK `fk_catalog_series_characters_character_id` tới `catalog_characters(id)` khi xóa `CASCADE` | Mã hồ sơ nhân vật. |


## `catalog_series_genres`

Liên kết bộ và thể loại.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `series_id` | `varchar(100)` | Không | — | PK, FK `fk_catalog_series_genres_series_id` tới `catalog_series(id)` khi xóa `CASCADE` | Mã bộ được liên kết. |
| `genre_id` | `varchar(100)` | Không | — | PK, FK `fk_catalog_series_genres_genre_id` tới `catalog_genres(id)` khi xóa `CASCADE` | Mã thể loại trong catalog. |


## `catalog_character_series`

Liên kết nhân vật và những bộ nhân vật xuất hiện.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `character_id` | `varchar(100)` | Không | — | PK, FK `fk_catalog_character_series_character_id` tới `catalog_characters(id)` khi xóa `CASCADE` | Mã hồ sơ nhân vật. |
| `series_id` | `varchar(100)` | Không | — | PK, FK `fk_catalog_character_series_series_id` tới `catalog_series(id)` khi xóa `CASCADE` | Mã bộ được liên kết. |


## `catalog_media_assets`

Nguồn video/audio, lưu trữ, quyền truy cập và phạm vi nội dung.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `content_type` | `varchar(50)` | Không | `video` | `ck_catalog_asset_content` | Loại nội dung video hoặc audio. |
| `role` | `varchar(50)` | Không | `feature` | `ck_catalog_asset_role` | Công dụng của tệp, như feature, trailer, dub hoặc audio_description. |
| `edition_label` | `varchar(100)` | Có | `NULL` | — | Tên bản phát hoặc phiên bản biên tập của tệp. |
| `spoken_languages_json` | `longtext` | Có | `NULL` | — | Ngôn ngữ được nói trong tệp. |
| `embedded_subtitle_languages_json` | `longtext` | Có | `NULL` | — | Ngôn ngữ phụ đề có sẵn trong tệp. |
| `storage_provider` | `varchar(50)` | Không | — | — | Nhà cung cấp hoặc loại kho lưu trữ. |
| `storage_key` | `varchar(100)` | Không | — | — | Mã cấu hình gốc lưu trữ chứa tệp. |
| `relative_path` | `varchar(500)` | Không | — | — | Đường dẫn tương đối tới tệp trong kho lưu trữ. |
| `drive_file_id` | `varchar(255)` | Có | `NULL` | — | Mã tệp ở Google Drive nếu lấy từ Drive. |
| `drive_folder_id` | `varchar(255)` | Có | `NULL` | — | Mã thư mục ở Google Drive nếu có. |
| `size_bytes` | `bigint` | Có | `NULL` | `ck_catalog_asset_size` | Kích thước tệp danh mục theo byte. |
| `sha256` | `varchar(100)` | Có | `NULL` | — | Dấu băm nội dung tệp dùng đối chiếu. |
| `duration_ms` | `bigint` | Có | `NULL` | `ck_catalog_asset_duration` | Thời lượng nội dung tính theo mili giây. |
| `technical_json` | `longtext` | Có | `NULL` | — | Thông số kỹ thuật của tệp. |
| `coverage_json` | `longtext` | Có | `NULL` | — | Phạm vi tập, phân đoạn và các mốc tệp bao phủ. |
| `related_asset_id` | `varchar(100)` | Có | `NULL` | FK `fk_asset_related` tới `catalog_media_assets(id)` khi xóa `SET NULL` | Tệp danh mục có liên quan, nếu có. |
| `access_policy` | `varchar(50)` | Không | `public` | `ck_catalog_asset_policy` | Mức truy cập tệp gồm private, authenticated và public. |
| `enabled` | `tinyint(1)` | Không | `1` | — | Tệp danh mục được bật để sử dụng. |
| `record_json` | `longtext` | Có | `NULL` | — | Trạng thái, phiên bản và thông tin kiểm chứng của bản ghi. |
| `raw_json` | `longtext` | Có | `NULL` | — | Bản gốc của thực thể khi nhập, dùng để truy vết và xuất gói. |
| `revision` | `int` | Không | `1` | — | Phiên bản nội dung của bản ghi hoặc gói. |
| `opt_lock_version` | `bigint` | Có | `0` | — | Phiên bản số của hàng để kiểm tra cập nhật đồng thời. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- `ck_catalog_asset_content` kiểm tra `(hex(content_type) in (hex(_utf8mb4\'video\'),hex(_utf8mb4\'audio\')))`.
- `ck_catalog_asset_duration` kiểm tra `(duration_ms > 0)`.
- `ck_catalog_asset_policy` kiểm tra `(hex(access_policy) in (hex(_utf8mb4\'private\'),hex(_utf8mb4\'authenticated\'),hex(_utf8mb4\'public\')))`.
- `ck_catalog_asset_role` kiểm tra `(hex(role) in (hex(_utf8mb4\'feature\'),hex(_utf8mb4\'trailer\'),hex(_utf8mb4\'extra\'),hex(_utf8mb4\'opening\'),hex(_utf8mb4\'ending\'),hex(_utf8mb4\'dub\'),hex(_utf8mb4\'audio_description\')))`.
- `ck_catalog_asset_size` kiểm tra `(size_bytes >= 0)`.

## `catalog_episode_assets`

Liên kết tập và các tệp chứa nội dung của tập.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `episode_id` | `varchar(100)` | Không | — | PK, FK `fk_cat_ep_asset_ep` tới `catalog_episodes(id)` khi xóa `CASCADE` | Mã tập được liên kết. |
| `media_asset_id` | `varchar(100)` | Không | — | PK, FK `fk_cat_ep_asset_media` tới `catalog_media_assets(id)` khi xóa `CASCADE` | Mã tệp danh mục liên kết. |


## `catalog_text_tracks`

Bản phụ đề, transcript hoặc OCR có nguồn xác định.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `media_asset_id` | `varchar(100)` | Có | `NULL` | FK `fk_text_track_asset` tới `catalog_media_assets(id)` khi xóa `CASCADE`, `ck_cat_text_track_origin` | Mã tệp danh mục liên kết. |
| `episode_id` | `varchar(100)` | Có | `NULL` | FK `fk_cat_track_episode` tới `catalog_episodes(id)` khi xóa `CASCADE`, `ck_cat_text_track_origin` | Mã tập được liên kết. |
| `source_id` | `varchar(100)` | Có | `NULL` | FK `fk_cat_track_source` tới `catalog_sources(id)` khi xóa `NO ACTION`, `ck_cat_text_track_origin` | Mã nguồn tạo track. |
| `language` | `varchar(50)` | Không | — | — | Mã ngôn ngữ của track. |
| `kind` | `varchar(50)` | Không | — | `ck_catalog_track_kind` | Kiểu track gồm subtitle, transcript và ocr. |
| `label` | `varchar(255)` | Có | `NULL` | — | Tiêu đề ngắn hiển thị cho track. |
| `format` | `varchar(50)` | Không | — | — | Định dạng dữ liệu track, thí dụ srt, vtt hoặc inline. |
| `is_default` | `tinyint(1)` | Không | `0` | — | Ưu tiên track này làm mặc định. |
| `external_file_json` | `longtext` | Có | `NULL` | — | Mã kho, đường dẫn tương đối và dấu băm của tệp phụ đề ngoài. |
| `cues_json` | `longtext` | Có | `NULL` | — | Các đoạn lời hoặc chữ và mốc thời gian. |
| `provenance_json` | `longtext` | Có | `NULL` | — | Nguồn chứng cứ và cách tạo bản ghi. |
| `record_json` | `longtext` | Có | `NULL` | — | Trạng thái, phiên bản và thông tin kiểm chứng của bản ghi. |
| `raw_json` | `longtext` | Có | `NULL` | — | Bản gốc của thực thể khi nhập, dùng để truy vết và xuất gói. |
| `revision` | `int` | Không | `1` | — | Phiên bản nội dung của bản ghi hoặc gói. |
| `opt_lock_version` | `bigint` | Có | `0` | — | Phiên bản số của hàng để kiểm tra cập nhật đồng thời. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- `ck_cat_text_track_origin` kiểm tra `((media_asset_id is not null) or ((episode_id is not null) and (source_id is not null)))`.
- `ck_catalog_track_kind` kiểm tra `(hex(kind) in (hex(_utf8mb4\'subtitle\'),hex(_utf8mb4\'transcript\'),hex(_utf8mb4\'ocr\')))`.

## `catalog_scenes`

Cảnh có thời điểm đầu/cuối, mô tả hoặc bằng chứng.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `varchar(100)` | Không | — | PK | Mã định danh của hàng trong bảng. |
| `media_asset_id` | `varchar(100)` | Có | `NULL` | FK `fk_scene_asset` tới `catalog_media_assets(id)` khi xóa `CASCADE` | Mã tệp danh mục liên kết. |
| `episode_id` | `varchar(100)` | Không | — | FK `fk_scene_episode` tới `catalog_episodes(id)` khi xóa `CASCADE` | Mã tập được liên kết. |
| `segment_id` | `varchar(100)` | Có | `NULL` | FK `fk_scene_segment` tới `catalog_segments(id)` khi xóa `SET NULL` | Mã phân đoạn của cảnh nếu đã gắn. |
| `start_ms` | `bigint` | Không | — | `ck_catalog_scene_time_range` | Mốc đầu của cảnh, tính theo mili giây. |
| `end_ms` | `bigint` | Không | — | `ck_catalog_scene_time_range` | Mốc cuối của cảnh, tính theo mili giây. |
| `title` | `varchar(255)` | Có | `NULL` | — | Tiêu đề của bản ghi. |
| `summary` | `longtext` | Có | `NULL` | — | Nội dung tóm tắt cảnh. |
| `visual_description` | `longtext` | Có | `NULL` | — | Mô tả hình ảnh hoặc hành động của cảnh. |
| `visual_tags_json` | `longtext` | Có | `NULL` | — | Nhãn mô tả đối tượng hoặc hoạt động nhìn thấy. |
| `sound_events_json` | `longtext` | Có | `NULL` | — | Các sự kiện âm thanh được ghi lại trong cảnh. |
| `transcript_cue_ids_json` | `longtext` | Có | `NULL` | — | Mã các mốc lời thoại được chứng thực ở cảnh. |
| `character_ids_json` | `longtext` | Có | `NULL` | — | Danh sách mã nhân vật của payload cũ. |
| `keywords_json` | `longtext` | Có | `NULL` | — | Từ khóa tìm kiếm của nội dung. |
| `themes_json` | `longtext` | Có | `NULL` | — | Các chủ đề của nội dung. |
| `attributes_json` | `longtext` | Có | `NULL` | — | Thuộc tính biên tập và giá trị theo thang đo. |
| `provenance_json` | `longtext` | Có | `NULL` | — | Nguồn chứng cứ và cách tạo bản ghi. |
| `record_json` | `longtext` | Có | `NULL` | — | Trạng thái, phiên bản và thông tin kiểm chứng của bản ghi. |
| `raw_json` | `longtext` | Có | `NULL` | — | Bản gốc của thực thể khi nhập, dùng để truy vết và xuất gói. |
| `revision` | `int` | Không | `1` | — | Phiên bản nội dung của bản ghi hoặc gói. |
| `opt_lock_version` | `bigint` | Có | `0` | — | Phiên bản số của hàng để kiểm tra cập nhật đồng thời. |
| `updated_at` | `timestamp` | Có | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- `ck_catalog_scene_time_range` kiểm tra `((start_ms >= 0) and (end_ms > start_ms))`.

## `watch_progress`

Vị trí tiếp tục xem và phiên bản cập nhật của người dùng cho một tập.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `bigint` | Không | `AUTO_INCREMENT` | PK | Mã định danh của hàng trong bảng. |
| `user_id` | `bigint` | Không | — | UNIQUE `uq_watch_progress_user_episode`, FK `fk_watch_progress_user` tới `users(id)` khi xóa `CASCADE` | Mã tài khoản của thao tác. |
| `episode_id` | `varchar(100)` | Không | — | UNIQUE `uq_watch_progress_user_episode`, FK `fk_watch_progress_episode` tới `catalog_episodes(id)` khi xóa `CASCADE` | Mã tập được liên kết. |
| `asset_id` | `varchar(100)` | Không | — | FK `fk_watch_progress_asset` tới `catalog_media_assets(id)` khi xóa `CASCADE` | Mã tệp danh mục dùng khi lưu tiến độ. |
| `position_ms` | `bigint` | Không | — | `ck_watch_progress_position` | Vị trí tiếp tục xem tính theo mili giây. |
| `opt_lock_version` | `bigint` | Không | `0` | — | Phiên bản số của hàng để kiểm tra cập nhật đồng thời. |
| `updated_at` | `timestamp` | Không | `CURRENT_TIMESTAMP` và `ON UPDATE CURRENT_TIMESTAMP` | — | Thời điểm bản ghi được cập nhật. |

- UNIQUE `uq_watch_progress_user_episode` gồm `(user_id, episode_id)`.
- `ck_watch_progress_position` kiểm tra `(position_ms >= 0)`.

## `audit_log`

Ảnh chụp thay đổi của tập được ghi bởi trigger MySQL.

| Cột | Kiểu MySQL | NULL | Mặc định hoặc tự động | Khóa và CHECK | Ý nghĩa |
| --- | --- | --- | --- | --- | --- |
| `id` | `bigint` | Không | `AUTO_INCREMENT` | PK | Mã định danh của hàng trong bảng. |
| `table_name` | `varchar(64)` | Không | — | — | Tên bảng đã phát sinh thay đổi. |
| `record_id` | `varchar(100)` | Không | — | — | Mã hàng được ghi vết. |
| `operation` | `varchar(8)` | Không | — | — | Loại thao tác ghi vết, UPDATE hoặc DELETE. |
| `old_values` | `json` | Không | — | — | Ảnh chụp các cột của tập trước UPDATE hoặc DELETE. |
| `new_values` | `json` | Có | `NULL` | — | Ảnh chụp các cột của tập sau UPDATE. Xóa thì để trống. |
| `action_at` | `timestamp` | Không | `CURRENT_TIMESTAMP` | — | Thời điểm trigger ghi thay đổi. |
| `mysql_user` | `varchar(288)` | Không | — | — | Tài khoản MySQL và host của phiên thực hiện thao tác. |
