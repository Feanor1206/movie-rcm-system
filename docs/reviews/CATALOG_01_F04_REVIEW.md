# CATALOG-01-F04 — REQUEST CHANGES

Review ngày 17/10/2026, branch dev; baseline d620bfc634b3c424a847408f0dc6e02626439f45.

**Chưa nghiệm thu snapshot; đặc biệt cần sửa scope của playback grant trước khi vận hành.**

## Tiến bộ và phạm vi review

- 112/112 hash manifest khớp lúc bắt đầu; 5 file contract giống ZIP gốc. Không sửa schema.
- Code đã có candidate catalog manager, reject bad hash/conflict trước copy manager, canonical key order/compact JSON, scene time tách khỏi logical mapper và playback grant. Những cải tiến này có thật, nhưng chưa đóng các gate bên dưới.
- Review chỉ tạo tài liệu/repro/evidence. Không sửa application, không commit/push, không Gemini CLI/automation, model/GPU/Drive hoặc DB live.
- **Không chạy nguyên `CATALOG_01_F04_probe.py` bàn giao**: nó viết rồi unlink file runtime `data/indices/catalog_sync_state.json`, không dùng temp path. Không dùng test này trên workspace đang có state thật.
- Independent probe an toàn: `python docs/reviews/repro/CATALOG_01_F04_independent_probe.py`. Kết quả: `docs/reviews/evidence/CATALOG_01_F04_independent_probe.json`.
- Java probe compile JwtUtils/JwtAuthenticationFilter production, dùng ephemeral signing key, fixture user và mock servlet requests. Python probe chạy nguyên sync function AST với real CatalogSyncManager, index/save fixture. Không mở HTTP/DB/model; không output key/token.

## R1 — P1: Playback grant bị chấp nhận như JWT đăng nhập đầy đủ, mất scope asset

JwtUtils.generatePlaybackGrant dùng cùng signing key/HS256 như access token, có type=playback_grant. Nhưng validateJwtToken chỉ kiểm tra chữ ký/expiry, không từ chối token type này. JwtAuthenticationFilter xử lý mọi Bearer token bằng validateJwtToken trước khi xét nhánh grant trên media route.

Probe production filter xác nhận:
- Grant asset-A hợp lệ cho A và không hợp lệ cho B qua validatePlaybackGrant.
- Cùng grant đặt vào Authorization: Bearer lại tạo ROLE_ADMIN SecurityContext trên `/api/admin/catalog/history`.
- Cùng grant Bearer cũng authenticate được `/api/media/stream/asset-B`.

Đây là fixture admin user, không phải truy cập tài khoản thật; chứng minh token scope asset bị bỏ qua tại authentication boundary. Token video không được biến thành quyền quản trị/general session của người cấp grant.

Nhánh grant còn fallback tạo authenticated user khi user lookup fail; cần deny khi user đã bị xóa/vô hiệu hóa, không phục hồi role từ token để bỏ qua revoke.

Sửa: token purpose/audience/issuer/key separation phù hợp; access-token validator không nhận playback grant; playback authentication chỉ áp dụng đúng method/path/asset, không thành credential gọi API khác. Test grant-A qua Bearer/query trên admin API, asset-B, HEAD/GET/Range, expiry/revoke/deleted user. Không chỉ test validatePlaybackGrant trực tiếp.

## R2 — P1: Frontend lấy sai khóa auth; protected browser playback chưa nối được

`frontend/lib/services/mediaService.ts`, requestPlaybackGrant đọc `localStorage.getItem('auth_token')`. AuthContext và catalog API dùng `dippie_auth_token` (catalog còn fallback token). Đăng nhập bình thường không tạo auth_token, nên grant POST không gửi Bearer.

SecurityConfig chỉ permit GET/HEAD media; POST grant yêu cầu authenticated. Request bình thường do helper tạo bị từ chối. Page fallback URL trực tiếp không credential không giải quyết protected stream.

Đây là source integration finding, chưa chạy browser user thật. Sửa bằng cơ chế auth client thống nhất; không tạo thêm bản sao token chỉ để che mismatch. Test admin/user login thực qua UI → grant request có credential đúng → video Range decode/seek; xử lý grant expiry/retry và identity khi asset đổi. Không output grant trong logs/screenshots.

## R3 — P1: Canonical hash vẫn không tương thích cho số hợp lệ theo schema

Compact + sort keys sửa được example nhưng chưa chuẩn hóa number serialization. Java/Jackson và Python khác cách biểu diễn scientific notation.

Probe dùng valid catalog (contract_errors=[]) với record.provenance.confidence=1e-8:
- Actual Java production hash: ff923eee9a961fa4810360dd61fa87926f2b56baa4969723e8b3262f0f186b9e.
- Python receiver hash: 3c37bbe7c61cc10115aa0cdc59d00483216f20554dad849b073c3c139a716335.
- match=false.

