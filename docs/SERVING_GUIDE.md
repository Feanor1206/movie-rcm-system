# Hướng Dẫn Vận Hành & Phục Vụ Model (Serving Guide) — SERVE-01

> **Tài liệu chuẩn hóa phục vụ suy luận Qwen3-4B + Phase 23 LoRA & Fallback Qwen3-0.6B GGUF**  
> **Dự án:** Dippie Animation Discovery Engine (`movie-rcm-system`)  
> **Phiên bản:** 2.3.0  
> **Mục tiêu ticket SERVE-01:** Phân định rõ 2 chế độ serving, thực thi chính sách thiết bị nghiêm ngặt, cơ chế fallback trung thực, kiểm soát đồng thời (concurrency), chuẩn hóa Docker GPU reservation và endpoint Readiness.

---

## 1. Kiến Trúc 2 Chế Độ Serving

Hệ thống hỗ trợ 2 chế độ phục vụ suy luận rõ ràng:

```
                            Yêu cầu khởi chạy
                                   │
                 ┌─────────────────┴─────────────────┐
                 ▼                                   ▼
        [SERVING_MODE=full]                 [SERVING_MODE=light]
       Qwen3-4B + Phase23 LoRA               Qwen3-0.6B GGUF
                 │                                   │
          ┌──────┴──────┐                            ▼
       Thành công      Thất bại             llama-cpp-python
          │             │                   + Phase23 Normalizer
          ▼             ▼                            │
      PEFT 4-bit   ENABLE_FALLBACK?                  ▼
         NF4       ┌────┴────┐                  HTTP 200 Ready
          │       True     False                     │
          ▼        │         │                       │
     HTTP 200    Fallback  HTTP 503                  │
      Ready       GGUF     Not Ready                 │
          │     (Degraded)                           │
          ▼        │                                 ▼
   ────────────────┴──────────────────────────────────
                FastAPI Gateway (:8000)
```

1. **Chế độ chính (Full Serving): `Qwen3-4B + Phase 23 LoRA`**
   - Base model: `Qwen/Qwen3-4B`
   - Adapter: `ai/models/qwen3-4b-phase23-lora` (LoRA rank r=16, alpha=32)
   - Quantization: 4-bit NF4 (`BitsAndBytesConfig`, compute dtype `torch.float16`) trên GPU CUDA.
   - Nhãn backend: `qwen3-4b-peft-lora-4bit-nf4`
   - Mục đích: Đạt chất lượng trích xuất ý định StructuredDiscoveryIntent v1 cao nhất.

2. **Chế độ nhẹ (Light Serving / Fallback): `Qwen3-0.6B GGUF + Phase 23 Normalizer`**
   - Model: `Qwen3-0.6B-Q8_0.gguf` chạy qua `llama-cpp-python` CPU/GPU.
   - Kết hợp: Bộ chuẩn hóa tất định v2.2 (Deterministic Normalizer) xử lý các trường hợp hội thoại, năm, thể loại loại trừ.
   - Nhãn backend: `qwen3-0.6b-gguf+phase23-normalizer`
   - Mục đích: Khởi động siêu nhanh, tiêu tốn ít RAM/VRAM (< 1GB), đóng vai trò fallback khi môi trường thiếu GPU hoặc thiếu base weights 4B.

---

## 2. Bảng Biến Môi Trường Cấu Hình

