# CATALOG-01-F01 — REQUEST CHANGES

Ngày review: 2026-10-16. Workspace `D:\Class\movie-rcm-system`, branch `dev`.
HEAD quan sát: `adf0dee0655fad19102b39f31d203aeaed42d906`; baseline trong manifest: `c2d29c04edd58c4cc0a6e648d316285a9377384f` (resolve được thành commit).

**Chưa nghiệm thu snapshot.** F01 sửa được các case probe cũ, thêm auth admin, raw_json và một số guard, nhưng các gate vận hành chính còn lỗi. Không sửa application, không chạy Gemini CLI/automation, không load GPU/model, không mount hoặc đụng DB live trong review.

## Những điểm đã xác minh đạt hoặc tiến bộ

- 28/28 SHA256 trong manifest khớp lúc bắt đầu và không drift lúc kiểm tra lại. Đây chỉ là phạm vi manifest, không phải toàn bộ source catalog.
- So sánh cả 5 file contract với ZIP đã giao trên Desktop: byte-for-byte giống nhau. Resource schema trong backend cũng bằng schema gốc. **Giữ nguyên schema này.**
- Chạy reviewer probe cũ: 6 case validator cho kết quả mong đợi; 2 input hợp lệ aliases object/null segment times không còn exception. Đây là 8 case giới hạn, không chứng minh toàn bộ Draft2020-12 hoặc toàn pipeline.
- SecurityConfig yêu cầu ADMIN, controller có method authorization; legacy public flag và provider được sửa. Chưa coi là HTTP auth/storage integration pass vì review không khởi động server.
- Search URL có episode/scene/asset/time và episode response có generation guard. Chưa đạt playback identity/readiness như finding bên dưới.
- `git apply --check -R docs/reports/CATALOG_01_F01.patch` exit0. Chỉ kiểm tra reverse applicability, không áp dụng patch vào working tree.

## Kiểm tra độc lập mới

1. `python docs/reviews/repro/CATALOG_01_F01_probe.py`: compile source Java CatalogValidator hiện tại vào temp và gọi trực tiếp; gọi CatalogSyncManager không pipeline/model. Evidence: `docs/reviews/evidence/CATALOG_01_F01_probe.json`.
2. `python docs/reviews/repro/CATALOG_01_F01_logic_probe.py`: compile source catalog hiện tại, gọi pure methods với repository proxy in-memory. Dùng dependency jars cache và bytecode legacy model có sẵn; không khởi động Spring/JPA/HTTP, không gọi importPackage. Evidence: `docs/reviews/evidence/CATALOG_01_F01_logic_probe.json`.

Không chạy lại full Maven/npm/GPU khi đã có blocker. Các số 15/15, 12/12, tsc trong handoff là bằng chứng do bên triển khai báo; review này không tái xác nhận chúng. Browser/Drive/model thật chưa được nghiệm thu qua các probes này. Test Python dùng fixture và TestClient; việc runtime có model CUDA không tự chứng minh tất cả kết quả test là inference/model/browser thật.

## F1 — P1: Service credential công khai trong frontend, auth sync vẫn bị bypass về bản chất

`frontend/lib/services/catalogService.ts:691` hardcode service token trong module được client component import. `backend/fastapi/main.py:145` dùng cùng giá trị làm default secret, và `CatalogImportService.java:1012` cũng hardcode giá trị đó. Không chép lại giá trị token trong review/evidence.

Người có frontend source/bundle có credential để gửi payload thay index toàn cục. Khi operator cấu hình secret mới ở FastAPI, Spring/browser còn hardcoded sẽ không sync được. Endpoint không có token trả401/sai token403 chưa khắc phục việc token thật được phát cho mọi client.

Sửa: xóa service credential khỏi browser/source/default fallback; server-to-server lấy secret từ cấu hình bên ngoài Git; fail closed khi chưa cấu hình. Browser gọi admin backend có session/token thật, không gọi service sync bằng shared credential. Thay credential mặc định nếu đang dùng. Test cả bundle không có secret, missing config và admin/user/anonymous.

## F2 — P1: Snapshot vẫn chỉ chứa package cuối, publish trước DB commit; “outbox” chưa có worker/retry

`CatalogImportService.java:385` importPackage là @Transactional; `843-859` gọi writeSnapshotToDisk(data), save snapshot rồi sync HTTP **trước method return/transaction commit**.

`969-995` ghi incoming package `data` vào committed_catalog_snapshot.json, không xuất toàn DB. `999-1034` gửi metadata package/revision/hash tới FastAPI, giữ network trong transaction. FastAPI request không có catalog sẽ load file (`main.py:165-175`), không xác minh body metadata tương ứng file hoặc DB đã commit.

