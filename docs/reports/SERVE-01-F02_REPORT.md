# SERVE-01-F02 — Báo Cáo Ready for Review

> **Ticket:** SERVE-01-F02 (Xử lý 3 review findings từ Lead Engineer Codex trong `docs/reviews/SERVE-01-F01_REVIEW.md`)  
> **Dự án:** Dippie Animation Discovery Engine (`D:\Class\movie-rcm-system`)  
> **Kỹ sư triển khai:** Gemini  
> **Kỹ sư trưởng thiết kế & nghiệm thu:** Codex  
> **Ngày:** 13/10/2026  
> **Trạng thái:** **Ready for Review**

---

## 1. Vấn đề và phạm vi

### 1.1 Vấn đề giải quyết
Ticket SERVE-01-F02 giải quyết dứt điểm 3 findings mức độ **P2** được Lead Engineer Codex chỉ định trong review độc lập F01:
1. **Finding P2 — Base Model Precedence:** Constructor `base_model_name` explicit bị adapter metadata ghi đè khi `BASE_MODEL_NAME` vắng mặt trong environment. Cần chuẩn hóa thứ tự ưu tiên: Constructor explicit → Environment explicit → Adapter metadata → Default (`Qwen/Qwen3-4B`), không suy đoán chuỗi `"Qwen/Qwen3-4B"` trong env là implicit.
2. **Finding P2 — GGUF Resolver Fallback:** Helper `_resolve_gguf_file` trả về đường dẫn file không tồn tại nếu chuỗi kết thúc bằng `.gguf`, bỏ qua các standard candidate paths hợp lệ. Cần đảm bảo resolver chỉ trả file thực tế tồn tại trên đĩa; nếu configured file bị missing thì tiếp tục duyệt standard candidates. Đồng thời kiểm thử trực tiếp filesystem qua temporary files, không mock resolver helper.
3. **Finding P2 — Artifact Patch Corrupt:** `docs/reports/SERVE-01-F01.patch` bị lỗi cú pháp tại dòng 109 (`corrupt patch at line 109`) do chỉnh sửa hunk count bằng tay. Cần tạo patch F02 độc lập, chuẩn Git unified diff, xác minh bằng `git apply --numstat` và `git apply --reverse --check` (exit 0). Đối với F01 artifact thiếu baseline thật, ghi rõ hạn chế provenance thay vì tạo diff giả.

### 1.2 Phạm vi thực hiện
- **Trong phạm vi:**
  - `backend/fastapi/services/qwen_service.py`: Cập nhật logic precedence base model, tách helper `_get_gguf_search_candidates`, sửa `_resolve_gguf_file` fallback và guard `get_health_status()`.
  - `backend/fastapi/tests/test_serving.py`: Viết lại `test_20` kiểm thử trực tiếp filesystem không mock resolver, cô lập env trong `test_19`, bổ sung `test_23` ma trận 6 kịch bản precedence base model.
  - `docs/SERVING_GUIDE.md`: Bổ sung mục 2.1 (Base Model Precedence), 2.2 (GGUF Resolution Policy) và cập nhật mục 7.1 (23 unit tests offline).
  - `docs/reports/SERVE-01-F02.patch`: Patch Git unified diff hợp lệ độc lập cho F02.
  - `docs/reports/SERVE-01-F02_REPORT.md`: Báo cáo nghiệm thu theo mẫu chuẩn.
- **Ngoài phạm vi (được bảo toàn nguyên vẹn):**
  - Không thay đổi endpoints FastAPI (`/v1/discover`, `/api/chat`, `/health`, `/ready`).
  - Không sửa logic ranking, constraint retrieval, deterministic normalizer.
  - Không tải lại mô hình, không train lại LoRA weights, không tạo GPU process mới.
  - Không commit và không push Git.

---

## 2. Files và thay đổi

