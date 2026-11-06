# M4-F03 — Khép1P2 descriptor terminal failures; thực hiện đa agent

taskId: M4-F03
promptVersion: 3
reviewedCheckpoint: M4-F02-CHECKPOINT-01

Bạn là Gemini điều phối tại D:\Class\movie-rcm-system,branch dev. Đọc docs/reviews/M4_F02_REVIEW.md. Backend admission/cleanup,actual browser playback/harness deadlines và storage đã đạt; không làm lại. Chỉ xử lý1nhóm T1: timeout/malformed/mismatched descriptor phải error+retry thay vì loading mãi hoặc empty giả. M4 chưa accepted. Automation tắt,bàn giao thủ công.

## Theo yêu cầu người dùng: dùng nhiều agent song song

Bạn làm agent chính: chốt error contract ngay, giao3agents có ownership riêng, tổng hợp integration/tests/JS budget/artifacts. Không cho agents sửa chồng file; không tự tạo nhánh. Nếu môi trường không có delegation thật, nêu rõ giới hạn, không bịa đã có agents hoặc chỉ đổi tên các đoạn công việc.

- **Agent A — client boundary:** sở hữu frontend/lib/services/mediaService.ts và một test file mới frontend/tests/media_descriptor_boundary_suite.mjs. Phân loại timeout nội bộ khác external abort, validate descriptor. Tests dùng transpilation Node20-compatible, không import TS trực tiếp.
- **Agent B — component lifecycle:** sở hữu frontend/features/movies/components/MovieDetail.tsx và frontend/tests/media_playback_suite.mjs. Dùng contract AgentA để mọi request hiện hành kết thúc ready/error; giữ cancellation,identity,focus,legacy preview. Không sửa client của AgentA.
- **Agent C — browser verification:** sở hữu scripts/run_m4_media_walkthrough.cjs và test-only backend walkthrough server nếu cần fault injection. Thêm timeout/malformed/mismatch->retry recovery qua production component/browser. Không sửa backend production streaming/admission. Không tự ghi final artifacts khi agents khác còn viết source.

Agent chính sở hữu frontend/package.json nếu nối suite mới,contract/report và final artifacts; chỉ chỉnh integration/bundle khi agents đã bàn giao để tránh collision. Ghi agents/tasks/files/evidence thực tế trong báo cáo. Không giao model/training/GPU/Drive hoặc scope mới.

## T1 contract bắt buộc

getMediaDescriptor hiện abort controller khi hết6000ms, nhưng MovieDetail nuốt AbortError giống route cancel. Phân biệt timeout xảy ra khi caller còn active thành error recoverable; chỉ external cancellation/unmount/route cũ mới im lặng. Timeout bao phủ fetch headers+body/JSON read, listeners/timers cleanup. Không đổi policy deadline sang unlimited hoặc trả valid empty khi timeout.

Validate HTTP200 payload tối thiểu: đúng object, literal movieId khớp request, hasFeature/hasTrailer boolean thật; advertised asset có kind/stream URL hợp lệ theo contract và consistency cần thiết. Không invent request movieId khi backend thiếu,Boolean-coerce undefined hoặc string thành valid flags. Missing required shape,wrong movieId,invalid advertised media phải error recoverable; valid empty vẫn ready. Giữ legacy preview rõ ràng; không bịa feature/private availability.

MovieDetail không được bỏ mọi AbortError vô điều kiện. Với request hiện hành, timeout/malformed/mismatch cần descriptorLoading=false,role=alert và descriptor-retry-btn; retry thực sự gọi lại và200valid khôi phục feature. Route A->B abort không hiện lỗi trênB/không stale overwrite. Chốt error shape giữaA/B trước implement; không thêm dependency/framework.

## Kiểm chứng

- Production service+component tests cho timeout trước headers,body đangpending,external abort,503,200{},wrong movieId,flags/assets malformed,valid empty vàretry200. HTTP mock phải tôn trọng abort để test realistic. Repro reviewer timeout script không sửa để lấy pass.
- Browser/network fault controlled: request deadline->error->clickretry->feature,malformed/mismatch tương tự. Không chỉnh video APIs hoặc state trực tiếp trong wait predicate,không fake0 latency/empty. F02 happy path/harness deadline giữ nguyên.
- npm test trên Node20.20.2 và runtime hiện tại,tsc,production build,dynamic guard<=140KiB. Detail hiện143249/143360bytes; tối ưu gọn/lazy nếu cần,không tăng budget hay xóa behavior/tests. Backend43pass F02 là prior evidence nếu production backend không đổi; chạy targeted/full phù hợp khi đổi test server/config,không gắn nhãn prior là run mới.
- Không cần tái làm toàn bộ throughput/storage benchmark chỉ để sửa descriptor; actual fault/recovery và các checks bị ảnh hưởng là trọng tâm. Không thêm player features,HLS/episodes/Drive/AI.

## Artifacts / quyền sở hữu

Snapshot baseline thực trước sửa; patch Git tooling riêng F03,finalize trước SHA256. docs/reports/M4_F03_REPORT.md,M4_F03.patch,M4_F03_MANIFEST.json,M4_F03_STATUS.json có taskId/runId mới,promptVersion3,sourceFrozen=true,ready_for_review cuối cùng;evidence output F03 riêng. Numstat/reverse check vàhash final bytes. F02 artifacts nguyên vẹn.

Gemini KHÔNG sửa/include như own implementation các file Codex sở hữu: docs/prompts/GEMINI_CURRENT_TASK.md,docs/prompts/M4_REVIEW_CONTROL.json,docs/M4_GEMINI_CODEX_HANDOFF.md hoặc reviewer repro/review files. Nếu baseline snapshot ghi cả chúng thì label baseline/read-only,không tự chuyển command=reviewing. Codex làm gate. Bàn giao thủ công,freeze rồi kết thúc,không polling/watchdog.

Không AI/FastAPI/Qwen/GPU/model,DB live,Drive install/mount/OAuth,OS settings,deploy,kill process người khác,tạo nhánh/commit/push/reset. Codex nghiệm thu và xử lý Git trực tiếp dev theo quyền user. Chỉ dọn process test do run mình sở hữu sau xác minh identity; không kill theo tên node/java/chrome.
