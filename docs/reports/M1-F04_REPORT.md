# M1-F04 Engineering Implementation & Verification Report

> **Milestone Ticket:** M1-F04 (Follow-up to M1-F03)  
> **Repository:** `D:\Class\movie-rcm-system`  
> **Branch:** `chore/taicautruc`  
> **Status:** READY FOR REVIEW M1-F04  
> **Implementation Engineer:** Antigravity (Gemini)  
> **Lead Reviewer:** Codex  

---

## 1. Executive Summary

Milestone **M1-F04** addresses the two remaining P2 findings identified in Codex's independent review (`docs/reviews/M1-F03_REVIEW.md`):
1. **H1 (P2) — Read/Write Ordering & Commit Watermarking:** Yêu cầu làm mới (refresh/read) bắt đầu trong lúc một write mutation đang pending không được phép ghi đè (overwrite) dữ liệu khi write hoàn tất commit sau đó. Client theo dõi thời điểm commit chính xác (`committedAtReadVersion`), bảo đảm một lượt đọc chỉ được công nhận và prune bản ghi nhật ký khi lượt đọc đó được khởi tạo *sau* thời điểm commit ($R > \text{op.committedAtReadVersion}$).
2. **H2 (P2) — Unknown Outcome Lifecycle & Retry Intent Preservation:** Khi một thao tác ghi gặp sự cố mất phản hồi mạng (`TypeError`) hoặc timeout (`AbortError`) sau khi có thể đã được commit vào DB backend, client không tự ý rollback mù quáng. Thao tác được chuyển sang `status: 'uncertain'` với `desiredValue` được lưu giữ nguyên vẹn. Khi người dùng bấm thử lại (retry), thao tác bảo lưu ý định gốc (`POST` tiếp tục gửi `POST`, không bị trạng thái hiển thị lạc quan đảo chiều thành `DELETE`).

Toàn bộ các yêu cầu của Codex's repro (`docs/reviews/repro/M1_F03_runtime_repro.cjs`), 20 bài kiểm thử hành vi frontend, build production Next.js và test tích hợp backend Spring Boot đều đạt kết quả 100% PASS.

---

## 2. Root Cause Analysis & Detailed Fixes

### 2.1 H1 — Read/Write Ordering & Commit Watermarking
- **Nguyên nhân gốc (Root Cause):** Trong F03, việc bảo vệ lớp phủ dựa trên `op.readVersionAtStart >= thisReadVersion`. Khi thao tác ghi X bắt đầu tại read version 0, một thao tác refresh bắt đầu tại read version 1, và X commit thành công trên server *trước* khi body của refresh về tới client: tại thời điểm body về, `op.readVersionAtStart (0) < thisReadVersion (1)`. Do đó, dữ liệu rỗng cũ từ refresh ghi đè làm mất tác phẩm X vừa được commit.
- **Giải pháp triển khai:**
  - Bổ sung trường `committedAtReadVersion: number | null` vào kiểu `OperationRecord`.
  - Khởi tạo `committedAtReadVersion = null` khi bắt đầu mutation. Khi mutation nhận phản hồi 200 OK từ server, gán `committedAtReadVersion = readGenRef.current`.
  - Trong `performFetchLibrary`: Một lượt đọc $R$ chỉ được công nhận (acknowledge) một commit khi và chỉ khi:
    $$R > \text{op.committedAtReadVersion}$$
  - Nếu $R \le \text{op.committedAtReadVersion}$ hoặc mutation đang `pending`, client bắt buộc áp dụng lớp phủ lạc quan (`op.desiredValue`) đè lên dữ liệu server cũ.
  - Thao tác dọn dẹp nhật ký (`operationsJournalRef.delete`) chỉ được thực hiện khi $R > \text{op.committedAtReadVersion}$.

