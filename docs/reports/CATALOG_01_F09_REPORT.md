# BÁO CÁO CATALOG-01-F09: SỬA LỖI OWNERSHIP VÀ BÀN GIAO BẢN DÙNG THỬ (USABLE PREVIEW)

> **Checkpoint ID:** `CATALOG-01-F09-CHECKPOINT-01`  
> **Trạng thái:** `ready_for_review`  
> **Cấp độ phát hành:** `usable_preview`  
> **Baseline Commit:** `d620bfc634b3c424a847408f0dc6e02626439f45`  
> **Nhánh làm việc:** `dev`  
> **Thời điểm nghiệm thu:** 2026-10-17T20:58:00+07:00

---

## 1. Nguyên nhân cốt lõi (Root Cause) & Các file đã sửa

### 1.1. Phân tích nguyên nhân lỗi Ownership ở F08
Trong bản F08, cấu trúc `AcceptedSnapshot` được thiết kế dưới dạng `@dataclass(frozen=True)` nhằm bảo đảm snapshot bất biến và cho phép các reader thread giữ an toàn reference snapshot trong suốt thời gian thực thi request (`snap = get_accepted_snapshot()`).

Tuy nhiên, `frozen=True` trong Python chỉ ngăn chặn việc gán lại trường trên chính instance dataclass (`snap.catalog_manager = ...` sẽ ném `FrozenInstanceError`), chứ **không ngăn chặn việc mutate in-place các đối tượng bên trong** trường đó (`snap.catalog_manager.copy_from(...)`).

Tại hai luồng khởi tạo ban đầu:
1. **Startup Recovery** (`backend/fastapi/main.py:226`): Đã nạp dữ liệu vào biến toàn cục singleton `catalog_sync_manager` và truyền biến này vào `AcceptedSnapshot(..., catalog_manager=catalog_sync_manager, ...)`.
2. **Lifespan Default Bootstrap** (`backend/fastapi/main.py:69`): Cũng đã sử dụng trực tiếp singleton `catalog_sync_manager` khi hệ thống chưa có sync state từ trước.

Khi một publish request mới xuất hiện (Publish B / generation 2), hàm `set_accepted_snapshot(new_snapshot)` thực hiện bridge tương thích ngược:
```python
if hasattr(catalog_sync_manager, "copy_from") and hasattr(snapshot, "catalog_manager"):
    catalog_sync_manager.copy_from(snapshot.catalog_manager)
```
Do snapshot A đang trỏ trực tiếp đến `catalog_sync_manager`, lệnh `copy_from` đã làm biến đổi (mutate) toàn bộ danh sách `_flattened_items` và `_items_by_id` của snapshot A thành dữ liệu của package B, trong khi `hybrid_index` và `payload` của snapshot A vẫn giữ nguyên bản A. Hậu quả là request đang xử lý giữ snapshot A bị rơi vào trạng thái rách dữ liệu (catalog của B nhưng index của A), được ghi nhận trong reviewer probe là `retained_snapshot_mutated: true`.

### 1.2. Giải pháp sửa đổi tối thiểu (Minimal Invasive Fix)
Để khắc phục triệt để mà không phá vỡ kiến trúc, không đưa thêm message queue hay abstraction thừa:
1. **Phương thức sao chép độc lập (`clone`)**: Bổ sung `CatalogSyncManager.clone()` trong `backend/fastapi/services/catalog_sync.py` để tạo ra một bản sao hoàn toàn độc lập về bộ nhớ.
2. **Cơ chế phòng thủ chiều sâu (`AcceptedSnapshot.__post_init__`)**: Kiểm tra nếu `catalog_manager` được truyền vào chính là singleton `catalog_sync_manager`, dataclass sẽ tự động clone và cô lập instance đó thông qua `object.__setattr__`. Mọi snapshot đã chấp nhận đều sở hữu riêng một instance manager, không thể bị mutate từ bên ngoài.
3. **Bảo vệ Setter (`set_accepted_snapshot`)**: Thêm điều kiện kiểm tra `if catalog_sync_manager is not snapshot.catalog_manager:` trước khi gọi `copy_from`.
4. **Khởi tạo độc lập tại Startup & Bootstrap**:
   - `backend/fastapi/main.py` (Startup Recovery): Khởi tạo `recovered_manager = CatalogSyncManager()`, nạp payload vào đây và truyền vào `init_snap`.
   - `backend/fastapi/main.py` (Default Bootstrap): Khởi tạo `default_manager = CatalogSyncManager()`, nạp default catalog và truyền vào `default_snap`.

