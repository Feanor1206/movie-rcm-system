# SERVE-01-F01 — Health phản ánh model thực tế trong mọi trạng thái

**Trạng thái cập nhật:** Patch tương ứng đã xuất hiện trong qwen_service.py và test_serving.py (22 test cases). Prompt triển khai bên dưới lưu làm contract lịch sử để review, không giao Gemini thực hiện lại nguyên ticket. Chỉ sửa thêm nếu review hiện trạng xác định một finding cụ thể.

Áp dụng `docs/prompts/GEMINI_ENGINEERING_RULES.md`. Chỉ thực hiện ticket này rồi dừng để Codex review.

## Vấn đề

Ở `qwen_service.py`, `get_health_status()` chọn activeBaseModelName theo serving_mode. Khi requested full nhưng runtime đã fallback sang GGUF, health vẫn trả `Qwen/Qwen3-4B`. Field active và legacy hiện mâu thuẫn activeInferenceBackend. Patch SERVE-01 trước đã xử lý exceptions/HTTP errors; giữ behavior đó.

## Source cần đọc và phạm vi sửa

- `backend/fastapi/services/qwen_service.py`: constructor, full/light loaders, cleanup, health/readiness.
- `backend/fastapi/schemas.py`: HealthResponse compatibility.
- `backend/fastapi/tests/test_serving.py`: tests 08/09/12/18 và mock loading.
- `docs/SERVING_GUIDE.md`, `docs/reviews/SERVE-01_RUNTIME_REVIEW.md`.

Chỉ sửa những files trên khi cần và thêm `docs/reports/SERVE-01-F01_REPORT.md`. Không sửa retrieval/ranking/frontend/Spring/Compose, training artifacts hoặc schema intent.

## Contract phải thực hiện

1. Full PEFT loaded: activeBaseModelName là base thực sự đã nạp; activeAdapterPath là adapter đã attach. Không lấy tên configured nếu loader đã resolve base khác từ adapter config.
2. Full requested nhưng GGUF fallback đang chạy: activeBaseModelName và legacy modelNameOrPath phản ánh GGUF thực tế; activeAdapterPath=null; degraded=true và phase23AdapterLoaded=false giữ nguyên.
3. Light GGUF: active model là GGUF đã resolve, kể cả cấu hình ban đầu là directory hoặc loader dùng search path khác. Không trả tên thư mục thay cho tên model.
4. Deterministic normalizer: không có active LLM; activeBaseModelName=null và activeAdapterPath=null. Legacy field dùng nhãn `phase23-deterministic-normalizer` để vẫn giữ kiểu string.
5. Chưa nạp hoặc load thất bại: active fields null; legacy modelNameOrPath có thể giữ configured target để tương thích nhưng tài liệu ghi đây là configured target khi uninitialized, không phải active.
6. fallbackModelPath giữ ý nghĩa configured fallback path. Không đổi readiness policy hoặc cách quyết định fallback.

Nếu cần, bổ sung state active model identity/resolved path tối thiểu trong loader và reset khi cleanup/load failure. Không refactor toàn bộ provider. Không sửa output HTTP 503/502/429 hoặc gọi normalizer thay inference lỗi.

## Tests cần có

- Full successful, với base resolution khác configured default qua adapter metadata.
- Full→GGUF fallback, kiểm tra field consistency.
- Light GGUF từ explicit file và directory resolved sang file cụ thể.
- Normalizer-only, không active model/adapter.
- Unloaded và failed load không giữ stale identity.
- Existing serving contract/error tests vẫn pass.

Mock loader/provider/weights và CUDA calls trong các cases mới; không đụng GPU thật. Với test file cũ, kiểm tra không phát sinh inference/download ngoài mock.

## Lệnh đề xuất

Từ `backend/fastapi`:

```powershell
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:RUN_FULL_INTEGRATION='0'
& 'C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe' -m unittest tests.test_serving tests.test_serving_integration
```

Nếu interpreter không tồn tại, xác định interpreter thích hợp đã có dependencies, ghi rõ; không tự tạo môi trường/tải model. Có thể GET health/readiness server hiện hữu nếu đang chạy; không restart/load process khác chỉ để lấy bằng chứng live.

## Bằng chứng giao lại

- Changed files và patch riêng của lượt này.
- Ma trận requested mode / active backend / health fields / readiness.
- Lệnh test, interpreter, passed/skipped/failed thực tế.
- Các ví dụ health mock cho fallback/normalizer và live health nếu đọc được.
- `docs/reports/SERVE-01-F01_REPORT.md` tồn tại thật, nêu phần chưa kiểm tra.

Không tự commit/push hoặc đổi policy. Dừng ở ready for review.