### 2.2 H2 — Unknown Outcome Lifecycle & Retry Intent Preservation
- **Nguyên nhân gốc (Root Cause):** Khi mutation gặp sự cố mạng (ví dụ `TypeError: Failed to fetch` do đứt kết nối sau khi server đã ghi DB), code F03 xóa bản ghi khỏi journal và kích hoạt background reconcile. Nếu reconcile thất bại (server tạm thời 500), giao diện giữ item lạc quan. Khi người dùng bấm lại nút toggle để thử lại, `toggleWatchlist` kiểm tra `alreadyInWatchlist` (lúc này là `true`) và quyết định gửi yêu cầu `DELETE`, dẫn đến việc xóa mất phim trên backend thay vì thử lại hành động thêm ban đầu.
- **Giải pháp triển khai:**
  - Mở rộng trạng thái bản ghi nhật ký: `status: 'pending' | 'committed' | 'uncertain'`.
  - Trong khối `catch` của `toggleWatchlist`, `toggleFavorite`, `rateMovie`, và `removeRating`: nếu gặp lỗi `AbortError` hoặc `TypeError`, bản ghi chuyển sang `op.status = 'uncertain'` thay vì xóa bỏ.
  - Khóa đồng bộ `syncPendingLocksRef` được giải phóng trong `finally`, bảo đảm `isActionPending(id)` trở về `false` để người dùng không bị kẹt spinner vô hạn.
  - Cung cấp hàm `isActionUnconfirmed(id, action)` qua `useWatchlist()` để giao diện phát hiện trạng thái chưa xác nhận.
  - Khi người dùng gọi lại thao tác (`toggleWatchlist`, `toggleFavorite`, `rateMovie`): kiểm tra xem có `existingOp` đang ở trạng thái `uncertain` hay không:
    - Nếu có, `isAdding = existingOp.desiredValue` (bảo lưu ý định ban đầu).
    - Thao tác thêm ban đầu tiếp tục gửi `POST` (idempotent), tuyệt đối không gửi `DELETE`.
    - Thao tác xóa ban đầu tiếp tục gửi `DELETE`, tuyệt đối không gửi `POST`.
  - Trong `performFetchLibrary`: bản ghi `uncertain` chỉ được công nhận hoặc dọn dẹp khi lượt đọc được khởi tạo *sau* khi thao tác bắt đầu ($R > \text{op.readVersionAtStart}$). Các lượt đọc cũ về trễ không được phép xóa bản ghi `uncertain`.

---

## 3. Changeset & Files Modified

Toàn bộ các thay đổi của M1-F04 được giới hạn nghiêm ngặt trong 3 files, được đối chiếu trực tiếp từ baseline snapshot `.f04_snapshot/`:

| File | Thay đổi chính |
| :--- | :--- |
| `frontend/lib/context/WatchlistContext.tsx` | Mở rộng `OperationRecord` (`committedAtReadVersion`, `status: 'uncertain'`); sửa logic overlay & prune theo watermark commit; xử lý unknown outcome và bảo toàn retry intent; bổ sung `isActionUnconfirmed`. |
| `frontend/tests/m1_behavior_suite.mjs` | Bổ sung regression tests 18, 19, 20 kiểm thử thực tế H1 read/write ordering, H2 POST retry intent preservation, và H2 DELETE retry intent preservation. |
| `docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md` | Bổ sung Mục 7 quy định chuẩn hợp đồng cho Commit Watermarking, Read Acknowledgment, và Vòng đời Uncertain/Retry. |

---

## 4. Verification & Evidence

### 4.1 Codex Runtime Repro (`docs/reviews/repro/M1_F03_runtime_repro.cjs`)
Lệnh thực thi:
```bash
node docs/reviews/repro/M1_F03_runtime_repro.cjs
```
**Kết quả đầu ra thực tế:**
```json
[
  {
    "scenario": "write pending -> read starts -> write commits -> old read body arrives",
    "before": [
      "X"
    ],
    "after": [
      "X"
    ]
  },
  {
    "scenario": "committed add loses response, reconcile fails, user retries toggle",
    "failedReconcile": {
      "watchlist": [
        "X"
      ],
      "pending": false,
      "error": "Không thể tải toàn bộ thư viện cá nhân từ máy chủ."
    },
    "methods": [
      "POST",
      "POST"
    ],
    "finalBackend": [
      "X"
    ]
  }
]
```
*So sánh với kết quả lỗi trước đó (`M1_F03_runtime_repro_output.json`):*
- Scenario 1: Trước đó `after: []` (bị xóa mất) $\rightarrow$ Hiện tại `after: ["X"]` (bảo toàn 100%).
- Scenario 2: Trước đó `methods: ["POST", "DELETE"]` và `finalBackend: []` (bị đảo chiều xóa mất backend) $\rightarrow$ Hiện tại `methods: ["POST", "POST"]` và `finalBackend: ["X"]` (giữ trọn vẹn ý định thêm).

