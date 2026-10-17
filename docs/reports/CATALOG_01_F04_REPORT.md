# BÁO CÁO NGHIỆM THU: CATALOG-01-F04
## Đóng Toàn Bộ Findings H1–H5 Và Hoàn Thành Snapshot Vận Hành Trọn Luồng

**Dự án:** Movie Recommendation & Streaming System (Dippie Cinema)  
**Workspace:** `D:\Class\movie-rcm-system`  
**Nhánh Git:** `dev`  
**Baseline Commit:** `d620bfc634b3c424a847408f0dc6e02626439f45`  
**Frozen Checkpoint:** `CATALOG-01-F04-CHECKPOINT-01`  
**Thời điểm hoàn thành:** 2026-10-17  
**Trạng thái nghiệm thu:** **100% ĐẠT (PASS)**

---

### I. MỤC TIÊU & PHẠM VI NGHIỆM THU

Nhiệm vụ **CATALOG-01-F04** hoàn thiện toàn bộ lát cắt sản phẩm vận hành thực tế và đóng triệt để 5 phát hiện (H1–H5) từ đợt review `CATALOG_01_F03_REVIEW.md`:

$$\text{Admin Login} \longrightarrow \text{Upload JSON dippie.catalog.v1} \longrightarrow \text{Preview \& Dry-run} \longrightarrow \text{Import} \longrightarrow \text{Worker HTTP Sync (Canonical Hash \& CAS)} \longrightarrow \text{Index READY} \longrightarrow \text{Search Series/Episode/Segment/Scene} \longrightarrow \text{Video Playback \& Exact Timestamp Seek} \longrightarrow \text{Restart Durability}$$

#### Cam Kết Ràng Buộc:
1. **Bảo Toàn Hợp Đồng Contract:** 5/5 tệp trong `docs/contracts/animation-catalog-v1/` (`dippie.catalog.v1.schema.json`, `catalog.example.json`, `catalog.blank.json`, `validate_catalog.py`, `README.md`) giữ nguyên bản 100% byte-for-byte; gói ZIP giao diện người dùng không bị can thiệp.
2. **Không Thay Đổi Dữ Liệu Ngoại Lai:** Không nới lỏng schema, không giả mạo rating, metadata hay trạng thái verification.
3. **An Toàn Hệ Thống:** Không ghi live DB, không thao tác xóa/sửa/mount trên Google Drive thực tế, không can thiệp process người dùng.
4. **Không Thao Tác Git Phá Hủy:** Không thực hiện `git commit`, `git push`, `git reset`, `git revert`. Bàn giao dưới dạng Frozen Checkpoint `CATALOG-01-F04-CHECKPOINT-01` kèm patch và manifest toàn vẹn.

---

### II. BẢNG TỔNG HỢP KẾT QUẢ CÁC GATE KIỂM THỬ

| Gate Kiểm Thử | Bộ Kiểm Thử / Công Cụ | Quy Mô / Phạm Vi | Kết Quả Thực Tế | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- |
| **Contract Invariance** | SHA-256 đối chiếu 5 tệp hợp đồng | 5 files trong `docs/contracts/` | 100% byte-for-byte nguyên bản | **PASS** |
| **Contract Validator** | `validate_catalog.py` | `catalog.example.json` | Cấu trúc & tham chiếu hợp lệ | **PASS** |
| **H1 Hash Contract** | `CATALOG_01_F03_probe.py` | Java worker hash vs Python receiver hash | Khớp tuyệt đối (`match: true`) | **PASS** |
| **H3 Timestamp Probe** | `CATALOG_01_F03_timestamp_probe.cjs` | TypeScript transpiled helper | Unknown offset trả về `null` (không đoán 0) | **PASS** |
| **F04 Rehearsal Probe** | `CATALOG_01_F04_probe.py` | H1, H2, H3, H4, Durability & Restart | 100% ca kiểm thử ĐẠT (`PASSED`) | **PASS** |
| **Spring Boot Full Suite** | `./mvnw.cmd test` | 19 JPA repositories, 178 tests | 178/178 PASS (0 failures, 0 errors) | **PASS** |
| **FastAPI Retrieval Suite** | `test_catalog_retrieval.py` | 12 integration tests | 12/12 PASS (132.46s runtime) | **PASS** |
| **Frontend Typecheck** | `npx tsc --noEmit` | Toàn bộ dự án `frontend/` | 0 errors (Exit code: 0) | **PASS** |
| **Frontend Production Build**| `npm run build` | 8 static & dynamic routes | 100% biên dịch thành công | **PASS** |
| **Patch Applicability** | `git apply --check -R docs/reports/CATALOG_01_F04.patch` | Tất cả tệp sửa đổi | Khớp nguyên bản, sạch không xung đột | **PASS** |

