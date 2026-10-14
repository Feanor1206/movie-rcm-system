# Round 13 — M3 acceptance

2026-10-14. **ACCEPTED — đóng M3 trong phạm vi UX, accessibility, account/catalog journeys, cấu hình vận hành và performance baseline đã kiểm chứng.** D1/D2 của Round12 closed, không còn finding chặn gate này. Đây không phải nghiệm thu toàn bộ sản phẩm/phát video hoặc xác nhận deploy production.

## Integrity

Round13 / prompt13 / run-round13-20261014-1325 khớp control/status.21 manifest entries khớp SHA256 trước/sau review; reverse patch check exit0. Codex chỉ chạy checks/viết docs và reviewer wrapper, không sửa application source hoặc Gemini status/artifacts. Manual/dev; automation vẫn tắt. Không dùng AI/GPU/live DB hoặc can thiệp service người dùng trên3100.

## D1 closed — prod controls và CI command

- Exact current CI equivalent **mvnw.cmd test -Dspring.profiles.active=test:25/25 pass, exit0**; bare **mvnw.cmd test:25/25 pass, exit0**. Không dùng global datasource override.
- Nested contexts log duy nhất prod trong cả hai runs. Positive control assert exact profile, seed=false, sql.init=never, ddl-auto=validate; actual YAML, canonical bootstrap SQL và migration được thực thi trên H2 PG-mode riêng. Missing-JWT/password controls fail đúng key; legacy data checks giữ nguyên.
- Helper tạo bản sao property sources, không sửa system properties toàn cục hoặc nới production preflight/config/schema. Production source không đổi trong vòng13.
- Runtime review JDK25.0.3; pom target17 và CI JDK17 giữ nguyên. Local exact-command pass chưa phải bằng chứng GitHub-hosted JDK17 CI pass.

## D2 closed — dynamic budget guard

compute_build_bytes.cjs đọc manifest/files hiện tại, deduplicate layout+page, tính raw/gzip/SHA256, ghi BUILD_ID, derive underBudget và throw khi vượt143360bytes. CLI trả exit1 khi lỗi. CI nối guard sau build; walkthrough dùng helper thay bảng hằng số.

Self-tests **5/5 pass**: missing manifest, missing route, missing chunk, tiny-budget failure, real-build positive. Independent reviewer audit bằng ROUND_12_build_bytes.cjs cho số gzip trùng helper:

| Route | Gzip bytes | KiB | Budget |
| --- | ---: | ---: | ---: |
| / |139231|135.97|140 KiB|
| /search |138015|134.78|140 KiB|
| /movies/[id] |140419|137.13|140 KiB|
| /profile |139137|135.88|140 KiB|

Reviewer BUILD_ID mE-SsBbv_9D8CElBvaSSB. Đây là tổng individually-gzipped layout+page JS, loại CSS/polyfills/RSC/API; không phải full network bytes.

## Regression and runtime evidence

- npm test **57/57 pass**:54 component/provider behavior +3 modal source-structure assertions. TypeScript và production build exit0.
- Preview dry-run self-tests **3/3 pass**, không phải importer/DB onboarding.
- Actual handed browser harness chạy qua reviewer wrapper chỉ redirect output sang temp riêng. **14/14 UI steps pass**, gồm login/logout A->B qua UI, isolation/reload, save/rate, uncertain retry, history, image404, catalog error/404, mobile touch targets/collisions.3cold+3warm samples trên4routes hoàn tất exit0. Negative harness pass vì detect missing selector và intentional shift0.222 đúng kỳ vọng.
- Reviewer LCP cold/warm medians(ms):Home176/116,Search100/80,Detail148/88,Profile144/96. Đây là corrected local baseline, không gọi application speedup hoặc trải nghiệm mạng thực.
- Evidence tại docs/reviews/evidence/ROUND_13: exact-CI/bare logs, frontend tests/build, independent/dynamic JS audits, browser positive/negative logs, assertions và raw perf JSON. Gemini frozen artifacts không bị ghi đè.

## Acceptance boundaries and closure

M1/M2 giữ acceptance trước đó; M3 gate hoàn tất. Chưa nghiệm thu INP, real video startup/seek/stall/concurrency, Drive/cache, full episodes, AI user features, public-network/production load. SQL validation dùng H2 PostgreSQL mode, không giả là PostgreSQL/container đã chạy. Không deploy hoặc sửa DB live.

Theo protocol, M2 và M3 đều accepted: control=stop,lastReviewedRoundId13. Automation vốn tắt vẫn tắt, không polling, không tự giao vòng14. Ưu tiên tiếp theo là media/storage playback spike theo docs/STORAGE_PERFORMANCE_DECISION.md, hiện chỉ backlog, chưa cài/mount/mua ổ hoặc tuyên bố phát mượt.

Codex commit/push checkpoint trực tiếp dev theo quyền người dùng; không đồng nghĩa deploy hoặc remote CI đã xanh.