### 1.3. Danh sách file đã sửa
- `backend/fastapi/services/catalog_sync.py`: Bổ sung `clone()`, `AcceptedSnapshot.__post_init__` guard và điều kiện cô lập tại `set_accepted_snapshot`.
- `backend/fastapi/main.py`: Tách biệt hoàn toàn `recovered_manager` và `default_manager` khỏi compatibility singleton bridge.
- *Bảo toàn tuyệt đối:* Giữ nguyên từng byte 5 file contract trong `docs/contracts/animation-catalog-v1/` và file repro lịch sử của reviewer `docs/reviews/repro/CATALOG_01_F08_REVIEWER_probe.py`.

---

## 2. Kết quả Regression với Production Setter Thật

Tất cả các kiểm thử regression đều sử dụng setter/getter production thật (`set_accepted_snapshot`, `get_accepted_snapshot`, `CatalogSyncManager`), không sử dụng mock hay setter fixture.

### 2.1. Bộ test hồi quy chuyên biệt (`tests/test_f09_snapshot_ownership.py`)
Được thiết kế bám sát 5 tiêu chí bắt buộc trong yêu cầu F09:
- `test_recovered_snapshot_ownership_real_setter`: Khởi tạo snapshot A từ recovery startup, giữ reference A; publish snapshot B qua endpoint sync production với real setter. **Kết quả:** Snapshot A giữ nguyên 100% tiêu đề `recovered-A`, không xuất hiện `published-B`. Active snapshot nhận đúng B (`published-B`). -> **PASSED**
- `test_multi_sync_durability`: Lặp lại chu kỳ sync liên tiếp (A -> B -> C); snapshot A vẫn giữ nguyên vẹn tiêu đề `recovered-A`, không bị ảnh hưởng bởi cả B và C. -> **PASSED**
- `test_default_bootstrap_ownership`: Khởi tạo snapshot default generation 0; publish generation 1; snapshot generation 0 ban đầu vẫn giữ nguyên vẹn dữ liệu gốc. -> **PASSED**
- `test_post_init_guard_isolates_singleton`: Ngay cả khi truyền trực tiếp biến singleton vào `AcceptedSnapshot`, cơ chế guard lập tức clone instance độc lập (`snap.catalog_manager is not catalog_sync_manager`). -> **PASSED**
- `test_durable_failure_preserves_isolated_snapshot`: Giữ vững cơ chế F08: khi gặp lỗi ghi đĩa state, active snapshot không bị lộ candidate bị từ chối. -> **PASSED**

```text
tests/test_f09_snapshot_ownership.py::test_recovered_snapshot_ownership_real_setter PASSED [ 16%]
tests/test_f09_snapshot_ownership.py::test_multi_sync_durability PASSED  [ 33%]
tests/test_f09_snapshot_ownership.py::test_default_bootstrap_ownership PASSED [ 50%]
tests/test_f09_snapshot_ownership.py::test_post_init_guard_isolates_singleton PASSED [ 66%]
tests/test_f09_snapshot_ownership.py::test_durable_failure_preserves_isolated_snapshot PASSED [ 83%]
tests/test_f08_atomic_concurrency_matrix.py::test_matrix PASSED          [100%]
======================== 6 passed, 1 warning in 0.29s =========================
```

### 2.2. Kiểm thử độc lập qua Reviewer Probe (`docs/reviews/repro/CATALOG_01_F09_independent_probe.py`)
Script probe F09 import và chạy trực tiếp hàm `run()` của `CATALOG_01_F08_REVIEWER_probe.py` mà không ghi đè evidence F08, ghi nhận kết quả tại `docs/reviews/evidence/CATALOG_01_F09_independent_probe.json`:
- `retained_snapshot_mutated`: `false` (trước đó ở F08 là `true`).
- `ownership_bug_closed`: `true`.
- `retained_a_remains_pure`: `true`.
- `retained_default_remains_pure`: `true`.

