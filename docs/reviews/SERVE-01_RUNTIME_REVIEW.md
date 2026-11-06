# SERVE-01 — Review runtime Qwen3-4B và nghiệm thu còn lại

Ngày: 13/10/2026. Codex chỉ kiểm tra và ghi review, không sửa mã ứng dụng.

## Kết luận

**Đã xác nhận local runtime nạp Qwen3-4B + Phase23 LoRA ở chế độ full/NF4/CUDA.** Không còn dùng GGUF 0.6B trong runtime được kiểm tra. Chưa đóng toàn bộ ticket vì cấu hình Docker và xử lý inference failure vẫn chưa tuân thủ policy đã chốt.

## Bằng chứng kiểm tra độc lập

- GET `/health`: HTTP 200, `modelLoaded=true`, `phase23AdapterLoaded=true`, `servingMode=full`, `activeInferenceBackend=qwen3-4b-peft-lora-4bit-nf4`, `actualDevice=cuda:0 (4bit-nf4)`, `degraded=false`, `loadError=null`.
- GET `/ready`: HTTP 200, `ready=true`, backend full LoRA.
- Cache base model có đủ ba shard, kích thước lần lượt 3957900840, 3987450520 và 99630640 bytes. Adapter được giữ nguyên trong repo.
- POST `/v1/discover` vào service đang chạy, session riêng `codex-serve01-review-20261013`, query: “Gợi ý cho tôi 2 phim hoạt hình phiêu lưu trước năm 2010 không có kinh dị”. HTTP thành công sau **81,15 giây** end-to-end, requested_k=2, year_max=2009, include Animation/Adventure, exclude Horror. Kết quả gồm Spirited Away và Fantasia.
- Đây là một mẫu end-to-end, không phải p95, không phải đo riêng thời gian model generate và không chứng minh toàn bộ chất lượng recommender. Kết quả hiện bị normalizer hậu xử lý, API chưa báo parser source/JSON validity per request để chứng minh không dùng đường sửa lỗi tất định.
- Rerun: `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -m pytest tests/test_serving.py -q -k 'not test_13'`, từ thư mục FastAPI, interpreter `C:\Users\Admin\anaconda3\python.exe`: **12 passed, 1 deselected, 42,45 giây**.
- Không chạy test_13 trong process model thứ hai vì test này chưa mock singleton inference và có thể load model/download/chiếm thêm GPU. Đã thay bằng smoke test qua service hiện hữu để review đường API mà không tạo bản model thứ hai.
- Interpreter `dippie-qwen` hiện không có pytest; đây là khác biệt cần ghi đúng trong hướng dẫn chạy test, không có nghĩa runtime thiếu dependencies inference.
- `nvidia-smi` tại thời điểm kiểm tra: total 6144 MiB, used 3841 MiB, free 2162 MiB. Không tái đo peak PyTorch allocations của báo cáo. Không diễn giải total VRAM trừ PyTorch reserved là headroom vật lý; GPU còn có allocation ngoài allocator PyTorch và các process khác.

## Findings trước khi đóng ticket

### P1 — Docker Compose vẫn bật fallback

`infrastructure/docker-compose.yml:83` vẫn là `ENABLE_FALLBACK=true`, trong khi defaults, .env và local launchers đã false. Chạy bằng Docker sẽ có policy khác local; khi full load lỗi có thể khởi tạo model 0.6B dù cấu hình nghiệm thu yêu cầu không tự đổi model.

Sửa cấu hình deployment chính về false. Light mode chỉ được lựa chọn rõ ràng. Không dùng readiness 503 như sự thay thế cho việc thực thi policy không fallback.

### P1 — Tắt fallback chưa ngăn kết quả normalizer khi inference thất bại

