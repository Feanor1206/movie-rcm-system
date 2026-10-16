# Review CATALOG-01 — chưa nghiệm thu

Ngày: 2026-10-16. Branch: `dev`. HEAD lúc review: `adf0dee0655fad19102b39f31d203aeaed42d906`.

Kết luận: **REQUEST CHANGES**. Có phần triển khai importer, bảng catalog, giao diện và truy xuất, nhưng chưa đạt contract hoặc luồng vận hành hoàn chỉnh. Không dùng kết luận “100% PASS/sẵn sàng vận hành” trong bàn giao làm acceptance. Không sửa application code, không import DB live, không mount Drive hoặc chạy model trong lượt review này.

## Bằng chứng độc lập và giới hạn

- `python docs/reviews/repro/CATALOG_01_contract_probe.py`: biên dịch **source CatalogValidator hiện tại** bằng javac, gọi trực tiếp với Jackson/Spring jars đã có; không khởi động Spring/database. Đối chiếu validator Python của contract. Example gốc hợp lệ ở cả hai; **5 payload sai schema bị contract từ chối nhưng production validator đều trả 0 lỗi**.
- Cùng probe gọi trực tiếp production `CatalogSyncManager`, không import pipeline/model: **2 payload hợp lệ theo contract gây TypeError**. Kết quả: `docs/reviews/evidence/CATALOG_01_contract_probe.json`.
- Các finding khác là kiểm tra source, không trình bày như HTTP/browser/Drive/transaction tests đã chạy.
- Không chạy lại toàn bộ Maven/npm/model suites vì đã có blocker tái lập được và artifact chưa đủ xác minh checkpoint. Số 15/15, 12/12, tsc là tuyên bố bàn giao, không phải số đo độc lập của review này. Typecheck không xác minh browser playback, auth, transaction hoặc search quality.
- 55 file source/artifact hiện có được chụp SHA256 ngoài Git và kiểm tra lại: không đổi trong khoảng review. Manifest bàn giao **không có SHA256**, nên không xác minh được tính khớp với checkpoint Gemini tuyên bố. Không sửa manifest/status của tác giả.

## C1 — P1: API import mở cho anonymous ở mọi profile

`SecurityConfig.java:87` dùng `.requestMatchers("/api/admin/catalog/**").permitAll()`. `AdminCatalogController.java:31-48` không có authorization annotation; chỉ import `PreAuthorize` không thực thi bảo vệ. Không có local-only/dev toggle.

Ảnh hưởng: người không đăng nhập có thể ghi catalog, cập nhật legacy movies/media và đọc lịch sử import nếu truy cập được backend. Đây là endpoint ghi thật, không phải dry-run.

Repro cần sau sửa: dùng isolated HTTP server/DB, POST import không token và user thường phải bị từ chối; admin hợp lệ mới được ghi. Không gửi request ghi vào server người dùng để chứng minh lỗi đã rõ trong source.

## C2 — P1: Import làm sai private policy và provider Drive

`CatalogImportService.java:584` ánh xạ chỉ chuỗi `google_drive` thành `drive`; contract chỉ cho `drive|local`, nên **asset hợp lệ provider=drive bị đổi thành local**. `:623` đặt `legacy.setPublic(true)` cho mọi asset, bỏ qua `access_policy`. `MediaStreamService.java:247-254` dựa vào flag public để cho truy cập asset.

Ảnh hưởng: chọn nhầm storage root/adapter; media private/authenticated thành public nếu tài nguyên tồn tại trong adapter được chọn. Hệ thống không enforce storage_key; importer đọc `root_storage_key` thay vì `storage_key`, rồi legacy stream không giữ mapping root theo asset.

Repro: fixture có hai root chứa cùng relative path, nhập asset `drive` và `private`; xác minh đúng root/adapter và anonymous không đọc được. Kiểm tra cả asset audio/trailer: code hiện gán mọi asset `feature`, `video/mp4` và version `v1`.

## C3 — P1: Backend không thực thi đầy đủ JSON Schema

`CatalogValidator.java:46-100` chỉ chặn cấu trúc/key lạ ở root, không có bước JSON Schema cho nested objects. Recursive walk không thay thế type/required/enum/format/additionalProperties validation.

Probe xác nhận cả năm case trả 0 lỗi production:
- thiếu `episodes[0].title`;
- `series[0].not_in_contract=true`;
- `package.revision="bad"`;
- `media_assets[0].enabled="false"`;
- `storage.provider="ftp"`.

Importer còn dùng `asInt/asBoolean/asText` để coercion/default. Đừng sửa bằng cách nới schema. Lỗi semantic dùng ID trong đường dẫn, ví dụ `/segments/seg_demo_001a`, không phải index của JSON array; đây không phải pointer trỏ được vào payload. Phải kiểm tra RFC6901 bằng resolve pointer thực, kể cả escaping.

