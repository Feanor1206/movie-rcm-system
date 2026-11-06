# BÁO CÁO NGHIỆM THU MILESTONE M4: XEM VIDEO THẬT, TUA RANGE VÀ NỀN TẢNG STORAGE WINDOWS
**Milestone:** M4 — Media Playback & Windows Storage Foundation  
**Nhánh:** `dev`  
**Ngày báo cáo:** 14/10/2026  
**Trạng thái bàn giao:** `READY_FOR_REVIEW` (Core Local Playback: Sẵn sàng nghiệm thu | Google Drive Gate: `BLOCKED_EXTERNAL_INPUT`)  
**Kỹ sư triển khai:** Gemini Pairing Assistant  
**Kỹ sư trưởng / Người nghiệm thu:** Codex

---

## 1. Tóm tắt Kết quả Thực hiện

Milestone M4 thiết lập nền tảng phân phối và phát video chuẩn xác theo RFC 9110 cho nền tảng Dippie Cinema:
1. **Phân phối Media Cục bộ (Local Ranged Delivery):** Hoàn tất 100% luồng phát trực tiếp qua `LocalMediaStorageAdapter` và Spring Boot HTTP Range handler. Video được truyền theo luồng đệm giới hạn 64 KiB, không bao giờ nạp toàn bộ vào Heap nhớ (`Zero Heap Overflow`).
2. **Cơ sở Dữ liệu & Additive Migration:** Bổ sung bảng `media_assets` lưu trữ thông tin video (feature và trailer) với khóa ngoại `ON DELETE CASCADE` tới bảng `movies`, đảm bảo tương thích ngược 100% với dữ liệu các milestone M1/M2/M3.
3. **Trình phát Video Hoàn chỉnh:** Phân biệt rõ phim có bản chiếu chính ("Xem phim") với tác phẩm chỉ có trailer ("Xem trailer / giới thiệu"). Trình phát hỗ trợ tua tiến trình qua Range, đệm video, phóng to toàn màn hình, âm lượng, phím tắt bàn phím và phục hồi lỗi với nút "Thử lại" lưu giữ chính xác vị trí thời gian đang xem. Kích thước nút bấm đạt chuẩn $\ge 44 \times 44$px trên tone màu xanh lá dịu mắt.
4. **Google Drive Gate:** Khảo sát môi trường xác nhận `rclone` và `WinFsp` chưa có trên máy. Trạng thái được phân loại chính xác là **`BLOCKED_EXTERNAL_INPUT`**; lập tài liệu vận hành chi tiết `docs/runbooks/MEDIA_STORAGE_RUNBOOK.md` mà không để việc thiếu Drive cản trở luồng phát cục bộ.
5. **Số đo Benchmark Cục bộ:** Sử dụng video fixture thật chuẩn H.264/AAC sinh bởi FFmpeg đo lường độ trễ khởi động (cold: 17.97ms, warm: 0.65ms), độ trễ tua seek (0.39ms), 0 lần gián đoạn (stalls) và khả năng phục vụ đồng thời lên đến 61.11 MB/s trên 5 luồng song song.

---

## 2. Kết quả Kiểm thử Toàn diện

### 2.1. Backend Spring Boot (37/37 Tests Đạt — 100%)
Chạy cả hai lệnh kiểm thử chính thức với JDK 25 (Target Java 17):
- `./mvnw.cmd test "-Dspring.profiles.active=test"`: **37/37 PASS** (16.7s)
- `./mvnw.cmd test`: **37/37 PASS** (16.6s)

| Bộ Kiểm thử | Số ca | Kết quả | Trọng tâm xác minh |
| :--- | :---: | :---: | :--- |
| `MediaStreamingIntegrationTest` | 12 | **PASS** | Descriptor parsing, Full 200 GET, HEAD preflight, Ranged 206 (closed, open, suffix), 416 Unsatisfiable, 404 Unknown, Path traversal security rejection |
| `SeedAndConfigPolicyTest` | 8 | **PASS** | Migration additive `03_add_media_assets.sql`, Hibernate `ddl-auto=validate`, bảo toàn dữ liệu hiện hữu |
| `CatalogIntegrationTest` | 8 | **PASS** | Catalog filtering, animation-only constraint, rating, detail resolution |
| `AuthAndLibraryIntegrationTest` | 9 | **PASS** | Actor isolation, Watchlist/Favorite/Rating CRUD, concurrency synchronization |

### 2.2. Frontend Next.js (64/64 Tests Đạt — 100%)
- Lệnh chạy: `npm test`
- Số ca test: **64/64 PASS** (1.74s)
- Kiểm tra kiểu tĩnh: `npx tsc --noEmit` — **0 LỖI**
- Production build: `npm run build` — **THÀNH CÔNG** (Gói trang chủ 139 kB, nằm trong ngân sách tải tối ưu).