`qwen_service.py:876` thử load nếu model chưa sẵn sàng, nhưng không chặn request khi full load thất bại. `qwen_service.py:910` bắt exception generation/JSON parsing và tiếp tục `normalize_phase23_intent` với raw_parsed rỗng, trả response khám phá như thành công. Nhánh này không kiểm tra `ENABLE_FALLBACK`.

Vì thế `/ready` có thể not ready nhưng endpoint discovery vẫn trả HTTP 200 từ logic tất định; hoặc model đã load nhưng request generation lỗi vẫn bị che bằng normalizer. Việc normalizer hậu xử lý output hợp lệ khác với dùng normalizer thay cho inference thất bại.

Yêu cầu: full mode + fallback false phải trả lỗi rõ khi model chưa sẵn sàng, generation lỗi hoặc output không hợp lệ. Nếu có fallback được cho phép ở mode khác, kết quả mỗi request cần thể hiện source/degraded, không gắn thành công của model cho output tất định. Giữ nguyên nghiệp vụ normalization trên output hợp lệ.

### P2 — Test API contract chưa là unit test offline

`tests/test_serving.py:385` tạo `TestClient(app)` và gọi API mà không patch `qwen_service`/model generation. Sau đổi default full, test có thể thực sự load weights/chiếm GPU, hoặc pass bằng normalizer sau load/inference lỗi. Nó không đáp ứng mô tả toàn bộ suite dùng mock loader và không tải model.

Tách: unit contract tests dùng fake provider/model; full-model integration tests được đánh dấu riêng và chạy chủ động trong môi trường phù hợp. Thêm cases model unavailable và JSON/generation failure với fallback false, kiểm tra HTTP lỗi chứ không chỉ readiness.

### P2 — Health vẫn hiển thị đường dẫn 0.6B trong modelNameOrPath

`qwen_service.py:598` vẫn trả `modelNameOrPath` là đường dẫn GGUF, dù full model đang phục vụ. Trường legacy này không chứng minh active model là 0.6B, nhưng gây hiểu nhầm đúng vấn đề người dùng vừa gặp.

Thêm các trường có ngữ nghĩa rõ như activeBaseModelName/adapterPath/fallbackModelPath; duy trì tương thích cần thiết và cập nhật docs. Với full mode, giao diện vận hành phải nhận biết Qwen3-4B ngay.

## Nhận xét sản phẩm và hiệu năng

Đường serving full đã hoạt động, nhưng 81,15 giây cho một lượt kiểm tra và 37,83 giây trong báo cáo là latency cần tiếp tục đo và tối ưu trước trải nghiệm chat tương tác. Không đổi xuống 0.6B để giải quyết khi người dùng yêu cầu dùng model fine-tuned.

Đợt performance riêng nên đo token input/output, stop reason, valid raw JSON, thời gian generate, thời gian normalizer/retrieval/rank/explanation và warm/cold runs. Sau đó mới tối ưu prompt, decoding budget, cache phù hợp hoặc serving implementation. Không cắt output token tùy ý làm JSON bị truncate; kiểm tra chất lượng parser sau mỗi thay đổi.

Metadata/root pipeline còn dùng tên “Qwen0.6B recommender/ranker”, trong khi code stage hiện là heuristic. Chưa đánh đồng smoke test serving với nghiệm thu recommender, personalized ranking hoặc toàn bộ năm tầng AI.

## Giao việc sửa nhỏ cho Gemini

Thực hiện bốn findings trong tài liệu này, giữ nguyên model Qwen3-4B + adapter và code thuật toán hiện hữu. Không huấn luyện lại, không chuyển runtime sang light. Bổ sung unit tests offline cho inference failure/invalid JSON/model unavailable và HTTP errors. Chạy lại kiểm tra phù hợp, ghi đúng interpreter. Không tạo process model thứ hai chỉ để chạy unit tests. Không gộp tối ưu latency hoặc CTX-01 vào patch này; hai phần đó là ticket tiếp theo. Báo diff và bằng chứng, không commit/push, dừng để review.
