# M1-F03 — Snapshot lifecycle và read/write reconciliation — Báo cáo ready for review

> **Ticket:** M1-F03 (Follow-up toàn diện khắc phục findings G1–G3 từ Codex review)  
> **Kỹ sư triển khai:** Gemini  
> **Kỹ sư trưởng nghiệm thu:** Codex  
> **Baseline snapshot:** `.f03_snapshot/` (đối soát SHA256 cho toàn bộ 13 files liên quan)  
> **Patch file:** `docs/reports/M1-F03.patch`  
> **Trạng thái:** **READY FOR REVIEW M1-F03**  

---

## 1. Tóm tắt bối cảnh và mục tiêu

Sau đợt nghiệm thu độc lập M1-F02 từ Codex (`docs/reviews/M1-F02_REVIEW.md`), kết luận là **CHANGES REQUESTED** với 1 blocker P1 (G1) và 2 nhóm P2 (G2, G3).
Gemini đã tạo baseline snapshot xác thực `.f03_snapshot/` (đối soát SHA256 cho toàn bộ 13 files liên quan) và triển khai một đợt duy nhất hoàn thiện toàn bộ findings G1–G3 theo đúng chỉ đạo trong `docs/prompts/M1-F03_GEMINI_PROMPT.md`.

Các cải tiến cốt lõi đã hoàn tất:
1. **G1 — Snapshot Lifecycle across Transitions:**
   - Sửa đổi cơ chế cam kết (commit) snapshot: khi phản hồi hợp lệ của tài khoản hiện tại về, snapshot được cập nhật với `ownerKey: thisActorKey` mới ngay cả khi snapshot trước đó thuộc về `status: checking`, `guest` hoặc tài khoản A cũ.
   - Giữ vững tính bất biến cô lập: Tại Render #1 của User B (trước khi passive effects hay fetch chạy), UI lập tức nhận `[]` (hoặc guest data) qua kiểm tra đồng bộ `snapshot.ownerKey === currentActorKey`. Dữ liệu của User A tuyệt đối không bị expose.
2. **G2 — Mutation Journal Overlay & Read/Write Ordering:**
   - Xây dựng sổ nhật ký thao tác có cấu trúc (`operationsJournalRef: Map<string, OperationRecord>`) định danh theo `${action}:${movieId}` (không bẻ chuỗi bằng delimiter `:`).
   - Thiết lập chính sách phối hợp Read/Write rõ ràng:
     - Phản hồi đọc cũ ($R$) về muộn không được ghi đè lên các thao tác đã hoàn thành hoặc đang chờ có thời điểm bắt đầu $readVersion \ge R$.
     - Thao tác thêm phim mới bảo lưu mục trong danh sách hiển thị dù read body cũ trả về danh sách rỗng.
     - Thao tác xóa phim bảo đảm mục bị loại bỏ dù read cũ trả về mục đó.
     - Đánh giá sao (chấm điểm mới hoặc gỡ điểm) được bảo vệ trọn vẹn trước phản hồi đọc cũ.
3. **G3 — Unified Read & Background Reconcile with Unknown Outcomes:**
   - Hợp nhất hoàn toàn `loadLibraryForCurrentActor` và `reconcileAuthoritativeLibrary` qua một core function duy nhất `performFetchLibrary`.
   - Khóa định danh actor mang token: `user:{userId}:{token}`. Khóa đồng bộ mang thế hệ phiên: `${sessionGen}:${actorKey}:${action}:${movieId}`.
   - Thao tác mutation gặp lỗi mạng (`TypeError / Failed to fetch`) hoặc timeout (`AbortError`) được xác định là **Unknown Write Outcome**: không rollback đảo chiều mù quáng, tự động kích hoạt hòa giải ngầm có giới hạn để đồng bộ lại trạng thái chính thức từ máy chủ.
   - Mutation chỉ trả về `true` khi và chỉ khi phiên hiện tại còn hiệu lực và thao tác thực sự thành công.

---

## 2. Ma trận khắc phục và nghiệm thu G1–G3

