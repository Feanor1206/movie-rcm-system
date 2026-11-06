# CATALOG-01-F06 — chưa đạt nghiệm thu snapshot dùng được

Ngày review: 17/10/2026. Checkpoint CATALOG-01-F06-CHECKPOINT-01; baseline d620bfc634b3c424a847408f0dc6e02626439f45.

## Tiến bộ và phạm vi xác minh

- 18/18 entries manifest khớp SHA-256 ban đầu; 5 contract files giống từng byte với ZIP gốc Desktop. Patch reverse-check thành công. Manifest chỉ liệt kê 18 files; reviewer theo dõi thêm 28 paths trong patch.
- Đã có script diễn tập gọi HTTP tới Spring/FastAPI, đăng nhập, import, chờ outbox READY, search, GET/Range và restart FastAPI; evidence bàn giao báo PASS. Đây là tiến bộ so với rehearsal AST cũ. Reviewer đọc script/evidence, không chạy lại services hoặc xác nhận độc lập lượt HTTP đó.
- Có sửa bootstrap tài khoản, auth header catalog service và cấu hình sync token. Không lặp toàn bộ suites/model/GPU để kiểm tra lại các gate không liên quan.
- Không sửa application, không chạy CLI agent/automation, không mount/ghi Drive, không dùng live DB, không commit/push.

## F1 — P1: rejected candidate vẫn thay index đang phục vụ khi durable save lỗi

`backend/fastapi/main.py:303` lấy active_index rồi gọi build_from_catalog trực tiếp. Rollback chỉ lưu/khôi phục `titles`, trong khi HybridMovieIndex thật dùng documents, embeddings, bm25, metadata_index và is_ready; không dùng titles làm trạng thái index.

Repro: `python docs/reviews/repro/CATALOG_01_F06_independent_probe.py`.

Probe dùng production sync/save/load trích AST, CatalogSyncManager thật và HybridMovieIndex/BM25 thật; thay encoder bằng vector fixture, state trong temp directory. Không import main, không model/network. Accept A/gen1, gửi B/gen2 và inject OSError ở durable save sau build. Kết quả:

- Request B trả HTTP500.
- Active manager/gen và persisted catalog vẫn A/gen1.
- **Active index documents đã là rejected-B**.

Evidence: `docs/reviews/evidence/CATALOG_01_F06_independent_probe.json`.

Vì vậy S1 chưa đóng; đổi thứ tự build/save khắc phục một nhánh nhưng tái tạo nhánh disk-fail. Publish lock chỉ khóa writers; readers còn có thể thấy build dở dang. Cần candidate index riêng và snapshot catalog/index/generation/hash nhất quán cho readers; failure giữ accepted snapshot nguyên vẹn. Test save-fail, partial-build-fail, concurrent reader và recovery. Không thêm thuộc tính titles chỉ để qua fixture cũ.

## F2 — P1: rehearsal chứng nhận tua sai hệ thời gian, chưa chạy player

`scripts/rehearsal_f06_production_stack.py` Step9 lấy scene.start_ms=15000 rồi cộng coverage source_in_ms=10000 để khẳng định 25 giây. Contract scene là file timeline, production `frontend/app/series/[id]/page.tsx` handleSeekScene tua `scene.startMs / 1000`, tức **15 giây**. Coverage conversion chỉ dùng cho logical segment/episode time.

HTTP Range bytes=10000-20000 chứng minh truy cập byte, không chứng minh mốc thời gian/decoder. Script không khởi động frontend hoặc browser, không click scene hoặc đọc video.currentTime/frame. `test_live_browser_f06.cjs` có sẵn là kịch bản Drive cũ tại /movies/drive-videoplayback, không nối rehearsal catalog này.

Cần giữ nghĩa scene của schema; sửa expectation sai trong rehearsal/runbook/acceptance và kiểm chứng browser thật qua trang series: click scene15s, segment mapping riêng, asset switch, unknown coverage không tua về0, protected grant và decode/time advance.

## F3 — P1: startup có thể ghi đè manager đã recovery bằng catalog mặc định

Module startup đọc SYNC_STATE_PATH, phục hồi accepted manager/index. Nhưng lifespan tiếp tục gọi load_default_catalog() vô điều kiện. Production loader dò data/catalog/committed_catalog_snapshot.json và imported_catalog.json, không dùng SYNC_STATE_PATH, rồi load vào cùng singleton manager. Nếu default file khác accepted payload, manager bị đổi nhưng index/gen/hash vừa recovery không đổi tương ứng. Đây là source finding; review không chạy lifecycle/model hoặc sửa runtime files để tái hiện.

Cần một nguồn accepted snapshot duy nhất; default bootstrap chỉ khi chưa có accepted state. Rehearsal temp state cần cô lập cả default catalog/index paths, không đọc nhầm workspace data. Test accepted A + default B trong temp, restart thực rồi đối chiếu manager/index/gen/hash và chính xác IDs, không chỉ results.length>0.

## F4 — P2: nghiệm thu toàn phần vượt bằng chứng bàn giao

- Rehearsal chỉ chạy hai backend, không admin upload UI, frontend decode/pause/resume/seek, hoặc Drive thật. Protected wrong-asset case dùng nonexistent_asset_id nên 404 không phân biệt asset binding với asset không tồn tại.
- Restart chỉ FastAPI; Spring/DB không restart. Kiểm tra search chỉ yêu cầu có kết quả, chưa xác nhận đúng catalog IDs/hash hoặc không fallback dữ liệu khác.
- wait_for_service coi cả404 là healthy; chưa preflight port trống hay xác minh responder thuộc process vừa tạo. Jar lấy từ target có sẵn, chưa gắn hash/source revision vào evidence.
- Runbook vẫn gợi ý import draft/private contract example rồi search/playback như dữ liệu đã publish. Fixture media synthetic/local khác Drive thật; không được suy ra Drive gate pass.

Đổi các gate chưa chạy thành NOT_RUN/BLOCKED và bỏ khuyến nghị production/unconditional acceptance hiện tại. Chốt bằng một rehearsal frontend + backend + worker + isolated DB/state/media, exact IDs/hash, browser decoder và restart cả services; lưu log/process/artifact identity. Gate Drive riêng chỉ PASS khi có bằng chứng video từ mount thật. Không thay bằng phép tính hoặc Range byte response.

## Kết luận

Chưa chấp thuận CATALOG-01-F06 là snapshot vận hành. Không cần mở tính năng mới; ưu tiên atomic snapshot F1, recovery F3 và rehearsal browser đúng timestamp F2/F4. Các PASS unit/build/HTTP hiện có được giữ đúng phạm vi, không phủ nhận tiến bộ hoặc trình bày như nghiệm thu trọn sản phẩm.
