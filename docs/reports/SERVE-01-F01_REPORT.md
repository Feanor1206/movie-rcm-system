# SERVE-01-F01 — Báo cáo ready for review

## 1. Vấn đề và phạm vi

- **Cải thiện cho người dùng & hệ thống vận hành:**
  - Trước ticket này, phương thức `get_health_status()` trong `qwen_service.py` lựa chọn `activeBaseModelName` và `modelNameOrPath` thuần túy dựa vào biến cấu hình `serving_mode == "full"`.
  - Hậu quả: Khi requested full nhưng runtime gặp lỗi và fallback sang GGUF (hoặc khi chưa nạp / nạp thất bại), health vẫn trả về `activeBaseModelName: "Qwen/Qwen3-4B"`, mâu thuẫn hoàn toàn với `activeInferenceBackend: "qwen3-0.6b-gguf+phase23-normalizer"`.
  - Khi cấu hình chế độ nhẹ bằng đường dẫn thư mục (`../../ai/models/qwen-0.6b`), health trả về tên thư mục `qwen-0.6b` thay vì tên file model thực tế.
  - Khi chạy deterministic normalizer (không có LLM), các trường active model không phản ánh trạng thái null.
  - Ticket SERVE-01-F01 chuẩn hóa toàn bộ khế ước hiển thị health trung thực, chính xác theo trạng thái runtime thực tế.

- **Contract/ticket thực hiện:** `SERVE-01-F01` theo đặc tả `docs/prompts/SERVE-01-F01_GEMINI_PROMPT.md` và nguyên tắc `docs/prompts/GEMINI_ENGINEERING_RULES.md`.
- **Baseline branch và thay đổi có sẵn:**
  - Giữ nguyên toàn bộ các thay đổi đang có của người khác trên branch hiện tại (bao gồm các thay đổi SERVE-01 trước đó về HTTP exception handling 503/502/429, prompt normalizer, docker compose, v.v.).
  - Không reset, không đổi branch, không commit hoặc push.
- **Phạm vi sửa đổi của lượt này:**
  - `backend/fastapi/services/qwen_service.py`: bổ sung tracking state active model identity, giải quyết GGUF file từ thư mục, cập nhật base resolution từ adapter metadata, reset state khi cleanup/failure, viết lại `get_health_status()`.
  - `backend/fastapi/schemas.py`: bổ sung mô tả và trường tương thích trong `HealthResponse`.
  - `backend/fastapi/tests/test_serving.py`: cập nhật test 08, 09, 12, 18; bổ sung test 19, 20, 21, 22.
  - `docs/SERVING_GUIDE.md`: cập nhật mục 5 với đầy đủ 5 trạng thái mẫu.
  - Patch riêng: `docs/reports/SERVE-01-F01.patch`.
  - Báo cáo: `docs/reports/SERVE-01-F01_REPORT.md`.

---

## 2. Files và thay đổi