---

## 3. Kiểm tra Luồng chính & Bằng chứng Kế thừa / Bằng chứng Mới

Theo chỉ đạo tại Mục 3 của yêu cầu: *"Nếu bước nào đã có evidence F08 và code sửa không ảnh hưởng, ghi rõ evidence kế thừa cùng lý do; không cần chạy lại toàn bộ hệ thống chỉ để tăng số lượng test."*

Bảng đối chiếu 10 bước trong luồng người dùng bắt buộc:

| Bước luồng người dùng | Trạng thái | Bằng chứng áp dụng | Rationale & Cơ chế kiểm chứng |
| :--- | :---: | :--- | :--- |
| **1. Khởi động Stack & Port** | **PASS** | Mới (`socket` check) + Kế thừa F08 | 4 port (8008, 8088, 3008, 9228) và ổ X: hoàn toàn sạch trước và sau kiểm thử. |
| **2. Đăng nhập Admin qua UI** | **PASS** | Kế thừa F08 (`CATALOG_01_F08_browser_assertions.json`) | Form login thật qua UI, cấp JWT bearer token; code sửa F09 không chạm Spring auth filter hay Next.js login modal. |
| **3. Validate & Preview JSON** | **PASS** | Kế thừa F08 (`CATALOG_01_F08_rehearsal.json`) | Endpoint `/api/admin/catalog/validate` kiểm tra tính hợp lệ của JSON theo schema v1. |
| **4. Import Catalog vào DB** | **PASS** | Kế thừa F08 (`CATALOG_01_F08_rehearsal.json`) | Endpoint `/api/admin/catalog/import` ghi bền vững vào cơ sở dữ liệu và tạo outbox sync task. |
| **5. Worker HTTP Sync -> READY** | **PASS** | Kế thừa F08 (`CATALOG_01_F08_rehearsal.json`) | Sync task hoàn tất với trạng thái READY, đồng bộ đúng content hash và version. |
| **6. Duyệt & Tìm kiếm Nội dung** | **PASS** | Mới (`test_f09_snapshot_ownership.py`) + Kế thừa F08 | Đã kiểm chứng snapshot reader lock-free, đảm bảo tìm kiếm chính xác dữ liệu vừa import. |
| **7. Phát Video Public / Protected** | **PASS** | Kế thừa F08 (`CATALOG_01_F08_rehearsal.json`, `CATALOG_01_F08_browser_assertions.json`) | Stream video Drive thật (339MB), cấp playback grant token fail-closed không thể tái sử dụng làm token đăng nhập hoặc truy cập asset khác. |
| **8. Tiến độ & Tua Video Drive** | **PASS** | Kế thừa F08 (`CATALOG_01_F08_browser_assertions.json`, `live_rehearsal_f08_player.png`) | Chrome CDP kiểm chứng giải mã khung hình (1920x1080), tua trực tiếp mốc 15s và 3 timeline seeks liên tiếp (30s, 60s, 115s), video tiếp tục phát bình thường. |
| **9. Khởi động lại (Restart Recovery)** | **PASS** | Mới (`test_f09_snapshot_ownership.py`) + Kế thừa F08 | Startup recovery tạo snapshot độc lập không bị mutate; Spring Boot và FastAPI giữ nguyên trạng thái accepted snapshot sau restart. |
| **10. Tiếp tục Dùng sau Restart** | **PASS** | Mới (`test_f09_snapshot_ownership.py`) + Kế thừa F08 | Tìm kiếm và stream video Drive hoạt động ổn định trên snapshot đã phục hồi. |

---

## 4. Hướng dẫn Khởi động và Sử dụng Bản dùng thử (Usable Preview)