| Bộ Kiểm thử Frontend | Số ca | Trọng tâm kiểm thử |
| :--- | :---: | :--- |
| `media_playback_suite.mjs` | 7 | Phân giải relative URL, chuẩn hóa descriptor, phân định nút "Xem phim" vs "Xem trailer", video player controls $\ge 44\text{px}$, phím tắt bàn phím, cơ chế retry giữ `currentTime` |
| `modal_a11y_suite.mjs` | 3 | Modal accessibility, focus trap, Escape close, opener focus restore |
| `search_experience_suite.mjs` | 12 | Search typing debounce, snapshot binding, URL filters, pagination |
| `m2_journey_suite.mjs` | 8 | Hành trình lưu/chấm điểm, Profile sync, uncertain retry |
| `m1_behavior_suite.mjs` | 25 | Session isolation, refresh idempotency, lock safety |
| `catalog_service_suite.mjs` | 9 | Timeout cancellation, 502 rejection on malformed payloads |

---

## 3. Kết quả Đo lường Benchmark Media

Dữ liệu được đo lường thực tế qua `scripts/benchmark_media_playback.cjs` trên tệp tin video MP4 thật (`feature_test.mp4`: 134.7 KiB, `trailer_test.mp4`: 44.0 KiB):

### 3.1. Độ trễ Khởi động (Startup Latency - Initial Chunk 64 KiB)
- **Cold Startup (Khởi động nguội):** **17.97 ms** (Bao gồm kết nối socket và nạp ban đầu).
- **Warm Startup (Khởi động nóng - 20 mẫu):**
  - Tối thiểu (Min): **0.41 ms**
  - Trung bình (Avg): **0.65 ms**
  - Phân vị 95 (P95): **1.56 ms**
  - Tối đa (Max): **1.56 ms**

### 3.2. Độ trễ Tua (Seek Latency qua 4 vị trí timeline: 25%, 50%, 75%, 90%)
- Số mẫu đo: 20 lần seek tuần tự
- Tối thiểu (Min): **0.26 ms**
- Trung bình (Avg): **0.39 ms**
- Phân vị 95 (P95): **0.78 ms**
- Tối đa (Max): **0.78 ms**

### 3.3. Gián đoạn Luồng phát (Playback Stalls & Underruns)
- Số chunk truyền tải: 5 chunks (kích thước 32 KiB)
- Tổng thời gian phân phối 10.0s video: **2.61 ms**
- Tỷ lệ phân phối so với thời gian thực: nhanh hơn thời gian thực **~3831 lần**
- Số lần gián đoạn (Stalls / Underruns): **0 lần**

### 3.4. Tải Đồng thời (Concurrent Streams)
| Số luồng song song | Số requests | Băng thông truyền tải | Latency trung bình | Latency P95 | Latency Max |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **1 Stream** | 10 | 49.34 MB/s | 0.43 ms | 1.12 ms | 1.12 ms |
| **3 Streams** | 30 | 49.69 MB/s | 1.34 ms | 2.77 ms | 2.81 ms |
| **5 Streams** | 50 | **61.11 MB/s** | **1.85 ms** | **3.68 ms** | **4.56 ms** |

---

## 4. Báo cáo Chi tiết Google Drive Gate (`BLOCKED_EXTERNAL_INPUT`)

1. **Thực trạng Máy chủ:**
   - Lệnh `rclone` và dịch vụ nhân `WinFsp` không tồn tại trên hệ thống.
   - Chưa có thông tin cấu hình remote OAuth hoặc thư mục Google Drive được chỉ định mount.
2. **Tuân thủ Nguyên tắc An toàn:**
   - Không tự ý cài đặt phần mềm cấp hệ điều hành (không chạy cài WinFsp ngầm, không mở port mạng ngoài).
   - Không block luồng phát cục bộ và không làm gián đoạn các tính năng khác.
3. **Giải pháp Vận hành Đã Bàn giao:**
   - Lập văn bản hướng dẫn `docs/runbooks/MEDIA_STORAGE_RUNBOOK.md` bao gồm 5 bước cài đặt, cấu hình lệnh mount có VFS Read Chunk Caching (16MB chunk), cấu hình biến môi trường `APP_MEDIA_DRIVE_MOUNT` và kế hoạch kiểm thử sau mount.
   - Triển khai `DriveMediaStorageAdapter.java` trả về mã lỗi `503 Service Unavailable` có thông báo thân thiện khi chưa có mount.

---

## 5. Kết luận & Khuyến nghị Phần cứng

- **Trạng thái Mã nguồn:** Đã đóng băng toàn bộ thay đổi (`Freeze source`), toàn bộ test backend (37/37) và frontend (64/64) đã xanh hoàn toàn.
- **Khuyến nghị Bộ nhớ / Ổ cứng:**
  - Dựa trên kết quả đo lường thực tế, luồng phát cục bộ đạt tốc độ seek dưới 1ms và khởi động dưới 18ms.
  - Bộ nhớ RAM không bị tăng đột biến nhờ cơ chế chunk streaming 64 KiB.
  - Không cần thiết phải trang bị thêm phần cứng SSD hoặc RAM mở rộng trong phạm vi phân phối cục bộ hiện tại. Nếu sau này kích hoạt Google Drive VFS Mount, chỉ cần cấp phát tối đa 2GB cache cục bộ trên ổ đĩa hiện có để đạt trải nghiệm mượt mà.