| File | Thay đổi chính trong ticket SERVE-01-F01 |
|---|---|
| `backend/fastapi/services/qwen_service.py` | 1. Khởi tạo `self.active_base_model_name`, `self.active_adapter_path`, `self.resolved_gguf_path`, `self._explicit_base_model`.<br>2. Cập nhật `_cleanup_partial_model()` dọn sạch active states và đặt `is_loaded = False`, `is_gguf = False`.<br>3. Thêm phương thức `_resolve_gguf_file()` giải quyết file `.gguf` cụ thể thay vì trả về tên thư mục.<br>4. Trong `_load_full_peft_model()`, ưu tiên base model name do adapter config chỉ định khi caller dùng default cấu hình, ghi nhận `active_base_model_name` và `active_adapter_path`.<br>5. Trong `_load_light_model()`, ghi nhận `active_base_model_name` và `resolved_gguf_path`; khi fallback sang normalizer thì đặt các active LLM fields thành `None`.<br>6. Trong `load_model()`, reset toàn bộ active identity fields khi gặp lỗi nạp.<br>7. Viết lại `get_health_status()` phản ánh trung thực 5 trạng thái runtime. |
| `backend/fastapi/schemas.py` | Cập nhật metadata `Field(description=...)` cho `modelNameOrPath`, `activeBaseModelName`, `activeAdapterPath`, `fallbackModelPath` trong schema `HealthResponse`. |
| `backend/fastapi/tests/test_serving.py` | 1. Cập nhật `test_08`: kiểm tra field consistency khi full fallback sang GGUF (`activeBaseModelName` là GGUF, `activeAdapterPath=None`, `modelNameOrPath != "Qwen/Qwen3-4B"`).<br>2. Cập nhật `test_09`: kiểm tra cả full và fallback đều thất bại thì active fields là `None`.<br>3. Cập nhật `test_12`: bổ sung assertion health cho ma trận 12a và 12b.<br>4. Cập nhật `test_18`: kiểm tra phân biệt active model và fallback model path.<br>5. Thêm `test_19`: Full PEFT resolution lấy base từ adapter metadata khác configured default.<br>6. Thêm `test_20`: Light GGUF giải quyết từ explicit file và directory sang file cụ thể (không trả folder name).<br>7. Thêm `test_21`: Normalizer-only không có active LLM/adapter, legacy field giữ nhãn string `phase23-deterministic-normalizer`.<br>8. Thêm `test_22`: Unloaded và cleanup sau load thất bại không giữ stale identity. |
| `docs/SERVING_GUIDE.md` | Cập nhật mục 5 (Trạng Thái Health và Readiness Mẫu) với 5 tình huống: Full PEFT (200), Full degraded sang GGUF fallback (503), Light GGUF (200), Normalizer-only (200), Uninitialized/Failed (503). |
| `docs/reports/SERVE-01-F01.patch` | File patch Git riêng biệt chứa diff độc lập của lượt triển khai này. |
| `docs/reports/SERVE-01-F01_REPORT.md` | Báo cáo nghiệm thu kỹ thuật theo mẫu chuẩn. |

---

## 3. Ma trận nghiệm thu