| Biến môi trường | Kiểu | Mặc định | Ý nghĩa & Hành vi |
|---|---|---|---|
| `SERVING_MODE` | `string` | `full` nếu `USE_FULL_QWEN3_4B_LORA=true`, ngược lại `light` | Chế độ phục vụ mong muốn: `'full'` hoặc `'light'`. |
| `USE_FULL_QWEN3_4B_LORA` | `boolean` | `false` | Cờ tương thích ngược; nếu `true` sẽ kích hoạt `SERVING_MODE=full`. |
| `DEVICE` | `string` | `auto` | Chính sách thiết bị: `'auto'` (chọn CUDA nếu có, ngược lại CPU), `'cuda'` (bắt buộc CUDA, báo lỗi nếu thiếu), `'cpu'` (bắt buộc CPU dù máy có GPU). |
| `ENABLE_FALLBACK` | `boolean` | `true` | Cho phép tự động chuyển sang chế độ nhẹ GGUF khi nạp full model thất bại. |
| `STRICT_READINESS` | `boolean` | `true` | Khi yêu cầu `full` mà chỉ chạy fallback: nếu `true`, `/ready` trả về HTTP 503 Degraded (không giả vờ full model đã sẵn sàng). |
| `MAX_CONCURRENT_INFERENCE` | `int` | `1` | Giới hạn số request suy luận đồng thời trên GPU; vượt quá sẽ trả về HTTP 429 Too Many Requests. |
| `MAX_NEW_TOKENS` | `int` | `256` | Giới hạn số token sinh mới tối đa cho mỗi lượt parse NLU. |
| `BASE_MODEL_NAME` | `string` | `Qwen/Qwen3-4B` | Tên hoặc đường dẫn local của base model Hugging Face. |
| `PHASE23_ADAPTER_DIR` | `string` | `../../ai/models/qwen3-4b-phase23-lora` | Đường dẫn chứa artifact LoRA (adapter_config.json, adapter_model.safetensors). |
| `MODEL_NAME_OR_PATH` | `string` | `../../ai/models/qwen-0.6b` | Đường dẫn file hoặc thư mục chứa model GGUF nhẹ. |
| `HF_HOME` | `string` | `~/.cache/huggingface` | Thư mục lưu cache base model Hugging Face. |

---

### 2.1 Thứ Tự Ưu Tiên Xác Định Base Model (Base Model Precedence)

Khi phục vụ ở chế độ Full PEFT LoRA (`SERVING_MODE=full`), base model được loader phân giải theo thứ tự ưu tiên nghiêm ngặt:
1. **Tham số Constructor `base_model_name` tường minh:** Nếu caller truyền trực tiếp vào constructor `QwenRecommendationService(base_model_name=...)`.
2. **Biến môi trường `BASE_MODEL_NAME` tường minh:** Nếu được khai báo trong environment/`.env`. Không suy đoán là implicit chỉ vì giá trị trùng với chuỗi mặc định `"Qwen/Qwen3-4B"`.
3. **Adapter Metadata (`base_model_name_or_path`):** Trích xuất từ file `adapter_config.json` nếu cả constructor và biến môi trường đều không khai báo.
4. **Mặc định hệ thống:** Fallback về `"Qwen/Qwen3-4B"` nếu không có bất kỳ cấu hình explicit hay metadata nào.

Trạng thái health (`/health`) luôn phản ánh trung thực base model thực tế được loader sử dụng thông qua trường `activeBaseModelName`.

### 2.2 Chính Sách Giải Quyết File GGUF (GGUF Resolution Policy)

Khi phục vụ ở chế độ Light hoặc Fallback GGUF (`SERVING_MODE=light`), file GGUF được giải quyết qua helper `_resolve_gguf_file()`:
1. **Configured file tường minh:** Nếu `MODEL_NAME_OR_PATH` trỏ tới file `.gguf` cụ thể và file đó **tồn tại thực tế trên đĩa**, file này được ưu tiên sử dụng.
2. **Configured directory:** Nếu `MODEL_NAME_OR_PATH` là một thư mục, helper tìm kiếm file `*.gguf` bên trong và trả về đường dẫn file cụ thể (không trả tên thư mục).
3. **Fallback search candidates:** Nếu file cấu hình bị thiếu (missing) hoặc không hợp lệ, hệ thống không fail sớm mà tiếp tục duyệt qua danh sách các candidate chuẩn (`/app/models/qwen-0.6b`, `../../ai/models/qwen-0.6b`, v.v.).
4. **Normalizer fallback:** Nếu không tìm thấy file `.gguf` hợp lệ ở bất kỳ candidate nào, resolver trả về `None` và kích hoạt chế độ `Phase 23 Deterministic Normalizer`.

---

## 3. Cách Chạy Trên Môi Trường Local (Windows)

### 3.1 Khởi chạy Chế độ Chính (Full Model Qwen3-4B + LoRA)
Yêu cầu: Đã kích hoạt môi trường Conda có GPU PyTorch, transformers, peft, bitsandbytes (ví dụ môi trường `dippie-qwen`).