Sửa bằng một hash protocol thật sự chung và versioned, hoặc exact serialized payload bytes được vận chuyển/verify nhất quán. Không bỏ verify hoặc cấm dữ liệu number hợp lệ bằng cách đổi schema. Golden vectors cần decimals/exponents/negative zero, Unicode/escaping, null, key order và arrays; cuối cùng production worker→receiver HTTP test.

## R4 — P1: Candidate index vẫn là active index; persistence failure làm catalog/index lệch nhau

`main.py` tạo candidate_manager nhưng bước “build candidate index” vẫn gọi `cascading_pipeline.retrieval_node.hybrid_index.build_from_catalog(...)` trên active index, save_to_disk=True. Sau đó mới save durable state và copy manager.

Independent failure-injection probe:
1. Accept generation1, accepted-A.
2. Generation2 chứa failed-durable-B, index build cập nhật xong.
3. Inject durable-state save failure → HTTP500.
4. Active generation=1 và catalog=accepted-A nhưng index=failed-durable-B.

Probe index fixture chỉ đo side effect/control flow của function production, không chạy encoder hoặc HTTP. Nó chứng minh failure path không publish một snapshot nhất quán. Active cache còn có thể được ghi trước durable failure. `copy_from` cũng là nhiều field assignments, không phải atomic swap một snapshot reference cho readers.

Sửa: build index object/candidate files riêng; không mutate active index/cache. Publish catalog/index/hash/generation như một immutable snapshot nhất quán, readers capture cùng snapshot. Failure ở build/save/publish giữ nguyên toàn bộ active state. Test concurrent reads, durable failure, cache failure, restart và response ACK đúng snapshot.

Startup còn load persisted payload rồi lifespan gọi load_default_catalog riêng; cần chứng minh không overwrite restored accepted payload bằng một snapshot file khác generation/hash. Không coi đọc JSON state trong test là service restart đã đạt.

## R5 — P1: Drive containment bị bỏ thay vì chuyển vào bounded operation

StorageKeyConfig hiện bỏ exists/toRealPath containment khi provider=drive. DriveMediaStorageAdapter.getResourceForPath/getResourceLengthForPath/openChannelForPath chỉ bọc exists/readable/size/open vào executor, không kiểm tra realTarget nằm trong realRoot cho đường ForPath.

Như vậy lexical startsWith còn nhưng ancestor symlink/junction real containment của Drive bị bỏ. Yêu cầu trước là giữ kiểm tra và đưa nó vào bounded provider operation, không bỏ policy để tránh block caller.

Sửa: truyền root+relative path hoặc resolved context vào provider; real root/target containment và metadata thực hiện trong bounded executor, giữ reservations/open/read/late-close. Test ancestor links bằng local temporary fixture giả provider Drive; không tạo link hoặc fault trên mount thật. Không chấp nhận “chỉ kiểm local” làm bằng chứng Drive containment pass.

## R6 — P2: Probe nghiệm thu không chứng minh playback/restart end-to-end và có tác động runtime nguy hiểm

`CATALOG_01_F04_probe.py`:
- H3 dùng `mock_resolve_file_timestamp` viết lại bằng Python và phép chia90s, không gọi frontend handler/browser.
- H4 trả dict mô tả và hardcode `pass: True`; không kiểm tra auth/grant/filter/browser.
- Durability viết gen42/payload vào runtime state path rồi đọc bằng json.load/loader mới và unlink file; không restart production service, không backup/restore state cũ.
- AST sync sandbox dùng dummy index, không chứng minh candidate real index/disk publication.

Do đó gate_status PASSED không chứng minh admin upload→transaction→worker HTTP→public search→decoder protected video→seek→restart. 178 Java tests/12 FastAPI tests/build là bằng chứng riêng, không thay rehearsal browser hoặc interoperability tests. Review không chạy lại model suite để lặp bằng chứng không bao phủ boundary đang lỗi.

Cần sửa test tooling để mọi mutable artifact/DB/ports ở temp riêng, không ghi/xóa runtime state. Assertions phải dựa production code thực, mỗi gate phân scope mock/HTTP/browser/Drive/model. Có clean reconstruction, CI runtime/Node20/route budget và replayable E2E evidence trước acceptance; gate chưa chạy ghi NOT_RUN/BLOCKED.

## Gate tiếp theo

Giữ nguyên contract. Ưu tiên R1/R2 rồi R3/R4/R5. Hoàn tất một rehearsal isolated thực sự: admin login/upload/import → worker HTTP READY đúng hash/generation → public/protected video decode và90s seek → reject bad hash/grant scope → restart services → lặp search/playback. Không đổi fixture thành public hoặc bịa PASS để vượt auth.

Chưa commit/push/deploy. Báo cáo implementation cũ giữ như lịch sử, không coi nhãn COMPLETE là acceptance.