| TT | Kịch bản nghiệm thu (Acceptance case) | Kỳ vọng (Expected) | Thực tế (Actual) | Bằng chứng (Evidence) | Kết luận |
|---|---|---|---|---|---|
| 1 | **Full PEFT loaded thành công** (Default configured base) | `status: "healthy"`, `modelLoaded: true`, `activeBaseModelName: "Qwen/Qwen3-4B"`, `activeAdapterPath: "<adapter_dir>"`, `modelNameOrPath: "Qwen/Qwen3-4B"`, `readiness: 200 Ready` | Trùng khớp 100% | `test_03_full_peft_load_success`, `test_18` | **Passed** |
| 2 | **Full PEFT loaded thành công** (Adapter metadata chỉ định base khác default) | `activeBaseModelName: "Qwen/Qwen2.5-3B-Instruct"`, `modelNameOrPath: "Qwen/Qwen2.5-3B-Instruct"`, không dùng configured default `"Qwen/Qwen3-4B"` | Base được nạp và báo cáo là `"Qwen/Qwen2.5-3B-Instruct"` | `test_19_full_success_with_base_resolved_from_adapter_metadata` | **Passed** |
| 3 | **Full requested nhưng Fallback sang GGUF đang chạy** (`ENABLE_FALLBACK=true`) | `status: "degraded"`, `degraded: true`, `phase23AdapterLoaded: false`, `activeBaseModelName: "Qwen3-0.6B-Q8_0.gguf"`, `activeAdapterPath: null`, `modelNameOrPath != "Qwen/Qwen3-4B"`, `fallbackModelPath` giữ nguyên cấu hình, `readiness: 503` (khi strict) | `status: "degraded"`, `activeBaseModelName: "Qwen3-0.6B-Q8_0.gguf"`, `activeAdapterPath: null`, `modelNameOrPath` chứa `"Qwen3-0.6B"` | `test_08_peft_load_failed_fallback_enabled`, `test_12b` | **Passed** |
| 4 | **Light GGUF từ file tường minh** | `status: "healthy"`, `activeBaseModelName: "<file>.gguf"`, `activeAdapterPath: null`, `fallbackModelPath: "<configured>"` | `activeBaseModelName: "Qwen3-0.6B-Custom.gguf"`, `activeAdapterPath: null` | `test_20a` trong `test_20_light_gguf_resolved_from_directory_and_explicit_file` | **Passed** |
| 5 | **Light GGUF từ cấu hình directory** (`../../ai/models/qwen-0.6b`) | Giải quyết sang file cụ thể `Qwen3-0.6B-Q8_0.gguf`, tuyệt đối không trả tên thư mục `qwen-0.6b` | `activeBaseModelName: "Qwen3-0.6B-Q8_0.gguf"` != `"qwen-0.6b"`, `modelNameOrPath` trỏ file `.gguf` | `test_20b` trong `test_20_light_gguf_resolved_from_directory_and_explicit_file` | **Passed** |
| 6 | **Deterministic Normalizer** (Không có LLM khả dụng) | `activeBaseModelName: null`, `activeAdapterPath: null`, `modelNameOrPath: "phase23-deterministic-normalizer"`, `activeInferenceBackend: "phase23-deterministic-normalizer"` | `activeBaseModelName: null`, `activeAdapterPath: null`, `modelNameOrPath: "phase23-deterministic-normalizer"` | `test_21_normalizer_only_has_no_active_model_or_adapter` | **Passed** |
| 7 | **Chưa nạp (Unloaded / Uninitialized)** | `status: "unhealthy"`, `modelLoaded: false`, `activeBaseModelName: null`, `activeAdapterPath: null`, `modelNameOrPath: "<configured_target>"`, `readiness: 503` | `activeBaseModelName: null`, `activeAdapterPath: null`, `modelNameOrPath: "Qwen/Qwen3-4B"` | `test_01`, `test_22a` trong `test_22` | **Passed** |
| 8 | **Nạp thất bại / Cleanup sau lỗi** (Cả full và fallback đều lỗi, hoặc reload lỗi) | Không giữ stale identity của model trước đó; `is_loaded: false`, `activeBaseModelName: null`, `activeAdapterPath: null` | `is_loaded: false`, active fields là `None` | `test_09_both_full_and_fallback_fail`, `test_22b` | **Passed** |
| 9 | **Bảo toàn các hành vi SERVE-01 trước đó** | Concurrency semaphore (429), Full unavailable (503), Generation OOM (502), Invalid JSON output (502) | 100% test cases API và error contracts tiếp tục hoạt động | `test_10`, `test_11`, `test_13`, `test_14`, `test_15`, `test_16`, `test_17` | **Passed** |

---

## 4. Kiểm tra thực hiện

### 4.1 Môi trường và Runtime
- **Operating System:** Windows (x64)
- **Interpreter:** `C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe` (Python 3.12, torch, peft, transformers, fastapi, pydantic)
- **Current Working Directory:** `D:\Class\movie-rcm-system\backend\fastapi`
- **Environment Flags:**
  - `HF_HUB_OFFLINE='1'`
  - `TRANSFORMERS_OFFLINE='1'`
  - `RUN_FULL_INTEGRATION='0'`
- **Bảo mật:** Không chứa secrets, tokens hoặc private paths nhạy cảm.

### 4.2 Lệnh và kết quả kiểm tra
```powershell
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:RUN_FULL_INTEGRATION='0'
& 'C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe' -m unittest -v tests.test_serving tests.test_serving_integration
```

**Kết quả thực thi:**
- **Exit Code:** 0
- **Thời gian thực thi:** 13.804 giây
- **Số lượng tests:** 24 tests
- **Passed:** 22 tests (100% unit & contract tests)
- **Skipped:** 2 tests (`test_full_model_live_health_and_readiness`, `test_full_model_live_intent_generation` được skip chủ động do `RUN_FULL_INTEGRATION='0'`)
- **Failed / Errored:** 0 tests

