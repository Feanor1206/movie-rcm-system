# CATALOG-01-F03 — chưa nghiệm thu snapshot

Ngày review: 2026-10-17, branch dev. Kết luận: **REQUEST CHANGES**.

## Tiến bộ và giới hạn kiểm tra

- 109/109 SHA256 trong manifest khớp; 5 file contract giống nguyên ZIP người dùng đã nhận. Không đổi schema.
- Reverse patch check `git apply --check -R docs/reports/CATALOG_01_F03.patch` exit0; không áp dụng patch thật.
- Source đã thêm scheduled worker/recovery/manual retry, trạng thái BLOCKED/SYNC_FAILED thay READY giả, reset index khi rebuild, publication checks, bounded Drive wrappers, cache policy và giao diện outbox/segments/pending seek. Có tiến bộ sản phẩm, nhưng chưa có bằng chứng end-to-end đóng gate.
- Chỉ tạo review/repro/evidence. Không sửa application, không load model/GPU, không gọi HTTP/DB live/Drive, không Gemini CLI/automation hoặc commit/push.
- Probe mới biên dịch source Java catalog hiện tại để gọi đúng hash helper production, chạy nguyên function AST sync_index với CatalogSyncManager thật và index/HTTP request giả. Probe TypeScript chạy đúng helper production qua transpile, không chạy browser. Không trình bày probes như HTTP/decoder/model verification.

## H1 — P1: Java worker và Python receiver không cùng hash contract; import→index bị chặn

`CatalogSyncWorker` dùng ObjectMapper.writeValueAsString(fullEligibleCatalog), sau đó CatalogImportService.computeSha256(catalogJson). Đây là hash compact JSON giữ key order của serializer.

`CatalogSyncManager.compute_hash` dùng json.dumps(payload, sort_keys=True, ensure_ascii=False), có spaces mặc định và sorted keys. Hai bên hash các bytes khác nhau. Việc thêm verify declared hash làm đường worker thực bị HTTP400.

Probe `python docs/reviews/repro/CATALOG_01_F03_probe.py` dùng cùng payload, actual Java ObjectMapper + production computeSha256 và Python compute_hash:
- java_worker_hash khác python_receiver_hash;
- sync function nhận worker hash trả HTTP400;
- request dùng hash Python thì có thể success.

Evidence: `docs/reviews/evidence/CATALOG_01_F03_probe.json`.

Sửa: quy định canonical serialization/hash chung giữa hai runtime, bao gồm Unicode, number, key order và array semantics. Test request do **production worker thực** tạo qua HTTP tới receiver isolated; không chỉ Python tự gửi hash Python. Không bỏ verify để làm xanh. Ack worker phải xác minh đúng cùng định nghĩa hash.

## H2 — P1: Request bị từ chối vẫn thay catalog đang phục vụ; chưa có candidate/publish atomic

`main.py` vẫn gọi `catalog_sync_manager.load_from_payload` trước verify hash và trước publish lock. Loader ghi trực tiếp global raw_catalog/flattened/items/hash. Sau đó hash mismatch400 hoặc same-generation conflict409 không rollback manager.

Probe xác nhận:
1. Accept generation1, title accepted-A.
2. Gửi payload rejected-B với hash worker khác receiver → HTTP400.
3. Generation vẫn1 nhưng manager public corpus đã thành rejected-B.
4. Gửi same-generation/different-content → HTTP409, manager vẫn rejected-B.

Catalog được pipeline lấy từ global manager nên đây là thay đổi active data dù request bị từ chối. Lock ở bước sau hoặc khôi phục payload trong một nhánh stale không bảo vệ mọi path hoặc concurrent readers.

Trong publish lock vẫn gọi build_from_catalog trực tiếp trên active hybrid_index; không có pointer swap như báo cáo tuyên bố. Readers không dùng lock này. Build fail có thể để catalog/index không cùng version.

Persistence chỉ lưu generation/hash, payload/index/disk snapshot phục hồi riêng; chưa chứng minh restart phục hồi đúng một snapshot nhất quán. `_save_sync_state` swallow I/O failure. Không được ACK durable success nếu durability gate chưa đạt.

Sửa: load/validate/build trong manager/index candidate độc lập; failure không mutate active object. Atomic publish cả catalog/index/generation/hash bằng immutable snapshot/reference thống nhất; readers đọc cùng snapshot. Persist/recover cùng generation/content; test bad hash,409,build fail,state save fail,concurrent query và restart.

## H3 — P1: Tua scene đổi file timestamp thành logical time lần nữa; unknown bị đoán thành0

Contract quy định scene.start_ms/end_ms đã là **file timeline**. F03 handleSeekScene và deep-link scene lại gọi resolveFileTimestamp(scene.startMs,asset), hàm chuyển **logical episode→file**.

