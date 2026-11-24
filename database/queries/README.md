# Truy vấn và phép đo MySQL

Chạy `sample_queries.sql` sau khi nạp `database/objects`. Bảng dưới đánh số theo thứ tự câu SQL. Số dòng và mẫu trích từ bộ dữ liệu của phép đo. Các truy vấn có LIMIT ghi số dòng thực trả về.

| # | Nghiệp vụ | Cách truy vấn | Kết quả mẫu |
| ---: | --- | --- | --- |
| 1 | Tập và nhân vật | Nối bộ, mùa, tập, bảng nối và hồ sơ nhân vật. | 50 dòng. Mẫu `series_title=Ấu trùng tinh nghịch (Larva)`, `episode_title=Kem`, `character_name=Red`. |
| 2 | Bộ có ít nhất 20 tập sẵn sàng | GROUP BY/HAVING đếm tập và cộng thời lượng. | 27 dòng. Mẫu `title=Pokémon`, `ready_episodes=479`, `total_hours=172.3`. |
| 3 | Tập dài hơn mức trung bình của bộ | CTE tính trung bình một lần cho mỗi bộ. | 50 dòng. Mẫu `title=Tàu Vũ Trụ Bằng Thùng Giấy Của Nobita, Hoa Lãng Quên`, `duration_ms=1733000`, `series_id=ser_doraemon`. |
| 4 | Tập thiếu video chính công khai | NOT EXISTS kiểm tra tệp video chính đang bật. | 50 dòng. Mẫu `id=ep_doraemon_s05_0209`, `title=Cuộc Chiến Của tay Vua Súng, Kem Người Sói`. |
| 5 | Người dùng chấm cao và có yêu thích | Hai EXISTS và truy vấn con tương quan tìm điểm cao nhất. | 1 dòng. Mẫu `username=demo_query`, `highest_rating=9`. |
| 6 | Xếp hạng thời lượng | RANK chia nhóm theo bộ và giữ đồng hạng. | 100 dòng. Mẫu `title=Tàu Vũ Trụ Bằng Thùng Giấy Của Nobita, Hoa Lãng Quên`, `duration_ms=1733000`, `duration_rank=1`. |
| 7 | Tập lưu ngay trước đó | LAG tìm số của bản lưu trước trong cùng bộ và tài khoản. | 3 dòng. Mẫu `user_id=1`, `id=ep_jadoo_s01_0001`, `previous_episode_number=NULL`. |
| 8 | Cơ cấu thể loại | CTE và SUM OVER tính tỷ trọng theo lượt gán thể loại. | 3 dòng. Mẫu `genre_id=animation`, `episode_count=2451`, `share_pct=51.97`. |
| 9 | Phân bố thời lượng dưới 60 phút | CTE đệ quy tạo 12 nhóm 5 phút, gồm cả nhóm trống. | 12 dòng. Mẫu `bucket_start=0`, `bucket_end=5`, `episode_count=160`. |
| 10 | Tủ phim hợp nhất | UNION gộp xem sau và yêu thích theo người dùng–phim. | 2 dòng. Mẫu `user_id=1`, `movie_id=afterlight`, `title=Afterlight`. |
| 11 | Phim được chấm cao | Dùng view điểm và hàm fn_movie_avg_rating. | 1 dòng. Mẫu `movie_title=The Last Orbit`, `rating_count=1`, `average_rating=9.00`. |
| 12 | Nhân vật xuất hiện nhiều | Đếm số bộ và số tập sẵn sàng của mỗi nhân vật. | 20 dòng. Mẫu `name=Ash Ketchum`, `series_count=1`, `episode_count=417`. |
| 13 | Tập phát hành gần đây | Sắp theo ngày phát hành và mã tập, lấy tối đa 20 dòng. | 20 dòng. Mẫu `title=ＥＮＤＯＦＴＨＥＰＲＯＬＯＧＵＥ`, `release_date=2019-12-29`, `series_title=Vinland Saga`. |
| 14 | Khối lượng biên tập từng bộ | Nhóm theo bộ và trạng thái, xếp theo số tập nháp. | 20 dòng. Mẫu `title=親子クラブ`, `episode_count=1323`, `draft_count=1323`, `ready_count=0`, `archived_count=0`. |
| 15 | Tệp bao phủ nhiều tập | HAVING lọc các tệp được nối với hơn một tập. | 0 dòng. Cột trả về `asset_id`, `role`, `episode_count`. |
| 16 | Tập thiếu phụ đề hoặc transcript | Hai NOT EXISTS kiểm tra track trực tiếp và track qua tệp. | 50 dòng. Mẫu `episode_id=ep_doraemon_s06_0271`, `episode_title=Hãy Cẩn Thận Khi Mua Đồ Ở Tương Lai, Doraemon Bị Bệnh Nặng`. |
| 17 | Cộng vị trí đã lưu | SUM OVER cộng vị trí tiếp tục xem, tính theo mili giây. | 3 dòng. Mẫu `user_id=1`, `position_ms=1000`, `cumulative_positions_ms=1000`. |
| 18 | Số tập và số giờ theo thể loại | Dùng v_genre_stats, tính các tập sẵn sàng. | 3 dòng. Mẫu `genre_id=animation`, `episode_count=2451`, `total_hours=907.28`. |
| 19 | Độ phủ cảnh đã ghi | Đếm cảnh và tổng độ dài các khoảng cảnh theo tập. | 0 dòng. Cột trả về `episode_id`, `episode_title`, `scene_count`, `scene_intervals_ms`. |
| 20 | Lịch sử sửa và xóa tập | Đọc audit và lấy trạng thái cũ/mới từ JSON. | 20 dòng. Mẫu `record_id=ep_madb_m99334`, `operation=DELETE`, `old_status=draft`, `new_status=NULL`. |

