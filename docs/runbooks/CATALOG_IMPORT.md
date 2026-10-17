# SỔ TAY VẬN HÀNH: NHẬP DỮ LIỆU HOẠT HÌNH JSON (dippie.catalog.v1)

Tài liệu này hướng dẫn đầy đủ quy trình xác thực, nhập dữ liệu, lưu trữ bền vững trong cơ sở dữ liệu, hiển thị trên giao diện web, phát video Google Drive và tích hợp tìm kiếm thông minh/CineBot cho hệ thống Dippie Cinema.

---

## 1. Hợp đồng dữ liệu `dippie.catalog.v1`

Tất cả các gói dữ liệu hoạt hình bên ngoài bắt buộc phải tuân thủ schema JSON tại:
`docs/contracts/animation-catalog-v1/dippie.catalog.v1.schema.json`

### 1.1. Cấu trúc gốc (Root Keys)
Một tệp catalog hợp lệ bao gồm trường phiên bản hợp đồng cùng 12 danh mục thực thể:
1. `schema_version`: Phải có giá trị chính xác là `"dippie.catalog.v1"`.
2. `package`: Metadata gói (`id`, `revision`, `created_at`, `default_language`, `import_mode`, `reference_scope`, `description`).
3. `genres`: Danh mục thể loại hoạt hình kèm nhãn đa ngôn ngữ (`labels`) và định danh `id`.
4. `attribute_scales`: Thang đo thuộc tính biên tập nội dung (`darkness_v1`, `pacing_v1`, ...).
5. `sources`: Nguồn gốc xuất xứ và metadata tài liệu tham khảo.
6. `series`: Danh mục các bộ hoạt hình (tiêu đề, năm phát hành, thể loại, studio, danh sách nhân vật).
7. `seasons`: Danh mục các mùa/phần thuộc bộ hoạt hình (`series_id`, `season_number`, `episode_count`).
8. `episodes`: Danh mục từng tập phim (`series_id`, `season_id`, `episode_number`, `duration_ms`, `plot_facts`, `keywords`, `themes`, `primary_media_asset_id`).
9. `segments`: Các mẩu chuyện hoặc phân đoạn nhỏ trong tập (`episode_id`, `position`, `episode_start_ms`, `episode_end_ms`, `plot_facts`).
10. `characters`: Nhân vật hoạt hình (`name`, `aliases`, `role`, `traits`, `series_ids`).
11. `media_assets`: Tài nguyên video/audio lưu trữ trên Google Drive hoặc cục bộ (`storage.provider`, `storage.storage_key`, `coverage`).
12. `text_tracks`: Phụ đề, bản dịch inline hoặc tệp ngoài (`cues`, `language`, `media_asset_id`).
13. `scenes`: Các phân cảnh hành động/nội dung quan trọng (`start_ms`, `end_ms`, `visual_description`, `summary`, `transcript_cue_ids`).

### 1.2. Tính duy nhất toàn cục của định danh (Global ID Uniqueness)
Tất cả các ID thực thể (`pkg_*`, `ser_*`, `ep_*`, `seg_*`, `char_*`, `asset_*`, `scene_*`, `cue_*`, v.v.) phải là **duy nhất tuyệt đối trên toàn bộ gói dữ liệu**, không được trùng lặp ngay cả giữa các kiểu thực thể khác nhau.

### 1.3. Chính sách kiểm soát phiên bản & Idempotency
- **Cùng revision và cùng SHA-256 content hash:** Ghi nhận thành công, bảo toàn dữ liệu hiện có (idempotent, không gây lỗi).
- **Cùng revision nhưng khác content hash:** Trả về mã lỗi **HTTP 409 Conflict** nhằm chống xung đột biên tập đồng thời.
- **Revision thấp hơn phiên bản đã lưu trong DB:** Bị từ chối để tránh ghi đè dữ liệu cũ lên dữ liệu mới.
- **Revision cao hơn:** Được cập nhật nguyên tử có bảo toàn transaction.

---

## 2. API Endpoints Quản Trị & Tra Cứu