```powershell
# 1. Kích hoạt môi trường conda chuyên biệt cho Qwen
conda activate dippie-qwen

# 2. Thiết lập biến môi trường
$env:SERVING_MODE = "full"
$env:USE_FULL_QWEN3_4B_LORA = "true"
$env:DEVICE = "cuda"
$env:ENABLE_FALLBACK = "false"
$env:STRICT_READINESS = "true"
$env:MAX_CONCURRENT_INFERENCE = "1"

# 3. Khởi chạy uvicorn
cd backend\fastapi
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

> [!NOTE]
> Khi khởi chạy lần đầu tiên, thư viện `transformers` sẽ tải base weights `Qwen/Qwen3-4B` (~8.5 GB) vào thư mục cache `%USERPROFILE%\.cache\huggingface\hub`. Đảm bảo máy tính có kết nối mạng ổn định và tối thiểu 15 GB dung lượng ổ đĩa khả dụng.

### 3.2 Khởi chạy Chế độ Nhẹ (Light GGUF)
Không yêu cầu GPU hay tải base model 8.5 GB:

```powershell
$env:SERVING_MODE = "light"
$env:USE_FULL_QWEN3_4B_LORA = "false"
$env:DEVICE = "cpu"

cd backend\fastapi
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 4. Cách Chạy Bằng Docker Compose

Cấu hình mẫu trong `infrastructure/docker-compose.yml` đã được cập nhật chuẩn hóa GPU reservation theo đặc tả chính thức của Docker Compose:

```yaml
  fastapi:
    build:
      context: ../backend/fastapi
      dockerfile: Dockerfile
    container_name: movie_rcm_fastapi
    restart: always
    environment:
      - HOST=0.0.0.0
      - PORT=8000
      - SERVING_MODE=full
      - USE_FULL_QWEN3_4B_LORA=true
      - DEVICE=cuda
      - BASE_MODEL_NAME=Qwen/Qwen3-4B
      - PHASE23_ADAPTER_DIR=/app/models/qwen3-4b-phase23-lora
      - MODEL_NAME_OR_PATH=/app/models/qwen-0.6b/Qwen3-0.6B-Q8_0.gguf
      - ENABLE_FALLBACK=false
      - STRICT_READINESS=true
      - MAX_CONCURRENT_INFERENCE=1
      - MAX_NEW_TOKENS=256
      - HF_HOME=/root/.cache/huggingface
    volumes:
      - ../ai/models:/app/models:ro
      - hf_cache:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    expose:
      - "8000"
    networks:
      - movie_network
```

Lệnh chạy:
```bash
cd infrastructure
docker compose up -d fastapi
```

---

## 5. Trạng Thái Health và Readiness Mẫu

### 5.1 Khi Chế độ Chính (Full Model) Sẵn Sàng (HTTP 200)
`GET http://localhost:8000/health`:
```json
{
  "status": "healthy",
  "modelLoaded": true,
  "modelNameOrPath": "Qwen/Qwen3-4B",
  "activeBaseModelName": "Qwen/Qwen3-4B",
  "activeAdapterPath": "D:\\Class\\movie-rcm-system\\ai\\models\\qwen3-4b-phase23-lora",
  "fallbackModelPath": "../../ai/models/qwen-0.6b",
  "phase23ArtifactVerified": true,
  "phase23AdapterLoaded": true,
  "phase23AdapterPath": "D:\\Class\\movie-rcm-system\\ai\\models\\qwen3-4b-phase23-lora",
  "activeInferenceBackend": "qwen3-4b-peft-lora-4bit-nf4",
  "device": "cuda:0 (4bit-nf4)",
  "servingMode": "full",
  "requestedDevice": "cuda",
  "actualDevice": "cuda:0 (4bit-nf4)",
  "quantization": "4bit-nf4",
  "degraded": false,
  "loadError": null
}
```

`GET http://localhost:8000/ready` (HTTP 200 OK):
```json
{
  "ready": true,
  "status": "ready",
  "servingMode": "full",
  "activeInferenceBackend": "qwen3-4b-peft-lora-4bit-nf4",
  "phase23AdapterLoaded": true,
  "degraded": false,
  "loadError": null,
  "message": "Qwen3-4B + Phase23 LoRA phục vụ đầy đủ theo yêu cầu."
}
```

