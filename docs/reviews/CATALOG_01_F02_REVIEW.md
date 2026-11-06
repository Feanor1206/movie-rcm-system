# CATALOG-01-F02 — REQUEST CHANGES

Review ngày 2026-10-16, branch dev. Chưa nghiệm thu snapshot vận hành.

## Phạm vi và tiến bộ

- 66/66 file trong manifest khớp SHA256 lúc bắt đầu; sẽ kiểm tra drift lần cuối. Contract 5 file vẫn byte-for-byte giống ZIP đã giao người dùng.
- Source đã bỏ service credential khỏi frontend, đưa sync ra worker sau commit, thêm canonical entity comparison, sửa các format/bounds đã nêu và thêm pending seek cho player. Đây là tiến bộ thực, không có nghĩa toàn bộ gates đã đạt.
- Review không sửa application, không chạy Gemini CLI/automation, không load GPU/model hoặc mở Drive/DB live.
- Bằng chứng mới: `python docs/reviews/repro/CATALOG_01_F02_probe.py`, kết quả tại `docs/reviews/evidence/CATALOG_01_F02_probe.json`. Java compile source hiện tại, gọi worker/query với repository proxies; không khởi động Spring/JPA. Python gọi nguyên function AST của sync_index với CatalogSyncManager thật và index giả, và HybridMovieIndex thật với encoder giả. Không trình bày đây là HTTP, DB transaction, model hay browser test.
- Không chạy full suites khi đã có blocker tái lập. Số 15/15,12/12,tsc là tuyên bố của bên triển khai, chưa được review tái xác minh độc lập.

## G1 — P1: Worker báo READY khi không sync, kể cả ghi snapshot thất bại; retry/recovery chưa bảo đảm

Production `CatalogSyncWorker.processSingleSnapshot`:
- Khi syncToken rỗng, ghi READY mà không có index ack.
- `writeSnapshotToDisk` catch lỗi và chỉ log, không báo failure cho caller.

Probe xác nhận cả hai:
1. Không token, file ghi được → READY dù không gọi index.
2. Không token, output là thư mục không thể thay bằng file → snapshot_file_exists=false nhưng vẫn READY.

Các lỗi lifecycle khác qua source:
- Có @Scheduled nhưng không có @EnableScheduling trong toàn `src/main/java`; method annotated không đủ bật polling. Hiện chỉ startup/afterCommit trigger chạy.
- Chỉ query PENDING/SYNC_FAILED. Crash sau save SYNCING làm row không được recovery. Sau5 retry bị skip vĩnh viễn, chưa có cơ chế manual retry tương ứng.
- Mọi HTTP2xx đều đánh READY trước khi kiểm tra status/hash/generation; SKIPPED HTTP200 sẽ vào nhánh thành công và không tới nhánh STALE_SKIPPED.
- Generation dùng MAX+1 trong transaction, chưa có DB sequence/lock/unique generation bảo đảm hai import cạnh tranh. @synchronized chỉ khóa method JVM; commit của proxy diễn ra sau method return.

Sửa: disk failure phải propagate; tách artifact-written khỏi index-ready, missing config là BLOCKED/FAILED; bật scheduling thật, claim/lease/recover SYNCING; ack có generation/hash/status đúng; DB generation allocation an toàn. Test Spring context thực, process restart, fail/retry và transaction cạnh tranh.

## G2 — P1: Sync cũ vẫn ghi đè snapshot mới; generation/hash không ràng buộc nội dung

`main.py:145-227`: check generation trước khi build, sau đó mutate global manager/index, không có lock hoặc compare-and-publish atomic. Hash request không được xác minh; generation chỉ giữ trong RAM và startup reset0. Cùng generation khác content cũng chưa bị conflict.

Deterministic probe dùng **nguyên function sync_index từ source**, chỉ thay encoder/index và HTTP request bằng fixture:
- Gen1 vượt check rồi đợi trong loader.
- Gen2 hoàn thành.
- Gen1 tiếp tục, ghi catalog cũ; global generation vẫn2 vì max(2,1).
- Kết quả: generation_after_both=2, final_series_titles=[older], cần [newer].

Đây là transport/concurrency simulation, không phải HTTP/model thật, nhưng race nằm trong chính function production. Cần build immutable candidate riêng, xác minh schema/hash/version, rồi compare-and-swap publish atomically; persist/recover generation và chống same-generation mismatch. Ack phải gắn với snapshot thực sự đang serve.

## G3 — P1: Rebuild index không loại bỏ document/embedding cũ

`HybridMovieIndex.build_from_catalog` ghi đè/add vào self.documents/self.embeddings nhưng không replace/clear bản cũ. BM25.fit với corpus rỗng còn return trước bước reset statistics.

Probe dùng production index và fake encoder (không load model):
- Build A, replace bằng B: documents vẫn [A,B].
- Build []: documents vẫn [A,B].

Hậu quả: bộ nhớ/file index giữ dữ liệu đã xóa/thu hồi quyền, gây stale corpus và có thể được dùng khi search gọi catalog=None/load cache. Cần replace cả documents, embeddings, BM25 statistics, metadata theo một generation atomic; empty catalog phải clear. Test lưu/reload cache và revoke public→private/draft, không chỉ search với explicit filtered list.