### 2.1. Quản trị nhập dữ liệu (Admin Endpoints - Bảo Mật ROLE_ADMIN)
| Method | Endpoint | Quyền hạn | Mô tả |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/admin/catalog/validate` | `ROLE_ADMIN` (`Bearer <token>`) | Xác thực cú pháp JSON Schema Draft 2020-12 & ngữ nghĩa quan hệ, tính SHA-256 và diff `toCreate`, `toUpdate`, `unchanged`, `conflicts` (Dry-run không ghi DB). |
| `POST` | `/api/admin/catalog/import` | `ROLE_ADMIN` (`Bearer <token>`) | Nhập gói catalog có transaction nguyên tử vào 12 bảng thực thể (@Version, raw_json), gán thế hệ tuần tự toàn cục (generation), ghi nhận sự kiện hàng đợi outbox `catalog_snapshots` và kích hoạt đồng bộ nền bất đồng bộ. |
| `GET` | `/api/admin/catalog/history` | `ROLE_ADMIN` (`Bearer <token>`) | Xem lịch sử các gói catalog đã nhập thành công trong cơ sở dữ liệu. |
| `GET` | `/api/admin/catalog/snapshots` | `ROLE_ADMIN` (`Bearer <token>`) | Giám sát trạng thái hàng đợi Outbox (`PENDING`, `SYNCING`, `READY`, `SYNC_FAILED`), số lần retry và snapshot version. |
| `GET` | `/api/admin/catalog/export` | `ROLE_ADMIN` (`Bearer <token>`) | Xuất toàn bộ dữ liệu hợp lệ dưới định dạng chuẩn `dippie.catalog.v1` (hỗ trợ tham số `include_draft` và `include_private` cho quản trị viên). |

### 2.2. Tra cứu dữ liệu & Tìm kiếm (Public Catalog Endpoints)
| Method | Endpoint | Mô tả |
| :--- | :--- | :--- |
| `GET` | `/api/catalog/series` | Danh sách tóm tắt tất cả các bộ hoạt hình công khai đã xuất bản (tự động loại bỏ bản nháp/draft và lưu trữ/archived). |
| `GET` | `/api/catalog/series/{id}` | Chi tiết một bộ hoạt hình bao gồm danh sách các phần (`seasons`) và các tập (`episodes`) đã xuất bản. |
| `GET` | `/api/catalog/episodes/{id}` | Chi tiết tập phim bao gồm các đoạn (`segments`), tài nguyên phát (`mediaAssets`) và phân cảnh (`scenes`). |
| `GET` | `/api/catalog/search?q={query}` | Tìm kiếm đa cấp độ theo tiêu đề, nhân vật, cốt truyện, phân cảnh và từ khóa (tuân thủ chính sách xuất bản công khai). |

### 2.3. Tiến trình Outbox Worker & Đồng bộ chỉ mục AI (FastAPI Index Sync)
Kiến trúc outbox thực sự đảm bảo tính nhất quán dữ liệu giữa Spring Boot và FastAPI:
1. **Giao dịch Cơ sở Dữ liệu Độc lập:** Khi quản trị viên nhập catalog, dữ liệu được commit đầy đủ vào cơ sở dữ liệu trước khi thực hiện bất kỳ thao tác ghi đĩa hoặc mạng nào.
2. **Hàng đợi Outbox & Máy trạng thái (`CatalogSyncWorker`):**
   - Trạng thái Snapshot:
     - `PENDING`: Vừa tạo sau transaction commit, sẵn sàng để đồng bộ.
     - `SYNCING`: Đang ghi tệp snapshot ra đĩa và gửi HTTP Ack tới FastAPI.
     - `READY`: FastAPI xác nhận thế hệ và content hash hợp lệ (`status: "success"` hoặc `"UNCHANGED"`), chỉ mục AI đã sẵn sàng phục vụ.
     - `BLOCKED`: Cấu hình thiếu syncToken; tiến trình dừng an toàn, không báo READY ảo.
     - `SYNC_FAILED`: Lỗi I/O ghi đĩa hoặc lỗi mạng/HTTP từ FastAPI (được propagate rõ ràng, có errorMessage).
   - Tự động phục hồi khi khởi động lại (`@EventListener(ApplicationReadyEvent.class)`):
     - Nếu tiến trình ứng dụng bị crash hoặc restart khi một snapshot đang ở trạng thái `SYNCING`, hệ thống tự động phát hiện và chuyển về `PENDING` để tiếp tục đồng bộ an toàn.
   - Cơ chế thử lại thủ công (Manual Retry):
     - Endpoint: `POST /api/admin/catalog/snapshots/{id}/retry` (bảo mật `ROLE_ADMIN`).
     - Cho phép quản trị viên kích hoạt lại snapshot bị lỗi (`SYNC_FAILED`) hoặc bị chặn (`BLOCKED`) mà không cần nhập lại toàn bộ gói catalog.
     - Giới hạn retry tối đa: 5 lần tự động qua `@Scheduled(fixedDelay = 5000)` kích hoạt bởi `@EnableScheduling`.
3. **AcceptedSnapshot Bất Biến & Hoán Đổi Tham Chiếu Nguyên Tử (Finding R1):**
   - FastAPI áp dụng mô hình `AcceptedSnapshot` (immutable dataclass) đóng gói: `generation`, `content_hash`, `catalog_manager`, `hybrid_index`, `payload`, `is_ready`.
   - Cơ chế Đọc Không Khóa (Lock-Free Reader Isolation): Mỗi request đọc (Search/Discover/Recommend) chụp tham chiếu snapshot duy nhất tại thời điểm bắt đầu thông qua `snap = get_accepted_snapshot()`. Toàn bộ các bước trong request (NLU Intent, Hard Filters, Vector Retrieval, BM25, Grounded Storytelling) chỉ tham chiếu trên cùng `snap` này.
   - Hoán đổi Nguyên tử (Atomic Pointer Swap): Quản trị viên publish snapshot mới không làm biến đổi (mutate in-place) chỉ mục đang phục vụ. Candidate manager và candidate index được dựng độc lập, sau đó hoán đổi nguyên tử duy nhất qua `set_accepted_snapshot(new_snap)`. Các readers đang chạy tiếp tục phục vụ snapshot cũ an toàn mà không bao giờ gặp tình trạng snapshot pha tạp (mixed state).
   - Khôi phục trạng thái sau restart: Lưu giữ `data/indices/catalog_sync_state.json` và nạp lại khi ứng dụng khởi động với thế hệ đã chấp nhận.
4. **Chính sách Cache-Control cho luồng phát media (`MediaStreamController`):**
   - Tài nguyên công khai (`isPublic = true`): Trả về `Cache-Control: public, max-age=3600`.
   - Tài nguyên bảo vệ (`isPublic = false` hoặc `authenticated`/`private`): Trả về `Cache-Control: private, no-cache, no-store, must-revalidate` trên toàn bộ các phương thức HEAD, GET toàn phần và Range byte response.
5. **Quy tắc chuyển đổi mốc thời gian chuẩn (Timestamp Semantics theo Hợp đồng dippie.catalog.v1 - F2/H3):**
   - **Phân đoạn / Truyện ngắn (`segments[].episode_start_ms`):** Là mốc thời gian logic của tập phim (`episode timeline`). Trình phát frontend sử dụng `resolveFileTimestamp(logicalMs, asset, segmentId, episodeId)` để ánh xạ sang trục thời gian của tệp video thực tế:
     $$\text{file\_timestamp\_sec} = \frac{\text{source\_in\_ms} + \max(0, \text{logicalMs} - \text{episode\_in\_ms})}{1000}$$
   - **Phân cảnh chi tiết (`scenes[].start_ms`):** Theo đúng hợp đồng `dippie.catalog.v1`, mốc `start_ms` của scene đã nằm trực tiếp trên trục thời gian của tệp video tương ứng (`file timeline`). Khi người dùng nhấp tua phân cảnh, trình phát tua trực tiếp tới:
     $$\text{file\_timestamp\_sec} = \frac{\text{scene.start\_ms}}{1000}$$
     Tuyệt đối không cộng thêm offset `source_in_ms` từ coverage lần thứ hai để tránh lệch mốc thời gian (Finding F2).
   - **Bảo vệ danh tính tệp phát (`Media Asset Identity Guard`):** Nếu phân cảnh hoặc phân đoạn trỏ đến `mediaAssetId` khác với tệp đang phát, hệ thống tự động chuyển đổi sang đúng media asset tương ứng (kèm yêu cầu cấp playback grant nếu là protected asset) trước khi thực hiện tua video; nếu asset không tồn tại trong tập, hệ thống phát cảnh báo và từ chối thao tác trên tệp không liên quan.
6. **Cấu hình Phát Video Google Drive Thực Tế (Finding R3):**
   - Điểm gắn rclone WinFsp chế độ chỉ đọc: `rclone mount --read-only --vfs-cache-mode off --buffer-size 16M cinema-drive: X:`
   - Biến môi trường Spring Boot: `APP_MEDIA_DRIVE_MOUNT=X:`
   - Tham số Timeout I/O Google Drive: Truyền `-Dapp.media.drive-read-timeout-ms=60000` và `-Dapp.media.drive-metadata-timeout-ms=60000` vào tiến trình Spring Boot để đảm bảo các file video lớn (>300MB) mở kênh và đọc partial range ổn định qua mạng mà không bị ngắt kết nối giữa chừng.

---

## 3. Giao Diện Người Dùng & Trải Nghiệm Thực Tế

### 3.1. Trang nhập dữ liệu: `/admin/import`
1. Người dùng có thể nhấn **"Chọn tệp JSON..."** để nạp tệp `catalog.json` từ máy tính hoặc dán trực tiếp nội dung vào khung soạn thảo.
2. Nhấn **"Kiểm tra & Xem trước"**:
   - Hệ thống hiển thị huy hiệu Trạng thái (Hợp lệ / Không hợp lệ).
   - Hiển thị bảng tổng hợp khác biệt: số lượng thực thể sẽ tạo mới (`+`), cập nhật (`~`), giữ nguyên và xung đột.
   - Nếu có lỗi ngữ nghĩa (sai mốc thời gian, tham chiếu gãy, ID trùng), hiển thị bảng chi tiết kèm **JSON Pointer Path** (ví dụ: `/episodes/0/synopsis`).
3. Nhấn **"Xác nhận nhập dữ liệu"**:
   - Hệ thống thực thi giao dịch commit nguyên tử vào cơ sở dữ liệu.
   - Hiển thị số lượng bản ghi của 12 thực thể đã nhập và Import ID.
   - Tự động kích hoạt đồng bộ chỉ mục AI cho FastAPI.

### 3.2. Trang chi tiết bộ hoạt hình & phát video: `/series/[id]`
1. Hiển thị thông tin tổng quan của bộ hoạt hình (tên, năm, thể loại, studio, tóm tắt).
2. Danh sách các tập phim bên cột phải: nhấp vào tập bất kỳ để chọn phát. Khi chuyển tập, state của tập cũ được xóa tức thời và yêu cầu fetch cũ bị hủy bằng `AbortController` để triệt tiêu hoàn toàn race condition.
3. Trình phát video chuẩn HTML5 phát trực tiếp video từ Google Drive thông qua Media Service với hỗ trợ đầy đủ `HTTP 206 Partial Content (Byte Range)`.
4. Danh sách **Phân cảnh chi tiết & Đảm bảo Danh tính Tua video (Seek Identity & Readiness Tuple)**:
   - Mỗi phân cảnh hiển thị mốc thời gian chính xác (ví dụ: `01:10 – 01:35`) và mô tả hình ảnh.
   - Khi người xem nhấp vào phân cảnh, nếu phân cảnh thuộc về tài nguyên media khác (`mediaAssetId`), hệ thống sẽ chuyển nguồn media và lưu lại `PendingSeekIdentity(seriesId, episodeId, assetId, sceneId, targetSec, generation)`.
   - Trình phát tuyệt đối không tua lên tài nguyên video cũ; chỉ khi trình phát kích hoạt sự kiện `onLoadedMetadata` hoặc `onCanPlay` và xác nhận đúng bộ ba định danh `(seriesId, episodeId, assetId)` mới áp dụng mốc thời gian đã giới hạn an toàn (`Math.min(targetSec, duration - 0.5)`).

### 3.3. Tích hợp Tìm kiếm: `/search`
- Khi người dùng nhập từ khóa tìm kiếm (ví dụ: `"Bảo Thần Tốc"`, `"hẻm núi"`, `"nhảy vực"`), hệ thống hiển thị đồng thời kết quả từ kho phim điện ảnh và đường ray **"Kết quả từ Danh Mục Hoạt Hình dippie.catalog.v1"** gồm các bộ, tập, truyện ngắn và phân cảnh khớp.
- Các liên kết hỗ trợ deep link định dạng đầy đủ: `/series/{seriesId}?episode={episodeId}&scene={sceneId}&asset={assetId}&t={startMs}`. Khi người dùng nhấp vào phân cảnh từ trang tìm kiếm, hệ thống tự động:
  1. Điều hướng đến đúng bộ hoạt hình (`seriesId`).
  2. Chọn đúng tập phim (`episodeId`), triệt tiêu race condition bằng AbortController.
  3. Chọn đúng tài nguyên media phát (`assetId`), đồng bộ nguồn Google Drive tương ứng với cảnh.
  4. Đợi metadata của video mới nạp xong mới tua chính xác đến mốc thời gian của phân cảnh (`t` / `startMs`).
  5. Đánh dấu sáng phân cảnh đang phát (`activeSceneId`).

### 3.4. Chatbot CineBot
- CineBot kết nối trực tiếp với backend AI FastAPI và tự động ưu tiên dữ liệu catalog thật đã nhập (nhân vật, tình tiết cốt truyện, mốc thời gian phân cảnh) để đưa ra câu trả lời được kiểm chứng (grounded explanations) thay vì phụ thuộc vào danh sách 12 phim mẫu cũ.

---

## 4. Hướng dẫn Khởi chạy Hệ thống & Trình tự Sử dụng Thực tế

Phần này hướng dẫn người dùng hoặc nhân viên vận hành khởi chạy đầy đủ 3 dịch vụ và thực hiện toàn bộ luồng hoạt động từ nhập catalog đến phát video có phân cảnh.

### 4.1. Yêu cầu Môi trường & Cổng Dịch vụ
- **Java**: JDK 21+ (hoặc JDK 25 hiện hành).
- **Python**: 3.10+ kèm PyTorch (hỗ trợ CUDA nếu có GPU).
- **Node.js**: 18.x hoặc 20.x LTS.
- **Bảng Cổng dịch vụ**:
  | Dịch vụ | Thư mục | Cổng | URL truy cập |
  | :--- | :--- | :--- | :--- |
  | **Spring Boot Core** | `backend/springboot` | `8080` | `http://localhost:8080` |
  | **FastAPI AI Engine** | `backend/fastapi` | `8000` | `http://localhost:8000` |
  | **Next.js Web Frontend** | `frontend` | `3000` | `http://localhost:3000` |