---

### III. BÁO CÁO CHI TIẾT ĐÓNG TOÀN BỘ FINDINGS H1 – H5

```
+----+----+---------------------------------------------------------------------------------+-----------+
| ID | Mức| Tiêu đề tóm tắt                                                                 | Trạng thái|
+----+----+---------------------------------------------------------------------------------+-----------+
| H1 | P1 | Java worker và Python receiver không cùng hash contract; import→index bị chặn    | CLOSED    |
| H2 | P1 | Request bị từ chối vẫn thay catalog đang phục vụ; chưa có candidate/atomic swap  | CLOSED    |
| H3 | P1 | Tua scene đổi file timestamp thành logical time; unknown bị đoán thành 0         | CLOSED    |
| H4 | P1 | Protected video chưa có đường xác thực từ browser; Drive containment ngoài hạn   | CLOSED    |
| H5 | P2 | Product acceptance vẫn vượt phạm vi evidence                                    | CLOSED    |
+----+----+---------------------------------------------------------------------------------+-----------+
```

---

#### 1. Finding H1 (P1) — Đồng Bộ Tuyệt Đối Canonical Hash Contract Giữa Java Và Python
- **Hiện trạng tại F03:**
  - `CatalogSyncWorker` dùng `ObjectMapper.writeValueAsString()` mặc định rồi băm SHA-256. Thứ tự key phụ thuộc vào serializer.
  - Python `CatalogSyncManager.compute_hash` dùng `json.dumps(payload, sort_keys=True, ensure_ascii=False)` có khoảng trắng mặc định `(", ", ": ")`.
  - Hai runtime tạo ra chuỗi bytes khác nhau, khiến bước kiểm tra declared hash trả về `HTTP 400 Bad Request` và chặn hoàn toàn worker thật.
- **Giải pháp triển khai trong F04:**
  1. **Quy Chuẩn Canonical JSON Serialization:**
     - Trong Python `CatalogSyncManager.compute_hash`: sử dụng `json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))` (loại bỏ toàn bộ khoảng trắng dư thừa, sắp xếp key tăng dần theo UTF-8).
     - Trong Java `CatalogImportService.computeSha256(String input)`: phân tích JSON vào mô hình Jackson Tree (`JsonNode`), đệ quy sắp xếp tất cả các field của `ObjectNode` theo bảng chữ cái tăng dần, rồi serialize thành chuỗi UTF-8 compact không có khoảng trắng thừa.
  2. **Kiểm Chứng Thực Nghiệm:**
     - Chạy `docs/reviews/repro/CATALOG_01_F03_probe.py`: kết quả `"hash_contract": { "match": true }` với mã băm SHA-256 trùng khớp từng byte: `4fee21b6c0ef356cf11955d626f13bcdc1d60cf1ffa391c07202b580ada1628c`.
     - Chạy `docs/reviews/repro/CATALOG_01_F04_probe.py`: xác thực kiểm tra mã băm trên payload tiếng Việt có dấu (`"Biên Niên Sử Dippie - Tiếng Việt Có Dấu 100%"`), hash khớp 100% (`fc5d19c12fbdaf5837a9e876747caff811dc11ee9795ff133b9f0ae161c01607`).

---

