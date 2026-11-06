# Hướng dẫn Chuẩn hóa và Nhập Metadata Phim Canonical (REC-01)

Tài liệu hướng dẫn quản trị viên và người biên tập chuẩn bị, kiểm tra và nhập siêu dữ liệu phim hoạt hình cho hệ thống Dippie Cinema.

---

## 1. Nguyên tắc cốt lõi về dữ liệu

1. **Không bịa đặt dữ liệu (No Fabrication):**
   - Nếu phim chưa có đánh giá hoặc chưa rõ thời lượng, trường `rating` hoặc `runtime_minutes` phải để `null`.
   - Tuyệt đối **không** tự ý điền số 0 (như `rating: 0` hay `darkness: 0.0`) cho dữ liệu chưa biết, vì số 0 là một giá trị định lượng có ý nghĩa thực tế (ví dụ: `darkness: 0.0` nghĩa là phim cực kỳ tươi sáng/hồn nhiên).
2. **Tách biệt siêu dữ liệu phim và tài sản phát (Media Asset Decoupling):**
   - Thông tin nghệ thuật của phim (tiêu đề, tóm tắt, nhân vật, chủ đề) hoàn toàn độc lập với tệp video vật lý.
   - Trường `media_assets` liệt kê các tệp video/trailer và nguồn lưu trữ (`local`, `google_drive`, `remote_url`). Trình nhập không mở hay giải mã video chỉ để kiểm tra metadata.
3. **Minh bạch về độ tin cậy (Provenance & Verification):**
   - Mỗi bộ phim phải có trường `provenance.verification_status` với một trong ba trạng thái:
     - `human_verified`: Do biên tập viên/chuyên gia điện ảnh kiểm chứng từ tài liệu chính thống.
     - `inferred`: Do mô hình AI trích xuất tự động (kèm `model_id`).
     - `draft`: Bản nháp chưa qua hậu kiểm.
   - Các tình tiết cốt truyện (`plot_facts`) ở trạng thái `draft` sẽ không được trình bày cho người dùng như sự thật đã xác minh.

---

## 2. Thang đo Thuộc tính So sánh (Comparative Attributes Scale)

Phục vụ cho các truy vấn so sánh điện ảnh phức tạp (ví dụ: *"giống Spirited Away nhưng bớt u tối hơn và nhịp phim nhanh hơn"*), hệ thống quy chuẩn thang đo phiên bản `v1.0-normalized-0-1`:

| Thuộc tính | Thang đo | Ý nghĩa 0.0 | Ý nghĩa 1.0 | Ví dụ tham chiếu |
| :--- | :---: | :--- | :--- | :--- |
| **`darkness`** | `0.0` – `1.0` | Tươi sáng, hài hước, thế giới trẻ thơ trong trẻo | Đen tối, kinh dị tâm lý, nỗi sợ hiện sinh, bi kịch | *Fantasia* (0.15) $\leftrightarrow$ *Coraline* (0.85) |
| **`pacing`** | `0.0` – `1.0` | Chậm rãi, chiêm nghiệm, nhịp điệu tĩnh lặng | Dồn dập, hành động liên tục, tiết tấu dồn dập | *Spirited Away* (0.45) $\leftrightarrow$ *Spider-Verse* (0.90) |

> [!IMPORTANT]
> Chỉ thực hiện phép so sánh tương đối khi **cả phim tham chiếu và phim ứng viên** đều có dữ liệu thuộc tính đáng tin cậy. Nếu một trong hai bên thiếu dữ liệu, hệ thống bắt buộc phải giải thích trung thực rằng *"chưa đủ dữ liệu để xác nhận điều kiện so sánh"*.

---

## 3. Cấu trúc tệp mẫu

- **JSON Schema:** [`docs/contracts/canonical_movie_schema.v1.json`](file:///d:/Class/movie-rcm-system/docs/contracts/canonical_movie_schema.v1.json)
- **Tệp mẫu hợp lệ (Valid Sample):** [`docs/contracts/canonical_catalog_sample.valid.json`](file:///d:/Class/movie-rcm-system/docs/contracts/canonical_catalog_sample.valid.json)
- **Tệp mẫu vi phạm (Invalid Sample):** [`docs/contracts/canonical_catalog_sample.invalid.json`](file:///d:/Class/movie-rcm-system/docs/contracts/canonical_catalog_sample.invalid.json)

---

## 4. Hướng dẫn sử dụng công cụ kiểm tra và nhập (Importer CLI)

Công cụ `scripts/import_canonical_metadata.py` hỗ trợ cả chế độ chạy thử nghiệm (dry-run) và nhập thực tế vào database snapshot cô lập:

### Chế độ kiểm tra tính hợp lệ (Dry-run mode, không ghi database):
```powershell
& "C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe" scripts/import_canonical_metadata.py `
    --input docs/contracts/canonical_catalog_sample.valid.json `
    --dry-run
```

### Chế độ nhập dữ liệu vào Snapshot DB:
```powershell
& "C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe" scripts/import_canonical_metadata.py `
    --input docs/contracts/canonical_catalog_sample.valid.json `
    --db-target snapshot `
    --build-index
```
Các tham số:
- `--input <path>`: Đường dẫn tệp JSON chuẩn hóa.
- `--dry-run`: Chỉ xác thực schema và logic, không ghi cơ sở dữ liệu.
- `--db-target <snapshot|dev>`: Chỉ định database đích (mặc định là `snapshot`, tuyệt đối không ghi đè DB live).
- `--build-index`: Tự động tái tạo chỉ mục tìm kiếm Hybrid (BM25 + Dense Vectors) ngay sau khi nhập.