---

### 4.2. Lệnh Khởi Chạy Từng Dịch Vụ

Mở 3 cửa sổ PowerShell độc lập để khởi động 3 dịch vụ:

#### Terminal 1: Khởi động Spring Boot Backend (Port 8080)
```powershell
cd D:\Class\movie-rcm-system\backend\springboot
$env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"
# Cấu hình token đồng bộ (phải khớp giữa Spring Boot và FastAPI):
$env:CATALOG_SYNC_TOKEN = "dippie_production_sync_secret_2026"
.\mvnw.cmd spring-boot:run
```
> Khi màn hình xuất hiện `Started MovieRcmApplication in ... seconds (process running for ...)`, backend Spring Boot đã sẵn sàng phục vụ tại `http://localhost:8080`.

#### Terminal 2: Khởi động FastAPI AI & Hybrid Index (Port 8000)
```powershell
cd D:\Class\movie-rcm-system\backend\fastapi
$env:FASTAPI_SYNC_SECRET = "dippie_production_sync_secret_2026"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
> Khi màn hình hiển thị `Application startup complete` và `Uvicorn running on http://0.0.0.0:8000`, dịch vụ tìm kiếm và đồng bộ chỉ mục AI đã sẵn sàng.

#### Terminal 3: Khởi động Next.js Web Frontend (Port 3000)
```powershell
cd D:\Class\movie-rcm-system\frontend
npm run dev
```
> Giao diện web sẵn sàng tại `http://localhost:3000`.

