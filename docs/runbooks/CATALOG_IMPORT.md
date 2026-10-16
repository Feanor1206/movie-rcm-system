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
3. **Compare-And-Swap (CAS) & Atomic Index Replacement tại FastAPI:**
   - FastAPI xác thực header `X-Service-Token` và kiểm tra `content_hash` khai báo so với hash chuẩn của payload nhận được.
   - Thực thi CAS dưới khóa luồng toàn cục `_publish_lock`:
     - Nếu cùng generation nhưng khác hash -> trả về **HTTP 409 Conflict**.
     - Nếu cùng generation và cùng hash -> trả về `status: "UNCHANGED"`.
     - Nếu incoming generation > current generation -> tính toán chỉ mục ứng viên trên đối tượng độc lập, sau đó hoán đổi nguyên tử (`atomic pointer swap`).
   - Khôi phục trạng thái sau restart: Lưu giữ `data/indices/catalog_sync_state.json` và nạp lại khi ứng dụng khởi động.
4. **Chính sách Cache-Control cho luồng phát media (`MediaStreamController`):**
   - Tài nguyên công khai (`isPublic = true`): Trả về `Cache-Control: public, max-age=3600`.
   - Tài nguyên bảo vệ (`isPublic = false` hoặc `authenticated`/`private`): Trả về `Cache-Control: private, no-cache, no-store, must-revalidate` trên toàn bộ các phương thức HEAD, GET toàn phần và Range byte response.
5. **Chuyển đổi mốc thời gian qua Coverage JSON (`resolveFileTimestamp`):**
   - Khi phát đoạn truyện ngắn hoặc phân cảnh có độ lệch thời gian giữa file gốc (`source_in_ms`) và tập phim logic (`episode_in_ms`), trình phát frontend tự động tính toán file timestamp: `(source_in_ms + Math.max(0, logicalMs - episode_in_ms)) / 1000`.
   - Nếu phân cảnh trỏ đến media asset không tồn tại trong tập, hệ thống phát cảnh báo và từ chối tua video trên asset không liên quan.

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
