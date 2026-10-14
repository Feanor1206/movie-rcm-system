# Round 9 — Codex acceptance of M2

2026-10-14. **ACCEPTED — đóng M2 trong phạm vi functional catalog/discovery/library integration đã kiểm chứng. Cho phép bắt đầu M3.**

Checkpoint: roundId=9, promptVersion=9, runId=run-round9-20261014-0950. Cả 17 SHA256 manifest entries khớp trước/sau review. Patch reverse check exit 0. Không sửa application source, không dùng DB live/GPU/AI.

## Findings B1–B3

- B1 closed cho gate M2: selectors/postconditions có finite timeout, evaluate exceptions được kiểm tra, asset status được theo dõi. Negative self-check thực sự thử selector mất và điều kiện sai. Bộ ảnh mới có style/catalog/action states; không tái sử dụng ảnh Round 8. Browser results được Codex chạy lại độc lập, không chỉ tin các câu actual trong report.
- B2 closed: standalone có static/public; browser hiển thị authenticated fixture user qua production AuthProvider verify /auth/me. Codex ghi nhận 13 authenticated me requests, 8 account POST requests có Authorization và 257 static responses không status>=400. Đây là fixture server trong bộ test, không phải Spring live hoặc bảo mật JWT production.
- B3 closed: synthetic m2-synthetic-anim-001 không nằm trong local movie fixture. Component click journey qua production provider/persisted transport; Profile tab ratings có score9. Codex thêm assertion độc lập: tab Đã chấm điểm có border-brand selected, document.body.innerText có Điểm của bạn và 9/10; đều đạt.

## Evidence Codex vừa chạy

1. Bốn frontend suites: **54/54 PASS**, exit 0; tsc --noEmit exit 0.
2. Browser harness toàn bộ 14 steps + negative checks: exit 0. Chạy bằng reviewer wrapper docs/reviews/repro/ROUND_9_browser_review.cjs để chuyển output sang temp, giữ nguyên artifacts Gemini. Lượt tăng cường thêm 2 animation frames trước screenshot, assert selected ratings tab/visible DOM text và lưu network log riêng cũng exit0.
3. Preview --test 3/3 PASS; không ghi DB.
4. Own manifest 17/17 SHA256 stable; reverse patch check exit0.
5. Không có application source thay đổi Round 8/9: production build là prior evidence Round 7, Spring17/17 là prior evidence Round3; không gọi là vừa chạy lại.

Review evidence đã lưu vào docs/reviews/evidence/ROUND_9/: review_network.json, review_profile_dom.json, walkthrough_evidence.json và 3 ảnh đại diện của lượt Codex. Frozen images/report của Gemini không bị ghi đè. Reviewer temp output: C:\Users\Admin\AppData\Local\Temp\codex-round9-browser-review-nxLaQA.

## Giới hạn acceptance

- Browser dùng production frontend và fixture REST/auth/storage, test component dùng hook adapter; không phải full-stack production acceptance hoặc browser login/register/password validation. Browser session được seed token fixture rồi production AuthProvider gọi me; không tuyên bố đã test form login trên browser ở vòng này.
- Browser ADD uncertain/retry đạt; DELETE uncertain/retry được kiểm tra component/provider integration, chưa có browser DELETE scenario. Desktop/mobile smoke và một Tab focus assertion không phải WCAG audit, touch-target/overflow toàn trang chưa đo đầy đủ. Các mục đó tiếp tục ở M3.
- Harness hiện chưa xuất/assert toàn bộ network journal trong report Gemini, chưa bắt tất cả Runtime.exceptionThrown/Network.loadingFailed, CDP command chưa có timeout toàn cục và debugger9222 chưa preflight trong script gốc. Reviewer wrapper đã preflight9222 và xuất network; gia cố harness trong M3 khi dùng để đo/CI, không tuyên bố mọi runtime exception đã được loại trừ.
- Catalog fixture và dry-run có provenance repository-unverified, media null; chưa import DB thật. App xử lý catalog animation rỗng một cách trung thực. M2 acceptance không cho phép tự ghi DB live hoặc deploy.
- Ảnh Profile viewport đầu không thấy rating row dưới fold; bằng chứng selected tab/score là DOM assertion, không suy diễn từ crop ảnh.

## Handoff

M3 được giao trong docs/prompts/M3_UX_OPERATIONS_GEMINI_PROMPT.md và GEMINI_CURRENT_TASK.md, roundId=10/promptVersion=10. Không làm lại M1/M2 hoặc AI. Manual handoff, automation tiếp tục tắt. Git snapshot/push không đồng nghĩa deployment.