---

### 4.3. Tài khoản Đăng nhập Hệ thống & Dữ liệu Thử nghiệm

#### A. Tài khoản mặc định (Được bootstrap tự động khi khởi động):
- **Tài khoản Quản trị viên (Admin):**
  - Tên đăng nhập: `admin` hoặc Email: `admin@dippie.com`
  - Mật khẩu: `password123`
  - Quyền hạn: `ROLE_ADMIN` (được phép truy cập `/admin/import`, kiểm tra và nhập catalog, quản lý snapshot outbox).
- **Tài khoản Người dùng (User):**
  - Tên đăng nhập: `user` hoặc Email: `user@dippie.com`
  - Mật khẩu: `password123`
  - Quyền hạn: `ROLE_USER` (xem phim, tìm kiếm, phát nội dung được cấp quyền).

#### B. Dữ liệu thử nghiệm có sẵn:
- **Tệp mẫu sản xuất tích hợp sẵn media cục bộ:**
  - Đường dẫn: `docs/fixtures/rehearsal_catalog.json`
  - Chứa 2 series, 2 seasons, 3 episodes, 1 segment, 3 characters, 3 media assets (`asset_feature_01`, `asset_feature_02`, `asset_trailer_01`), 1 text track, 1 scene có mốc seek chính xác.
  - Đã được gắn trực tiếp vào các tệp video mẫu thực tế tại `media/synthetic/feature_test.mp4` và `media/synthetic/trailer_test.mp4`.