| File | Loại thay đổi | Mô tả chi tiết |
|---|---|---|
| `backend/fastapi/services/qwen_service.py` | Modified | • `__init__`: Phân tách và theo dõi cờ cấu hình tường minh (`constructor_base_model`, `_has_explicit_constructor_base`, `configured_env_base`, `_has_explicit_env_base`).<br>• Tách method `_get_gguf_search_candidates(self) -> List[Path]`.<br>• `_resolve_gguf_file`: Chỉ trả về file tồn tại thực tế trên đĩa (`is_file()` & `.gguf`) hoặc file `.gguf` đầu tiên trong thư mục tồn tại. Nếu missing, tiếp tục vòng lặp candidate.<br>• `_load_full_peft_model`: Áp dụng chuẩn precedence: `Constructor explicit` → `ENV explicit` → `Adapter metadata` → `Default ("Qwen/Qwen3-4B")`.<br>• `get_health_status`: Thêm điều kiện `and os.path.isfile(self.model_name_or_path)` tránh leak đường dẫn missing vào `active_base_model`. |
| `backend/fastapi/tests/test_serving.py` | Modified | • Import `Optional` từ `typing`.<br>• `test_19`: Cô lập `BASE_MODEL_NAME` bằng `patch.dict(os.environ)` tránh bị `.env` máy ảnh hưởng.<br>• `test_20`: Viết lại hoàn toàn với `tempfile.TemporaryDirectory()`, kiểm tra trực tiếp `_resolve_gguf_file` qua 4 kịch bản filesystem mà **không mock helper**.<br>• `test_23`: Bổ sung ma trận 6 kịch bản precedence base model với fake loaders và temp adapters, cô lập env triệt để. |
| `docs/SERVING_GUIDE.md` | Modified | • Bổ sung mục 2.1 giải thích chi tiết Base Model Precedence.<br>• Bổ sung mục 2.2 giải thích GGUF Resolution & Fallback Policy.<br>• Cập nhật mục 7.1 phản ánh 23 unit tests offline đạt 100% OK. |
| `docs/reports/SERVE-01-F02.patch` | Created | Git unified diff chuẩn cho scope F02, được tạo bằng `git diff --no-index` giữa snapshot F01 và source hiện tại. |
| `docs/reports/SERVE-01-F02_REPORT.md` | Created | Báo cáo ready for review nộp Lead Engineer Codex. |

---

## 3. Ma trận nghiệm thu (Acceptance Matrix)

