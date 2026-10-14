# M1-F06 Engineering Implementation & Verification Report

> **Milestone Ticket:** M1-F06 (Follow-up to M1-F05)  
> **Repository:** `D:\Class\movie-rcm-system`  
> **Branch:** `chore/taicautruc`  
> **Status:** READY FOR REVIEW M1-F06  
> **Implementation Engineer:** Antigravity (Gemini)  
> **Lead Reviewer:** Codex  

---

## 1. Executive Summary

Milestone **M1-F06** resolves the single remaining P2 finding identified in Codex's independent review (`docs/reviews/M1-F05_REVIEW.md`):
- **Vấn đề cốt lõi (Core Finding):** Trong `ProfileOverview.tsx`, mặc dù nút retry đánh giá khi thao tác ở trạng thái bất định (`status: 'uncertain'`) đã hiển thị đúng nhãn `Chưa xác nhận điểm • Thử lưu lại điểm đánh giá`, hàm `handleRemoveMissingItem` lại gọi `removeRating` vô điều kiện khi tab là `'ratings'`. Điều này dẫn đến việc khi người dùng bấm "Thử lưu lại", hệ thống lại gửi lệnh `DELETE /api/users/ratings/{id}` làm xóa mất điểm số của người dùng trên backend (`finalBackendRating: null`).
- **Phạm vi giải quyết trọn vẹn tại M1-F06:**
  1. Destructure `rateMovie`, `getUnconfirmedRating`, và `showToast` từ `useWatchlist()` trong `ProfileOverview.tsx`.
  2. Sửa handler `handleRemoveMissingItem` cho tab `'ratings'`:
     - Khi `intent === 'rate'`: lấy đúng điểm số bất định cần retry qua `getUnconfirmedRating(id)` và gọi `rateMovie(id, score, title)`. Thao tác gửi lại `POST` (idempotent), bảo lưu tuyệt đối điểm số ban đầu, không gửi `DELETE`.
     - Khi `intent === 'remove_rating'`: gọi `removeRating(id, title)` (gửi `DELETE`).
     - Khi thao tác đã confirmed (xóa điểm thông thường): gọi `removeRating(id, title)`.
     - Khi điểm số bất định không tồn tại hoặc không hợp lệ: hiển thị thông báo lỗi rõ ràng qua toast, tuyệt đối không bịa điểm giả và không gọi `DELETE`.
  3. Áp dụng đồng bộ cho cả 3 loại hàng trong tab Đánh giá: hàng tìm thấy (`status === 'found'`), hàng lỗi kết nối (`status === 'error'`), và hàng orphan (`status === 'not_found'`).
  4. Bổ sung bài kiểm thử hồi quy thực tế (Test 25) trong `frontend/tests/m1_behavior_suite.mjs` chạy trực tiếp component `ProfileOverview` cùng production `WatchlistProvider`, kiểm tra đầy đủ kịch bản POST commit lost response → retry gửi POST điểm 9 → transition sang confirmed delete gửi DELETE → kiểm tra error/orphan rows.

Toàn bộ 25 bài kiểm thử hành vi frontend, build production Next.js, kiểm tra kiểu dữ liệu TypeScript, repro Codex F05 (`M1_F05_profile_rating_repro.cjs`), và repro Codex F03 đều đạt kết quả 100% PASS.

---

## 2. Root Cause Analysis & Detailed Fixes

### 2.1 Nguyên nhân gốc (Root Cause)
Trong ticket M1-F05, `WatchlistContext` đã cung cấp `getActionIntent` và `getUnconfirmedRating`, đồng thời giao diện `ProfileOverview` đã hiển thị nhãn và aria-label chính xác theo intent. Tuy nhiên, logic click handler `handleRemoveMissingItem` ở dòng 219 vẫn giữ nguyên logic cũ:
```typescript
} else if (tab === 'ratings') {
  await removeRating(id);
}
```
Do đó, khi người dùng click vào nút có nhãn "Thử lưu lại", hàm `removeRating` được kích hoạt và gửi yêu cầu `DELETE` lên máy chủ, gây ra tình trạng xóa ngược dữ liệu người dùng muốn lưu.

