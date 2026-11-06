# MA TRẬN ÁNH XẠ TRƯỜNG DỮ LIỆU: CATALOG-01-F02
## Chuẩn Hợp Đồng dippie.catalog.v1 <-> Thực Thể JPA <-> Bảng CSDL <-> Outbox Worker & Streaming Resolver <-> Chỉ Mục Tìm Kiếm AI

Tài liệu này xác định bảng quy chiếu chi tiết (canonical field mapping matrix) giữa hợp đồng JSON bên ngoài `dippie.catalog.v1`, các thực thể Spring Boot JPA, cấu trúc bảng H2/PostgreSQL (`schema.sql`), bảng kế thừa tương thích (`movies`, `media_assets`), đường phân giải lưu trữ đa nguồn `StorageKeyConfig`, và các trường chỉ mục tìm kiếm Hybrid Retrieval (BM25 + Dense multilingual-e5) trong FastAPI.

---

### 1. Bảng Tổng Quan Ánh Xạ Danh Mục Thực Thể (Collections)

| Danh mục Contract (`dippie.catalog.v1`) | Bảng CSDL Hiện Đại | Thực thể Spring Boot JPA | Bảng Kế Thừa (Legacy) | Đối tượng Chỉ mục AI |
| :--- | :--- | :--- | :--- | :--- |
| `package` | `catalog_packages` | `CatalogPackage` | - | Metadata gói (`pkg_*`) |
| `genres` | `catalog_genres` | `CatalogGenre` | - | Lọc & nhãn thể loại |
| `attribute_scales` | `catalog_attribute_scales` | `CatalogAttributeScale` | - | Thang đo thuộc tính biên tập |
| `sources` | `catalog_sources` | `CatalogSource` | - | Nguồn gốc xuất xứ provenance |
| `series` | `catalog_series` | `CatalogSeries` | `movies` | Mục tìm kiếm cấp Bộ (`series`) |
| `seasons` | `catalog_seasons` | `CatalogSeason` | - | Cấu trúc phân mùa (`seasons`) |
| `episodes` | `catalog_episodes` | `CatalogEpisode` | `movies` | Mục tìm kiếm cấp Tập (`episode`) |
| `segments` | `catalog_segments` | `CatalogSegment` | - | Mục tìm kiếm cấp Đoạn (`segment`) |
| `characters` | `catalog_characters` | `CatalogCharacter` | - | Bổ trợ tên & bí danh nhân vật |
| `media_assets` | `catalog_media_assets` | `CatalogMediaAsset` | `media_assets` | Nguồn phát trực tiếp Google Drive / Local |
| `text_tracks` | `catalog_text_tracks` | `CatalogTextTrack` | - | Phụ đề & mốc thời gian cue |
| `scenes` | `catalog_scenes` | `CatalogScene` | - | Mục tìm kiếm cấp Cảnh (`scene`) |
| - | `catalog_snapshots` | `CatalogSnapshot` | - | Outbox đồng bộ toàn bộ catalog committed |

---

### 2. Chi Tiết Ánh Xạ Từng Bảng Thực Thể

#### 2.1. Gói Dữ Liệu (`package` -> `catalog_packages`)
| Hợp đồng JSON | Kiểu JSON | Entity JPA | Cột CSDL | Ràng buộc DDL | Ghi chú & Chuyển đổi |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `package.id` | `string` | `id` | `id` | `VARCHAR(100) PRIMARY KEY` | Định danh duy nhất toàn cục |
| `package.version` | `string` | `version` | `version` | `VARCHAR(50) NOT NULL` | Phiên bản package (vd: 1.0.0) |
| `package.revision` | `integer` | `revision` | `revision` | `INT NOT NULL` | Số nguyên tăng dần >= 1 |
| `package.default_language` | `string` | `defaultLanguage` | `default_language` | `VARCHAR(20) NOT NULL` | Ngôn ngữ mặc định (`vi`) |
| `package.import_mode` | `string` | `importMode` | `import_mode` | `VARCHAR(50) NOT NULL` | `"upsert"` / `"replace"` / `"append"` |
| `package.reference_scope` | `string` | `referenceScope` | `reference_scope` | `VARCHAR(50) NOT NULL` | `"self_contained"` / `"external"` |
| `package.description` | `string` | `description` | `description` | `TEXT` | Mô tả gói |
| - | - | `contentHash` | `content_hash` | `VARCHAR(100) NOT NULL` | SHA-256 toàn bộ JSON |
| - | - | `status` | `status` | `VARCHAR(50) NOT NULL` | `"COMMITTED"` |
| - | - | `importedAt` | `imported_at` | `TIMESTAMP` | Thời điểm nạp hệ thống |
| - | - | `optLockVersion` | `opt_lock_version`| `BIGINT DEFAULT 0` | Khóa lạc quan `@Version` (bảo toàn khi re-import) |

