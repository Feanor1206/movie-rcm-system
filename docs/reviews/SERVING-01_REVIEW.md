# Review cập nhật serving Gemini — 13/10/2026

## Review bổ sung sau báo cáo SERVE-01

**Chưa nghiệm thu serving Qwen3-4B fine-tuned.** Báo cáo triển khai của Gemini được đọc và đối chiếu lại với workspace/runtime.

- Health local mới trả `servingMode=light`, `degraded=false`, `loadError=null`, `phase23AdapterLoaded=false`. Service đang chọn light trực tiếp, không có bằng chứng trong trạng thái này rằng nó vừa thử full rồi fallback.
- Loader mặc định light khi không có `SERVING_MODE` hoặc flag full. Cả `start-all.ps1` và `start-all.bat` hiện chỉ chọn interpreter rồi gọi Uvicorn, chưa đặt các biến full. Báo cáo nói có thể chỉ dùng launcher để chạy full là thiếu điều kiện: environment cha phải được cấu hình trước, hoặc launcher phải có chế độ full rõ.
- Compose đã đổi sang `SERVING_MODE=full`, flag LoRA true và có GPU reservation, nhưng đó không phải cấu hình được launcher local tự động sử dụng.
- Adapter weights vẫn hiện diện, kích thước 132187888 bytes. Base snapshot trong cache mặc định ghi tổng weights 8044936192 bytes; hai shard `model-00001-of-00003.safetensors` và `model-00002-of-00003.safetensors` chưa có, shard thứ ba có. Đây là cache đã kiểm tra, không kết luận không có bản base model ở nơi khác.
- Báo cáo nêu 13 mock tests pass và smoke test 0.6B. Mock tests không chứng minh weights 4B đã được load hoặc inference thành công; lần review bổ sung chưa tái chạy suite này.

Hướng sửa theo yêu cầu dùng Qwen4B của người dùng: full là chế độ mặc định cho deployment chính và launcher dự án; `ENABLE_FALLBACK=false` trong cấu hình nghiệm thu. Light chỉ bật qua lựa chọn rõ ràng, không dùng làm kết quả hoàn thành ticket. Chuẩn bị base model đầy đủ, chạy base + adapter và cung cấp health/readiness cùng request inference 4B thực tế trước khi nghiệm thu. Không huấn luyện lại hoặc thay thế artifact fine-tuned.

Các phần dưới đây là snapshot review trước cập nhật này; những findings về thiếu GPU reservation đã được Gemini sửa trong Compose, còn nghiệm thu full runtime vẫn chưa đạt.

Phạm vi: các thay đổi mới trong requirements, loader Qwen, health schema và Docker Compose. Chưa thấy implementation CTX-01 trong Spring Boot ở workspace hiện tại. Codex chỉ review, không sửa mã ứng dụng.

## Kết quả

Chấp nhận hướng sửa về tính trung thực của trạng thái artifact/adapter. Chưa nghiệm thu serving Qwen3-4B fine-tuned.

Bằng chứng GET `http://127.0.0.1:8000/health` trong lần review:

```json
{
  "status": "healthy",
  "modelLoaded": true,
  "phase23ArtifactVerified": true,
  "phase23AdapterLoaded": false,
  "activeInferenceBackend": "qwen3-0.6b-gguf+phase23-normalizer",
  "device": "llama_cpp (Qwen3-0.6B-Q8_0 GGUF + Phase23 Normalizer)"
}
```

Đây là trạng thái đang chạy của endpoint local, không phải chỉ suy luận từ cấu hình. Không kết luận service này đang chạy trong Docker hoặc máy/môi trường khác dùng cùng cấu hình.

## Những phần đã sửa đúng

- Bổ sung dependencies `peft`, `bitsandbytes`, `llama-cpp-python` vào requirements.
- Đường dẫn model/adapter trong Compose phù hợp volume `/app/models`.
- Tách `phase23ArtifactVerified` và `phase23AdapterLoaded`; cờ adapter loaded chỉ true sau nhánh nạp PEFT thành công.
- Bổ sung `activeInferenceBackend` vào health để phân biệt full 4B/LoRA, GGUF nhỏ và normalizer.
- Nhánh CUDA có cấu hình NF4 4-bit; chưa có bằng chứng nhánh này đã load/inference thành công trên GPU hiện có.

## Findings cần xử lý

### P1 — Chế độ serving hiện tại chưa sử dụng Qwen3-4B fine-tuned

`infrastructure/docker-compose.yml:76` vẫn đặt `USE_FULL_QWEN3_4B_LORA=false`; loader chỉ vào nhánh PEFT khi flag true và adapter tồn tại. Health local xác nhận đang dùng Qwen3-0.6B GGUF và adapter chưa được load. `BASE_MODEL_NAME=Qwen/Qwen3-4B` một mình không kích hoạt nhánh full model.