- **Tệp hợp đồng mẫu:**
  - `docs/contracts/animation-catalog-v1/catalog.example.json`

---

### 4.4. Trình Tự Thao Tác Toàn Luồng Sản Phẩm (P1 – P5)

#### Bước 1: Đăng nhập Quản trị viên
1. Mở trình duyệt web truy cập `http://localhost:3000/login`.
2. Điền `admin` / `password123` và nhấn **Đăng nhập**.
3. Hệ thống lưu token vào `dippie_auth_token` trên localStorage và chuyển hướng về trang chủ.

#### Bước 2: Tải lên và Kiểm tra Catalog JSON (Validation & Dry-Run)
1. Truy cập trang quản trị catalog: `http://localhost:3000/admin/import`.
2. Nhấn nút **"Chọn tệp JSON..."** và chọn file dữ liệu hợp lệ (ví dụ: `docs/contracts/animation-catalog-v1/catalog.example.json`), hoặc dán nội dung JSON vào khung soạn thảo.
3. Nhấn **"Kiểm tra & Xem trước"**:
   - Backend Spring Boot thực hiện xác thực Schema Draft 2020-12 và kiểm tra toàn vẹn quan hệ cha-con (series, seasons, episodes, segments, media_assets, scenes).
   - Màn hình hiển thị bảng tóm tắt: Trạng thái Hợp lệ, Mã băm SHA-256 nội dung, số bản ghi sẽ thêm mới (`+`) hoặc cập nhật (`~`).

