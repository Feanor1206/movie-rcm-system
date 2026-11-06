# CATALOG-01-F07 — chưa nghiệm thu toàn phần

Ngày review: 17/10/2026. Checkpoint CATALOG-01-F07-CHECKPOINT-01, baseline d620bfc634b3c424a847408f0dc6e02626439f45.

## Đã xác minh tiến bộ

- 24/24 manifest entries khớp SHA-256; theo dõi tổng cộng 44 paths gồm manifest và patch. Contract 5 files giống từng byte ZIP gốc Desktop. Patch reverse applicability thành công. Integrity trước/sau lưu riêng.
- Chạy lại function của reviewer repro F06, không chạy main để tránh ghi đè lịch sử evidence: durable save failure trả500, manager/index/disk đều giữ accepted-A/gen1, không còn rejected-B leak. Nhánh lỗi này đã sửa.
- Source có candidate index riêng, chia sẻ encoder; startup guard bỏ load_default_catalog khi đã có generation/manager; default path đã cấu hình được. Đây là tiến bộ có thực. Chưa chứng thực độc lập corrupt-state recovery hoặc service restart thật.
- Đã bổ sung browser script và diễn tập restart cả Spring/FastAPI hai lần. Evidence bàn giao báo PASS. Reviewer đọc code/evidence, không chạy lại stack/model/Drive.

## R1 — P1: publication vẫn chưa atomic cho readers

`backend/fastapi/main.py` build candidate riêng nhưng sau durable save vẫn gọi manager.copy_from rồi lần lượt gán active_index.documents, embeddings, bm25, metadata_index, is_ready. Cuối cùng mới cập nhật generation/hash. Biến hybrid_index tiếp tục trỏ cùng active_index cũ. Đây không phải single snapshot pointer swap như báo cáo mô tả.

`ai_pipeline.py` đọc catalog_sync_manager và hybrid_index ở các thời điểm riêng; readers không giữ publish lock hoặc capture cùng một snapshot. CatalogSyncManager.copy_from cũng gán nhiều field.

Repro độc lập:
`python docs/reviews/repro/CATALOG_01_F07_independent_probe.py`

Sau baseline A/gen1, writer publish B/gen2. Reviewer đặt scheduling barrier ngay sau production manager.copy_from, trước index assignments; một reader đọc production getters/index trong cửa sổ này:
- manager: next-B.
- index: accepted-A.
- active_generation:1.
- persisted_generation:2.

Evidence: `docs/reviews/evidence/CATALOG_01_F07_independent_probe.json`.
Đây là thread scheduling/failure harness dùng sync AST, manager/HybridMovieIndex/BM25 thật, encoder fixture và temp disk, không phải HTTP/load benchmark. Barrier không thay payload hoặc trạng thái publication; nó phơi ra cửa sổ interleaving đang tồn tại.

Matrix F07 case9 chỉ đọc list(index.documents.values()) và kiểm tra không rỗng. Nó không so catalog/index/BM25/hash/gen, không thực hiện production search, nên không bắt lỗi này. Case3 ném lỗi trước khi mutate thay vì partial build. Case10 là fresh-loader simulation, không lifecycle startup.

Sửa cần thiết: immutable accepted snapshot gồm manager/index/gen/hash; mỗi reader capture cùng snapshot cho cả request và publisher đổi một reference. Hoặc một cơ chế lock thống nhất readers/writers bảo đảm toàn request nhất quán, có đánh giá ảnh hưởng latency. Không chỉ đổi tên comment hoặc thêm assertion không bao phủ publication.

## R2 — P1: browser gate có đường PASS dù scene UI hỏng; chưa chứng minh trọn luồng