| Acceptance Case | Expected | Actual | Evidence | Result |
|---|---|---|---|---|
| **P2-1.1: Base precedence: No constructor/env** | Dùng adapter metadata | Base = `Meta/AdapterBase`, loader nhận `Meta/AdapterBase` | `test_23` (subcase 1) passed | **Passed** |
| **P2-1.2: Base precedence: Constructor explicit khác adapter, env absent** | Dùng constructor explicit | Base = `Caller/ExplicitBase`, loader nhận `Caller/ExplicitBase` | `test_23` (subcase 2) passed | **Passed** |
| **P2-1.3: Base precedence: Env explicit khác adapter, constructor absent** | Dùng env explicit | Base = `Env/ExplicitBase`, loader nhận `Env/ExplicitBase` | `test_23` (subcase 3) passed | **Passed** |
| **P2-1.4: Base precedence: Constructor và env đều có** | Constructor explicit thắng env | Base = `Caller/ExplicitBase`, loader nhận `Caller/ExplicitBase` | `test_23` (subcase 4) passed | **Passed** |
| **P2-1.5: Base precedence: Env explicit đúng chuỗi default, adapter khác** | Env explicit thắng adapter metadata, không bị xem là implicit | Base = `Qwen/Qwen3-4B`, loader nhận `Qwen/Qwen3-4B` | `test_23` (subcase 5) passed | **Passed** |
| **P2-1.6: Base precedence: Không explicit, không metadata** | Dùng mặc định `Qwen/Qwen3-4B` | Base = `Qwen/Qwen3-4B` | `test_23` (subcase 6) passed | **Passed** |
| **P2-2.1: GGUF resolver: Configured explicit valid file** | Trả về đúng file cấu hình tồn tại | Resolver trả file path thực, `is_file=True` | `test_20` (subcase 20a) passed, không mock helper | **Passed** |
| **P2-2.2: GGUF resolver: Configured directory chứa GGUF** | Trả về đường dẫn file `.gguf` cụ thể, không trả tên thư mục | Resolver trả file trong thư mục, basename khác tên thư mục | `test_20` (subcase 20b) passed, không mock helper | **Passed** |
| **P2-2.3: GGUF resolver: Configured file missing, candidate valid** | Bỏ qua file missing, fallback sang candidate valid | Resolver trả về candidate file hợp lệ, không trả file missing | `test_20` (subcase 20c) passed, không mock helper | **Passed** |
| **P2-2.4: GGUF resolver: Không có file ở bất kỳ candidate nào** | Trả về `None` | Resolver trả `None` | `test_20` (subcase 20d) passed, không mock helper | **Passed** |
| **P2-3.1: Patch parse validation: numstat** | Git apply parse thành công không báo corrupt | Exit code 0, numstat liệt kê đúng 3 files | `git apply --numstat docs/reports/SERVE-01-F02.patch` exit code 0 | **Passed** |
| **P2-3.2: Patch integrity: reverse --check** | Khớp 100% với source code hiện tại | Exit code 0, không có rejected hunk | `git apply --reverse --check docs/reports/SERVE-01-F02.patch` exit code 0 | **Passed** |
| **Regression Suite: Full offline suite** | Toàn bộ 23 tests unit pass, 2 GPU integration skipped | 25 tests run, 23 passed, 2 skipped, 0 failures, 0 errors | `unittest` exit code 0, duration ~20.196s | **Passed** |

---

## 4. Kiểm tra thực hiện

### 4.1 Môi trường thực thi
- **Interpreter:** `C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe`
- **CWD:** `D:\Class\movie-rcm-system\backend\fastapi`
- **Offline Environment Flags:**
  ```powershell
  $env:HF_HUB_OFFLINE = "1"
  $env:TRANSFORMERS_OFFLINE = "1"
  $env:RUN_FULL_INTEGRATION = "0"
  ```

### 4.2 Lệnh kiểm thử Unit Test & Kết quả
```powershell
$env:HF_HUB_OFFLINE='1'; $env:TRANSFORMERS_OFFLINE='1'; $env:RUN_FULL_INTEGRATION='0'; & 'C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe' -m unittest -v tests.test_serving tests.test_serving_integration
```

**Kết quả chi tiết:**
```text
test_01_artifact_exists_but_model_not_loaded ... ok
test_02_adapter_missing_or_invalid ... ok
test_03_full_peft_load_success ... ok
test_04_device_policy_cpu_overrides_cuda ... ok
test_05_device_policy_cuda_enforces_cuda_available ... ok
test_06_quantization_labels_nf4_and_fp32 ... ok
test_07_peft_failure_without_fallback_raises_error ... ok
test_08_peft_failure_with_fallback_loads_gguf ... ok
test_09_full_and_fallback_both_fail ... ok
test_10_concurrent_model_loading_is_idempotent ... ok
test_11_bounded_concurrency_capacity_limit ... ok
test_12_readiness_and_health_reporting_semantics ... ok
test_13_api_discover_and_chat_contracts ... ok
test_14_full_mode_not_ready_returns_503 ... ok
test_15_full_mode_generation_failure_returns_502 ... ok
test_16_full_mode_invalid_json_output_returns_502 ... ok
test_17_full_mode_valid_generation_preserves_normalization ... ok
test_18_health_distinguishes_active_and_fallback_models ... ok
test_19_full_success_with_base_resolved_from_adapter_metadata ... ok
test_20_light_gguf_resolved_from_directory_and_explicit_file ... ok
test_21_normalizer_only_has_no_active_model_or_adapter ... ok
test_22_unloaded_and_failed_load_do_not_retain_stale_identity ... ok
test_23_base_model_selection_precedence_matrix ... ok
test_full_model_live_health_and_readiness ... skipped 'Bỏ qua integration tests khi chạy offline. Đặt RUN_FULL_INTEGRATION=1 để kích hoạt kiểm thử với GPU thật.'
test_full_model_live_intent_generation ... skipped 'Bỏ qua integration tests khi chạy offline. Đặt RUN_FULL_INTEGRATION=1 để kích hoạt kiểm thử với GPU thật.'

----------------------------------------------------------------------
Ran 25 tests in 20.196s

OK (skipped=2)
```
- **Exit code:** `0`
- **Tổng số tests:** 25
- **Passed:** 23 tests
- **Skipped:** 2 tests (Live GPU integration, chủ động bỏ qua theo cờ `RUN_FULL_INTEGRATION=0`)
- **Failed / Errored:** 0

