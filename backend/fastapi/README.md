# Dippie FastAPI AI Gateway (`backend/fastapi`)

Dịch vụ AI Gateway phụ trách tìm kiếm ngữ nghĩa lai (Hybrid Search), tìm kiếm bằng khung hình (Frame Search), gợi ý phim theo độ tương đồng nội dung (Hybrid Affinity Recommendation), và hội thoại thông minh đặt trên nền tảng dữ liệu danh mục (Catalog-Grounded CineBot SSE).

---

## 🚀 Khởi chạy & Cấu hình

### 1. Cài đặt thư viện
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/fastapi/requirements.txt
```

### 2. Cấu hình biến môi trường (Tuỳ chọn)
- **Chế độ vận hành**:
  - `MODEL_MODE=light`: Sử dụng tìm kiếm Hybrid/BM25 và câu trả lời mẫu xác định (không cần LLM).
  - `MODEL_MODE=cloud`: Bật LLM (DeepSeek / OpenAI-compatible Cloud hoặc Local Ollama/vLLM qua `http://127.0.0.1`).
- **Kết nối LLM (Cloud hoặc Local)**:
  - `LLM_BASE_URL` (hoặc `DEEPSEEK_BASE_URL`): Ví dụ `https://api.deepseek.com` hoặc `http://127.0.0.1:11434/v1` (Ollama).
  - `LLM_MODEL` (hoặc `DEEPSEEK_MODEL`): Tên model (ví dụ `deepseek-flash`, `qwen2.5:3b`).
  - `LLM_API_KEY` (hoặc `DEEPSEEK_API_KEY`): API key (không bắt buộc nếu dùng `http://localhost` / `http://127.0.0.1`).
  - `ALLOW_FULL_CATALOG_GROUNDING=1`: Cho phép CineBot sử dụng bằng chứng từ toàn bộ tập phim trong catalog thay vì chỉ nhóm tập pilot.
- **Model & Chỉ mục cục bộ**:
  - `TEXT_ENCODER_PATH`: Đường dẫn thư mục ONNX Text Encoder.
  - `RERANKER_MODEL_PATH`: Đường dẫn thư mục TorchScript Reranker.
  - `SCORE_CALIBRATION_PATH`: Đường dẫn file JSON hiệu chuẩn điểm số.
  - `FRAME_INDEX_PATH`: Đường dẫn thư mục chứa `keyframes.json` để bật tính năng tìm kiếm bằng ảnh (`/v1/frame-search`).

---

## 📡 API Endpoints

- `POST /api/index/sync`: Đồng bộ snapshot catalog nguyên tử từ Spring Boot.
- `POST /v1/search` & `POST /v1/discover`: Tìm kiếm phim, tập phim, phân cảnh và lời thoại (Field-weighted BM25 + Bi-gram + Dense RRF + Reranker).
- `POST /api/chat`: Hội thoại CineBot qua luồng SSE (`metadata` ➔ `token` ➔ `done`) kèm danh sách phim, bằng chứng và gợi ý câu hỏi tiếp theo (`followUps`).
- `POST /api/recommend` & `POST /v1/recommend`: Gợi ý phim lai theo hồ sơ phim đã thích (`likedMovieIds`), thể loại (`genres`) và tâm trạng (`mood`).
- `POST /v1/frame-search`: Tìm kiếm tập phim và mốc thời gian từ ảnh chụp màn hình (JPEG/PNG/WebP).
- `GET /health` & `GET /ready`: Kiểm tra trạng thái sẵn sàng độc lập của từng tính năng AI.