`scripts/rehearsal_browser_f07.cjs`:
- Không tìm thấy scene button thì tự đặt video.currentTime=15/20, rồi vẫn đánh scene_seek PASS. Vì vậy missing/broken scene UI không làm test đỏ.
- Ba lần seek đặt currentTime trực tiếp, không thử timeline control.
- Protected asset gate chỉ yêu cầu src chứa asset_feature_02 và grant=, chưa bắt buộc frame decoded/time advance cho asset mới. Gán currentTime không chứng minh decoder đã phát asset đó.
- Fallback playback có thể chấp nhận videoWidth>0 dù time không tiến; pause/resume chỉ kiểm paused, chưa kiểm thời gian dừng/tiến.
- Browser nhận admin JWT tiêm localStorage, mở thẳng /series/...; login/upload/import/search vẫn do Python HTTP. Chưa kiểm các UI tương ứng.
- Không có thực thi deep-link dù header nói có; thiếu logical segment, null coverage, rapid switch và retry cases đã yêu cầu.

Sửa test fail-closed: selector đúng và bắt buộc click thành công; không direct-seek fallback cho gate scene/UI. Chờ đúng currentSrc/asset identity, seeked và decoded frame/time advance sau chuyển asset. Kiểm toàn tuyến UI login→upload→preview→import→search→player và lặp lại browser sau restart. Có thể giữ direct currentTime như một decoder API test riêng, không tính là UI gate.

Evidence JSON rehearsal chỉ ghi gate PASS, không lưu browser assertions/measurements; script in stdout rồi bỏ. Cần lưu sanitized raw assertions, IDs, timestamps và source/artifact identity; screenshot đơn lẻ không thay thế các assertion.

## R3 — P1: Drive playback chưa được test, gate chỉ chứng minh đọc header

`scripts/rehearsal_f07_production_stack.py` mount X:, list folder rồi read1024 bytes của một MP4. Không mapping file đó vào catalog test/production media service, không HTTP Range hoặc browser decode/seek trên Drive video. Browser trước đó dùng synthetic local media. Vì vậy chỉ có mount/read evidence; **Drive playback gate là NOT_RUN**, không phải PASS.

Mount readiness cũng chỉ kiểm X:/ exists, chưa preflight drive letter trống hoặc chứng minh mount thuộc process vừa tạo. Nếu X: đã có, test có thể đọc mount của người dùng. Không chạy lại script này trước khi sửa ownership/readiness.

Cần map đúng video Drive vào DB/catalog test riêng, stream qua production service và frontend, chứng minh decoded frame/time advance/pause/resume/3 seeks gồm gần cuối, HEAD/GET/Range. Giữ read-only, bounded cache/RAM, không ghi Drive, không đụng mount người dùng. Blocker thực phải ghi BLOCKED, không thay bằng đọc header.

## Giới hạn khác cần sửa trong cùng lượt rehearsal

- Restart queries vẫn chỉ kiểm results.length>0; chưa đối chiếu exact IDs/index hash/generation, chưa kiểm acceptedA+defaultB hoặc browser sau restart.
- Jar SHA được ghi lại nhưng script dùng target jar có sẵn, commit là HEAD cũ trong dirty working tree; chưa chứng minh artifact được build từ frozen sources hiện tại.
- Gate matrix expired/tampered grant và normal-user/admin chưa được bao phủ đầy đủ trong rehearsal này. Giữ PASS hẹp của những case đã chạy, không suy ra security toàn diện.

## Kết luận và phạm vi review

Không chấp thuận UNCONDITIONALLY ACCEPTED/production-ready. Lỗi disk-save leak F06 đã đóng, timestamp scene source giữ đúng15s, startup/default guard đã tiến bộ. Còn ba đầu việc chốt: publication nhất quán cho readers; browser tests fail-closed qua UI thật; Drive playback thật thay vì header read. Không cần mở tính năng mới.

Reviewer chỉ đọc application và viết repro/review/evidence. Không chạy Gemini CLI, automation, model/GPU, live services/DB hoặc mount; không commit/push. Không sửa status/manifest/handoff của tác giả. Không lặp toàn bộ suites đã báo; chỉ chạy repro độc lập liên quan trực tiếp.