### 2.2 Giải pháp triển khai
Cập nhật handler `handleRemoveMissingItem` trong `ProfileOverview.tsx`:
```typescript
const handleRemoveMissingItem = async (id: string, tab: Tab, title?: string) => {
  if (tab === 'watchlist') {
    await toggleWatchlist(id, title);
  } else if (tab === 'favorites') {
    await toggleFavorite(id, title);
  } else if (tab === 'ratings') {
    if (isActionUnconfirmed(id, 'rating')) {
      const intent = getActionIntent(id, 'rating');
      if (intent === 'rate') {
        const score = getUnconfirmedRating(id);
        if (typeof score === 'number' && Number.isFinite(score) && score >= 1 && score <= 10) {
          await rateMovie(id, score, title);
        } else {
          showToast('Không tìm thấy điểm số đánh giá hợp lệ để thử lại', 'error');
        }
        return;
      }
      if (intent === 'remove_rating') {
        await removeRating(id, title);
        return;
      }
    }
    // Confirmed removal or normal deletion
    await removeRating(id, title);
  }
};
```
Và truyền đầy đủ tiêu đề phim (`title`) vào handler tại các vị trí hiển thị dòng đánh giá.

---

## 3. Changeset & Files Modified

Toàn bộ thay đổi của M1-F06 được đối chiếu trực tiếp từ baseline snapshot `.f06_snapshot/`:

| File | Thay đổi chính |
| :--- | :--- |
| `frontend/features/profile/components/ProfileOverview.tsx` | Destructure `rateMovie`, `getUnconfirmedRating`, `showToast`; sửa `handleRemoveMissingItem` để retry đúng điểm rating với `rateMovie` khi intent là `'rate'`; giữ `removeRating` cho intent `remove_rating` và confirmed delete; áp dụng cho found/error/orphan rows. |
| `frontend/tests/m1_behavior_suite.mjs` | Bổ sung bài kiểm thử hồi quy (Test 25) chạy actual `ProfileOverview` + production `WatchlistProvider`, xác minh retry POST score 9, transition sang delete confirmed, và xử lý error/orphan rows. |
| `docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md` | Cập nhật Mục 7.3 tài liệu hóa quy chuẩn xử lý rating retry handler trong `ProfileOverview`. |

---

## 4. Verification & Evidence

### 4.1 Codex Profile Rating Repro (`docs/reviews/repro/M1_F05_profile_rating_repro.cjs`)
Lệnh thực thi:
```bash
node docs/reviews/repro/M1_F05_profile_rating_repro.cjs
```
**Kết quả đầu ra thực tế:**
```json
{
  "label": "Chưa xác nhận điểm • Thử lưu lại điểm đánh giá",
  "methods": [
    "POST",
    "POST"
  ],
  "finalBackendRating": 9
}
```
*So sánh với kết quả lỗi trước đó (`M1_F05_profile_rating_repro_output.json`):*
- Trước đó: `methods: ["POST", "DELETE"]` và `finalBackendRating: null` (bị xóa mất trên backend).
- Hiện tại: `methods: ["POST", "POST"]` và `finalBackendRating: 9` (giữ nguyên vẹn điểm 9 và gửi lại POST retry).

