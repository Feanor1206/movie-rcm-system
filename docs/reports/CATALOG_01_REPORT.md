# BÁO CÁO KỸ THUẬT NHIỆM VỤ: CATALOG-01
## Import Dữ Liệu Hoạt Hình JSON (dippie.catalog.v1), Nối Web & Hệ Thống Tìm Phim AI

- **Repository:** `D:\Class\movie-rcm-system`
- **Branch:** `dev`
- **Tiêu chuẩn dữ liệu:** `docs/contracts/animation-catalog-v1/dippie.catalog.v1.schema.json`
- **Ngày hoàn thành:** 16/10/2026
- **Trạng thái:** **HOÀN THÀNH TOÀN DIỆN (100% PASS)**

---

## 1. Tổng quan kiến trúc & Luồng dữ liệu hoàn chỉnh

```
                                [ JSON Bên ngoài (dippie.catalog.v1) ]
                                                  │
                                                  ▼
                         [ Giao diện Admin: /admin/import ]
                                                  │
                 ┌────────────────────────────────┴──────────────────────────────┐
                 │ 1. Validate & Preview                                         │ 2. Commit Import
                 ▼                                                               ▼
[ POST /api/admin/catalog/validate ]                            [ POST /api/admin/catalog/import ]
 (Spring Boot CatalogValidator)                                  (Spring Boot CatalogImportService)
 - Kiểm tra cấu trúc & header contract                           - `@Transactional` atomic transaction
 - JSON Pointer error reporting (`/episodes/0/duration_ms`)       - Idempotency & Revision check
 - Diff preview: toCreate, toUpdate, unchanged, conflicts        - Lưu 12 bảng Catalog Database
                                                                 - Tự động map vào `media_assets` & `movies`
                                                                 - Trigger POST /api/index/sync
                                                                                 │
                                    ┌────────────────────────────────────────────┴───────────────────────────┐
                                    ▼                                                                        ▼
                     [ Spring Boot Data & Streaming ]                                        [ FastAPI AI Retrieval & Chat ]
                      - 12 bảng JPA Entity quan hệ                                            - CatalogSyncManager (Flattening 4 cấp)
                      - `/api/catalog/series`, `/series/{id}`                                - HybridMovieIndex (BM25 + e5-small)
                      - `/api/catalog/episodes/{id}`                                         - Item type normalization (Vi -> En)
                      - `/api/catalog/search`                                                - Qwen3-4B LoRA NLU & Grounded Stage 5
                      - `/api/media/stream/{assetId}`                                        - `/api/chat`, `/v1/discover`, `/api/recommend`
                      (Google Drive HTTP 206 Byte Range)                                                     │
                                    │                                                                        │
                                    └────────────────────────────────────────────┬───────────────────────────┘
                                                                                 ▼
                                                                [ Next.js Frontend Web Experience ]
                                                                 - `/admin/import`: Upload, Preview diff, Commit
                                                                 - `/series/[id]`: Xem bộ, chọn tập, xem mô tả
                                                                 - Player: Phát video Google Drive thật (HTTP 206)
                                                                 - Timeline Cảnh: Bấm phân cảnh -> Tua trực tiếp `start_ms`
                                                                 - `/search`: Tìm đa cấp bộ, tập, phân cảnh
                                                                 - CineBot Chat: Trả lời dựa trên catalog hoạt hình thật
```

---

## 2. Chi tiết triển khai theo tầng

### 2.1 Spring Boot Backend — DDL, Entity, Validator, Importer & REST API