Truy vấn 8 tính tỷ trọng trên lượt gán. Một tập có nhiều thể loại có thể xuất hiện ở nhiều nhóm. Truy vấn 17 cộng các vị trí lưu cho từng tập để minh họa window function. Truy vấn 19 cộng độ dài các khoảng cảnh nên hai khoảng chồng nhau đều đóng góp vào tổng.

## Đo trên 100.000 tập

Chạy MySQL 8.0.46 cục bộ, InnoDB. Khôi phục bản dump danh mục 100.617 tập của dự án vào schema thử, chạy migration 07–09 và bỏ 617 tập nháp trên bản sao. Bộ đo có đúng **100.000 tập**, gồm **2.451 sẵn sàng** và **97.549 nháp**. Nạp thêm seed phim và một tài khoản mẫu có đánh giá, xem sau, yêu thích và ba điểm tiếp tục xem. Các hàng audit mẫu phát sinh khi thu gọn bản sao.

Đo cả 20 câu trước khi tối ưu và chọn năm câu có trung vị lớn nhất. Cập nhật thống kê bằng `ANALYZE TABLE` trước mỗi đợt đo, làm nóng một lượt, rồi đo năm lượt `EXPLAIN ANALYZE` cho từng câu. Bảng lấy mốc hoàn thành của nút gốc trong `actual time`, theo mili giây. SHA-256 của các hàng theo đúng thứ tự trả về khớp ở cả năm câu trước và sau. [Cách đọc EXPLAIN ANALYZE](https://dev.mysql.com/doc/refman/8.0/en/explain.html)

| # | Trước (ms) | Sau (ms) | Nhanh hơn | Hàng trả về | Thay đổi trong kế hoạch |
| ---: | ---: | ---: | ---: | ---: | --- |
| 14 | 2,230.00 | 39.80 | 56.0× | 20 | Đọc index phủ cho 100.000 tập. Nối tên của 20 bộ sau tổng hợp. |
| 18 | 1,788.00 | 13.20 | 135.5× | 3 | Tổng hợp từ tập sẵn sàng trước. Bản cũ xét 102.267 lượt nối thể loại và tập. |
| 3 | 1,626.00 | 18.00 | 90.3× | 50 | Tính trung bình cho 40 bộ bằng một CTE, giảm từ 2.451 lượt gọi truy vấn con. |
| 9 | 104.00 | 1.20 | 86.7× | 12 | Gom mỗi tập vào một nhóm thời lượng. Bản cũ tra tập sẵn sàng 12 lượt. |
| 12 | 77.10 | 28.80 | 2.7× | 20 | Tổng hợp theo mã nhân vật trước, rồi nối tên cho 20 kết quả. |

Để đối chiếu, `benchmark_baseline.sql` giữ bản trước tối ưu của các câu 3, 9, 12, 14, 18 theo thứ tự đó. Dùng schema và view ở commit giai đoạn C `b4cc169` cho lần đo trước. Trên cùng dữ liệu, chạy migration 10, nạp lại `views.sql`, cập nhật thống kê rồi đo các câu tương ứng trong `sample_queries.sql`. Thay đổi tỷ lệ tập nháp hoặc bộ nhớ đệm có thể làm thời gian khác đi.

## Chỉ mục

| Thay đổi | Lý do |
| --- | --- |
| Thêm `idx_cat_ep_status_series_duration` | Phủ lọc theo trạng thái và tổng hợp theo bộ/thời lượng. Kế hoạch đọc trực tiếp index cho trung bình và phân bố thời lượng. |
| Bỏ `idx_watchlist_user`, `idx_favorite_user`, `idx_ratings_user` | Cột `user_id` đứng đầu các khóa UNIQUE `(user_id, movie_id)` tương ứng. Khóa ngoại và tra cứu theo người dùng dùng được tiền tố này. |
| Bỏ `idx_media_movie_id` và `idx_media_movie_kind` | `(movie_id)` và `(movie_id, kind)` là tiền tố của `uq_movie_kind_version (movie_id, kind, version)`. |

Giữ `idx_cat_ep_publication` cho đường lọc trạng thái và mã tập. Kế hoạch truy vấn 3 sau tối ưu vẫn dùng nó để nạp hàng kết quả. Kiểm thử đối chiếu index giữa SQL khởi tạo, SQLAlchemy và schema đã chạy migration 10 hai lần. [Tiền tố của chỉ mục nhiều cột](https://dev.mysql.com/doc/refman/8.0/en/multiple-column-indexes.html)