### 5.2 Khi Full Model Lỗi và Đang Chạy Fallback GGUF (HTTP 503 khi STRICT_READINESS=true)
`GET http://localhost:8000/health`:
```json
{
  "status": "degraded",
  "modelLoaded": true,
  "modelNameOrPath": "../../ai/models/qwen-0.6b/Qwen3-0.6B-Q8_0.gguf",
  "activeBaseModelName": "Qwen3-0.6B-Q8_0.gguf",
  "activeAdapterPath": null,
  "fallbackModelPath": "../../ai/models/qwen-0.6b",
  "phase23ArtifactVerified": true,
  "phase23AdapterLoaded": false,
  "phase23AdapterPath": "D:\\Class\\movie-rcm-system\\ai\\models\\qwen3-4b-phase23-lora",
  "activeInferenceBackend": "qwen3-0.6b-gguf+phase23-normalizer",
  "device": "llama_cpp (Qwen3-0.6B-Q8_0.gguf + Phase23 Normalizer)",
  "servingMode": "full",
  "requestedDevice": "cuda",
  "actualDevice": "llama_cpp (Qwen3-0.6B-Q8_0.gguf + Phase23 Normalizer)",
  "quantization": "q8_0",
  "degraded": true,
  "loadError": "RuntimeError: Lỗi tải base model weights"
}
```

`GET http://localhost:8000/ready` (HTTP 503 Service Unavailable):
```json
{
  "ready": false,
  "status": "degraded",
  "servingMode": "full",
  "activeInferenceBackend": "qwen3-0.6b-gguf+phase23-normalizer",
  "phase23AdapterLoaded": false,
  "degraded": true,
  "loadError": "RuntimeError: Lỗi tải base model weights",
  "message": "Yêu cầu chế độ Full Qwen3-4B LoRA nhưng chỉ đang chạy fallback backend."
}
```

### 5.3 Khi Chế độ Nhẹ (Light GGUF) Sẵn Sàng (HTTP 200)
`GET http://localhost:8000/health`:
```json
{
  "status": "healthy",
  "modelLoaded": true,
  "modelNameOrPath": "../../ai/models/qwen-0.6b/Qwen3-0.6B-Q8_0.gguf",
  "activeBaseModelName": "Qwen3-0.6B-Q8_0.gguf",
  "activeAdapterPath": null,
  "fallbackModelPath": "../../ai/models/qwen-0.6b",
  "phase23ArtifactVerified": false,
  "phase23AdapterLoaded": false,
  "phase23AdapterPath": null,
  "activeInferenceBackend": "qwen3-0.6b-gguf+phase23-normalizer",
  "device": "llama_cpp (Qwen3-0.6B-Q8_0.gguf + Phase23 Normalizer)",
  "servingMode": "light",
  "requestedDevice": "cpu",
  "actualDevice": "llama_cpp (Qwen3-0.6B-Q8_0.gguf + Phase23 Normalizer)",
  "quantization": "q8_0",
  "degraded": false,
  "loadError": null
}
```

### 5.4 Khi Chế độ Deterministic Normalizer Hoạt Động (Không Có LLM)
`GET http://localhost:8000/health`:
```json
{
  "status": "healthy",
  "modelLoaded": true,
  "modelNameOrPath": "phase23-deterministic-normalizer",
  "activeBaseModelName": null,
  "activeAdapterPath": null,
  "fallbackModelPath": "../../ai/models/qwen-0.6b",
  "phase23ArtifactVerified": false,
  "phase23AdapterLoaded": false,
  "phase23AdapterPath": null,
  "activeInferenceBackend": "phase23-deterministic-normalizer",
  "device": "cpu (deterministic-normalizer)",
  "servingMode": "light",
  "requestedDevice": "cpu",
  "actualDevice": "cpu (deterministic-normalizer)",
  "quantization": "none",
  "degraded": false,
  "loadError": null
}
```

### 5.5 Khi Chưa Nạp Hoặc Nạp Thất Bại (HTTP 503)
`GET http://localhost:8000/health`:
```json
{
  "status": "unhealthy",
  "modelLoaded": false,
  "modelNameOrPath": "Qwen/Qwen3-4B",
  "activeBaseModelName": null,
  "activeAdapterPath": null,
  "fallbackModelPath": "../../ai/models/qwen-0.6b",
  "phase23ArtifactVerified": false,
  "phase23AdapterLoaded": false,
  "phase23AdapterPath": null,
  "activeInferenceBackend": "uninitialized",
  "device": "uninitialized",
  "servingMode": "full",
  "requestedDevice": "cuda",
  "actualDevice": "uninitialized",
  "quantization": "none",
  "degraded": false,
  "loadError": "RuntimeError: Lỗi đọc trọng số"
}
```

