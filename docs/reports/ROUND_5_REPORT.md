# ROUND 5 Implementation & Verification Report

> **Loop Mode:** Round-Based Review Cycle (`docs/GEMINI_CODEX_REVIEW_LOOP.md`)  
> **Target Round ID:** 5 | **Prompt Version:** 5  
> **Milestone:** M2 (Catalog Backend & Animation Discovery)  
> **Run ID:** `run-round5-20261014-0805`  
> **Status:** READY FOR REVIEW  
> **Implementation Engineer:** Antigravity (Gemini)  
> **Lead Reviewer:** Codex  

---

## 1. Executive Summary

Trong **Vòng 5**, toàn bộ 4 findings **S1, S2, S3, S4** (mức độ P2) từ `docs/reviews/LOOP_ROUND_4_REVIEW.md` đã được xử lý triệt để trên codebase sản phẩm:

1. **S1 (P2) — Bảo toàn Draft Input trước URL Update trễ từ Router:**
   - **Nguyên nhân gốc rễ:** `SearchExperience.tsx` trước đây có effect đồng bộ `setInputValue(urlQuery)` vô điều kiện mỗi khi URL thay đổi. Khi router push có độ trễ bất đồng bộ: user đang ở `q=A`, gõ `B`, sau 350ms debounce router push `q=B`. Nếu user tiếp tục gõ `C` trước khi router push hoàn tất, khi URL `q=B` cập nhật về component, effect cũ đã set đè input về `B`, làm mất ký tự `C` của người dùng.
   - **Giải pháp triển khai:**
     - Sử dụng `lastPushedQueryRef` để ghi nhận giá trị query do chính component vừa đẩy lên router (`own navigation acknowledgment`).
     - Khi URL thay đổi: nếu `lastPushedQueryRef.current === urlQuery`, đây là phản hồi từ thao tác push của chính component. Nếu user đã gõ tiếp (`inputValue !== urlQuery`), quyền ưu tiên thuộc về thao tác gõ của user -> giữ nguyên `inputValue` và xóa ref, cho phép debounce tiếp theo đẩy giá trị mới (`C`).
     - Khi URL thay đổi do người dùng nhấn **Back / Forward** trên trình duyệt hoặc deep link bên ngoài (`lastPushedQueryRef.current !== urlQuery`), `inputValue` được đồng bộ chuẩn xác về `urlQuery`.
     - Nút Xóa từ khóa ("Clear") và "Đặt lại bộ lọc" có chính sách đồng bộ nhất quán: dọn dẹp `lastPushedQueryRef` và input draft ngay lập tức.

2. **S2 (P2) — Gắn Canonical Query Key vào Snapshot & Chống No-Results Giả:**
   - **Nguyên nhân gốc rễ:** Khi chuyển từ một query cũ rỗng (`items: []`) sang một query mới đang tải (`loading: true`), nhánh render `data && data.items.length === 0` vẫn kích hoạt với `urlQuery` mới. Giao diện vừa hiện chỉ báo loading vừa khẳng định "Không có phim hoạt hình nào khớp với từ khóa [query mới]" trong khi request query mới chưa trả về.
   - **Giải pháp triển khai:**
     - Tạo kiểu dữ liệu `DataSnapshot` chứa đầy đủ metadata của request đã hoàn tất: `{ key, query, genres, yearMin, yearMax, sort, direction, page, size, data }`.
     - Tính toán `currentParamsKey` từ các tham số chuẩn hóa hiện hành. Cờ `isCurrentData = dataSnapshot !== null && dataSnapshot.key === currentParamsKey`.
     - Khi một query mới đang in-flight (`loading && !isCurrentData`), giao diện **bắt buộc** hiển thị Skeleton loading và cờ `Đang cập nhật...`, tuyệt đối không render thông báo No-Results cho query mới trước khi có response.
     - Khối thông báo Empty state chỉ render khi và chỉ khi `isCurrentData && dataSnapshot.data.items.length === 0`.
     - Nếu còn snapshot cũ trong lúc đang tải query mới, giao diện ghi rõ nhãn "Kết quả trước: X phim" kèm hiệu ứng opacity và không coi đó là kết quả của query mới.