#### 2.2. Hàng Đợi Outbox Snapshot (`catalog_snapshots`)
| Trường Entity JPA | Cột CSDL | Kiểu CSDL | Ràng buộc | Ý Nghĩa Vận Hành (F2) |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `id` | `VARCHAR(100)` | `PRIMARY KEY` | Khóa snapshot: `snap_{ts}_{pkgId}_g{generation}` |
| `snapshotVersion` | `snapshot_version` | `BIGINT` | `NOT NULL` | **Monotonic Global Generation** - Tăng dần tuần tự toàn hệ thống |
| `contentHash` | `content_hash` | `VARCHAR(100)` | `NOT NULL` | SHA-256 của toàn bộ danh mục xuất bản cam kết |
| `itemCount` | `item_count` | `INT` | `NOT NULL` | Tổng số lượng thực thể eligible được xuất |
| `status` | `status` | `VARCHAR(50)` | `NOT NULL` | `PENDING` -> `SYNCING` -> `READY` / `SYNC_FAILED` / `STALE_SKIPPED` |
| `retryCount` | `retry_count` | `INT` | `DEFAULT 0` | Số lần thử lại kết nối khi FastAPI bận |
| `errorMessage` | `error_message` | `TEXT` | `NULL` | Chi tiết lỗi HTTP/kết nối nếu thất bại |
| `createdAt` | `created_at` | `TIMESTAMP` | `NOT NULL` | Thời điểm tạo snapshot outbox sau commit DB |
| `completedAt` | `completed_at` | `TIMESTAMP` | `NULL` | Thời điểm hoàn thành đồng bộ chỉ mục AI |

#### 2.3. Bộ Hoạt Hình (`series` -> `catalog_series` & `movies`)
| Hợp đồng JSON | Kiểu JSON | Entity JPA | Cột CSDL | Ánh xạ Legacy (`movies`) | Chỉ mục AI (Cascading Pipeline) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `string` | `id` | `id` | `movies.id` | `id` |
| `title` | `string` | `title` | `title` | `movies.title` | `title` (BM25 + Dense multilingual-e5) |
| `original_title` | `string / null` | `originalTitle` | `original_title` | - | `original_title` |
| `aliases` | `array[string]` | `aliasesJson` | `aliases_json` | - | `aliases` |
| `synopsis` | `string / null` | `synopsis` | `synopsis` | `movies.description` | `synopsis` (BM25 + Vector) |
| `release_year_start` | `int / null` | `releaseYearStart`| `release_year_start`| `movies.release_year` | `year` (Lọc cứng khoảng năm) |
| `release_year_end` | `int / null` | `releaseYearEnd` | `release_year_end` | - | Năm kết thúc |
| `genre_ids` | `array[string]` | `genreIdsJson` | `genre_ids_json` | `movies.genres` | `genres` (Lọc cứng bao hàm/loại trừ) |
| `character_ids` | `array[string]` | `characterIdsJson`| `character_ids_json`| - | Tên & bí danh nhân vật mở rộng |
| `attributes` | `array[object]` | `attributesJson` | `attributes_json` | - | Thang đo so sánh (`darkness`, `pacing`, ...) |
| `record.status` | `string` | `recordJson` | `record_json` | - | Chính sách xuất bản (`draft`/`published`/`archived`) |
| `record.revision`| `int` | `revision` | `revision` | - | Revision độc lập của thực thể (không bị nâng giả) |
| - | - | `rawJson` | `raw_json` | - | JSON gốc nguyên vẹn (bảo toàn 100%) |
| - | - | `optLockVersion` | `opt_lock_version`| - | `@Version` lạc quan |