---

## 6. Kiểm Soát Tài Nguyên & Concurrency

1. **Giới hạn đồng thời (Bounded Concurrency):**
   - Với GPU laptop RTX 3050 (6GB VRAM), thiết lập khuyến nghị là `MAX_CONCURRENT_INFERENCE=1`.
   - Cơ chế: `threading.BoundedSemaphore` bảo vệ mọi lượt gọi generate của mô hình.
   - Khi vượt ngưỡng hoặc timeout: trả về HTTP 429 Too Many Requests kèm thông điệp rõ ràng, ngăn ngừa tình trạng CUDA Out-Of-Memory.
2. **Khóa chống nạp trùng (Idempotent Lifecycle Lock):**
   - `_load_lock` ngăn chặn nhiều request khởi tạo đồng thời kích hoạt nạp model nhiều lần.
3. **Dọn dẹp bộ nhớ khi nạp thất bại:**
   - Tự động xóa tham chiếu `self.model`, `self.tokenizer`, gọi `gc.collect()` và `torch.cuda.empty_cache()` để giải phóng VRAM.

---

## 7. Kết Quả Kiểm Thử (Unit Tests & Integration Tests)

### 7.1 Bộ kiểm thử Unit Tests Offline (23 test cases)
Bộ kiểm thử `backend/fastapi/tests/test_serving.py` mock 100% inference và loader, không tải trọng số từ internet và không chiếm giữ GPU:

- **Chạy với pytest (Base Python)**:
```powershell
$env:HF_HUB_OFFLINE="1"; $env:TRANSFORMERS_OFFLINE="1"
C:\Users\Admin\anaconda3\python.exe -m pytest tests/test_serving.py -v
```
- **Chạy với unittest (Conda env `dippie-qwen`)**:
```powershell
$env:HF_HUB_OFFLINE="1"; $env:TRANSFORMERS_OFFLINE="1"; $env:RUN_FULL_INTEGRATION="0"
C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe -m unittest tests/test_serving.py
```

Kết quả: **23 passed (100% OK)** bao phủ:
1. Artifact tồn tại nhưng model chưa load.
2. Adapter thiếu hoặc không hợp lệ.
3. Full PEFT load thành công.
4. DEVICE=cpu khi máy có CUDA.
5. DEVICE=cuda khi CUDA không khả dụng.
6. NF4 và CPU dtype label đúng.
7. PEFT load thất bại, fallback tắt.
8. PEFT load thất bại, fallback bật và GGUF load thành công.
9. Cả full model và fallback đều thất bại.
10. Nhiều request khởi tạo không tạo load trùng.
11. Giới hạn inference/concurrency được thực thi (HTTP 429).
12. Health/readiness đúng từng trạng thái.
13. Khế ước API `/v1/discover` và `/api/chat` được mock offline.
14. Full mode + fallback false: Model chưa sẵn sàng trả HTTP 503.
15. Full mode + fallback false: Lỗi sinh văn bản trả HTTP 502 (không che bằng normalizer).
16. Full mode + fallback false: Output JSON lỗi trả HTTP 502 (không che bằng normalizer).
17. Full mode + fallback false: Output hợp lệ bảo toàn chuẩn hóa tất định (HTTP 200).
18. Health status phân biệt rõ `activeBaseModelName`, `activeAdapterPath`, `fallbackModelPath`.
19. Base resolution theo adapter metadata khi không có explicit constructor hay env configuration.
20. GGUF resolver kiểm thử filesystem trực tiếp qua temporary files (explicit file, directory chứa GGUF, missing file fallback standard candidates, và missing all candidates).
21. Normalizer-only mode: không có active model hay adapter khi thiếu weights.
22. Unloaded và failed load: không giữ lại stale active identities.
23. Ma trận ưu tiên xác định base model (6 kịch bản precedence nghiêm ngặt).

### 7.2 Full-Model GPU Integration Tests
File tách biệt: `backend/fastapi/tests/test_serving_integration.py` (chỉ chạy khi kích hoạt chủ động cờ `RUN_FULL_INTEGRATION=1`):
```powershell
$env:RUN_FULL_INTEGRATION="1"
C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe -m unittest tests/test_serving_integration.py
```
