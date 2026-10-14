# SERVE-01-F02 — Sửa ba findings của review F01

Áp dụng `docs/prompts/GEMINI_ENGINEERING_RULES.md`. Đọc `docs/reviews/SERVE-01-F01_REVIEW.md` và current code trước. Patch F01 đã được triển khai và 22 tests hiện có pass; chỉ sửa những findings dưới đây, không làm lại ticket hoặc thay đổi Qwen fine-tuned.

## Phạm vi

- `backend/fastapi/services/qwen_service.py`: base selection và GGUF resolver.
- `backend/fastapi/tests/test_serving.py`: meaningful regression cases mới.
- `docs/SERVING_GUIDE.md`: ghi rõ precedence/fallback selection nếu cần.
- `docs/reports/SERVE-01-F02_REPORT.md` và valid follow-up patch.
- Sửa `docs/reports/SERVE-01-F01.patch` khi có baseline thực để tái tạo; nếu không có, ghi rõ limitation, không tạo diff giả.

Không sửa FastAPI endpoints, readiness/fallback enable policy, ranking/retrieval/normalizer semantics, frontend/Spring/Compose hoặc adapters/weights. Không khởi tạo full model khác hay tải model.

## 1. Base selection

Precedence cần thực hiện: constructor `base_model_name` explicit → BASE_MODEL_NAME explicit từ env → adapter metadata nếu cả hai không khai báo → default Qwen/Qwen3-4B.

Không đoán env/default name là implicit chỉ vì chuỗi bằng `Qwen/Qwen3-4B`. Track explicit source đúng, health vẫn báo base thực đã được loader dùng.

Tests với fake loaders và temp adapter metadata:

- Không constructor/env → adapter metadata được dùng.
- Constructor explicit khác adapter, env absent → constructor được dùng.
- Env explicit khác adapter, constructor absent → env được dùng.
- Constructor và env đều có → constructor được dùng.
- Env explicit đúng chuỗi default nhưng adapter khác → env vẫn được dùng.
- Không có explicit/metadata → default được dùng.

Isolate env trong tests; không phụ thuộc .env máy đang chạy. Không thay model deployment chính; mọi base khác ở đây chỉ là fake test IDs.

## 2. GGUF resolution

Configured explicit file tồn tại có ưu tiên; missing file tiếp tục search paths như policy trước. Trả file thực, không directory/missing path. Tracking resolved active path vẫn phản ánh file đã nạp; không load llama/GPU để kiểm tra filesystem helper.

Tests trực tiếp helper bằng temp files và controlled search paths:

- Configured explicit valid file.
- Configured directory có GGUF.
- Configured file missing, standard search candidate valid → chọn valid candidate.
- Không có file ở bất kỳ candidate nào → None.

Không mock `_resolve_gguf_file()` trong các regression filesystem tests. Có thể mock candidate paths/filesystem boundaries để tránh dựa vào model file thật của máy.

## 3. Artifact patch

Lưu before snapshot đúng scope trước follow-up để tạo patch F02 độc lập, valid Git unified diff. Không hand-edit hunk counts và không gộp changes trước vào patch mới.

Kiểm tra `git apply --numstat <patch>` và `git apply --reverse --check <patch>` đối với current source đúng follow-up, không thực sự apply. Với F01 artifact thiếu baseline thật, ghi rõ nó không đủ provenance để phục hồi, kèm valid F02 patch; không dùng báo cáo “patch riêng hợp lệ” khi Git không parse được.

## Kiểm tra và bàn giao

Rerun từ `backend/fastapi` bằng interpreter dippie-qwen, HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1, RUN_FULL_INTEGRATION=0:

```powershell
& 'C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe' -m unittest -v tests.test_serving tests.test_serving_integration
```

Report actual test totals/duration, regression expectations/actuals, patch check exit codes và limitations. Giữ nguyên healthy full-mode contract và HTTP 503/502/429. Không cần GPU live inference cho patch này. Dừng ready for review; không commit/push hoặc chuyển ticket khác.
