# SERVE-01-F01 — Review độc lập

Ngày: 13/10/2026. Verdict: **changes requested**. Codex đọc report, patch riêng, current source/tests và rerun offline suite; không sửa mã ứng dụng, không nạp weights, không chạy GPU integration.

## Phần đã đạt

- Health dùng active identity được tracking từ loader; full/fallback/normalizer/unloaded có nhánh riêng.
- Active adapter và resolved GGUF identity được lưu và cleanup.
- Existing HTTP failure contracts và readiness được giữ trong suite hiện có.
- Rerun bằng `C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe`, cwd `backend/fastapi`, offline flags và RUN_FULL_INTEGRATION=0: **24 tests, 22 passed, 2 skipped, exit 0; unittest duration 11,353 giây**.
- Không yêu cầu live inference hoặc load process thứ hai cho patch metadata này. Chưa đọc lại live health trong lượt review này; không nghiệm thu inference/performance từ tests mock.

## Findings

### P2 — Explicit constructor base bị adapter metadata ghi đè

`backend/fastapi/services/qwen_service.py:444` kiểm tra `not env_base` trước `_explicit_base_model`. Khi BASE_MODEL_NAME không có trong environment, condition luôn true, dù caller truyền `base_model_name` cụ thể.

Repro offline: constructor base `Caller/ExplicitBase`, adapter metadata `Adapter/MetadataBase`, env không có BASE_MODEL_NAME, fake tokenizer/model loaders. `_explicit_base_model=true`, nhưng AutoModel loader nhận `Adapter/MetadataBase`; health báo base này. Không nạp weights hoặc GPU.

Tác động: caller không kiểm soát được base đã cấu hình, có thể nạp model khác hoặc không tương thích adapter. Field health đúng với model đã nạp không thay thế việc tuân thủ cấu hình caller.

Yêu cầu: precedence rõ và kiểm thử: constructor explicit → environment explicit → adapter metadata khi không có explicit configuration → default. Không suy một cấu hình là implicit chỉ vì giá trị bằng tên default. Giữ Qwen3-4B/adapter hiện hữu cho deployment chính.

### P2 — Resolver trả đường GGUF không tồn tại, bỏ qua search paths hợp lệ

`backend/fastapi/services/qwen_service.py:398–399` trả ngay mọi configured path có suffix .gguf mà không kiểm tra file có tồn tại. `_load_light_model()` thấy path không tồn tại và chuyển normalizer; các search paths chuẩn không được thử.

Repro offline: configured file `<temporary directory>/missing.gguf` không tồn tại, có một GGUF thật tại standard search directory. `_resolve_gguf_file()` trả missing path với `resolved_exists=false`, không chọn standard candidate.

Baseline trước helper extraction duyệt tiếp các paths nếu configured file không tồn tại. Đây là thay đổi fallback selection không được yêu cầu trong ticket metadata.

Yêu cầu: resolver chỉ trả file hợp lệ; missing configured file tiếp tục search theo policy trước. Thêm tests trực tiếp resolver bằng temporary files, không mock resolver trong những tests này. Test20 hiện mock helper nên không bao phủ lỗi.

### P2 — Patch riêng bị corrupt

`docs/reports/SERVE-01-F01.patch` không parse được bởi Git:

```text
git apply --reverse --check docs/reports/SERVE-01-F01.patch
error: corrupt patch at line 109

git apply --numstat docs/reports/SERVE-01-F01.patch
error: corrupt patch at line 109
```

Các lệnh trên chỉ kiểm tra, không apply/mutate source. Không thể dùng artifact này để xác minh patch riêng như báo cáo mô tả.

Yêu cầu: tạo lại diff bằng công cụ từ before/after snapshot đúng scope, không viết tay hunk counts. Không lấy toàn bộ working tree vs HEAD làm patch riêng vì có nhiều thay đổi cũ. Nếu thiếu before snapshot, ghi rõ provenance limit và cung cấp follow-up patch độc lập hợp lệ.

## Phần tiếp theo

Chỉ giao follow-up nhỏ theo `docs/prompts/SERVE-01-F02_GEMINI_PROMPT.md`. Không triển khai lại toàn SERVE-01/F01, không refactor engine hoặc chuyển ticket sản phẩm khác. Sau sửa, rerun offline suite/regression cases và kiểm tra patch artifact rồi Codex review lại.