#### Bước 3: Xác nhận Nhập Dữ Liệu (Atomic DB Import & Outbox Enqueue)
1. Nhấn nút **"Xác nhận nhập dữ liệu"**.
2. Spring Boot thực thi giao dịch cơ sở dữ liệu nguyên tử (@Transactional):
   - Lưu trữ dữ liệu vào 12 bảng thực thể.
   - Gán `generation` tuần tự toàn cục (bắt đầu từ thế hệ mới nhất).
   - Ghi nhận bản ghi Outbox snapshot với trạng thái ban đầu `PENDING`.
3. Giao diện hiển thị thông báo thành công và danh sách Import ID.

#### Bước 4: Giám Sát Đồng Bộ Chỉ Mục AI (HTTP Worker Sync)
1. Tiến trình `CatalogSyncWorker` chạy ngầm:
   - Ghi file snapshot bền vững ra thư mục `data/indices/` (hoặc snapshot folder).
   - Gửi HTTP Request kèm header `X-Service-Token` sang FastAPI endpoint `POST http://localhost:8000/api/index/sync`.
   - Chuyển trạng thái Outbox snapshot từ `PENDING` sang `SYNCING`, và cuối cùng là `READY` khi FastAPI xác nhận CAS thành công.
2. Tại bảng **"Lịch sử hàng đợi Outbox"** trên trang `/admin/import`, người dùng thấy thế hệ mới nhất đạt trạng thái `READY`.