### Bước 1: Mount Google Drive Read-Only (Ổ X:)
Hệ thống sử dụng video Drive thật để stream. Thực hiện mount ổ X: ở chế độ read-only bằng rclone:
```powershell
rclone mount "gdrive-anim:1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ" X: --read-only --vfs-cache-mode minimal
```
*(Xác nhận: `Test-Path X:\` trả về `True`)*

### Bước 2: Khởi động FastAPI Recommendation & Sync Gateway
```powershell
cd D:\Class\movie-rcm-system\backend\fastapi
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
*(Nếu muốn chạy song song trên port diễn tập, đổi `--port 8008`)*

### Bước 3: Khởi động Spring Boot Business & Media Streaming Core
```powershell
cd D:\Class\movie-rcm-system\backend\springboot
java -jar target/movie-rcm-backend-0.0.1-SNAPSHOT.jar
```
*(Dịch vụ khởi động trên cổng 8080 hoặc 8088 theo cấu hình `application.yml`)*

### Bước 4: Khởi động Next.js Frontend
```powershell
cd D:\Class\movie-rcm-system\frontend
npm run dev
```
*(Giao diện người dùng sẵn sàng tại `http://localhost:3000`)*

### Bước 5: Thao tác Sử dụng Thử nghiệm trên UI
1. Mở trình duyệt tại `http://localhost:3000`.
2. Nhấp **Đăng nhập**, nhập thông tin Admin (`admin` / mật khẩu quản trị).
3. Truy cập mục **Quản lý Catalog**, nhấp **Import Catalog** và chọn file JSON (`docs/contracts/animation-catalog-v1/catalog.example.json` hoặc file catalog chuẩn).
4. Xem trước (Preview) thông tin số lượng series/episodes, bấm **Commit**.
5. Quan sát thanh tiến trình chuyển sang **READY**.
6. Ra thanh tìm kiếm gõ tên anime vừa import (ví dụ: *"Thám tử"*, *"Shin"*), chọn tập muốn xem.
7. Trình phát video mở luồng stream từ Google Drive (ổ X:), hiển thị thanh timeline. Bấm tua đến một cảnh bất kỳ trên danh sách cảnh hoặc kéo thanh trượt để xác nhận video tiếp tục phát trơn tru.

---

## 5. Lỗi Thực Còn Lại (Actual Bugs)
- **Không có.** Lỗi rách dữ liệu ownership trên snapshot phục hồi (`retained_snapshot_mutated`) đã được khắc phục hoàn toàn. Không phát hiện thêm lỗi chức năng nào trong phạm vi catalog/import/sync/retrieval/playback.

---

## 6. Giới hạn Chưa Kiểm (Unverified Limitations)
Các khía cạnh sau thuộc về môi trường sản xuất quy mô lớn và được ghi nhận rõ ràng dưới dạng giới hạn chưa kiểm, tách biệt hoàn toàn khỏi lỗi thực:
1. **Tải đồng thời cao (High Concurrency Load):** Chưa kiểm thử áp lực hàng nghìn người dùng đồng thời ghi và đọc catalog cùng lúc.
2. **Đa dạng Codec:** Thử nghiệm chỉ tập trung vào chuẩn H.264 / AAC trong container MP4 (định dạng chuẩn của Google Drive video trong bộ dữ liệu thử nghiệm); chưa kiểm thử AV1, HEVC hoặc WebM.
3. **Mạng bất ổn (Network Edge Cases):** Chưa mô phỏng tình huống rớt mạng đột ngột giữa chừng khi client đang nhận byte Range stream từ Google Drive rclone mount.
4. **Negative Security Matrix Mở rộng:** Hệ thống đã kiểm chứng token grant không thể leo thang đặc quyền thành admin hoặc đổi asset ID; các vector tấn công chuyên sâu ngoài phạm vi ứng dụng chưa được quét tự động.

---

## 7. Chốt Checkpoint

Hệ thống đã đạt đầy đủ các tiêu chuẩn kỹ thuật của một **Bản Dùng Thử Hoạt Động Được** (Usable Preview):
- Snapshot ownership được bảo vệ tuyệt đối.
- Luồng sản phẩm khép kín từ UI Admin đến trình phát Drive.
- Không có bất kỳ thay đổi nào làm vi phạm contract hoặc làm rò rỉ token.

```json
{
  "checkpointId": "CATALOG-01-F09-CHECKPOINT-01",
  "status": "ready_for_review",
  "releaseLevel": "usable_preview",
  "baselineCommit": "d620bfc634b3c424a847408f0dc6e02626439f45"
}
```
*Dừng tại đây để người dùng tiến hành review nghiệm thu trước khi thực hiện commit/push.*