#### A. DDL & Schema Database (12 Bảng Catalog):
- Đã bổ sung 12 bảng chuẩn vào [schema.sql](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/resources/schema.sql):
  1. `catalog_packages`: Quản lý gói package, phiên bản revision, metadata.
  2. `catalog_genres`: Thể loại chuẩn (`id`, `name`, `description`).
  3. `catalog_attribute_scales`: Thang đo định lượng/tương đối (`darkness_v1`, `pacing_v1`).
  4. `catalog_sources`: Nguồn gốc xuất xứ (franchise, IP owner, license).
  5. `catalog_series`: Bộ phim hoạt hình cha (`title`, `original_title`, `aliases`, `synopsis`, `themes`).
  6. `catalog_seasons`: Phần/mùa trong bộ (`series_id`, `season_number`, `title`, `episode_count`).
  7. `catalog_episodes`: Tập phim (`series_id`, `season_id`, `number`, `duration_ms`, `plot_facts`, `attributes`).
  8. `catalog_segments`: Đoạn/truyện ngắn trong tập (`episode_id`, `start_ms`, `end_ms`, `plot_facts`, `attributes`).
  9. `catalog_characters`: Nhân vật hoạt hình (`name`, `role`, `aliases`, `description`).
  10. `catalog_media_assets`: File video/audio (`content_type`, `role`, `drive_file_id`, `coverage`).
  11. `catalog_text_tracks`: Phụ đề / transcript (`media_asset_id`, `language`, `cues`).
  12. `catalog_scenes`: Phân cảnh chi tiết (`episode_id`, `segment_id`, `media_asset_id`, `start_ms`, `end_ms`, `visual_description`, `sound_events`).

#### B. Validator chuẩn Contract (`dippie.catalog.v1`):
- Triển khai tại [CatalogValidator.java](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/catalog/CatalogValidator.java):
  - Định dạng báo lỗi theo **JSON Pointer** RFC 6901 (ví dụ: `/episodes/0/duration_ms`).
  - Kiểm tra tính duy nhất ID toàn cục (Global ID uniqueness) qua tất cả các collection và cue phụ đề.
  - Kiểm tra quan hệ toàn vẹn: `series_id`, `season_id`, `episode_id`, `media_asset_id`, `character_ids`.
  - Kiểm tra tính hợp lệ của mốc thời gian: `start_ms < end_ms`, không vượt quá thời lượng tập, khoảng phụ đề không trùng lặp và tăng đơn điệu.

#### C. Dịch vụ Import có Transaction & Quản lý Xung Đột:
- Triển khai tại [CatalogImportService.java](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/service/catalog/CatalogImportService.java):
  - `validateAndPreview`: Tính toán diff trực quan (`toCreate`, `toUpdate`, `unchanged`, `conflicts`) mà không ghi vào DB.
  - `importPackage`: Bọc trong `@Transactional(rollbackFor = Exception.class)`. Đảm bảo tính nguyên tử (Atomic Ingestion) — nếu 1 bản ghi lỗi, toàn bộ package sẽ rollback.
  - Quản lý phiên bản revision: Nếu `package_id` đã tồn tại với revision cũ/trùng lặp, hệ thống phát hiện và yêu cầu tăng revision hoặc giữ nguyên trạng nếu không đổi.
  - Tự động đồng bộ Media Service: Tự động ghi nhận `CatalogMediaAsset` vào bảng `media_assets` và `movies` cốt lõi, sinh URL phát `/api/media/stream/{assetId}` hỗ trợ stream video Drive qua HTTP 206 Partial Content.
  - Tự động gọi sang FastAPI endpoint `POST /api/index/sync` để cập nhật index BM25 và Vector.

#### D. REST Controllers:
- [AdminCatalogController.java](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/controller/AdminCatalogController.java):
  - `POST /api/admin/catalog/validate`: Dry-run validation & preview diff.
  - `POST /api/admin/catalog/import`: Transactional commit import.
  - `GET /api/admin/catalog/history`: Lịch sử các gói catalog đã nhập.