Cần tách cấu hình rõ cho chế độ Qwen4B fine-tuned và fallback nhẹ. Chế độ nhằm nghiệm thu full model phải thực sự load adapter và hoàn thành một request inference; thiếu tài nguyên hoặc load lỗi phải được báo rõ, không nghiệm thu từ việc tìm thấy artifact.

### P1 — Compose chưa cấp GPU và DEVICE chưa được thực thi như cấu hình

Compose mới chỉ đổi `DEVICE=cuda`, chưa thấy GPU device reservation hoặc cấu hình tương đương. Biến môi trường không cấp thiết bị GPU cho container. Xem tài liệu chính thức: https://docs.docker.com/compose/how-tos/gpu-support/.

Loader lưu `device_config`, nhưng nhánh full model vẫn chọn CUDA/CPU chỉ từ `torch.cuda.is_available()`. Vì vậy giá trị `DEVICE=cpu` cũng không đảm bảo chạy CPU nếu CUDA có sẵn; `DEVICE=cuda` không đảm bảo lỗi rõ khi CUDA thiếu. Nhánh GGUF không cấu hình GPU offload qua `n_gpu_layers`.

Cần có policy `auto/cpu/cuda` rõ, cấu hình cấp GPU cho chế độ Docker tương ứng và bằng chứng CUDA visibility trong chính runtime phục vụ model. Không bật offload hoặc thay đổi GGUF nếu ticket chỉ phục vụ full Qwen4B.

### P2 — Nhãn backend CPU ghi FP16 trong khi load FP32

`qwen_service.py:276` mặc định `quant_label=fp16`, nhưng nhánh CPU ở dòng 291 đặt `torch_dtype=torch.float32`. Health/log sẽ ghi sai `qwen3-4b-peft-lora-fp16` nếu full model được load trên CPU. Cần đặt nhãn theo dtype/quantization thực tế.

## Kiểm tra đã thực hiện và giới hạn

- Parse AST thành công cho `main.py`, `schemas.py`, `services/qwen_service.py`.
- GET health local thành công, trạng thái như trên.
- Đã đối chiếu Compose, requirements và các nhánh loader.
- Chưa chạy full Qwen4B, chưa tải thêm base weights, chưa restart service, chưa build Docker, chưa đo latency/VRAM hoặc chạy regression suite. Không có Docker CLI trong PATH của process review.

## Prompt tiếp theo đề xuất cho Gemini

Triển khai ticket SERVE-01 để nghiệm thu serving Qwen3-4B fine-tuned theo ba findings trên. Đọc repo và bảo toàn mọi thay đổi chưa commit. Không huấn luyện lại, không sửa thuật toán ranking/parser, không làm CTX-01 cùng ticket này.

1. Chốt và ghi rõ hai chế độ: full Qwen4B + Phase23 LoRA, và fallback GGUF. Cấu hình nghiệm thu full model phải bật nhánh đó. Không dùng trạng thái fallback làm bằng chứng full model hoạt động.
2. Thực thi DEVICE=auto/cpu/cuda đúng; cuda không khả dụng phải báo rõ trong trạng thái lỗi/degraded hoặc readiness theo policy đã ghi. Sửa dtype label CPU. Không hứa toàn bộ model trên GPU chỉ từ device_map=auto; nếu có offload, báo placement thực tế.
3. Thêm cấu hình cấp GPU Docker cho profile/full-model deployment; kiểm tra visibility trong container nếu môi trường Docker khả dụng. Nếu serving local, kiểm tra trong đúng interpreter/process phục vụ FastAPI và ghi rõ chưa kiểm tra Docker.
4. Kiểm thử các nhánh bằng mock/fake loader, gồm adapter thiếu, CUDA thiếu, load PEFT lỗi và fallback. Chứng minh health flags/backend labels đúng từng nhánh mà không cần tải model trong unit tests.
5. Ưu tiên base weights và môi trường có sẵn. Chuẩn bị dependencies trong môi trường dự án; nếu cần chạy lại service để áp dụng cấu hình, dùng đúng cách khởi chạy của dự án và tránh tạo nhiều process cùng giữ model. Báo blocker chính xác nếu chưa đủ điều kiện smoke test runtime.
6. Khi runtime đủ điều kiện, cung cấp health cho full model với adapterLoaded=true, backend/dtype đúng, kết quả một request discovery, latency và VRAM đo được. Đây là smoke test serving, không chứng minh chất lượng toàn bộ recommender.
7. Báo diff, lệnh kiểm tra, kết quả, giới hạn và trạng thái từng tiêu chí. Không tự commit/push; dừng để review.

CTX-01 có thể được triển khai độc lập sau đó. Serving và tính năng weather/context là hai ticket riêng để review không lẫn phạm vi.