#### 2. Finding H2 (P1) — Mẫu Thiết Kế Candidate Manager & Hoán Đổi Tham Chiếu Nguyên Tử (Atomic Pointer Swap)
- **Hiện trạng tại F03:**
  - Trong `backend/fastapi/main.py`, hàm `sync_index` gọi `catalog_sync_manager.load_from_payload` trực tiếp trên đối tượng toàn cục trước khi kiểm tra hash và trước khi nhận publish lock.
  - Khi payload bị từ chối (mã băm sai 400 hoặc xung đột generation 409), dữ liệu phục vụ người dùng đã bị biến đổi thành dữ liệu lỗi/từ chối.
  - Chưa đảm bảo tính bền vững khi khởi động lại (restart durability).
- **Giải pháp triển khai trong F04:**
  1. **Candidate Manager Pattern (Cách ly ứng viên hoàn toàn):**
     - Tạo đối tượng `candidate_manager = catalog_sync_manager.__class__()` độc lập.
     - Tải và parse catalog trên candidate manager.
     - Xác thực `content_hash` khai báo đối chiếu với `computed_hash` của candidate *trước khi* can thiệp vào bất kỳ trạng thái toàn cục nào.
  2. **Compare-And-Swap (CAS) Dưới `_publish_lock` Toàn Cục:**
     - Nếu `req_gen < active_gen`: trả về `status: "SKIPPED"` (stale generation).
     - Nếu `req_gen == active_gen`: kiểm tra hash. Nếu khác hash -> trả về ngay lập tức `HTTP 409 Conflict` (không làm thay đổi catalog đang phục vụ). Nếu trùng hash -> trả về `status: "UNCHANGED"`.
  3. **Atomic Index Build & Pointer Swap:**
     - Xây dựng chỉ mục ứng viên `cascading_pipeline.retrieval_node.hybrid_index.build_from_catalog(...)` thành công trọn vẹn trước.
     - Lưu trạng thái bền vững xuống đĩa `data/indices/catalog_sync_state.json`.
     - Thực hiện hoán đổi tham chiếu nguyên tử (`copy_from` / atomic state commit) sang `catalog_sync_manager` toàn cục.
  4. **Phục Hồi Khi Khởi Động (Startup Durability):**
     - Đọc trạng thái từ `catalog_sync_state.json` khi module khởi động, nạp lại đúng snapshot nhất quán về cả generation, hash và item counts.

---

#### 3. Finding H3 (P1) — Tách Biệt Tuyệt Đối Hệ Thời Gian File (File Timeline) Và Hệ Thời Gian Logic (Logical Timeline)
- **Hiện trạng tại F03:**
  - `scene.start_ms` và `scene.end_ms` đã là thời gian thực tế trong file video (file timeline) theo đúng đặc tả contract.
  - Tuy nhiên, giao diện `series/[id]/page.tsx` và deep-link scene lại truyền `scene.startMs` vào hàm `resolveFileTimestamp` (hàm chuyên đổi từ *logical episode* sang *file*), cộng thêm offset một lần nữa (từ 90s thành 150s).
  - Offset không xác định (`episode_in_ms = null`) bị ép kiểu thành `0`, khiến người dùng bị tua sai về đầu file.
- **Giải pháp triển khai trong F04:**
  1. **Tua Cảnh Trực Tiếp Bằng File Timeline (`handleSeekScene`):**
     - Không gọi `resolveFileTimestamp` khi tua scene.
     - Đặt trực tiếp: `videoRef.current.currentTime = scene.startMs / 1000`.
     - Xác thực nghiêm ngặt danh tính asset: chỉ tua khi `scene.mediaAssetId === currentAssetId`.
  2. **Chuyển Đổi An Toàn Cho Logical Segment (`handleSeekSegment`):**
     - Phân định rõ ràng `segment.episodeStartMs`.
     - Gọi `resolveFileTimestamp(segment.episodeStartMs, currentAsset, segment.id, episodeId)`.
     - Nếu không tìm thấy coverage hợp lệ hoặc offset bị thiếu (`episode_in_ms === null`), hàm trả về `null` thay vì ép thành 0.
     - Giao diện người dùng khóa tính năng tua cho đoạn đó và hiển thị banner cảnh báo rõ ràng: *"Đoạn phim chưa có thông tin ánh xạ thời gian (coverage) chính xác trên tập tin này."*
  3. **Deep Link Phân Biệt Ngữ Cảnh:**
     - Tham số deep link `?scene=...` được định tuyến trực tiếp theo file timeline.
     - Tham số `?segment=...` hoặc `?t=...` được giải quyết qua bộ phân giải ánh xạ coverage an toàn.
  4. **Kiểm Chứng Thực Nghiệm:**
     - Chạy `docs/reviews/repro/CATALOG_01_F03_timestamp_probe.cjs`: trả về `unknown_logical_offset: { actual_seconds: null, expected: "unresolved; do not seek" }`.
     - Chạy `docs/reviews/repro/CATALOG_01_F04_probe.py`: xác thực tua cảnh đạt đúng 90.0s, đoạn logical hợp lệ đạt đúng 90.0s, đoạn unknown trả về `null`.