Hậu quả:
- Nhập A rồi B: database có A+B nhưng file/index chỉ B. Browser cũng còn gọi sync với package vừa nhập.
- DB commit fail sau disk/HTTP: index có thể chứa dữ liệu rollback. Atomic rename không làm file/HTTP trở thành DB transaction.
- JVM/HTTP không sẵn sàng: snapshot được đánh SYNC_PENDING nhưng không có consumer/retry implementation. Repository chỉ có findTopByOrderBySnapshotVersionDesc; không có scheduler/job/after-commit sync path xử lý pending.
- Retry package identical trả READY vô điều kiện (`421`), không đọc lại trạng thái sync.
- File path vẫn đoán theo cwd/thư mục tồn tại; version dùng package revision, không phải global monotonic snapshot generation. Hai package cùng revision không có thứ tự global.

Sửa bằng DB outbox thật: commit entity+event trước, worker lấy snapshot toàn catalog eligible từ dữ liệu committed, publish có version/hash/ack đúng, retry và chống stale generation. Không mở transaction catalog khi network/model chạy. Test A+B, rollback sau flush/commit, process restart, sync failure/retry và job cũ hoàn thành muộn.

## F3 — P1: Runtime vẫn index draft/private; API public trả metadata và raw JSON không lọc

`catalog_sync.py:145-149`: include_draft=True/include_private=True mặc định. Runtime startup/load_from_file và sync endpoint gọi loader mà không đổi các flags. Probe dùng example hợp lệ có status=draft và asset=private: **4/4 searchable items vẫn được index**, scene giữ media_asset_id private.