### 4.3 Lệnh kiểm tra Patch Artifact & Kết quả
Tạo patch bằng `git diff` giữa snapshot F01 và current work:
- Lệnh numstat:
  ```powershell
  git apply --numstat docs/reports/SERVE-01-F02.patch
  ```
  **Output (Exit code 0):**
  ```text
  53	25	backend/fastapi/services/qwen_service.py
  165	46	backend/fastapi/tests/test_serving.py
  28	3	docs/SERVING_GUIDE.md
  ```
- Lệnh reverse check:
  ```powershell
  git apply --reverse --check docs/reports/SERVE-01-F02.patch
  ```
  **Output (Exit code 0):** Không có output và không có lỗi (patch hoàn toàn sạch và tương thích 2 chiều).

---

## 5. Kết quả và limitations

### 5.1 Phần đã đạt
- Cả 3 review findings P2 đã được giải quyết trọn vẹn theo đúng yêu cầu thiết kế của Lead Engineer Codex.
- Base model precedence hoạt động chính xác theo ma trận 6 kịch bản, bảo toàn quyền kiểm soát của caller và environment.
- GGUF resolver chỉ trả file thực tế và fallback chuẩn qua các standard candidate paths nếu file cấu hình bị thiếu.
- Bổ sung regression tests filesystem trực tiếp không thông qua mock helper.
- Patch `docs/reports/SERVE-01-F02.patch` là Git unified diff chuẩn xác, parse thành công và không bị corrupt.

### 5.2 Hạn chế và ghi nhận provenance đối với `SERVE-01-F01.patch`
- **Hạn chế provenance của F01:** Tệp `docs/reports/SERVE-01-F01.patch` được tạo trong phiên F01 trước đó bị lỗi cú pháp tại dòng 109 do chỉnh sửa thủ công hunk counts mà không có một baseline Git commit sạch trước đó để tái tạo tự động. Do repo hiện có nhiều file untracked và thay đổi chưa commit từ các giai đoạn trước, việc cố gắng tự sinh lại diff toàn bộ working tree cho F01 sẽ gây nhiễu và tạo ra diff giả. Vì vậy, nhóm triển khai giữ nguyên artifact F01 kèm ghi nhận hạn chế provenance này, và cung cấp `docs/reports/SERVE-01-F02.patch` độc lập, được tự sinh và kiểm tra nghiêm ngặt 100% bằng Git tooling.
- **Phần chưa kiểm tra:** Kiểm thử live-model GPU inference trên mô hình 4B thật với trọng số đầy đủ (`RUN_FULL_INTEGRATION=1`) không được thực hiện trong ticket này theo đúng ràng buộc "không tạo thêm process model trên GPU, không làm gián đoạn tài nguyên phần cứng".

---

## 6. Bàn giao

- **Trạng thái:** **Ready for Review**
- **Cam kết:** 
  - Không tự đánh giá accepted.
  - Không tự commit hoặc push vào kho Git.
  - Không tự chuyển sang ticket tiếp theo.
  - Dừng lại tại đây để Lead Engineer Codex nghiệm thu độc lập.