`node docs/reviews/repro/CATALOG_01_F03_timestamp_probe.cjs` trích và chạy chính TypeScript helper production:
- Coverage source_in_ms=60000, episode_in_ms=0.
- Scene file start_ms=90000 cần tua90s.
- Luồng hiện tại tính thành150s.

Unknown episode_in_ms=null cũng bị coi là0; logical30s trả90s thay vì unresolved. Helper fallback logicalMs/1000 khi thiếu/malformed mapping; không có episodeId để phân biệt coverage nhiều tập. Segment start null bị `??0`. Đây là đoán vị trí phát trái contract.

Evidence: `docs/reviews/evidence/CATALOG_01_F03_timestamp_probe.json`.

Sửa:
- Scene/file timestamp: dùng trực tiếp đúng media_asset_id, không convert thêm.
- Segment logical timestamp: chọn đúng episode/segment, coverage interval [start,end), đầy đủ offset; thiếu/ambiguous thì disable seek và báo lý do.
- Deep link phải mang hoặc suy ra chắc chắn hệ thời gian, không xử lý mọi t= như logical.
- Test nonzero source_in/episode_in, multi-episode/multi-file, unknown, boundary, edition khác qua browser decoder. Fixture offset0 không phát hiện lỗi này.

## H4 — P1: Protected video chưa có đường xác thực từ browser; Drive containment vẫn ở ngoài deadline

Source findings, chưa thực hiện HTTP/browser/Drive thật:

- Page phát `<video src={streamUrl}>` trực tiếp. Auth hiện nằm localStorage và các API fetch tự gắn Bearer; HTML video không tự lấy token localStorage làm Authorization header.
- JwtAuthenticationFilter chỉ đọc Authorization: Bearer, không cookie/session/playback grant. MediaStreamService từ chối non-public khi SecurityContext anonymous. Vì vậy đăng nhập admin/user trong web chưa đủ làm video authenticated/private phát được qua player này.
- Cần thiết kế browser-compatible auth transport an toàn cho HEAD/GET/Range (server session/proxy hoặc grant ngắn hạn có scope phù hợp). Không đưa token dài hạn vào URL và không đổi asset thành public để bypass.
- Drive wrapper đã được nối lại là tiến bộ. Tuy nhiên MediaStreamService gọi StorageKeyConfig.resolvePath trước wrapper; resolvePath chạy Files.exists/toRealPath(root và target) trực tiếp trên caller. Metadata mount chậm vẫn có thể block trước khi tới DriveIoExecutor.executeMetadata. Cần đưa cả resolution/real containment vào bounded provider operation, giữ read-only và late-close ownership.
- getResourceForPath cũng gọi exists/isReadable trực tiếp. Kiểm tra toàn bộ call chain, không chỉ openChannel wrapper.

Test: admin/user/anonymous browser playback đúng policy; Range/cache/expiry/revoke; fixture metadata resolver bị giữ để xác minh deadline thật. Không fault bằng mount/rename Drive thật.

## H5 — P2: Product acceptance vẫn vượt phạm vi evidence

Handoff gọi targeted15 Java tests là “full Maven suite”, tsc/build là bằng chứng player/browser, reverse patch check là reconstruction. Đây là các gate khác nhau.

Chưa có evidence khớp checkpoint cho:
- production worker→HTTP receiver với token/hash thực;
- full backend CI/JDK17 và concurrency/restart transaction tests;
- frontend Node20 behavioral suite và route JS budget;
- browser admin import→outbox READY→search→đúng video/time;
- protected media browser playback;
- clean-baseline reconstruction + packaged resource verification;
- restart catalog/index snapshot nhất quán;
- Drive thật so với local fixture.

P1–P4 phải phân biệt implemented với verified. Các repro reporter in JSON/exit0 không tự chứng minh mọi kỳ vọng đã PASS. Ví dụ probe cũ không gửi production worker hash hoặc scene nonzero offset nên không bao phủ H1/H3.

## Gate tiếp theo — tập trung hoàn thành lát cắt sản phẩm

Không cần mở thêm tính năng. Giữ nguyên contract và hoàn thiện một rehearsal tự động trên DB/temp media riêng:
1. Admin login → upload/preview/import package hợp lệ có nonzero coverage và hai edition.
2. Worker thực sync qua HTTP → READY với cùng hash/generation ở hai service.
3. Search mở đúng episode/asset; decoder chạy, pause/resume, seek đúng scene90s.
4. Request sai hash/conflict không thay active results.
5. Restart services rồi lặp search/playback và đối chiếu generation/hash.
6. Public/authenticated/private được test đúng policy, không dùng private→public để làm demo qua.

Sửa H1–H4 và hoàn tất rehearsal trước khi đánh P1–P4 COMPLETE. Gate thiếu môi trường ghi BLOCKED/NOT_RUN. Review không commit/push hoặc deploy.