## C4 — P1: Import/export mất nội dung cần để tìm phim

Mapping trong `CatalogImportService.java` dùng nhiều tên ngoài contract, trong khi không lưu bản raw từng record làm fallback round-trip:

| Contract | Importer hiện đọc | Hậu quả |
| --- | --- | --- |
| genres.labels | name/translations (`239-244`) | mất nhãn thể loại |
| sources.kind/title/note/retrieved_at | origin/source_type/name/notes (`278-285`) | mất nguồn/căn cứ |
| series.origin_countries/original_languages/release_year_start/end/release_status/character_ids | singular origin_country/original_language/release_year/status/characters (`306-313`) | mất năm/ngôn ngữ/nhân vật |
| seasons.number/synopsis/kind | season_number/description (`338-343`) | mất số/mô tả/loại mùa |
| episodes.number/kind/release_date/genre_ids/primary_language | episode_number/episode_type/air_date (`360-391`) | số tập/ngày phát và các field khác không được giữ đúng |
| media.size_bytes/edition_label/spoken_languages/storage.storage_key | byte_length/edition/language/root_storage_key (`450-465`) | size thành 0, mất metadata/root |
| scenes.title/summary/visual_description/visual_tags/provenance | visual_summary/dialogue_summary (`511-522`) | mất nội dung cảnh và nguồn |
| text_tracks.external_file object/provenance | external_file.asText (`490`) | mất object đường dẫn/hash và provenance |

Segments còn mất translations/primary_language; scale mất version/source_ids; characters đọc voice_actors thay voice_credits. Cần audit **toàn bộ schema**, không chỉ vài field trong bảng.

`CatalogQueryService.java:168-178` export entity dạng camelCase/JSON-as-string, thiếu genres/scales/sources/text_tracks/header, không tái tạo contract snake_case. `catalog_sync.py` lại mong contract gốc. Dữ liệu người dùng xây đúng schema chưa thể round-trip vào hệ thống mà không mất thông tin.

Importer/flatten còn tự đặt rating 8–8.5, năm 2025/2026 và poster ngoài nguồn. Unknown phải giữ unknown; adapter/frontend phải hỗ trợ thay vì tạo facts giả.

## C5 — P1: JSON hợp lệ làm hỏng sync tìm kiếm

Probe tái lập:
- Nhân vật có alias object `{text,language,kind}` đúng schema: `catalog_sync.py` ghép alias dict vào `char_names`, sau đó `dict.fromkeys` ném **unhashable type: 'dict'** (`162-168`, `228`, tương tự ở episode/segment/scene).
- Segment có `episode_start_ms=null`, `episode_end_ms=null` đúng schema: phép `end_ms - start_ms` (`367`) ném **unsupported operand type(s) for -: 'NoneType' and 'NoneType'**.

Cả hai input được contract validator xác nhận 0 lỗi. Fixture test dùng alias string và timestamp có sẵn không bảo vệ input thực.

## C6 — P1: DB và index không có cùng snapshot; READY không phản ánh thực tế

`CatalogImportService.java:528-538,628-639`: ghi **chỉ package vừa nhập** vào một file relative `data/catalog/imported_catalog.json`, ngay trong transaction, swallow lỗi và trả indexStatus=READY. Không có server-side sync vào FastAPI; request sync chỉ được gọi từ browser (`CatalogImportModal.tsx:116-124`).

`CatalogSyncManager.load_from_payload` thay toàn bộ state (`483-495`), không merge DB catalog. Luồng A import → B import làm index chỉ còn B khi browser sync; restart cũng chỉ đọc file package cuối, hoặc không tìm thấy vì working directory Spring/FastAPI khác nhau. Client đóng tab/API import trực tiếp không kích hoạt sync. File có thể được ghi trước DB commit; lỗi commit không rollback file. `triggerAiIndexSync` không kiểm tra res.ok nên JSON HTTP500 vẫn có thể hiện “đồng bộ thành công”.

Yêu cầu: snapshot từ DB đã commit, toàn catalog eligible, outbox/job/version/freshness và retry; READY chỉ khi bằng chứng index đúng revision. Integration test nhập hai package, restart, failure injection và retry idempotent.

## C7 — P1: Version policy chỉ bảo vệ package, không bảo vệ entity dùng chung

`CatalogImportService.java:201-225` chỉ xét revision/hash của package ID. Entity được findById rồi ghi đè; revision entity bị đặt bằng package revision (`321`, `394`, tương tự). Không so sánh `record.revision` hoặc nội dung entity hiện có. Package B mới/revision thấp vẫn có thể ghi đè series/character của package A đã có revision cao. Có thể tạo global ID collision giữa các bảng qua hai package dù trong từng payload ID không trùng.

