# MA TRẬN ÁNH XẠ TRƯỜNG DỮ LIỆU: CATALOG-01-F01
## Chuẩn Hợp Đồng dippie.catalog.v1 <-> Thực Thể JPA <-> Bảng CSDL <-> Chỉ Mục Tìm Kiếm AI

Tài liệu này xác định bảng quy chiếu chi tiết (canonical field mapping matrix) giữa hợp đồng JSON bên ngoài `dippie.catalog.v1`, các thực thể Spring Boot JPA, cấu trúc bảng H2/PostgreSQL (`schema.sql`), bảng kế thừa tương thích (`movies`, `media_assets`), và các trường chỉ mục tìm kiếm Hybrid Retrieval (BM25 + Dense multilingual-e5) trong FastAPI.

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
| `media_assets` | `catalog_media_assets` | `CatalogMediaAsset` | `media_assets` | Nguồn phát trực tiếp Google Drive |
| `text_tracks` | `catalog_text_tracks` | `CatalogTextTrack` | - | Phụ đề & mốc thời gian cue |
| `scenes` | `catalog_scenes` | `CatalogScene` | - | Mục tìm kiếm cấp Cảnh (`scene`) |
| - | `catalog_snapshots` | `CatalogSnapshot` | - | Outbox đồng bộ chỉ mục AI |

---

### 2. Chi Tiết Ánh Xạ Từng Bảng Thực Thể

#### 2.1. Gói Dữ Liệu (`package` -> `catalog_packages`)
| Hợp đồng JSON | Kiểu JSON | Entity JPA | Cột CSDL | Ràng buộc DDL | Ghi chú & Chuyển đổi |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `package.id` | `string` | `id` | `id` | `VARCHAR(128) PRIMARY KEY` | Định danh duy nhất toàn cục |
| `package.schema_version` | `string` | `schemaVersion` | `schema_version` | `VARCHAR(64)` | Bắt buộc `"dippie.catalog.v1"` |
| `package.revision` | `integer` | `revision` | `revision` | `INT NOT NULL` | Số nguyên tăng dần >= 1 |
| `package.default_language` | `string` | `defaultLanguage` | `default_language` | `VARCHAR(16)` | Ngôn ngữ mặc định (ví dụ: `"vi"`) |
| `package.import_mode` | `string` | `importMode` | `import_mode` | `VARCHAR(32)` | `"upsert"` / `"replace"` / `"append"` |
| `package.reference_scope` | `string` | `referenceScope` | `reference_scope` | `VARCHAR(32)` | `"self_contained"` / `"external"` |
| `package.description` | `string` | `description` | `description` | `CLOB` | Mô tả gói |
| - | - | `contentHash` | `content_hash` | `VARCHAR(64) NOT NULL` | SHA-256 toàn bộ JSON |
| - | - | `status` | `status` | `VARCHAR(32)` | `"COMMITTED"` |
| - | - | `importedAt` | `imported_at` | `TIMESTAMP` | Thời điểm nạp hệ thống |
| - | - | `rawJson` | `raw_json` | `CLOB` | JSON gốc nguyên vẹn |
| - | - | `version` | `opt_lock_version`| `BIGINT` | Khóa lạc quan `@Version` |

#### 2.2. Bộ Hoạt Hình (`series` -> `catalog_series` & `movies`)
| Hợp đồng JSON | Kiểu JSON | Entity JPA | Cột CSDL | Ánh xạ Legacy (`movies`) | Chỉ mục AI |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `string` | `id` | `id` | `movies.id` | `id` |
| `title` | `string` | `title` | `title` | `movies.title` | `title` (BM25 + Vector) |
| `original_title` | `string / null` | `originalTitle` | `original_title` | - | `original_title` |
| `aliases` | `array[string]` | `aliasesJson` | `aliases_json` | - | `aliases` |
| `translations` | `array[object]` | `translationsJson`| `translations_json`| - | Bản dịch tên & tóm tắt |
| `synopsis` | `string / null` | `synopsis` | `synopsis` | `movies.description` | `synopsis` (BM25 + Vector) |
| `release_status` | `string` | `releaseStatus` | `release_status` | - | Trạng thái phát hành |
| `release_year_start` | `int / null` | `releaseYearStart`| `release_year_start`| `movies.release_year` | `year` (Lọc khoảng năm) |
| `release_year_end` | `int / null` | `releaseYearEnd` | `release_year_end` | - | Năm kết thúc |
| `genre_ids` | `array[string]` | `genreIdsJson` | `genre_ids_json` | `movies.genres` | `genres` (Lọc cứng bao hàm/loại trừ) |
| `character_ids` | `array[string]` | `characterIdsJson`| `character_ids_json`| - | Tên nhân vật mở rộng |
| `keywords` | `array[string]` | `keywordsJson` | `keywords_json` | - | Từ khóa mở rộng |
| `themes` | `array[string]` | `themesJson` | `themes_json` | - | Chủ đề cốt truyện |
| `attributes` | `array[object]` | `attributesJson` | `attributes_json` | - | Thang đo so sánh (`darkness`, ...) |
| `ratings` | `array[object]` | `ratingsJson` | `ratings_json` | `movies.rating` | Điểm đánh giá |
| `content_advisory` | `object` | `advisoriesJson` | `advisories_json` | - | Phân loại độ tuổi & cảnh báo |
| `artwork` | `array[object]` | `artworksJson` | `artworks_json` | `movies.poster`, `backdrop` | Ảnh bìa, poster, thumbnail |
| `record` | `object` | `recordJson` | `record_json` | - | Metadata audit & revision |
| - | - | `revision` | `revision` | - | Phiên bản bản ghi |
| - | - | `rawJson` | `raw_json` | - | Toàn vẹn JSON gốc |
| - | - | `version` | `opt_lock_version`| - | `@Version` |