#### 2.4. Tập Phim (`episodes` -> `catalog_episodes` & `movies`)
| Hợp đồng JSON | Kiểu JSON | Entity JPA | Cột CSDL | Ánh xạ Legacy (`movies`) | Chỉ mục AI |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `string` | `id` | `id` | `movies.id` | `id` |
| `series_id` | `string` | `seriesId` | `series_id` | - | `series_id` (Phân cấp cha-con) |
| `season_id` | `string / null` | `seasonId` | `season_id` | - | `season_id` |
| `number` | `int` | `number` | `number` | - | Số thứ tự tập |
| `title` | `string` | `title` | `title` | `movies.title` | `title` |
| `synopsis` | `string / null` | `synopsis` | `synopsis` | `movies.description` | `synopsis` |
| `duration_ms` | `long / null` | `durationMs` | `duration_ms` | `movies.runtime` (mins) | Thời lượng phát |
| `release_date` | `string (date)`| `releaseDate` | `release_date` | `movies.release_year` | Định dạng strict YYYY-MM-DD |
| `genre_ids` | `array[string]` | `genreIdsJson` | `genre_ids_json` | `movies.genres` | `genres` |
| `character_ids` | `array[string]` | `characterIdsJson`| `character_ids_json`| - | Danh sách nhân vật xuất hiện |
| `plot_facts` | `array[object]` | `plotFactsJson` | `plot_facts_json` | - | Tình tiết nhớ cốt truyện của CineBot |
| `record.status` | `string` | `recordJson` | `record_json` | - | Kế thừa trạng thái xuất bản từ series cha |

#### 2.5. Phân Đoạn & Truyện Ngắn (`segments` -> `catalog_segments`)
| Hợp đồng JSON | Kiểu JSON | Entity JPA | Cột CSDL | Chỉ mục AI | Ghi chú & Kế thừa |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `string` | `id` | `id` | `id` | Định danh phân đoạn |
| `episode_id` | `string` | `episodeId` | `episode_id` | `episode_id` | Khóa ngoại tập phim |
| - | - | - | - | `series_id` | Tự động kế thừa từ tập cha |
| `position` | `int` | `position` | `position` | Thứ tự trong tập |
| `title` | `string` | `title` | `title` | `title` | Tiêu đề mẩu chuyện/đoạn |
| `synopsis` | `string / null` | `synopsis` | `synopsis` | `synopsis` | Nội dung mẩu chuyện |
| `episode_start_ms` | `long / null` | `episodeStartMs` | `episode_start_ms` | `start_ms` | Mốc bắt đầu logic |
| `episode_end_ms` | `long / null` | `episodeEndMs` | `episode_end_ms` | `end_ms` | Mốc kết thúc logic |
| `character_ids` | `array[string]` | `characterIdsJson` | `character_ids_json`| `characters` | Nhân vật trong đoạn |
| `plot_facts` | `array[object]` | `plotFactsJson` | `plot_facts_json` | `plot_facts` | Tình tiết phân đoạn (Stage 5 CineBot) |

#### 2.6. Phân Cảnh Hành Động (`scenes` -> `catalog_scenes`)
| Hợp đồng JSON | Kiểu JSON | Entity JPA | Cột CSDL | Chỉ mục AI | Deep Linking URL & Seek Tuple |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `string` | `id` | `id` | `id` | `?scene={id}` |
| `episode_id` | `string` | `episodeId` | `episode_id` | `episode_id` | `?episode={episodeId}` |
| - | - | - | - | `series_id` | `/series/{seriesId}` |
| `segment_id` | `string / null` | `segmentId` | `segment_id` | `segment_id` | Đoạn chứa cảnh |
| `media_asset_id` | `string` | `mediaAssetId` | `media_asset_id` | `media_asset_id` | `?asset={mediaAssetId}` |
| `start_ms` | `long` | `startMs` | `start_ms` | `start_ms` | `?t={startMs}` |
| `end_ms` | `long` | `endMs` | `end_ms` | `end_ms` | Mốc kết thúc cảnh |
| `title` | `string / null` | `title` | `title` | `title` | Tiêu đề cảnh |
| `summary` | `string / null` | `summary` | `summary` | `synopsis` | Tóm tắt cảnh |
| `visual_description`| `string / null` | `visualDescription`| `visual_description`| `visual_summary` | Mô tả hành động / thị giác (Stage 5) |
| `transcript_cue_ids`| `array[string]` | `transcriptCueIdsJson`| `transcript_cue_ids_json`| Thoại phụ đề | Cues đối thoại |