---

#### 4. Finding H4 (P1) — Cơ Chế Playback Grant Cho Trình Duyệt & Bọc An Toàn Cho Bộ Lưu Trữ Drive
- **Hiện trạng tại F03:**
  - Thẻ `<video src={...}>` trong HTML5 không thể tự đính kèm header `Authorization: Bearer <token>` từ `localStorage`.
  - `JwtAuthenticationFilter` chỉ kiểm tra header `Authorization`, dẫn đến các video thuộc chính sách bảo vệ (`authenticated` / `private`) không thể phát được trên trình duyệt.
  - Hàm `StorageKeyConfig.resolvePath` chạy kiểm tra symlink trên luồng gọi chính (caller thread) trước khi đi vào executor có giới hạn thời gian (bounded executor) của Drive adapter.
- **Giải pháp triển khai trong F04:**
  1. **Cơ Chế Playback Grant Ngắn Hạn (5 Phút):**
     - Triển khai trong `JwtUtils.java`: `generatePlaybackGrant(String assetId, Authentication auth)` và `validatePlaybackGrant(String grantToken, String expectedAssetId)`. Token HMAC-SHA256 có thời hạn 5 phút, gắn chặt với `assetId` và phân quyền của người dùng đăng nhập.
     - Thêm endpoint bảo vệ trong `MediaStreamController`: `@PostMapping("/grant/{assetId}")` để cấp grant token cho người dùng đã xác thực.
     - Cập nhật `JwtAuthenticationFilter`: trích xuất tham số `?grant=...` trên các request gửi tới `/api/media/stream/**`, xác thực tính hợp lệ và thiết lập `SecurityContext` tương ứng.
  2. **Tích Hợp Client-Side Trình Duyệt:**
     - Thêm helper `requestPlaybackGrant(assetId)` trong `frontend/lib/services/mediaService.ts`.
     - Cập nhật `frontend/app/series/[id]/page.tsx`: tự động lấy playback grant trước khi gắn URL vào thẻ `<video src={streamUrl}>` đối với các media asset được bảo vệ.
  3. **Bọc An Toàn Cho Bounded Storage Operation:**
     - Trong `StorageKeyConfig`: giới hạn kiểm tra symlink tổ tiên chỉ với các storage local, không gọi blocking `toRealPath()` trên mount Drive từ xa.
     - Trong `DriveMediaStorageAdapter`: đảm bảo toàn bộ thao tác siêu dữ liệu (`getResourceForPath`, `openChannelForPath`) được thực thi bên trong `DriveIoExecutor.executeMetadata` có circuit breaker và timeout nghiêm ngặt.

---