## G4 — P1: Public search vẫn trả draft; snapshot/public DTO chưa lọc hết quan hệ

Production `CatalogQueryService.searchCatalog` vẫn gọi searchSeries/searchEpisodes/searchSegments/searchScenes và trả kết quả không qua publication checks. `CatalogController` public GET /api/catalog/search gọi trực tiếp method này.

Probe gọi chính query service trong SecurityContext trống với repository trả draft fixture: **anonymous_search_results có draft_secret_series**. Đây là service-boundary proof, chưa gọi HTTP live.

Các đường còn hở qua source:
- `isPublished` trả true khi record missing/malformed hoặc status lạ; không deny-by-default ready.
- getSeriesDetail không lọc draft seasons hoặc parent season; getEpisodeDetail không propagate đầy đủ season/segment/media eligibility.
- exportEligibleSnapshot lọc một phần series/episode/scene nhưng xuất toàn characters và text_tracks; assets chỉ loại private, không lọc enabled/record/coverage parent. Transcript của private asset vẫn có thể đi vào snapshot, hoặc references trỏ entity đã bị filter, làm gói không self-contained.
- Public controller trả entity có rawJson và storage metadata thay public DTO tối thiểu.
- Legacy movies được tạo cho draft cũng cần xét đường GET /api/movies, không chỉ API catalog mới.

Sửa: dùng một policy chung cho public reads/search/export/index/legacy compatibility; lọc cascade theo quan hệ, bảo toàn self-contained references cho export, DTO không lộ raw/storage. Test actual anonymous/admin HTTP, private transcript/scene, archived parent và dữ liệu record lỗi.

## G5 — P1: storage_key route mới bypass Drive executor/deadline/cleanup; private responses vẫn public-cacheable

`MediaStreamService.java:304-342`: asset có storage_key đi thẳng resolvePath→Files.size/FileSystemResource/FileChannel.open, bỏ DriveMediaStorageAdapter. Trong adapter, open/read/metadata được quản lý bởi DriveIoExecutor, reservation và DriveSeekableByteChannel.

Vì catalog importer luôn gán storage_key, video Drive từ importer đi vào nhánh native I/O trực tiếp. Bulkhead HTTP không thay thế metadata/open/read deadlines và late-close ownership đã xây trước đó. Khi mount chậm/treo, request và close có thể không được giới hạn như policy Drive. Cần route đúng root nhưng vẫn qua adapter/executor bounded; không được sửa root bằng cách bỏ toàn bộ safety boundary.

StorageKeyConfig chỉ kiểm tra Files.isSymbolicLink trên leaf; symlink/junction ở ancestor path cần kiểm tra real containment tại read boundary (không thử tạo link trên Drive thật).

F02 mở phát authenticated/private theo user, nhưng `MediaStreamController` vẫn set `Cache-Control: public, max-age=3600` trên GET response, không phân policy. Protected media phải private/no-store theo quyết định đã chốt, không public cache như public asset. Kiểm tra cả HEAD/Range/error paths. Đây là source finding; review không mở Drive hoặc gửi protected video thật.

## G6 — P2: Bằng chứng gate chưa đủ; một repro cũ hiện có giả định không còn đúng

- Chỉ tsc chưa chứng minh tuple/readiness/browser race đã đạt. pending.generation được lưu nhưng cần test nó thực sự được kiểm tra khi event đến; signal/canplay/currentSrc, route swap, missing scene asset và logical→file conversion phải được đo bằng behavioral/browser tests.
- Chưa có full backend CI/JDK17, frontend Node20 behavioral/production build/route budget, populated round-trip, HTTP auth, two-package DB transaction/restart, clean-baseline reconstruction trong handoff. Không đánh các gate đó PASS bằng targeted tests/reverse patch check.
- `CATALOG_01_F01_probe.py` cũ truy cập `.get('media_asset_id')` trên get_item_by_id(scene) mà không xử lý None. Khi fix publication đúng và không index scene draft, script này ném lỗi ở bước ghi output. Vì vậy claim file hiện tại chạy PASS cần log/revision khớp; không được coi exit0 của probe reporter là assertions pass. Giữ lịch sử repro; dùng probe mới có kỳ vọng phù hợp publication thay vì làm yếu application policy.
- Artifact expanded66 hashes là tiến bộ, nhưng reverse applicability không thay thế clean reconstruction và packaged resource/CI build.

## Hướng sửa tiếp và acceptance

Giữ nguyên schema/ZIP. Ưu tiên G1–G5; bổ sung regression cho worker state machine, index CAS/generation, removal/empty index, public eligibility và bounded Drive path. Dùng DB/temp fixtures riêng, không model/GPU để thay thế integration gates.

Khi source ổn định mới chạy required suites trên cùng revision; status phân PASS/FAIL/BLOCKED/NOT_RUN. Bàn giao frozen checkpoint có hash/patch/evidence nhất quán. Review này không sửa application, không commit/push và chưa cho phép deploy.