3. **S3 (P2) — Hỗ trợ Đầy đủ URL Parameters `yearMin`, `yearMax`, `size` theo Backend Contract:**
   - **Nguyên nhân gốc rễ:** Vòng 4 chưa trích xuất `yearMin`, `yearMax` từ URL search parameters và hard-code kích thước trang `size = 12`, làm rơi rụng các bộ lọc nâng cao khi người dùng truy cập qua URL hoặc phân trang.
   - **Giải pháp triển khai:**
     - Trích xuất và validate nghiêm ngặt `yearMin` (1888–2100), `yearMax` (1888–2100), và `size` (1–100, mặc định 12) từ URL search parameters; chuyển đổi thành số nguyên hợp lệ (không chấp nhận số thực làm sai lệch contract).
     - Forward đầy đủ `yearMin`, `yearMax`, `size` sang `browseCatalog` cùng với `animationOnly=true`.
     - Bổ sung thanh tóm tắt bộ lọc nâng cao (**Advanced Filter Summary Bar**) hiển thị trực quan các tiêu chí active: `Từ năm: ...`, `Đến năm: ...`, `Cỡ trang: ...`.
     - Xử lý invalid range (`yearMin > yearMax`): hiển thị banner cảnh báo rõ ràng `Khoảng năm không hợp lệ`, không gửi request lỗi lên backend, cung cấp nút "Xóa bộ lọc" dọn dẹp URL sạch sẽ.