**Chi tiết các bài kiểm tra chạy thành công:**
1. `test_01_artifact_exists_but_model_not_loaded`: ok
2. `test_02_adapter_missing_or_invalid`: ok
3. `test_03_full_peft_load_success`: ok
4. `test_04_device_cpu_enforced_when_cuda_available`: ok
5. `test_05_device_cuda_when_cuda_not_available_fails`: ok
6. `test_06_nf4_and_cpu_dtype_labels`: ok
7. `test_07_peft_load_failed_fallback_disabled`: ok
8. `test_08_peft_load_failed_fallback_enabled` *(cập nhật assertions SERVE-01-F01)*: ok
9. `test_09_both_full_and_fallback_fail` *(cập nhật assertions SERVE-01-F01)*: ok
10. `test_10_concurrent_load_requests_no_duplicate`: ok
11. `test_11_inference_concurrency_limit_enforced`: ok
12. `test_12_health_and_readiness_state_matrix` *(cập nhật assertions SERVE-01-F01)*: ok
13. `test_13_api_contracts_mocked_offline`: ok
14. `test_14_full_mode_model_unavailable_returns_503`: ok
15. `test_15_full_mode_generation_failure_returns_502`: ok
16. `test_16_full_mode_invalid_json_output_returns_502`: ok
17. `test_17_full_mode_valid_generation_preserves_normalization`: ok
18. `test_18_health_distinguishes_active_and_fallback_models` *(cập nhật SERVE-01-F01)*: ok
19. `test_19_full_success_with_base_resolved_from_adapter_metadata` *(mới)*: ok
20. `test_20_light_gguf_resolved_from_directory_and_explicit_file` *(mới)*: ok
21. `test_21_normalizer_only_has_no_active_model_or_adapter` *(mới)*: ok
22. `test_22_unloaded_and_failed_load_do_not_retain_stale_identity` *(mới)*: ok
23. `test_full_model_live_health_and_readiness`: skipped (offline mode)
24. `test_full_model_live_intent_generation`: skipped (offline mode)

---

## 5. Kết quả và limitations

### 5.1 Phần đã đạt
- Toàn bộ 6 điểm khế ước của ticket `SERVE-01-F01` đã được hoàn thành đầy đủ và chính xác.
- Endpoint `/health` và phương thức `get_health_status()` phản ánh trung thực trạng thái phục vụ:
  - Khi full model loaded: trả về đúng base model và adapter path đã nạp.
  - Khi fallback GGUF: trả về đúng model GGUF thực tế, `activeAdapterPath: null`, `degraded: true`.
  - Khi light GGUF: giải quyết ra tên file model cụ thể, không bị nhầm thành tên thư mục.
  - Khi deterministic normalizer: không trả về active LLM hay adapter, legacy field dùng nhãn `phase23-deterministic-normalizer`.
  - Khi chưa nạp hoặc nạp thất bại: active fields là `null`, không giữ stale identity.
  - `fallbackModelPath` giữ nguyên cấu hình dự phòng.
- Tất cả unit tests đều offline, không chiếm GPU, không tải weights từ internet, tương thích với môi trường `dippie-qwen`.

### 5.2 Phần chưa kiểm tra & Giới hạn
- **Live server inference & GPU integration:** Chưa chạy `RUN_FULL_INTEGRATION=1` theo đúng quy định tại prompt (không tải/huấn luyện lại model, không tạo thêm process model trên GPU).
- **Live HTTP check cổng 8000:** Service FastAPI live hiện không chạy nền trên cổng 8000; kỹ sư không tự restart/chạy process mới chỉ để lấy log live.
- **Không có thay đổi ngoài scope:** Không sửa đổi các tầng heuristic/ranking/retrieval, không sửa frontend, không sửa Spring Boot, không sửa Docker Compose, giữ nguyên các thay đổi có sẵn của người khác.

---

## 6. Bàn giao

- **Trạng thái:** **Ready for review**.
- **Kỹ sư trưởng nghiệm thu:** Codex.
- **Cam kết:** Không tự đánh dấu accepted, không tự chuyển sang ticket tiếp theo, không tự commit hoặc push Git.
