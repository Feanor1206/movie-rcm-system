# SERVE-01-F02 — Nghiệm thu độc lập

Ngày: 13/10/2026. Kỹ sư trưởng review: Codex. **Verdict: ACCEPTED trong phạm vi ticket F02.** Ba findings của review F01 đã được xử lý; không yêu cầu follow-up thêm cho các findings này.

## 1. Source và regression coverage

- Base selection thực hiện constructor explicit → environment explicit → adapter metadata → default. Không còn điều kiện coi chuỗi default trong environment là implicit. Test23 kiểm tra sáu trường hợp với fake loaders, temp adapter và environment được cô lập.
- GGUF resolver kiểm tra configured file thực tế rồi duyệt candidate paths khi missing. Test20 kiểm tra trực tiếp filesystem bằng temporary files: explicit file, directory, missing configured file với candidate valid và không có file hợp lệ. Những regression cases này không mock `_resolve_gguf_file`.
- Existing health identity, readiness và HTTP error contracts tiếp tục được coverage bởi suite serving hiện có.

Không phát hiện finding mới cần chặn nghiệm thu trong phạm vi ba sửa đổi F02 đã giao.

## 2. Kiểm tra patch độc lập

Từ root repository, Codex chạy:

```text
git apply --numstat docs/reports/SERVE-01-F02.patch
53  25  backend/fastapi/services/qwen_service.py
165 46  backend/fastapi/tests/test_serving.py
28  3   docs/SERVING_GUIDE.md
Exit code: 0

git apply --reverse --check docs/reports/SERVE-01-F02.patch
Exit code: 0
```

Chỉ kiểm tra, không apply/reverse patch hoặc thay đổi source. Patch parse được và reverse check khớp current files. F01 patch corrupt vẫn là artifact lịch sử với provenance limitation được ghi rõ; không giả tạo baseline để sửa lại lịch sử.

## 3. Rerun offline suite

Interpreter: `C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe`.
Cwd: `D:\Class\movie-rcm-system\backend\fastapi`.
Flags: HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1, RUN_FULL_INTEGRATION=0.

```text
python -m unittest -v tests.test_serving tests.test_serving_integration
Ran 25 tests in 19.236s
OK (skipped=2)
Exit code: 0
```

Kết quả độc lập: **23 passed, 2 skipped, 0 failed/errors**. Hai tests skipped là full-model GPU integration và không được tính như đã pass.

## 4. Giới hạn và bàn giao

- Không chạy live-model GPU inference, không khởi tạo/tải thêm weights; các assertions model load/generate trong suite là mock.
- Không sửa mã ứng dụng, commit, push hoặc tự triển khai ticket tiếp theo.
- Acceptance này xác nhận các sửa đổi metadata/config resolution/patch artifact trong SERVE-01-F02, không phải benchmark chất lượng recommender hoặc latency inference.
- Có thể đóng ba findings của SERVE-01-F01 và ticket SERVE-01-F02. Phần Qwen fine-tuned hiện hữu được giữ nguyên.
