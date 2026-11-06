# CATALOG-01-F08 — chưa đạt điều kiện push bản nghiệm thu

Ngày review: 17/10/2026. Checkpoint CATALOG-01-F08-CHECKPOINT-01; baseline d620bfc634b3c424a847408f0dc6e02626439f45.

## Tiến bộ được ghi nhận

- 31/31 manifest hashes khớp ban đầu, theo dõi tổng cộng52 paths gồm manifest/patch. Contract5 files giống byte-for-byte ZIP gốc Desktop; patch reverse check exit0. Integrity cuối review lưu riêng.
- Đã có AcceptedSnapshot và request pipeline capture snapshot/index. Candidate được build riêng; hướng sửa đúng hơn F07.
- Chạy độc lập `python tests/test_f08_atomic_concurrency_matrix.py`:12/12 cases PASS. Tuy nhiên setter trong test bị thay bằng fixture, nên chưa bao phủ ownership của production recovery.
- Browser script đã login form thật, paste/validate/import qua UI, search/click card, click scene bằng selector bắt buộc, kiểm time advance và pause/resume. Scene fallback cũ đã bỏ. Evidence bàn giao ghi public1280x720 và Drive1920x1080. Reviewer đọc script/raw JSON; không tự chạy lại browser/services/Drive.
- Drive HTTP evidence đã có production HEAD339,074,277 bytes và Range đầu/cuối, khác F07 chỉ read1KB. Không phủ nhận bằng chứng tiến bộ này.

## R1 — P1: snapshot phục hồi vẫn bị thay đổi bởi lần publish tiếp theo

Nguồn lỗi:
- `main.py` recovery tạo init_snap với `catalog_manager=catalog_sync_manager` (singleton).
- Default bootstrap cũng dùng cùng singleton.
- `services/catalog_sync.py:set_accepted_snapshot` đổi `_current_snapshot` rồi gọi `catalog_sync_manager.copy_from(snapshot.catalog_manager)`.
- Do snapshot đã recovery giữ reference singleton, copy_from của publish mới sửa chính manager của snapshot cũ. frozen dataclass chỉ khóa field assignment, không làm object bên trong bất biến.

Repro độc lập:
`python docs/reviews/repro/CATALOG_01_F08_REVIEWER_probe.py`

Probe dùng production sync AST và **setter/getter/AcceptedSnapshot thật**, production manager/index/BM25, encoder fixture, state tạm. Khởi tạo đúng ownership recovery A/gen1; giữ reference như request đang chạy; publish B/gen2. Sau khi sync thành công:
- Retained snapshot generation1.
- Retained snapshot manager chứa published-B.
- Retained snapshot index và payload vẫn recovered-A.
- Snapshot hiện hành generation2.
- retained_snapshot_mutated=true.

Không cần timing may rủi: snapshot cũ vẫn mixed ngay cả khi publication đã hoàn tất. Request capture trước sync nhưng tiếp tục pipeline sau đó có thể dùng catalogB/indexA. Đây là source-level concurrency/recovery repro, không trình bày như HTTP load test.

Evidence: `docs/reviews/evidence/CATALOG_01_F08_REVIEWER_probe.json`.

Vì sao matrix bàn giao bỏ lọt: `create_test_context` dùng ctx_set_snapshot chỉ gán dict pointer, không gọi production set_accepted_snapshot/copy_from; snapshots test cũng dùng manager riêng, không giống startup recovery. Probe bàn giao reuse context này. 12PASS không đóng invariant còn thiếu.

Sửa: không để recovered/default snapshot giữ manager mà compatibility singleton sẽ mutate. Tạo manager riêng cho mọi snapshot từ startup/recovery/bootstrap; hoặc bỏ mutable singleton bridge và chuyển tất cả consumers sang captured snapshot. Audit payload/index nested mutation. Test retained recovered snapshot sau nhiều sync với setter thật và pipeline reader thật; không chỉ trước/sau con trỏ fixture.

## R2 — P2: chưa hoàn tất các gate playback/seek/restart đã yêu cầu

Đây là khoảng trống kiểm chứng, không khẳng định video Drive không phát được:

- Browser local3 seeks vẫn gán video.currentTime trực tiếp, chưa kiểm control timeline UI như nhãn three_timeline_seeks mô tả.
- Drive chỉ seek60s một lần. Sau assignment kiểm currentTime nằm59.5–65 rồi PASS, không chờ decoded frame/time advance sau seek. currentTime=60 trong raw evidence chưa chứng minh decode tại60s. Chưa có3 seeks gồm gần cuối trên Drive hoặc pause/resume riêng trên Drive.
- Protected episode kiểm src có grant và dimensions, nhưng không assert exact asset ID và time/frame advance sau chuyển nguồn.
- Restart cả hai backend có thực trong script, nhưng chỉ assert discover results>0/series>=2; state generation chấp nhận g hoặc g+1 sau UI revision2. Không đối chiếu final accepted hash/generation/IDs chính xác, không chạy browser playback lại sau restart.
- Deep-link/reload, logical segment/null coverage, rapid switch/retry và expired/tampered/normal-user security cases chưa có evidence đầy đủ trong rehearsal này.

Cần giữ PASS đúng phạm vi UI import/search, initial decode và HTTP Range đã có; đánh partial/NOT_RUN phần còn thiếu, không dùng UNCONDITIONALLY ACCEPTED. Hoàn thiện cùng rehearsal: browser UI timeline, Drive3 seeks với decode/time advance sau từng seek, exact protected identity, final outbox generation/hash/IDs và browser sau restart. Không cần thêm tính năng.

## Artifact và vận hành

Rehearsal ghi HEAD cũ và jar hash, chưa liên kết toàn dirty source identity với jar/frontend build. Log temp directory bị xóa sau run; raw browser JSON có một số measurements nhưng chưa đủ samples Drive seek/restart. Bổ sung identity và lưu sanitized logs để lần review sau có thể đối chiếu frozen code với execution artifacts.

## Kết luận

Chưa push theo điều kiện người dùng “nếu ổn”: R1 là lỗi code thực đã tái hiện; R2 là các gate chưa hoàn tất. Không cần bắt đầu lại hoặc mở module mới. Chốt ownership của recovered snapshot và bổ sung các assertion cuối vào rehearsal hiện có.

Reviewer chỉ viết review/repro/evidence; không sửa application/status/manifest của tác giả, không chạy Gemini CLI/automation/model/GPU/live DB/services/mount; không commit/push. Không ghi đè reviewer evidence cũ.