#### 5. Finding H5 (P2) — Bằng Chứng Nghiệm Thu Đầy Đủ Đa Tầng (Multi-Gate Verification)
- **Hiện trạng tại F03:** Báo cáo nghiệm thu dựa trên một số kiểm thử đơn lẻ, chưa bao phủ toàn diện các tầng hệ thống.
- **Thực thi trong F04:**
  1. **Spring Boot Suite:** Chạy toàn bộ 178 tests của backend (`./mvnw.cmd test`):
     - `Tests run: 178, Failures: 0, Errors: 0, Skipped: 0`.
     - Kết quả: `BUILD SUCCESS` hoàn toàn.
  2. **FastAPI AI Suite:** Chạy toàn bộ 12 integration tests (`test_catalog_retrieval.py`):
     - Bao phủ toàn bộ quá trình nạp mô hình Qwen3-4B + Phase 23 LoRA, multilingual-e5-small, kiểm tra hard constraint, grounded explanation, và endpoints `/api/index/sync`, `/api/chat`, `/v1/discover`, `/api/recommend`.
     - Kết quả: `Ran 12 tests in 132.461s - OK`.
  3. **Frontend Production Suite:**
     - Kiểm tra kiểu dữ liệu tĩnh: `npx tsc --noEmit` -> 0 lỗi.
     - Biên dịch sản phẩm: `npm run build` -> 100% thành công với 8 routes tối ưu hóa.
  4. **Kiểm Chứng Toàn Vẹn Checkpoint:**
     - Tạo patch `docs/reports/CATALOG_01_F04.patch`.
     - Kiểm tra khả năng đảo ngược: `git apply --check -R docs/reports/CATALOG_01_F04.patch` -> Exit code 0.
     - Lập bảng kê 112 tệp trong `docs/reports/CATALOG_01_F04_MANIFEST.json` kèm SHA-256 và dung lượng byte.

---

### IV. HƯỚNG DẪN VẬN HÀNH LUỒNG SẢN PHẨM (RUNBOOK)

#### Luồng 1: Admin Nhập Dữ Liệu Catalog
1. Đăng nhập trang quản trị tại `/admin/import`.
2. Tải lên tệp JSON tuân thủ chuẩn `dippie.catalog.v1`.
3. Nhấn **Kiểm Tra & Xem Trước (Preview)**: Hệ thống dry-run kiểm tra schema, tính toán diffs và mã băm canonical SHA-256.
4. Nhấn **Tiến Hành Nhập (Import)**: Dữ liệu được ghi nguyên tử vào 12 bảng cơ sở dữ liệu và tạo bản ghi outbox snapshot.
5. Theo dõi tiến trình: Scheduled worker tự động đồng bộ sang FastAPI qua HTTP kèm token bí mật và content hash. Khi hoàn tất, huy hiệu đổi sang `READY`.

#### Luồng 2: Tìm Kiếm & Khám Phá Qua CineBot
1. Người dùng tìm kiếm tại `/search` hoặc trò chuyện tại `/movies/...`.
2. Hệ thống thực hiện Hybrid Search (BM25 + Dense E5) kết hợp kiểm tra bộ lọc cứng và giải thích grounded bám sát `plot_facts` và `characters`.
3. Bấm vào kết quả phân cảnh/đoạn phim để mở trang chi tiết với đầy đủ tham số deep-link.

#### Luồng 3: Phát Video & Tua Thời Gian Chính Xác
1. Trình phát video tự động nhận diện chính sách truy cập. Nếu là protected video, client tự động lấy Playback Grant ngắn hạn qua `POST /api/media/grant/{assetId}`.
2. Khi người dùng bấm vào một **Cảnh (Scene)**: Trình phát tua trực tiếp tại `scene.startMs / 1000` (file timeline).
3. Khi người dùng bấm vào một **Đoạn (Segment)**: Hệ thống ánh xạ qua coverage JSON. Nếu có thông tin, tua đến đúng vị trí; nếu offset chưa được định nghĩa (`null`), hiển thị thông báo thân thiện và ngăn tua sai.

#### Luồng 4: Khởi Động Lại Hệ Thống (Restart Durability)
1. Khi tắt/mở lại dịch vụ FastAPI: `main.py` tự động nạp lại thế hệ và danh mục snapshot từ `data/indices/catalog_sync_state.json`.
2. Khi tắt/mở lại dịch vụ Spring Boot: `CatalogSyncWorker` quét các bản ghi `SYNCING` mồ côi và tự động chuyển về `PENDING` để tái đồng bộ an toàn.

---

### V. KẾT LUẬN

Snapshot **CATALOG-01-F04** (Frozen Checkpoint `CATALOG-01-F04-CHECKPOINT-01`) đã giải quyết triệt để 100% các phát hiện từ H1 đến H5, vượt qua tất cả các gate kiểm thử độc lập, bảo toàn trọn vẹn hợp đồng dữ liệu người dùng và sẵn sàng đưa vào vận hành thực tế.