#### Bước 5: Tìm kiếm Nội dung Đa Cấp Độ & Trò chuyện CineBot
1. Truy cập `http://localhost:3000/search`.
2. Nhập từ khóa: `"Shin"`, `"Bảo Thần Tốc"`, hoặc `"nhảy vực"`.
3. Hệ thống trả về kết quả tìm kiếm tức thì theo từng cấp độ: Bộ phim, Tập phim, Đoạn truyện và Phân cảnh.
4. Mở cửa sổ CineBot ở góc dưới màn hình, gõ câu hỏi: *"Tìm phân cảnh xe địa hình nhảy vực"* — CineBot phân tích NLU và trích xuất đúng mốc thời gian kèm lời giải thích sát thực tế.

#### Bước 6: Phát Video và Tua Chính Xác Mốc Phân Cảnh (Playback & Seek)
1. Từ kết quả tìm kiếm hoặc trang danh mục, nhấp vào phân cảnh cần xem.
2. Trình duyệt mở trang chi tiết tập phim tại `http://localhost:3000/series/[id]`.
3. Trình phát video tải luồng từ Google Drive / Media Stream endpoint:
   - **Tài nguyên công khai (`public`):** Phát trực tiếp với `Cache-Control: public, max-age=3600`.
   - **Tài nguyên bảo vệ (`protected`):** Frontend tự động gọi `POST /api/media/grant/{assetId}` để lấy token Playback Grant ngắn hạn (5 phút, khóa cứng theo assetId), sau đó truyền qua URL `?grant=<token>`.
   - **Bảo mật tuyệt đối:** Token Grant chỉ dùng để phát stream `GET`/`HEAD` cho đúng `assetId` đó; không thể dùng làm Bearer token để truy cập API quản trị hoặc stream video khác.
4. Hệ thống áp dụng `PendingSeekIdentity`, đợi video tải đủ metadata rồi tua chính xác tới giây thứ của phân cảnh (ví dụ: giây thứ 90.0). Phân cảnh đang phát được tô sáng trên danh sách.

#### Bước 7: Kiểm thử Tính Bền Vững Sau Khởi Động Lại (Durability & Restart Recovery)
1. Tắt cả 3 tiến trình terminal (`Ctrl + C`).
2. Khởi động lại Spring Boot và FastAPI theo lệnh ở mục 4.2.
3. Khi khởi động:
   - Spring Boot kiểm tra các snapshot `SYNCING` dở dang và tự động phục hồi về `PENDING` để đồng bộ lại.
   - FastAPI đọc tệp `data/indices/catalog_sync_state.json`, nạp lại thế hệ và content hash đã lưu bền vững.
4. Mở lại trình duyệt tại `http://localhost:3000/search` hoặc `http://localhost:3000/series/[id]`: toàn bộ dữ liệu hoạt hình và khả năng phát video tiếp tục hoạt động chính xác mà không cần nhập lại catalog.