#### 2.3. Tập Phim (`episodes` -> `catalog_episodes` & `movies`)
| Hợp đồng JSON | Kiểu JSON | Entity JPA | Cột CSDL | Ánh xạ Legacy (`movies`) | Chỉ mục AI |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `string` | `id` | `id` | `movies.id` | `id` |
| `series_id` | `string` | `seriesId` | `series_id` | - | `series_id` |
| `season_id` | `string / null` | `seasonId` | `season_id` | - | `season_id` |
| `number` | `int` | `number` | `number` | - | Số thứ tự tập |
| `title` | `string` | `title` | `title` | `movies.title` | `title` |
| `aliases` | `array[string]` | `aliasesJson` | `aliases_json` | - | `aliases` |
| `kind` | `string` | `kind` | `kind` | - | `"standard"` / `"special"` |
| `synopsis` | `string / null` | `synopsis` | `synopsis` | `movies.description` | `synopsis` |
| `duration_ms` | `long / null` | `durationMs` | `duration_ms` | `movies.runtime` (mins) | Thời lượng phát |
| `release_date` | `string / null` | `releaseDate` | `release_date` | `movies.release_year` | Ngày phát sóng |
| `primary_language` | `string / null` | `primaryLanguage` | `primary_language` | - | Ngôn ngữ thoại chính |
| `genre_ids` | `array[string]` | `genreIdsJson` | `genre_ids_json` | `movies.genres` | `genres` |
| `character_ids` | `array[string]` | `characterIdsJson`| `character_ids_json`| - | Danh sách nhân vật xuất hiện |
| `record` | `object` | `recordJson` | `record_json` | - | Audit & provenance |
| - | - | `rawJson` | `raw_json` | - | JSON gốc nguyên vẹn |
| - | - | `version` | `opt_lock_version`| - | `@Version` |

#### 2.4. Phân Đoạn & Truyện Ngắn (`segments` -> `catalog_segments`)
| Hợp đồng JSON | Kiểu JSON | Entity JPA | Cột CSDL | Chỉ mục AI | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `string` | `id` | `id` | `id` | Định danh phân đoạn |
| `episode_id` | `string` | `episodeId` | `episode_id` | `episode_id` | Khóa ngoại tập phim |
| - | - | - | - | `series_id` | Tự động suy diễn từ tập cha |
| `position` | `int` | `position` | `position` | Vị trí trong tập |
| `title` | `string` | `title` | `title` | `title` | Tiêu đề mẩu chuyện/đoạn |
| `synopsis` | `string / null` | `synopsis` | `synopsis` | `synopsis` | Nội dung cốt truyện |
| `episode_start_ms` | `long / null` | `episodeStartMs` | `episode_start_ms` | `start_ms` | Mốc bắt đầu logic |
| `episode_end_ms` | `long / null` | `episodeEndMs` | `episode_end_ms` | `end_ms` | Mốc kết thúc logic |
| `character_ids` | `array[string]` | `characterIdsJson` | `character_ids_json`| `characters` | Nhân vật trong đoạn |
| `plot_facts` | `array[string]` | `plotFactsJson` | `plot_facts_json` | `plot_facts` | Tình tiết nhớ của CineBot |
| `record` | `object` | `recordJson` | `record_json` | Audit | Revision |
| - | - | `rawJson` | `raw_json` | Toàn vẹn | Raw JSON |
| - | - | `version` | `opt_lock_version`| Khóa | `@Version` |