4. **S4 (P2) — Thay Thế Hoàn Toàn Simulation Tests Bằng Tests Chạy Production Code:**
   - **Nguyên nhân gốc rễ:** Test suite Vòng 4 sử dụng các helper giả lập nội bộ (`parseSearchExperienceUrl`, `serializeSearchUrl`, `mockFetch`) thay vì thực thi component thật.
   - **Giải pháp triển khai:**
     - Viết lại toàn bộ [`frontend/tests/search_experience_suite.mjs`](file:///d:/Class/movie-rcm-system/frontend/tests/search_experience_suite.mjs) (12 tests) sử dụng `typescript.transpileModule` và harness thực thi mã nguồn thật của [`SearchExperience.tsx`](file:///d:/Class/movie-rcm-system/frontend/features/search/components/SearchExperience.tsx) và [`MovieCard.tsx`](file:///d:/Class/movie-rcm-system/frontend/features/movies/components/MovieCard.tsx).
     - Không có bất kỳ helper giả lập logic nào trong test suite.
     - Test suite bao phủ đầy đủ: S1 (draft preservation khi router trễ, external back/forward, clear), S2 (query key binding, pending transitions, loading skeleton), S3 (year/size URL forwarding, invalid year range reset), và S4 (generation guard slow A/fast B, unmount cancellation, MovieCard missing poster fallback với icon `Film`, Next Image rendering, và unconfirmed watchlist retry action).

---

## 2. Changeset & Hash Manifest

### 2.1 Own Changed Files

| File | Trạng thái | SHA256 Hash | Size (Bytes) |
| :--- | :--- | :--- | :--- |
| `frontend/features/search/components/SearchExperience.tsx` | **Modified** | `99f503b2a3ce7dc7dae03dbb8a0d6a5b48f7d7eb08cccfa64fca31d23a35bb76` | 22,606 |
| `frontend/tests/search_experience_suite.mjs` | **Modified** | `3eee0d9ae51102beca5d7f3e6fce9230f640bcb8c57e35132dd78b07ea0892c2` | 24,270 |

*Ghi chú: [`frontend/features/movies/components/MovieCard.tsx`](file:///d:/Class/movie-rcm-system/frontend/features/movies/components/MovieCard.tsx) (SHA256: `2192d2178ffb2df3233f2065f3fe76851c4dfca8a30bef16dfc4a3d7f4ee3a57`) được snapshot giữ nguyên và chạy test trực tiếp từ production code trong Vòng 5.*

### 2.2 Patch Integrity Checks

- **Patch file:** [`docs/reports/ROUND_5.patch`](file:///d:/Class/movie-rcm-system/docs/reports/ROUND_5.patch)
- **Lệnh kiểm tra numstat:**
  ```bash
  git apply --numstat docs/reports/ROUND_5.patch
  ```
  *Kết quả:*
  ```
  233	83	frontend/features/search/components/SearchExperience.tsx
  707	176	frontend/tests/search_experience_suite.mjs
  ```
  *Exit code:* `0`.
- **Lệnh kiểm tra reverse patch check:**
  ```bash
  git apply --reverse --check docs/reports/ROUND_5.patch
  ```
  *Exit code:* `0` (Sạch sẽ tuyệt đối, không có reject hay conflict).

---

## 3. Verification & Execution Evidence

### 3.1 Test Suites Execution (46/46 Passed)

Chạy đồng thời toàn bộ 3 test suites của frontend:
```bash
node --test tests/search_experience_suite.mjs tests/catalog_service_suite.mjs tests/m1_behavior_suite.mjs
```

**Kết quả chi tiết:**
```
✔ 1. Catalog Client: browseCatalog constructs correct query string and normalizes PageResponse (140.1478ms)
✔ 2. C1: External abort after headers received while body is pending aborts transport and throws cancellation (36.5222ms)
✔ 3. C1: Slow body triggers timeout and cleans up timers (87.0703ms)
✔ 4. C1: Pre-aborted external signal rejects immediately without setting timer (33.0903ms)
✔ 5. C2: Malformed paginated payload (data={} or missing items) throws 502 (22.2598ms)
✔ 6. C2: normalizeCatalogMovie rejects missing required fields and never fabricates phantom zeros (26.3494ms)
✔ 7. C2: getCatalogMovieById verifies response ID matches requested canonical ID (23.0838ms)
✔ 8. C2: getCatalogMovieById returns null on 404 HTML body without syntax error (21.9045ms)
✔ 9. C2: Search/Query precedence: blank query falls back to search parameter (22.427ms)
✔ 1. Auth login sends verbatim raw password with spaces (144.1576ms)
✔ 2. R1 (P1): Logout while response JSON is pending does NOT resurrect session (48.5359ms)
✔ 3. R1: Runtime validation rejects malformed auth payloads (40.5588ms)
✔ 4. F1 (P1): Late A 401 response after B login does NOT trigger handleSessionExpired on B (123.6016ms)
✔ 5. F1 (P1): Old A finally does NOT release B synchronous lock for the same item (100.1794ms)
✔ 6. F2 (P1): First render of User B derives empty state before passive effects flush (56.8422ms)
✔ 7. F3 (P2): Same-actor refresh does NOT invalidate pending mutation or leave pending stuck (36.9142ms)
✔ 8. F4 (P2): Slow JSON body parsing after headers triggers timeout and aborts (50.2265ms)
✔ 9. R3: Targeted rollback: X failure retains successfully added Y (37.8058ms)
✔ 10. R4: Unavailable sessions do NOT write to guest storage (47.0399ms)
✔ 11. R7: removeRating removes rating and sends DELETE request without mutating watchlist (44.1054ms)
✔ 12. G1 (P1): Boot checking to verified A restores nonempty library (watchlist, favorites, ratings) (42.113ms)
✔ 13. G1 (P1): A -> logout -> B loads B nonempty library without leaking A library (29.0434ms)
✔ 14. G2 (P2): Older refresh body arriving after successful add preserves newly added items (34.4153ms)
✔ 15. G2 (P2): Refresh during delete followed by delete success keeps item deleted (53.2788ms)
✔ 16. G2 (P2): Rating update is protected against stale read returning old score (60.3943ms)
✔ 17. G3 (P2): Unknown write outcome (network error) triggers background reconcile (47.9117ms)
✔ 18. H1 (P2): Read initiated while write was pending cannot overwrite subsequent commit when read body arrives late (37.9994ms)
✔ 19. H2 (P2): Unknown outcome on write network loss marks operation uncertain and retrying toggle maintains POST intent (35.3621ms)
✔ 20. H2 (P2): Unknown outcome on DELETE maintains delete intent on retry without inverting to POST (44.4428ms)
✔ 21. UI H2: MovieCard renders unconfirmed ADD badge/label and click triggers retry POST, returning to normal on confirm (45.0572ms)
✔ 22. UI H2: MovieCard renders unconfirmed DELETE label and click triggers retry DELETE, returning to normal on confirm (46.0381ms)
✔ 23. UI H2: MovieDetail renders unconfirmed Watchlist, Favorite, and Rating with explicit retry buttons and handles new rating selection (16.4908ms)
✔ 24. UI H2: ProfileOverview renders persistent library error banner and orphan retry actions for Watchlist, Favorites, and Ratings (29.9996ms)
✔ 25. UI H2: ProfileOverview rating retry with production provider executes POST rating without deleting, and respects remove intent and confirmed transition across found/error/not_found rows (129.5497ms)
✔ 1. S1 (P2): Delayed router navigation does NOT overwrite user typing draft (14.6629ms)
✔ 2. S1 (P2): External navigation (browser back/forward or deep link) syncs draft input (3.628ms)
✔ 3. S1 (P2): Clear button resets input draft and triggers push with query removed (3.2848ms)
✔ 4. S2 (P2): Snapshot query key binding prevents false no-results on pending query transition (3.6885ms)
✔ 5. S2 (P2): Query transition from results to pending preserves previous results labeled as updating (4.4065ms)
✔ 6. S3 (P2): URL yearMin, yearMax, and size parameters are parsed, validated, and forwarded to browseCatalog (2.477ms)
✔ 7. S3 (P2): Invalid year range (yearMin > yearMax) renders warning and resets cleanly (3.0277ms)
✔ 8. S4 (P2): Generation guard - Slow response A does NOT overwrite subsequent response B (3.472ms)
✔ 9. S4 (P2): Cancellation and cleanup on unmount (2.7849ms)
✔ 10. S4 (P2): MovieCard renders fallback placeholder when poster is missing or empty (2.9854ms)
✔ 11. S4 (P2): MovieCard renders Next Image with correct src and alt when poster is valid (1.1922ms)
✔ 12. S4 (P2): MovieCard renders unconfirmed watchlist status badge and executes retry action (1.2315ms)
ℹ tests 46
ℹ suites 0
ℹ pass 46
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1744.2234
```
**Exit Code:** `0` (46 passed, 0 failed, 0 skipped).

### 3.2 Codex Repro Script Execution

Chạy script tái hiện độc lập của Codex (`docs/reviews/repro/ROUND_4_search_repro.cjs`):
```bash
node docs/reviews/repro/ROUND_4_search_repro.cjs
```
**Kết quả đầu ra:**
```json
[
  {
    "scenario": "delayed router update B arrives after user typed C",
    "pushes": [
      "/search?q=B"
    ],
    "before": "C",
    "after": "C"
  },
  {
    "scenario": "old empty data while new query pending",
    "showsNoResultsForNew": false,
    "showsLoading": true
  },
  {
    "scenario": "year and size URL options sent to browseCatalog",
    "yearMin": 2000,
    "yearMax": 2005,
    "size": 2
  }
]
```
**Exit Code:** `0`. Cả 3 kịch bản đều đạt chuẩn (S1: input giữ `C`; S2: `showsNoResultsForNew: false`, `showsLoading: true`; S3: nhận diện đầy đủ `yearMin=2000`, `yearMax=2005`, `size=2`).

### 3.3 TypeScript Typecheck & Production Build

- **Typecheck:**
  ```bash
  npx tsc --noEmit
  ```
  *Exit code:* `0` (Không có lỗi).
- **Production Build:**
  ```bash
  npm run build
  ```
  *Exit code:* `0` (Tất cả 7/7 routes biên dịch thành công, route `/search` đạt 6.22 kB).

### 3.4 Backend Test Baseline Reference

Theo quy định của `GEMINI_CURRENT_TASK.md`: backend Spring Boot không có thay đổi trong Vòng 5, bảo lưu kết quả nghiệm thu **17/17 tests PASS** từ Vòng 3 (chứng cứ tại `docs/reports/M2_M3_STATUS.json` và `docs/reviews/LOOP_ROUND_2_REVIEW.md`).

---

## 4. Acceptance Matrix (S1–S4)

| Finding | Vấn đề tại Vòng 4 | Giải pháp tại Vòng 5 | Chứng cứ kiểm thử | Kết luận |
| :--- | :--- | :--- | :--- | :--- |
| **S1 (P2)** | URL update chậm từ router push đè mất ký tự người dùng vừa gõ tiếp. | Theo dõi `lastPushedQueryRef`; user typing có độ ưu tiên cao hơn router push trễ. Đồng bộ draft khi external navigation. | Test 1, 2, 3 trong `search_experience_suite.mjs` & Codex Repro Scenario 1. | **RESOLVED** |
| **S2 (P2)** | Query cũ rỗng + query mới pending -> hiển thị No-Results cho query mới trước khi có kết quả. | Gắn canonical query key vào `dataSnapshot`. Khi pending, bắt buộc hiển thị Skeleton và Updating indicator; chỉ hiển thị No-Results khi response chính thức của query đó trả về rỗng. | Test 4, 5 trong `search_experience_suite.mjs` & Codex Repro Scenario 2. | **RESOLVED** |
| **S3 (P2)** | URL `yearMin`, `yearMax`, `size` bị bỏ qua; hard-code `size=12`. | Parse, validate và forward `yearMin`, `yearMax`, `size` sang `browseCatalog`; thêm summary bar; xử lý invalid year range rõ ràng. | Test 6, 7 trong `search_experience_suite.mjs` & Codex Repro Scenario 3. | **RESOLVED** |
| **S4 (P2)** | Test suite dùng helper mô phỏng thay vì chạy code sản phẩm. | Viết lại test suite transpile và thực thi actual `SearchExperience.tsx` và `MovieCard.tsx`. Cover S1–S3, generation guard slow A/fast B, unmount abort, poster fallback, actions. | 12 tests trong `search_experience_suite.mjs` chạy trực tiếp actual components. | **RESOLVED** |

---

## 5. Scope Boundaries & Next Steps

- **Scope tuân thủ:** Toàn bộ thay đổi gói gọn trong `SearchExperience.tsx` và `search_experience_suite.mjs`.
- **Bảo toàn:** Không can thiệp backend, không sửa AI/FastAPI/Qwen, không tác động DB live, không can thiệp Home/Detail/Profile.
- **Tiếp theo:** Sau khi Codex nghiệm thu Search Gate ở Vòng 5, sẵn sàng nhận nhiệm vụ chuyển giao các trang Home / Detail / Profile cutover sang Catalog API trong Vòng 6.