- [CatalogController.java](file:///D:/Class/movie-rcm-system/backend/springboot/src/main/java/com/dippie/moviercm/controller/CatalogController.java):
  - `GET /api/catalog/series`: Danh sách bộ phim hoạt hình.
  - `GET /api/catalog/series/{id}`: Chi tiết bộ phim, danh sách mùa và tập.
  - `GET /api/catalog/episodes/{id}`: Chi tiết tập, đoạn phân đoạn (segments) và danh sách cảnh (scenes) kèm mốc thời gian `start_ms`.
  - `GET /api/catalog/search`: Tìm kiếm đa cấp (bộ, tập, phân cảnh).
  - `GET /api/catalog/export`: Xuất snapshot catalog chuẩn JSON contract.

---

### 2.2 FastAPI AI Search & Chatbot — Trích xuất Đa cấp, BM25 + Vector, Qwen Stage 5 Grounding

#### A. CatalogSyncManager (Làm phẳng dữ liệu 4 cấp):
- Triển khai tại [catalog_sync.py](file:///D:/Class/movie-rcm-system/backend/fastapi/services/catalog_sync.py):
  - Làm phẳng toàn bộ hệ phân cấp (`series`, `episode`, `segment`, `scene`) thành các đơn vị tìm kiếm độc lập.
  - Xây dựng văn bản mô tả tìm kiếm đa tầng (`searchable_text`) bao gồm: tiêu đề chính, bí danh (aliases), nhân vật và vai trò, tóm tắt, sự thật cốt truyện (plot facts), mô tả hình ảnh cảnh quay (visual description) và âm thanh (sound events).
  - Chuẩn hóa thang đo thuộc tính (`attributes`) thành định dạng thang điểm (`darkness_v1`, `pacing_v1`) phục vụ lọc và xếp hạng so sánh (comparative ranking).

#### B. True Hybrid Search & Chuẩn hóa Thực thể:
- Triển khai tại [hybrid_retrieval.py](file:///D:/Class/movie-rcm-system/backend/fastapi/services/hybrid_retrieval.py):
  - Thuật toán Robertson-Spärck Jones BM25 kết hợp dense multilingual embedding (`intfloat/multilingual-e5-small`).
  - Trọng số trường tùy biến: `title` (3.0x), `aliases` (2.5x), `characters` (2.0x), `plot_facts` (1.8x), `scenes` (1.5x), `synopsis` (1.0x).
  - Bổ sung bộ từ điển `ITEM_TYPE_SYNONYMS` chuẩn hóa tiếng Việt:
    - `"phân cảnh"`, `"cảnh quay"`, `"đoạn trích"` $\rightarrow$ `scene`
    - `"phân đoạn"`, `"truyện ngắn"`, `"tiểu phẩm"` $\rightarrow$ `segment`
    - `"tập"`, `"tập phim"`, `"chương"` $\rightarrow$ `episode`
    - `"bộ"`, `"loạt phim"`, `"phim bộ"` $\rightarrow$ `series`
  - Đảm bảo các truy vấn như *"cảnh xe địa hình nhảy qua hẻm núi"* ưu tiên trả về đúng thực thể cảnh (scene) thay vì cả bộ phim chung chung.

#### C. Qwen3-4B LoRA Grounded Explanation (Chống ảo giác):
- Triển khai tại [ai_pipeline.py](file:///D:/Class/movie-rcm-system/backend/fastapi/services/ai_pipeline.py):
  - Loại bỏ hoàn toàn giới hạn 12 bộ phim tĩnh mặc định. Pipeline tự động tìm kiếm trên toàn bộ catalog động.
  - Đánh giá ràng buộc so sánh (Comparative Constraints) phát hiện rõ trạng thái thiếu dữ liệu thuộc tính (`missing_trait_data`) thay vì tự suy đoán.
  - Stage 5 Grounded Storyteller: Nhúng mốc thời gian chính xác (`01:10–01:35`), tên tập/bộ cha, chi tiết hình ảnh thực tế và sự thật cốt truyện vào câu trả lời, không bịa đặt nội dung hư cấu.

---

### 2.3 Next.js Frontend — Quản trị Nhập liệu, Xem Phim & Tua Cảnh Trực Tiếp

#### A. Trang Quản Trị Nhập Dữ Liệu (`/admin/import`):
- Triển khai tại [page.tsx](file:///D:/Class/movie-rcm-system/frontend/app/admin/import/page.tsx) & [CatalogImportModal.tsx](file:///D:/Class/movie-rcm-system/frontend/features/admin/components/CatalogImportModal.tsx):
  - Hỗ trợ tải file JSON kéo thả hoặc dán chuỗi JSON trực tiếp.
  - Nút **"Validate & Preview"**: Gửi payload dry-run lên backend, hiển thị bảng diff số lượng thực thể sẽ tạo mới (`toCreate`), cập nhật (`toUpdate`), giữ nguyên (`unchanged`), hoặc xung đột (`conflicts`). Báo rõ vị trí lỗi JSON Pointer nếu có.
  - Nút **"Xác nhận Import"**: Thực hiện commit có transaction vào cơ sở dữ liệu và tự động gọi AI Index Sync.
  - Bảng lịch sử các gói catalog đã nhập thành công.

#### B. Trang Chi Tiết Bộ Phim & Player Tua Cảnh (`/series/[id]`):
- Triển khai tại [page.tsx](file:///D:/Class/movie-rcm-system/frontend/app/series/[id]/page.tsx):
  - Trình duyệt phân cấp: Bộ phim $\rightarrow$ Danh sách phần (Seasons) $\rightarrow$ Danh sách tập (Episodes).
  - Video Player tích hợp HTML5 hỗ trợ phát video Google Drive / Local Storage qua endpoint `/api/media/stream/{assetId}` với chuẩn HTTP 206 Partial Content (Byte Range requests).
  - **Tua Cảnh Trực Tiếp (Scene Seek):** Danh sách cảnh quay hiển thị mốc thời gian dạng `mm:ss` kèm tóm tắt hình ảnh. Khi người dùng bấm vào bất kỳ phân cảnh nào, hàm `handleSeekToScene(start_ms)` lập tức gán `playerRef.current.currentTime = start_ms / 1000.0`, cuộn video đến đúng giây bắt đầu của cảnh và phát mượt mà.

#### C. Tích Hợp Tìm Kiếm & CineBot Chat:
- [SearchExperience.tsx](file:///D:/Class/movie-rcm-system/frontend/features/search/components/SearchExperience.tsx): Kết nối với `searchAnimationCatalog`, hiển thị kết quả tìm kiếm đa cấp (gắn nhãn rõ ràng: `BỘ PHIM`, `TẬP PHIM`, `PHÂN ĐOẠN`, `PHÂN CẢNH`) dẫn thẳng đến trang chi tiết.
- [route.ts](file:///D:/Class/movie-rcm-system/frontend/app/api/chat/route.ts): Gỡ bỏ danh sách 12 phim mẫu cố định, nối trực tiếp vào FastAPI dynamic hybrid search.

---

## 3. Bằng chứng kiểm thử & Xác minh chất lượng

### 3.1 Spring Boot Test Suite (15/15 PASS)
```powershell
mvn test -Dtest=CatalogValidatorTest,CatalogImportServiceTest
```
- `CatalogValidatorTest`: **9/9 PASS**
  - `testValidateValidCatalog`: PASS
  - `testValidateMissingHeader`: PASS
  - `testValidateDuplicateIdsAcrossCollections`: PASS
  - `testValidateOrphanedSeason`: PASS
  - `testValidateOrphanedEpisode`: PASS
  - `testValidateOrphanedMediaAsset`: PASS
  - `testValidateNegativeOrInvertedTimeIntervals`: PASS
  - `testValidateCueIntervals`: PASS
  - `testValidateJsonPointerFormat`: PASS
- `CatalogImportServiceTest`: **6/6 PASS**
  - `testValidateAndPreviewDiff`: PASS
  - `testImportValidPackageAtomicCommit`: PASS
  - `testImportIdempotentRevision`: PASS
  - `testImportConflictOnOldRevision`: PASS
  - `testImportRegistersMediaAssetsAndMovies`: PASS
  - `testImportAtomicRollbackOnError`: PASS
- **Kết quả:** `BUILD SUCCESS` (0 failures, 0 errors).

### 3.2 FastAPI AI Search & Pipeline Test Suite (12/12 PASS)
```powershell
& "C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe" -m unittest backend/fastapi/tests/test_catalog_retrieval.py
```
- `test_01_catalog_flattening_entities`: PASS (Làm phẳng đúng 2 series, 2 episodes, 1 segments, 1 scenes)
- `test_02_retrieval_by_series_title`: PASS (Tìm đúng "Biên Niên Sử Dippie")
- `test_03_retrieval_by_episode_title`: PASS (Tìm đúng tập "Bình Minh Trên Sao Hỏa")
- `test_04_retrieval_by_character_alias`: PASS (Tìm theo alias nhân vật "Tiểu Bảo", "Hacker Chi")
- `test_05_retrieval_by_plot_fact_memory`: PASS (Tìm theo ký ức cốt truyện "chìa khóa năng lượng nguyên thủy")
- `test_06_retrieval_by_scene_description`: PASS (Tìm phân cảnh "xe địa hình phóng qua bờ vực sâu đá đỏ")
- `test_07_hard_constraint_genre_exclusion`: PASS (Lọc loại trừ thể loại kinh dị Horror)
- `test_08_hard_constraint_year_filtering`: PASS (Lọc năm phát hành >= 2025)
- `test_09_comparative_constraint_diagnostics_when_trait_missing`: PASS (Báo lỗi chẩn đoán khi thiếu thang đo thuộc tính)
- `test_10_comparative_constraint_evaluation_when_trait_present`: PASS (Tính điểm so sánh khi thuộc tính đã được hiệu chuẩn)
- `test_11_grounded_stage_5_explanation`: PASS (Lời giải thích bám sát mốc thời gian 01:10–01:35 và nhân vật)
- `test_12_fastapi_endpoints_sync_and_serve_real_catalog`: PASS (`/api/index/sync`, `/api/chat`, `/v1/discover`, `/api/recommend`)
- **Kết quả:** `Ran 12 tests in 58.4s - OK`.

### 3.3 Frontend Compilation & Type Checking
```powershell
npx tsc --noEmit
```
- **Kết quả:** Exit code `0` (Zero errors).

---

## 4. Hướng dẫn vận hành nhanh (Runbook)

1. **Khởi động hệ thống:**
   - Spring Boot: `scripts/start_backend_dev.ps1` (Port 8080)
   - FastAPI AI: conda env `dippie-qwen` chạy `uvicorn main:app --port 8000` (Port 8000)
   - Frontend Next.js: `pnpm dev` (Port 3000)
2. **Nhập dữ liệu hoạt hình:**
   - Truy cập: `http://localhost:3000/admin/import`
   - Bấm **"Nhập gói Catalog"**, chọn file JSON (ví dụ: `docs/contracts/animation-catalog-v1/catalog.example.json`).
   - Bấm **"Validate & Xem trước Diff"** để kiểm tra tính hợp lệ và danh sách thực thể sẽ import.
   - Bấm **"Xác nhận Import"** để ghi dữ liệu vào cơ sở dữ liệu và đồng bộ hóa AI index.
3. **Trải nghiệm xem phim & tua cảnh:**
   - Truy cập: `http://localhost:3000/series/ser_demo`
   - Chọn tập bất kỳ, video Google Drive sẽ bắt đầu phát trực tiếp qua HTTP 206 Partial Content.
   - Trong bảng **"Danh sách Phân cảnh"**, bấm vào cảnh quay bất kỳ (ví dụ: `01:10 - Cú Nhảy Vực Thẳm`) $\rightarrow$ Video sẽ tự động nhảy đến giây thứ 70 (`start_ms: 70000`).
4. **Hỏi đáp AI CineBot:**
   - Mở cửa sổ CineBot chat, gõ câu hỏi: *"Tìm phân cảnh xe địa hình nhảy qua hẻm núi"*
   - Bot sẽ trích xuất đúng phân cảnh từ catalog thực tế kèm thời gian và mô tả chi tiết thay vì đưa ra các bộ phim mẫu cũ.
