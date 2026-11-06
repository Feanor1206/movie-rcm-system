# CATALOG-01-F05 — chưa nghiệm thu snapshot vận hành

Ngày review: 17/10/2026. Branch dev, baseline d620bfc634b3c424a847408f0dc6e02626439f45.

## Đã tiến bộ và được xác minh

- 121/121 hashes trong manifest khớp lúc bắt đầu. Contract 5 file giống byte-for-byte ZIP gốc.
- **Lỗi grant-as-Bearer cũ đã qua repro độc lập**: grant-A vẫn hợp lệ cho A, không hợp lệ cho B; không còn authenticate được admin endpoint hoặc asset-B khi dùng như Bearer. Đây là production filter với mock servlet/fixture user, không phải full HTTP/browser matrix.
- Auth token key được thống nhất trong media helper. Drive provider đã nhận root context và thực hiện real containment trong bounded metadata operations. Đây là cải thiện source; chưa gọi Drive thật.
- Không sửa application, không commit/push, không chạy Gemini CLI/automation, model/GPU, HTTP/DB live hay Drive trong review.

## Bằng chứng độc lập

`python docs/reviews/repro/CATALOG_01_F05_independent_probe.py`

Evidence: `docs/reviews/evidence/CATALOG_01_F05_independent_probe.json`.

Probe reuse production JWT/filter và chạy nguyên sync/save/load functions trích AST; real CatalogSyncManager, index failure fixture và state trong temp directory. Không chạm runtime state. Phần load sau failure là restart-loader simulation, không trình bày như service restart thật.

## S1 — P1: Lỗi index build sau durable save làm snapshot bị từ chối sống lại sau restart

F05 không tạo candidate index độc lập như handoff mô tả. Trong `backend/fastapi/main.py`:
1. `_save_sync_state(req_gen, computed_hash, req_catalog)` ghi candidate xuống accepted state file.
2. Lấy **active** `cascading_pipeline.retrieval_node.hybrid_index` và gọi build_from_catalog trực tiếp.
3. Sau đó mới copy manager và cập nhật active generation.

Repro độc lập:
- Accept A/gen1.
- Gửi B/gen2, inject lỗi build index.
- Request trả HTTP500; active generation1/catalogA/indexA.
- Nhưng persisted state đã thành gen2/payloadB.
- Gọi production state loader và fresh manager phục hồi **rejected-build-B**, cần accepted-A/gen1.

Vì vậy đổi thứ tự save trước build chỉ sửa nhánh save-fail cũ, chưa sửa atomic publication/durability. Build thật còn có thể sửa active index/cache một phần trước lỗi. `copy_from` nhiều field assignments không phải single immutable snapshot pointer cho readers.

Sửa cần thiết:
- Build candidate manager/index/cache riêng, không mutate active object.
- Accepted state/durable pointer chỉ đổi sau khi candidate hoàn chỉnh và generation được chấp nhận.
- Failure ở bất kỳ bước nào giữ nguyên accepted snapshot; recovery không promote candidate bị từ chối.
- Readers capture cùng snapshot cho catalog/index/hash/generation.
- Test cả save-fail **và build-fail sau save**, crash windows, concurrent query, stale jobs và service restart thật.

## S2 — P1: Hướng dẫn “mở lên dùng ngay” chưa khớp luồng production

Các điểm kiểm tra từ source/runbook:

- Runbook yêu cầu login `admin`, nhưng DataInitializer hiện tạo admin có username `alex`; chưa có bước bootstrap tài khoản tương ứng trong hướng dẫn. Không thử đăng nhập vào live server để kiểm chứng.
- Runbook hướng dẫn import `catalog.example.json` rồi tìm kiếm/phát như dữ liệu thật. Contract example là draft/private/hư cấu; policy đúng phải loại khỏi public search/index. Example không trỏ video Drive thật. Import thành công không chứng minh search/playback có dữ liệu.
- Runbook không hướng dẫn cấu hình sync secret cho hai service. Spring worker đọc `app.catalog.sync-token`, Python đọc CATALOG_SYNC_TOKEN/FASTAPI_SYNC_SECRET; không có binding tự động từ tên Python sang Spring property trong source config đã đọc. Lệnh ba terminal được nêu chưa đủ làm outbox READY trên cấu hình mặc định.
- Public catalog detail/list/search fetch chỉ gửi Accept, không Bearer dù frontend đã login. Backend dựa SecurityContext để cho admin xem private assets/draft; vì vậy đường admin preview/private asset selection chưa được nối bằng các fetch này. Grant helper sửa key không tự sửa toàn luồng chọn private video.

Sửa bằng một bootstrap/rehearsal trên DB riêng có tài khoản test thực, secret config ngoài Git, fixture hợp lệ đủ điều kiện publish trong môi trường test, media mapping thật trong fixture và auth transport thống nhất. Giữ example/schema nguyên vẹn; không promote nội dung hư cấu vào live catalog hoặc đổi private thành public để lấy demo.

## S3 — P2: Rehearsal vẫn là offline simulation, chưa chứng minh P1–P5

`CATALOG_01_F05_rehearsal.py` có cải thiện isolation/temp files và grant negative matrix, nhưng các nhãn sản phẩm vẫn vượt phạm vi:
- P1 là contract_errors==0, không phải admin login/upload/DB import.
- P2 gọi sync function AST với fake index, không phải production worker HTTP.
- P3 tự chia scene milliseconds và viết hàm mapping Python, không test production frontend handler, search UI hoặc browser decoder.
- P4 dựa filter matrix, không phát video bằng browser.
- P5 tạo JSON temp gen42 rồi fresh manager.load_from_payload, không restart services hoặc DB/outbox/index process.

Không có browser driver/service launch/restart trong script này. Vì vậy all_product_flows_passed không chứng minh toàn chuỗi đã chạy. Full178 Java tests,12 Python tests,tsc/build là các gate khác; review không chạy lại GPU suite để lặp evidence không bao phủ S1/S2.

Cần một entry point rehearsal thật: isolated DB + actual services trên ports trống + browser + temp media/state. Mỗi gate có evidence PASS/FAIL/BLOCKED/NOT_RUN, không đổi tên simulation thành HTTP/browser/restart.

## Bước tiếp theo để kết thúc vòng sửa nhỏ

Không cần thêm tính năng. Chốt hai deliverables:
1. Atomic accepted snapshot đúng cả runtime và disk với failure matrix S1.
2. Một rehearsal production-stack thực đi qua admin login→upload→import→worker HTTP READY→search→public/protected decode→90s seek→restart→lặp lại, trên DB/media/state riêng.

S2 phải được phát hiện/sửa bằng chính rehearsal này. Nếu môi trường thiếu, ghi blocker thật; đừng thay bằng toy probe rồi đánh ACCEPTED.

Giữ nguyên schema, các sửa bảo mật đã đạt và lịch sử evidence. Chưa commit/push hoặc deploy checkpoint F05.