`CatalogQueryService.java:61-101` dùng findAll/findById và assets enabled, không kiểm tra publication/access policy/owner. SecurityConfig cho public GET /api/catalog/**, gồm export. API trả entity có rawJson, storage path/Drive metadata; public flag của streaming không ngăn rò metadata qua catalog/search/chat.

Tắt auto demo fallback là tiến bộ nhưng không thay thế eligibility. Khi include_private=False, chỉ lọc asset mapping chưa đủ: scenes/transcript/metadata có thể vẫn đi vào index nếu không propagate policy.

Sửa: chốt public vs admin preview DTO/index; public mặc định deny draft/archived/private và kiểm tra parent eligibility. Internal export phải authenticated, không public raw storage/provenance nhạy cảm. Test anonymous search/detail/export/chat không thấy draft/private, admin preview đúng quyền.

## F4 — P1: Revision entity vẫn bị package revision nâng giả; key order gây conflict giả

`CatalogImportService.java:139-177`: extractRevision dùng Math.max(record.revision, packageRevision), trái yêu cầu giữ revision entity độc lập.

Probe gọi chính production evaluateDiff:
- Existing entity revision5; incoming record revision1, package revision10 → **UPDATE**, cần **CONFLICT**. Entity cũ vẫn có thể bị ghi đè bởi package revision cao.
- Cùng entity/nội dung/revision, chỉ đổi thứ tự key → **CONFLICT**, cần **UNCHANGED**. computeSha256 dùng JsonNode.toString/raw string, chưa canonicalize object keys.

Với genres/scales/sources không có record, cần policy riêng cho shared dictionary thay vì fallback package revision rồi conflict giả khi import lại cùng dictionary ở package khác.

Ngoài ra import luôn dựng CatalogPackage mới (`431-434`) có opt_lock_version khởi tạo0, thay vì update managed existing entity/version đã load. Cần regression nhiều lần tăng revision sau khi @Version đã tăng, cùng transaction concurrency thật; thêm @Version không tự chứng minh luồng update đúng.

## F5 — P1: storage_key chưa nối vào streaming; nhiều edition vẫn đụng unique constraint

StorageKeyConfig có resolvePath nhưng import chỉ gọi isAllowed (`739-745`). Streaming MediaAsset chỉ giữ provider/relativePath, không giữ storage_key; MediaStreamService vẫn chọn adapter chung theo provider. resolvePath không được gọi từ đường mở stream.

Ví dụ server allowlist demo_local trỏ localRoot/demo nhưng asset relative_path='clip.mp4': legacy stream mở localRoot/clip.mp4. Hai storage_key cùng provider/root khác nhau chưa được resolve đúng. Path resolver không được dùng không thể bảo đảm containment tại read boundary.

`syncToLegacyMediaAsset` luôn version=v1 (`960`); legacy entity có unique(movie_id,kind,version). Hai asset feature/edition cho cùng episode vì thế đụng unique constraint; coverage chỉ gắn episode đầu. Contract cho phép nhiều edition/file và một file nhiều tập nhưng adapter chưa đáp ứng.

Private được đổi thành public=false là sửa đúng một phần; authenticated cũng thành false trong khi MediaStreamService hiện từ chối mọi non-public, không có nhánh cấp quyền phát cho user đã đăng nhập. Cần thực thi policy thực và test đúng hai root, hai edition, hai episode chung file, role/audio và unknown size. Không thay schema để giới hạn các trường hợp này.

## F6 — P1: Scene đổi asset nhưng seek vẫn tác động video cũ; deep-link timer không giữ identity

`frontend/app/series/[id]/page.tsx:181-197`: handleSeekScene gọi setSelectedAsset rồi lập tức gán currentTime/play lên videoRef.current. React chưa commit src mới; thao tác áp vào asset cũ, src mới load có thể reset về0 hoặc nhận timestamp không thuộc nó.

Deep-link (`139-160`) dùng setTimeout300ms thay metadata/readiness event; timer không cleanup/generation/asset guard. Chuyển tập trước timer fire có thể tua nhầm video mới. initialDeepLinkHandledRef không reset khi URL scene thay đổi trên cùng route. AbortController được tạo nhưng signal không truyền vào getCatalogEpisodeDetail; chỉ generation guard là có tác dụng cho fetch.

Series fetch vẫn không có cancellation/generation guard, có thể overwrite state khi route đổi. Request lỗi/404 tập mới hiện bị swallow, chưa có error/retry rõ. Deep-link segment còn dùng logical timestamp như file time khi thiếu coverage conversion.

Sửa: pending seek mang tuple series/episode/asset/scene/generation, đợi đúng loadedmetadata/canplay rồi apply; invalidate khi identity đổi/unmount. Behavioral/browser tests phải chứng minh đúng asset/time cho slow A/B, scene khác edition và URL đổi; tsc không phải bằng chứng.

## F7 — P2: Validation chưa khớp contract; export vẫn không hợp lệ

Extended validator probe xác nhận contract từ chối nhưng Java trả0 lỗi:
- release_date='2026-99-99': chưa enforce format=date.
- source.url='not a uri': chưa enforce format=uri.
- rating value=0, scale_max=0: bỏ exclusiveMinimum=0.

Handwritten engine chỉ implement subset, không phải “100% Draft2020-12”. initSchema swallow lỗi và khi không tìm được schema thì bỏ structural validation thay vì fail closed. Cần tests resource packaged/cwd độc lập, malformed structural input không ném exception ở semantic phase, và mọi keyword thực sự có trong schema.

Probe gọi production exportSearchableCatalog với repository proxy trống: export thiếu schema_version, package.created_at/description và thêm package.contract_version/version ngoài schema. Contract validator trả4 lỗi. Đường DB có package cũng dùng cấu trúc header tương tự. raw_json đã giúp bảo toàn item nhưng chưa tạo được export hợp lệ. Cần full round-trip và populated export, không chỉ entity có thêm raw_json.

## F8 — P2: Manifest/patch chưa bao trọn dependency, bằng chứng đóng gate chưa đủ

- Hash28 mục và reverse patch check đạt; nhưng **31 file catalog DTO/entity/repository/resource cần thiết nằm ngoài manifest**. Resource schema không có trong F01 patch; các entity/repository chứa field mới/@Version/rawJson cũng chưa được hash đầy đủ. Phải reconstruct clean baseline rồi build/validate packaged resource trước khi khẳng định bàn giao tái lập được.
- FIELD_MAPPING_MATRIX và CROSS_REVIEW không thay thế round-trip/authorization/storage/index/browser checks.
- Status dùng tsc để đóng C8, test package/idempotency để đóng concurrency/outbox; không đủ phạm vi chứng minh.
- Chỉ targeted Java tests trên JDK25 chưa chứng minh CI JDK17; không có kết quả full frontend Node20 behavioral/production build/route budget trong handoff này.
- Status đặt lại tên các finding khiến C6/C9 gốc (committed index/publication) bị đánh CLOSED bằng test khác scope. Bảng sửa tiếp phải map về finding và trigger gốc, không chỉ tên mới.

## Gate bàn giao tiếp

Giữ nguyên contract và ZIP. Sửa F1–F8 theo ownership độc lập; ưu tiên credential/publication, commit/index và revision trước. Bổ sung tests chính xác cho các repro trên, full schema round-trip, HTTP auth trên H2 riêng, two-package/restart/retry/concurrency và browser playback identity. Không chạy GPU/model để thay thế các gate này.

Publish checkpoint frozen có hash toàn bộ dependency, patch reconstruct từ baseline và status PASS/FAIL/BLOCKED/NOT_RUN theo từng gate. Không báo “C1–C10 closed triệt để” khi các gate trên chưa đạt. Review này chưa commit/push, không deploy.