### 4.2 Frontend Behavioral Suite (`frontend/tests/m1_behavior_suite.mjs`)
Lệnh thực thi:
```bash
node --test tests/m1_behavior_suite.mjs
```
**Kết quả đầu ra thực tế:**
```
✔ 1. Auth login sends verbatim raw password with spaces (127.5216ms)
✔ 2. R1 (P1): Logout while response JSON is pending does NOT resurrect session (32.2416ms)
✔ 3. R1: Runtime validation rejects malformed auth payloads (25.4806ms)
✔ 4. F1 (P1): Late A 401 response after B login does NOT trigger handleSessionExpired on B (74.3797ms)
✔ 5. F1 (P1): Old A finally does NOT release B synchronous lock for the same item (68.3445ms)
✔ 6. F2 (P1): First render of User B derives empty state before passive effects flush (48.3927ms)
✔ 7. F3 (P2): Same-actor refresh does NOT invalidate pending mutation or leave pending stuck (43.4731ms)
✔ 8. F4 (P2): Slow JSON body parsing after headers triggers timeout and aborts (51.0558ms)
✔ 9. R3: Targeted rollback: X failure retains successfully added Y (43.2685ms)
✔ 10. R4: Unavailable sessions do NOT write to guest storage (35.535ms)
✔ 11. R7: removeRating removes rating and sends DELETE request without mutating watchlist (36.2771ms)
✔ 12. G1 (P1): Boot checking to verified A restores nonempty library (watchlist, favorites, ratings) (38.8367ms)
✔ 13. G1 (P1): A -> logout -> B loads B nonempty library without leaking A library (29.8304ms)
✔ 14. G2 (P2): Older refresh body arriving after successful add preserves newly added items (31.1269ms)
✔ 15. G2 (P2): Refresh during delete followed by delete success keeps item deleted (37.284ms)
✔ 16. G2 (P2): Rating update is protected against stale read returning old score (29.972ms)
✔ 17. G3 (P2): Unknown write outcome (network error) triggers background reconcile (47.7636ms)
✔ 18. H1 (P2): Read initiated while write was pending cannot overwrite subsequent commit when read body arrives late (39.1824ms)
✔ 19. H2 (P2): Unknown outcome on write network loss marks operation uncertain and retrying toggle maintains POST intent (25.7735ms)
✔ 20. H2 (P2): Unknown outcome on DELETE maintains delete intent on retry without inverting to POST (35.0147ms)
✔ 21. UI H2: MovieCard renders unconfirmed ADD badge/label and click triggers retry POST, returning to normal on confirm (41.6625ms)
✔ 22. UI H2: MovieCard renders unconfirmed DELETE label and click triggers retry DELETE, returning to normal on confirm (36.4868ms)
✔ 23. UI H2: MovieDetail renders unconfirmed Watchlist, Favorite, and Rating with explicit retry buttons and handles new rating selection (15.6899ms)
✔ 24. UI H2: ProfileOverview renders persistent library error banner and orphan retry actions for Watchlist, Favorites, and Ratings (37.2799ms)
✔ 25. UI H2: ProfileOverview rating retry with production provider executes POST rating without deleting, and respects remove intent and confirmed transition across found/error/not_found rows (104.0237ms)
ℹ tests 25
ℹ suites 0
ℹ pass 25
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1442.7304
```
**Exit Code:** `0` (25/25 tests PASS tuyệt đối).

### 4.3 Codex Runtime Repro F03 (`docs/reviews/repro/M1_F03_runtime_repro.cjs`)
Lệnh thực thi:
```bash
node docs/reviews/repro/M1_F03_runtime_repro.cjs
```
**Exit Code:** `0` (Cả 2 kịch bản H1 và H2 đều pass).

### 4.4 TypeScript Compilation Check
Lệnh thực thi:
```bash
npx tsc --noEmit
```
**Exit Code:** `0` (0 errors).

### 4.5 Production Next.js Build
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
┌ ○ /                                    6.05 kB         136 kB
├ ○ /_not-found                          140 B           106 kB
├ ƒ /api/chat                            140 B           106 kB
├ ƒ /movies/[id]                         4.6 kB          134 kB
├ ○ /profile                             7.47 kB         137 kB
└ ○ /search                              4.04 kB         134 kB
+ First Load JS shared by all            105 kB
```
**Exit Code:** `0`.

### 4.6 Backend Prior Evidence
Do không có thay đổi mã nguồn backend trong ticket M1-F06 (chỉ sửa duy nhất Profile rating handler, tests và contract), không chạy lại backend suite để tránh lãng phí tài nguyên. Kết quả kiểm thử tích hợp Spring Boot trước đó tại F02:
- Suite: `com.dippie.moviercm.AuthAndLibraryIntegrationTest`
- Kết quả: `Tests run: 8, Failures: 0, Errors: 0, Skipped: 0` (BUILD SUCCESS).

### 4.7 Patch Integrity Verification
Lệnh thực thi:
```bash
git apply --numstat docs/reports/M1-F06.patch
git apply --reverse --check docs/reports/M1-F06.patch
```
**Kết quả đầu ra:**
```
1	0	docs/contracts/M1_ACCOUNT_LIBRARY_CONTRACT.md
27	7	frontend/features/profile/components/ProfileOverview.tsx
123	0	frontend/tests/m1_behavior_suite.mjs
```
- `git apply --reverse --check docs/reports/M1-F06.patch` trả về **exit code 0**, xác nhận patch sạch sẽ, chính xác và có thể đảo chiều hoàn hảo về baseline `.f06_snapshot/`.

---

## 5. Scope & Safety Commitments Preserved

- Không chỉnh sửa AI pipeline, FastAPI, Qwen serving, adapter hay model weights; không khởi tạo process GPU.
- Không sửa đổi database production live; không xóa bảng dữ liệu hiện có.
- Không thực hiện `git commit`, `git push`, hoặc `git reset`.
- Giữ nguyên vẹn toàn bộ các thay đổi chưa commit trước đó của các ticket UX-01A, F01, F02, F03, F04, F05.
- Dừng lại tại **READY FOR REVIEW M1-F06** để Codex nghiệm thu độc lập.