#### 2.5. Phân Cảnh Hành Động (`scenes` -> `catalog_scenes`)
| Hợp đồng JSON | Kiểu JSON | Entity JPA | Cột CSDL | Chỉ mục AI | Deep Linking URL |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `string` | `id` | `id` | `id` | `?scene={id}` |
| `episode_id` | `string` | `episodeId` | `episode_id` | `episode_id` | `?episode={episodeId}` |
| - | - | - | - | `series_id` | Đường dẫn gốc `/series/{seriesId}` |
| `segment_id` | `string / null` | `segmentId` | `segment_id` | `segment_id` | Đoạn chứa cảnh |
| `media_asset_id` | `string` | `mediaAssetId` | `media_asset_id` | `media_asset_id` | `?asset={mediaAssetId}` |
| `start_ms` | `long` | `startMs` | `start_ms` | `start_ms` | `?t={startMs}` |
| `end_ms` | `long` | `endMs` | `end_ms` | `end_ms` | Mốc kết thúc cảnh |
| `title` | `string / null` | `title` | `title` | `title` | Tiêu đề cảnh |
| `summary` | `string / null` | `summary` | `summary` | `synopsis` | Tóm tắt cảnh |
| `visual_description`| `string / null` | `visualDescription`| `visual_description`| `visual_summary` | Mô tả hành động/hình ảnh |
| `transcript_cue_ids`| `array[string]` | `transcriptCueIdsJson`| `transcript_cue_ids_json`| Thoại phụ đề | Cues đối thoại |
| `record` | `object` | `recordJson` | `record_json` | Audit | Revision |
| - | - | `rawJson` | `raw_json` | Toàn vẹn | Raw JSON |
| - | - | `version` | `opt_lock_version`| Khóa | `@Version` |

#### 2.6. Tài Nguyên Phát (`media_assets` -> `catalog_media_assets` & `media_assets`)
| Hợp đồng JSON | Kiểu JSON | Entity JPA | Cột CSDL | Ánh xạ Legacy (`media_assets`) | Trình Phát Web |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `string` | `id` | `id` | `media_assets.id` | Stream URL `/api/media/stream/{id}` |
| `storage.provider` | `string` (`drive`/`local`) | `storageProvider` | `storage_provider` | `media_assets.storage_provider` | Phân giải Drive/Local |
| `storage.storage_key`| `string` | `storageKey` | `storage_key` | Kiểm tra allowlist máy chủ | Xác thực danh mục an toàn |
| `storage.relative_path`| `string` | `relativePath` | `relative_path` | `media_assets.file_path` | Chống path traversal |
| `storage.drive_file_id`| `string / null` | `driveFileId` | `drive_file_id` | `media_assets.drive_file_id` | Phát trực tiếp Google Drive |
| `size_bytes` | `long` | `sizeBytes` | `size_bytes` | `media_assets.file_size` | Hỗ trợ HTTP 206 Byte-Range |
| `duration_ms` | `long / null` | `durationMs` | `duration_ms` | `media_assets.duration_seconds` | Thanh thời lượng video |
| `coverage` | `array[object]` | `coverageJson` | `coverage_json` | Ánh xạ tới tập / đoạn | Kiểm tra khớp tập khi phát |
| `access_policy` | `string` | `accessPolicy` | `access_policy` | Quyền truy cập video | Mặc định `"public"` |
| `record` | `object` | `recordJson` | `record_json` | Audit | Revision |
| - | - | `rawJson` | `raw_json` | Toàn vẹn | Raw JSON |
| - | - | `version` | `opt_lock_version`| Khóa | `@Version` |

---

### 3. Quy Tắc Bảo Toàn Dữ Liệu & Khóa Lạc Quan
1. **Toàn vẹn JSON gốc (`raw_json`):** Mọi trường mở rộng, chú thích tùy biến trong schema `dippie.catalog.v1` được lưu giữ 100% trong cột `raw_json`. Khi API `/api/catalog/export` xuất dữ liệu cho FastAPI hoặc sao lưu, payload được tái tạo với độ chính xác tuyệt đối mà không bị rụng trường.
2. **Khóa lạc quan (`opt_lock_version`):** Cả 12 bảng thực thể đều tích hợp cột `opt_lock_version` kiểu `BIGINT NOT NULL DEFAULT 0` kết hợp annotation `@Version` của Jakarta Persistence. Bất kỳ thao tác ghi đè đồng thời nào không đúng phiên bản đều kích hoạt `OptimisticLockingFailureException` ngay lập tức, ngăn ngừa hoàn toàn tình trạng mất dữ liệu do race condition.
