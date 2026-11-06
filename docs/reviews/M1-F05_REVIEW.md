# M1-F05 — Review độc lập

Ngày 14/10/2026, Asia/Bangkok. Verdict: **CHANGES REQUESTED — chỉ 1 P2, rating retry handler ở Profile**. Không làm lại Card/Detail/context/backend đã đạt.

## Checks

- Frontend suite actual-source: 24/24 pass, 0 skipped, exit 0, 1398ms. TypeScript và Next production build exit 0.
- Patch numstat/reverse check exit 0, 6 files, scope đúng.
- Source và component tests xác nhận Card add/delete uncertain labels/clicks/confirmed transition; Detail watchlist/favorites/rating banner có intent-specific feedback. Profile giữ grids khi library error và có retry banner.
- Backend không đổi, không rerun; bằng chứng 8/8 thuộc review trước. Không DB live/GPU hoặc application edits/commit/push trong review. Chưa browser E2E; component hook adapter là source execution.

## P2 — Profile retry chấm điểm đang xóa điểm

`frontend/features/profile/components/ProfileOverview.tsx:219–226`: handleRemoveMissingItem gọi removeRating vô điều kiện khi tab ratings. Cả found/error/orphan rating buttons dùng handler này nhưng aria-label/title phân biệt intent rate và remove_rating. Nếu intent rate, label “Chưa xác nhận điểm • Thử lưu lại điểm đánh giá” vẫn gọi DELETE.

Repro chạy actual Profile và actual production provider, fake backend commit rating 9 rồi mất response, reconcile 500, click button trong tab ratings:

```
label: Chưa xác nhận điểm • Thử lưu lại điểm đánh giá
methods: [POST, DELETE]
finalBackendRating: null
```

Script `docs/reviews/repro/M1_F05_profile_rating_repro.cjs`, output cùng tên `_output.json`. Component adapter tái sử dụng từ suite Gemini, không copy implementation Profile; không network/DB. Suite test 24 hiện chọn tab watchlist và chỉ assert handler watchlist, chưa click ratings/favorites dù title đề cập cả ba.

## Sửa đúng phạm vi

Profile cần dùng rateMovie với getUnconfirmedRating khi intent rate; removeRating khi intent remove_rating hoặc thao tác xóa confirmed. Không default bịa điểm; missing score phải có error/verify phù hợp. Apply một handler chung cho found/error/orphan rating rows. Tests actual component + provider verify request POST/body đúng score và giữ rating sau retry, DELETE đúng cho remove intent; các selectors và transition confirmed vẫn đúng.

Giao `docs/prompts/M1-F06_GEMINI_PROMPT.md`; chỉ nhánh này/tests và report. Không mở thêm features hoặc quay lại lifecycle.
