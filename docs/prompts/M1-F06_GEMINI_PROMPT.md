# M1-F06 — Sửa duy nhất Profile rating retry

Bạn là Gemini tại `D:\Class\movie-rcm-system`. Đọc `docs/reviews/M1-F05_REVIEW.md`. Chỉ sửa Profile rating handler và regression tests; giữ mọi phần F05 đã đạt. Không chuyển M2, không làm lại context/lifecycle/backend.

Trong ProfileOverview, nút rating intent 'rate' ghi “Thử lưu lại” nhưng handleRemoveMissingItem gọi removeRating. Sửa handler chung:
- uncertain + intent rate: gọi rateMovie(id, getUnconfirmedRating(id), title nếu có), score đúng bản ghi uncertain.
- uncertain + intent remove_rating: gọi removeRating.
- confirmed + người dùng chọn xóa: gọi removeRating.
- missing/invalid retry score: verify/error rõ, không fallback điểm bịa hoặc DELETE.

Áp dụng cho found/error/orphan rating rows, giữ pending/labels/aria consistent. Không thay labels để hợp thức hóa hành vi xóa sai. Có thể đổi tên handler cho rõ nhưng không refactor ngoài scope.

Regression actual Profile + actual production provider/mock transport: POST rating 9 đã commit rồi lost response, reconcile 500 → click “Thử lưu lại” ở tab ratings → POST score 9, final backend rating 9. Removal intent → DELETE, không POST. Test cả rows found/error/not_found và confirmed transition; không chỉ mock callback boolean hoặc chọn watchlist tab.

Bằng chứng: `docs/reviews/repro/M1_F05_profile_rating_repro.cjs` và output. Không sửa repro để che lỗi. Giữ 24 existing tests, chạy suite + TypeScript/build, không cần rerun backend không đổi.

Snapshot F06; bàn giao `docs/reports/M1-F06_REPORT.md`, `docs/reports/M1-F06.patch`, numstat/reverse check pass. Không AI/GPU/DB live/commit/push/reset hoặc scope mới. READY FOR REVIEW M1-F06 một lần sau fix nhỏ này.