`synchronized` trên service chỉ là khóa JVM, không phải database concurrency/version policy; transaction commit của proxy diễn ra ngoài method body. Không có @Version/lock ở CatalogPackageRepository/entity để bảo đảm xung đột liên tiến trình. Cần test entity chung + hai import đồng thời và commit riêng thực, không chỉ transaction test bao ngoài.

Dry-run (`119-175`) chỉ đếm package/series/episodes/assets, bỏ các collection còn lại, và luôn đếm entity tồn tại là update kể cả identical. Preview không khớp diff 12 collection đã hứa.

## C8 — P1: Kết quả scene/segment không dẫn đến đúng nội dung; player có stale identity

`CatalogQueryService.java:129-158` trả scene/segment `seriesId=null`; `SearchExperience.tsx:542-544` fallback `/series/{item.id}`. Route đó gọi getSeriesDetail với scene/segment ID nên không tìm thấy bộ. Episode result chỉ mở bộ, không truyền episode ID; page luôn chọn tập đầu (`series/[id]/page.tsx:87-89`). Không có deep-link scene/timestamp/asset.

Page episode fetch (`104-127`) không abort/generation guard hoặc clear detail/asset ngay khi đổi tập. B trả trước A thì A có thể overwrite; B trả404/throw thì giữ video A dưới tiêu đề B. Seek scene (`136-143`) không kiểm tra/switch `scene.mediaAssetId` và highlight cũng không filter asset. Multi-edition/file khác sẽ tua nhầm video. Coverage của file tổng hợp không giới hạn playback theo tập.

Cần behavioral/browser test đổi tập nhanh, lỗi tập mới, scene khác edition, search→đúng episode/asset/time và keyboard activation. Không lấy tsc làm bằng chứng này.

## C9 — P1: Example hư cấu tự vào catalog chạy thật và sync không có quyền quản trị

`catalog_sync.py:26-29,513-523` dùng `catalog.example.json` làm fallback mặc định. Startup `main.py:50` gọi loader. Fixture draft/hư cấu được trả như dữ liệu thật; flatten không enforce record eligibility/access policy. Điều này trái yêu cầu không publish sample và không lấy draft làm verified.

`main.py:145-189` cho `/api/index/sync` không auth; nhận payload hoặc đường dẫn file từ client rồi thay index toàn cục. Đây là chức năng ghi trạng thái dùng chung, không phải public search. Cần service/admin authentication, không nhận filesystem path tùy ý, demo mode explicit/off mặc định và filter eligibility.

## C10 — P2: Artifact và bằng chứng bàn giao chưa tái lập được

- Manifest không có SHA256/baseline/checkpoint cụ thể, thiếu danh mục entity/repository/DTO và chỉ sai hai đường dẫn test (thực tế có thêm thư mục `/service/catalog/`).
- `git apply --check -R docs/reports/CATALOG_01.patch` exit1: nhiều hunk không khớp, có invalid path `.../service/catalog\CatalogValidator.java`. Không áp dụng patch thật; chỉ read-only check. Cần tạo patch đường dẫn Git portable, kiểm tra reconstruct trong temp checkout và normalize line endings có ghi nhận.
- Status chỉ COMPLETED/PASS, thiếu phân biệt schema/import fixture/web/browser/Drive thật/model thật và thiếu ready_for_review/FROZEN identity.
- Cross-review kết luận optimistic locking, full Drive/player verification và zero regressions không được chứng minh bởi các test liệt kê. Không có verifier/agent ownership/finding trail đầy đủ trong báo cáo; không suy luận số agent thật từ tài liệu.

## Gate cho lượt sửa tiếp

1. Không đổi contract/ZIP người dùng đang xây dữ liệu để hợp thức hóa importer sai.
2. Sửa C1–C9 và bổ sung repro thành regression; audit schema→DB→API→index theo từng field, null và status.
3. Chạy integration thật trên DB riêng: auth, two-package, shared entity revision, rollback, concurrency, restart/index, search deep link và đúng asset.
4. Chạy CI backend/frontend (bao gồm production build và route budget), browser flow và phân loại Drive/model evidence trung thực. Không tự tải model/cài/mount hay đụng live DB.
5. Đóng băng checkpoint mới, hashes/source/patch nhất quán, report tách PASS/FAIL/BLOCKED/NOT_RUN. Review lại trước acceptance.

Lượt này chỉ tạo review/repro/evidence; không sửa application, không commit/push hay gọi Gemini CLI/automation.