#### 2.7. Tài Nguyên Media (`media_assets` -> `catalog_media_assets` & `media_assets`)
| Hợp đồng JSON | Kiểu JSON | Entity JPA | Cột CSDL | Ánh xạ Legacy (`media_assets`) | Trình Phát Web & Phân Giải Đường Dẫn (F5) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `string` | `id` | `id` | `media_assets.id` | Stream URL `/api/media/stream/{id}` |
| `storage.provider` | `string` (`drive`/`local`) | `storageProvider` | `storage_provider` | `media_assets.storage_provider` | Phân giải Drive/Local qua adapter |
| `storage.storage_key`| `string` | `storageKey` | `storage_key` | `media_assets.storage_key` | **Định tuyến root**: `StorageKeyConfig.resolvePath` |
| `storage.relative_path`| `string` | `relativePath` | `relative_path` | `media_assets.relative_path` | Kiểm tra containment nghiêm ngặt, chống traversal |
| `storage.drive_file_id`| `string / null` | `driveFileId` | `drive_file_id` | - | Định danh Google Drive API |
| `role` | `string` | `role` | `role` | `media_assets.kind` | `"feature"`, `"trailer"`, `"audio"` |
| - | - | - | - | `media_assets.version` | **Unique version**: `"v1_" + aid` (chống đụng unique key) |
| `size_bytes` | `long` | `sizeBytes` | `size_bytes` | `media_assets.byte_length` | HTTP 206 Partial Content (Byte Range) |
| `duration_ms` | `long / null` | `durationMs` | `duration_ms` | `media_assets.duration_seconds` | Thời lượng video (giây) |
| `access_policy` | `string` | `accessPolicy` | `access_policy` | `media_assets.is_public` | `public` -> tự do; `authenticated` -> login; `private` -> `ROLE_ADMIN` |
| `enabled` | `boolean` | `enabled` | `enabled` | `media_assets.is_available` | Trạng thái sẵn sàng phát |

---

### 3. Chính Sách Xuất Bản (Publication Policy & Parent Cascade)
1. **Lọc Mặc Định (Deny-by-default for Non-Admin):**
   - Chỉ các thực thể có `record.status` khác `"draft"` và khác `"archived"` mới được đưa vào danh mục công khai và chỉ mục Hybrid Retrieval.
2. **Kế Thừa Phân Cấp (Parent Cascade Rule):**
   - Nếu bộ hoạt hình (`series`) có trạng thái `draft` hoặc `archived`, toàn bộ các mùa (`seasons`), tập (`episodes`), phân đoạn (`segments`) và phân cảnh (`scenes`) con đều **tự động bị loại khỏi chỉ mục và API tra cứu công khai**.
   - Nếu tập phim (`episode`) có trạng thái `draft` hoặc `archived`, toàn bộ các phân đoạn (`segments`) và phân cảnh (`scenes`) thuộc tập đó đều **bị loại bỏ**.
   - Nếu tài nguyên media (`media_assets`) có `access_policy = "private"`, các phân cảnh chỉ trỏ tới tài nguyên này sẽ **không gắn `media_asset_id` trong chỉ mục công khai** để ngăn chặn rò rỉ metadata.
3. **Phân Quyền Quản Trị (Admin Preview):**
   - Người dùng có quyền `ROLE_ADMIN` được phép xem trước toàn bộ các bản ghi `draft` và `private` thông qua endpoint xác thực `/api/admin/catalog/export?include_draft=true&include_private=true`.