| Finding | Mức độ | File sửa đổi | Cơ chế xử lý đã triển khai | Bằng chứng thực tế | Kết luận |
|:---|:---|:---|:---|:---|:---|
| **G1** | **P1 (Blocker)** | [`WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx) | **Snapshot lifecycle cho actor hiện hành:**<br>1. Loại bỏ điều kiện chặn `if (prev.ownerKey !== thisActorKey) return prev;`. Thay vào đó, sau khi vượt qua guard phiên (`sessionGenRef.current === thisSessionGen && lastKnownActorKeyRef.current === thisActorKey`), phản hồi từ backend khởi tạo snapshot mang `ownerKey: thisActorKey`.<br>2. Hỗ trợ đầy đủ các chuyển đổi: checking → verified A, guest → A, A → logout → B, unavailable retry → authenticated.<br>3. Render đồng bộ tính toán `visibleWatchlist`, `visibleFavorites`, `visibleRatings` dựa trên `snapshot.ownerKey === currentActorKey`, bảo đảm Render #1 của User B hoàn toàn rỗng trước khi load xong. | 1. `docs/reviews/repro/M1_F02_runtime_repro.cjs`<br>- *boot checking to verified A, backend nonempty:* `watchlist: ['A-saved-film']`, `loading: false`, `error: null`.<br>- *A to B, backend B nonempty:* `watchlist: ['B-saved-film']`, `loading: false`, `error: null`.<br>2. `frontend/tests/m1_behavior_suite.mjs`<br>- Test 12 (G1 checking -> verified A) pass.<br>- Test 13 (G1 A -> logout -> B) pass. | **RESOLVED** |
| **G2** | **P2** | [`WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx) | **Mutation journal overlay & Read/Write Ordering:**<br>1. Áp dụng sổ nhật ký `operationsJournalRef` lưu trữ metadata thao tác (`action`, `movieId`, `readVersionAtStart`, `status: pending \| committed`, `desiredValue`).<br>2. Định danh trực tiếp theo `${action}:${movieId}`, loại bỏ rủi ro với ID phim có ký tự đặc biệt.<br>3. Khi phản hồi đọc phiên bản $R$ trả về: các mục có mutation mới hơn ($readVersionAtStart \ge R$) hoặc đang pending được áp dụng `desiredValue` thay vì server data cũ.<br>4. Bảo vệ cả add/remove watchlist/favorite, rating update/remove; successful operations đã unlock vẫn được bảo vệ trước read cũ.<br>5. Prune các committed operations cũ khi có read mới hơn cập bến. | 1. `docs/reviews/repro/M1_F02_runtime_repro.cjs`<br>- *older refresh body arrives after successful add:* `before: ['X']`, `after: ['X']`.<br>- *refresh during delete followed by delete success:* `watchlist: []`.<br>2. `frontend/tests/m1_behavior_suite.mjs`<br>- Test 14 (G2 older refresh after add) pass.<br>- Test 15 (G2 refresh during delete) pass.<br>- Test 16 (G2 rating update/remove vs stale read) pass. | **RESOLVED** |
| **G3** | **P2** | [`WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx) | **Hợp nhất Read/Reconcile & Xử lý Unknown Write Outcomes:**<br>1. Hợp nhất `loadLibraryForCurrentActor` và `reconcileAuthoritativeLibrary` qua `performFetchLibrary` với session guard, read version, timeout 7000ms cả body, AbortController và G2 journal merge.<br>2. Khóa actor phân biệt phiên: `user:{userId}:{token}`. Khóa đồng bộ: `${sessionGen}:${actorKey}:${action}:${movieId}`.<br>3. Lỗi mạng (`TypeError`) hoặc timeout (`AbortError`) sau khi gửi write request được định danh là **Unknown Outcome**: không rollback đảo chiều mù quáng, tự động gọi `performFetchLibrary({ isBackgroundReconcile: true })` để lấy dữ liệu chính xác từ máy chủ.<br>4. Mutation chỉ trả về `true` khi `isStillCurrentSession()` và thành công; stale callbacks/finally không có tác động đến phiên mới. | 1. `docs/reviews/repro/M1_F01_runtime_repro.cjs`<br>- All 5 scenarios pass (expiryCalls: 0, first B render: [], pending: false, bWrites: 1, timer: [7000]).<br>2. `frontend/tests/m1_behavior_suite.mjs`<br>- Test 17 (G3 unknown write outcome network error reconcile) pass. | **RESOLVED** |

---

## 3. Danh sách files thay đổi trong M1-F03 (3 files)

1. [`docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md`](file:///D:/Class/movie-rcm-system/docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md): Bổ sung Mục 6 cam kết kiến trúc G1–G3 (Snapshot Lifecycle, Mutation Journal Overlay, Unified Reconcile & Unknown Outcomes).
2. [`frontend/lib/context/WatchlistContext.tsx`](file:///D:/Class/movie-rcm-system/frontend/lib/context/WatchlistContext.tsx): Triển khai toàn diện G1 (lifecycle owner transition), G2 (operationsJournalRef & read/write ordering), G3 (unified performFetchLibrary, unknown outcome reconciliation, session-scoped locks).
3. [`frontend/tests/m1_behavior_suite.mjs`](file:///D:/Class/movie-rcm-system/frontend/tests/m1_behavior_suite.mjs): Mở rộng bộ kiểm thử lên 17 tests chạy trực tiếp mã nguồn production, bổ sung trọn vẹn các ca kiểm thử G1, G2, G3.

---

## 4. Kết quả kiểm thử thực tế và nghiệm thu

### 4.1 Bằng chứng kiểm tra trực tiếp Codex Repro F02 (`docs/reviews/repro/M1_F02_runtime_repro.cjs`)
- **Lệnh thực hiện:**
  ```powershell
  node docs/reviews/repro/M1_F02_runtime_repro.cjs
  ```
- **Kết quả:**
  ```json
  [
    {
      "scenario": "boot checking to verified A, backend nonempty",
      "watchlist": [
        "A-saved-film"
      ],
      "loading": false,
      "error": null
    },
    {
      "scenario": "A to B, backend B nonempty",
      "watchlist": [
        "B-saved-film"
      ],
      "loading": false,
      "error": null
    },
    {
      "scenario": "older refresh body arrives after successful add",
      "before": [
        "X"
      ],
      "after": [
        "X"
      ]
    },
    {
      "scenario": "refresh during delete followed by delete success",
      "watchlist": []
    }
  ]
  ```
- **Exit code:** `0`

### 4.2 Bằng chứng kiểm tra lại Codex Repro F01 (`docs/reviews/repro/M1_F01_runtime_repro.cjs`)
- **Lệnh thực hiện:**
  ```powershell
  node docs/reviews/repro/M1_F01_runtime_repro.cjs
  ```
- **Kết quả:**
  ```json
  [
    {
      "scenario": "late A 401 after B authenticated",
      "expiryCalls": 0
    },
    {
      "scenario": "first B render before effect-driven rerender",
      "watchlist": []
    },
    {
      "scenario": "refresh while same-actor mutation pending",
      "pending": false,
      "watchlist": [
        "X"
      ]
    },
    {
      "scenario": "A finally releases B same-item lock",
      "bWrites": 1
    },
    {
      "scenario": "mutation body pending after headers",
      "pending": true,
      "activeTimerMs": [
        7000
      ]
    }
  ]
  ```
- **Exit code:** `0`

### 4.3 Frontend Behavior Suite (`frontend/tests/m1_behavior_suite.mjs`)
- **Lệnh thực hiện:**
  ```powershell
  cd frontend
  node --test tests/m1_behavior_suite.mjs
  ```
- **Kết quả:**
  ```text
  ✔ 1. Auth login sends verbatim raw password with spaces (130.4797ms)
  ✔ 2. R1 (P1): Logout while response JSON is pending does NOT resurrect session (29.1334ms)
  ✔ 3. R1: Runtime validation rejects malformed auth payloads (23.8584ms)
  ✔ 4. F1 (P1): Late A 401 response after B login does NOT trigger handleSessionExpired on B (69.7709ms)
  ✔ 5. F1 (P1): Old A finally does NOT release B synchronous lock for the same item (63.5354ms)
  ✔ 6. F2 (P1): First render of User B derives empty state before passive effects flush (63.1284ms)
  ✔ 7. F3 (P2): Same-actor refresh does NOT invalidate pending mutation or leave pending stuck (44.4209ms)
  ✔ 8. F4 (P2): Slow JSON body parsing after headers triggers timeout and aborts (34.9072ms)
  ✔ 9. R3: Targeted rollback: X failure retains successfully added Y (35.5927ms)
  ✔ 10. R4: Unavailable sessions do NOT write to guest storage (33.5426ms)
  ✔ 11. R7: removeRating removes rating and sends DELETE request without mutating watchlist (33.0781ms)
  ✔ 12. G1 (P1): Boot checking to verified A restores nonempty library (watchlist, favorites, ratings) (34.9499ms)
  ✔ 13. G1 (P1): A -> logout -> B loads B nonempty library without leaking A library (36.6033ms)
  ✔ 14. G2 (P2): Older refresh body arriving after successful add preserves newly added items (50.1577ms)
  ✔ 15. G2 (P2): Refresh during delete followed by delete success keeps item deleted (32.2354ms)
  ✔ 16. G2 (P2): Rating update is protected against stale read returning old score (37.8029ms)
  ✔ 17. G3 (P2): Unknown write outcome (network error) triggers background reconcile (30.1566ms)
  ℹ tests 17
  ℹ suites 0
  ℹ pass 17
  ℹ fail 0
  ℹ cancelled 0
  ℹ skipped 0
  ℹ todo 0
  ℹ duration_ms 1132.1142
  ```
- **Exit code:** `0`

### 4.4 Backend Spring Boot Integration Tests
- **Lệnh thực hiện:**
  ```powershell
  cd backend/springboot
  $env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"; .\mvnw.cmd test -Dtest=AuthAndLibraryIntegrationTest
  ```
- **Kết quả:**
  ```text
  [INFO] Running com.dippie.moviercm.AuthAndLibraryIntegrationTest
  ...
  [INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 9.769 s -- in com.dippie.moviercm.AuthAndLibraryIntegrationTest
  [INFO] 
  [INFO] Results:
  [INFO] 
  [INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0
  [INFO] 
  [INFO] ------------------------------------------------------------------------
  [INFO] BUILD SUCCESS
  [INFO] ------------------------------------------------------------------------
  [INFO] Total time:  13.014 s
  ```
- **Exit code:** `0`

### 4.5 TypeScript Typecheck & Production Build
- **Typecheck:**
  ```powershell
  cd frontend
  npx tsc --noEmit
  ```
  *Kết quả:* Exit `0`, 0 error.
- **Production Build:**
  ```powershell
  cd frontend
  npm run build
  ```
  *Kết quả:* Exit `0`, tạo thành công tất cả 7 routes tĩnh/động.

### 4.6 Xác minh tính hợp lệ của Patch File (`docs/reports/M1-F03.patch`)
- **Numstat:**
  ```powershell
  git apply --numstat docs/reports/M1-F03.patch
  ```
  *Kết quả:* Exit `0`
  ```text
  36	0	docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md
  445	317	frontend/lib/context/WatchlistContext.tsx
  281	0	frontend/tests/m1_behavior_suite.mjs
  ```
- **Reverse Check:**
  ```powershell
  git apply --reverse --check docs/reports/M1-F03.patch
  ```
  *Kết quả:* Exit `0` (patch khớp chính xác với working tree và đảo ngược sạch sẽ về baseline `.f03_snapshot`).

---

## 5. Giới hạn & các phần chưa kiểm tra

1. **Cơ sở dữ liệu ngoài & tài khoản thực tế:** Kiểm thử chạy trên in-memory H2 database độc lập và mock transport trong test harness; không tác động tới PostgreSQL staging/production hay tài khoản người dùng thực.
2. **Qwen AI serving:** Toàn bộ thành phần AI (FastAPI, Qwen weights, serving pipeline) được giữ nguyên vẹn, không nạp lại model và không chiếm dụng tài nguyên GPU.
3. **Browser E2E tự động:** Không có công cụ trình duyệt E2E tự động (Playwright/Puppeteer) cài sẵn trong container; các tương tác lifecycle phức tạp đã được kiểm chứng bằng harness nạp trực tiếp file nguồn production TSX với mock hooks/DOM environment.

---

## 6. Kết luận

Toàn bộ 3 findings G1–G3 từ đợt review độc lập của Codex đã được khắc phục triệt để và chứng minh qua cả 2 script repro của Codex, bộ kiểm thử mở rộng 17 tests của frontend, và kiểm thử Spring Boot của backend.

Gemini xin bàn giao và dừng tại trạng thái:  
**READY FOR REVIEW M1-F03** để Kỹ sư trưởng Codex tiến hành nghiệm thu độc lập. Không tự ý commit/push hoặc chuyển sang M2.