### 4.2 Frontend Behavioral Test Suite (`frontend/tests/m1_behavior_suite.mjs`)
Lệnh thực thi:
```bash
node --test tests/m1_behavior_suite.mjs
```
**Kết quả đầu ra thực tế:**
```
✔ 1. Auth login sends verbatim raw password with spaces (124.8803ms)
✔ 2. R1 (P1): Logout while response JSON is pending does NOT resurrect session (34.7464ms)
✔ 3. R1: Runtime validation rejects malformed auth payloads (25.4861ms)
✔ 4. F1 (P1): Late A 401 response after B login does NOT trigger handleSessionExpired on B (82.093ms)
✔ 5. F1 (P1): Old A finally does NOT release B synchronous lock for the same item (68.7778ms)
✔ 6. F2 (P1): First render of User B derives empty state before passive effects flush (42.2136ms)
✔ 7. F3 (P2): Same-actor refresh does NOT invalidate pending mutation or leave pending stuck (40.9826ms)
✔ 8. F4 (P2): Slow JSON body parsing after headers triggers timeout and aborts (43.2333ms)
✔ 9. R3: Targeted rollback: X failure retains successfully added Y (35.7017ms)
✔ 10. R4: Unavailable sessions do NOT write to guest storage (37.6441ms)
✔ 11. R7: removeRating removes rating and sends DELETE request without mutating watchlist (34.7248ms)
✔ 12. G1 (P1): Boot checking to verified A restores nonempty library (watchlist, favorites, ratings) (37.3193ms)
✔ 13. G1 (P1): A -> logout -> B loads B nonempty library without leaking A library (36.8416ms)
✔ 14. G2 (P2): Older refresh body arriving after successful add preserves newly added items (56.8701ms)
✔ 15. G2 (P2): Refresh during delete followed by delete success keeps item deleted (40.2376ms)
✔ 16. G2 (P2): Rating update is protected against stale read returning old score (37.8651ms)
✔ 17. G3 (P2): Unknown write outcome (network error) triggers background reconcile (34.4257ms)
✔ 18. H1 (P2): Read initiated while write was pending cannot overwrite subsequent commit when read body arrives late (37.3773ms)
✔ 19. H2 (P2): Unknown outcome on write network loss marks operation uncertain and retrying toggle maintains POST intent (27.867ms)
✔ 20. H2 (P2): Unknown outcome on DELETE maintains delete intent on retry without inverting to POST (31.7124ms)
ℹ tests 20
ℹ suites 0
ℹ pass 20
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1223.2025
```
**Exit Code:** `0`

### 4.3 TypeScript Compilation Check
Lệnh thực thi:
```bash
npx tsc --noEmit
```
**Exit Code:** `0` (Không có bất kỳ lỗi kiểu dữ liệu nào).

### 4.4 Production Next.js Build
Lệnh thực thi:
```bash
npm run build
```
**Kết quả đầu ra:**
```
   ▲ Next.js 15.1.2
   - Environments: .env.local

   Creating an optimized production build ...
 ✓ Compiled successfully
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (0/7) ...
   Generating static pages (1/7) 
   Generating static pages (3/7) 
   Generating static pages (5/7) 
 ✓ Generating static pages (7/7)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                              Size     First Load JS
┌ ○ /                                    6.05 kB         135 kB
├ ○ /_not-found                          140 B           106 kB
├ ƒ /api/chat                            140 B           106 kB
├ ƒ /movies/[id]                         3.96 kB         133 kB
├ ○ /profile                             6.71 kB         136 kB
└ ○ /search                              4.04 kB         133 kB
+ First Load JS shared by all            105 kB
```
**Exit Code:** `0`

### 4.5 Backend Spring Boot Integration Tests
Lệnh thực thi:
```bash
cmd /c "set JAVA_HOME=C:\Program Files\Java\jdk-25.0.3&& mvnw.cmd test -Dspring.profiles.active=test"
```
**Kết quả đầu ra:**
```
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0 -- in com.dippie.moviercm.AuthAndLibraryIntegrationTest
[INFO] BUILD SUCCESS
[INFO] Total time: 13.184 s
```
**Exit Code:** `0`

### 4.6 Patch Integrity Verification
Lệnh thực thi:
```bash
git apply --numstat docs/reports/M1-F04.patch
git apply --reverse --check docs/reports/M1-F04.patch
```
**Kết quả đầu ra:**
```
33	0	docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md
197	60	frontend/lib/context/WatchlistContext.tsx
174	0	frontend/tests/m1_behavior_suite.mjs
```
- `git apply --reverse --check docs/reports/M1-F04.patch` trả về **exit code 0** tuyệt đối, chứng minh patch hoàn toàn tương thích và hợp lệ ngược chiều với baseline `.f04_snapshot/`.

---

## 5. Scope & Safety Commitments Preserved

- Không chỉnh sửa AI pipeline, FastAPI, Qwen serving, adapter hay model weights; không khởi tạo process GPU mới.
- Không sửa đổi database trực tiếp trong môi trường production; không xóa bảng dữ liệu hiện có.
- Không thực hiện `git commit`, `git push`, hoặc `git reset`.
- Giữ nguyên vẹn toàn bộ các thay đổi chưa commit trước đó của các ticket UX-01A, F01, F02, F03.
- Dừng lại tại **READY FOR REVIEW M1-F04** để Codex nghiệm thu độc lập.
