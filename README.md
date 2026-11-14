# Dippie (`movie-rcm-system`)

Nền tảng khám phá phim hoạt hình, quản lý danh mục (`dippie.catalog.v1`), thư viện cá nhân, phát video trực tuyến (HTTP Range / Google Drive) và trợ lý AI **CineBot v4**.

Dự án hỗ trợ **2 kiến trúc Backend song song** dùng chung cơ sở dữ liệu **MySQL 8.0** và **AI Engine v4**:
- **`java-main` (`Spring Boot Main` + `FastAPI AI` + `MySQL 8.0`)**: Spring Boot (`:8080`) đảm nhiệm Auth, Catalog, Library, Watch Progress & Streaming; FastAPI (`:8000`) đảm nhiệm AI Search, CineBot RAG, Frame Search & Recommendation.
- **`python-main` (`FastAPI Unified Main & AI` + `MySQL 8.0`)**: Một dịch vụ FastAPI duy nhất (`:8000`) đảm nhiệm toàn bộ REST API nghiệp vụ (`/api/*`) lẫn AI Engine (`/v1/*`, `/api/chat`, `/api/recommend`), kết nối trực tiếp vào MySQL 8.0.

---

## 🌿 Cấu trúc Nhánh GitHub
- `main` / `dev`: Nhánh hợp nhất chứa đầy đủ cả 2 chế độ (`Java Main` và `Python Main`).
- `java-main`: Bản chạy **Spring Boot** làm Backend chính + **FastAPI** làm AI Gateway + **MySQL 8.0**.
- `python-main`: Bản chạy **FastAPI** làm Unified Backend + AI + **MySQL 8.0** (đã lược bỏ thư mục `backend/springboot`).

---

## 🚀 Khởi chạy nhanh trên Windows

### 1. Cài đặt môi trường
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/fastapi/requirements.txt
cd frontend
npm ci
cd ..
```

### 2. Khởi chạy MySQL 8.0 (Docker)

Đặt `APP_JWT_SECRET` theo [hướng dẫn cấu hình](backend/fastapi/README.md#2-cấu-hình-biến-môi-trường) trước khi chạy Compose.

```powershell
cd infrastructure
docker compose up -d mysql
cd ..
```
*(Nếu máy chưa bật MySQL, bản `Python Main` tự động fallback sang SQLite nội bộ tại `data/python_main.db`, còn bản `Java Main` có thể chạy profile `test`/`H2 MySQL Mode`).*

### 3. Chạy ứng dụng
- **Chạy bản Java Main (`Spring Boot :8080` + `FastAPI AI :8000` + `Next.js :3000`):**
  ```powershell
  .\start-java-main.ps1 -Background
  ```
- **Chạy bản Python Main (`FastAPI Full Main + AI :8000` + `Next.js :3000`):**
  ```powershell
  .\start-python-main.ps1 -Background
  ```
- Dừng toàn bộ dịch vụ:
  ```powershell
  .\scripts\stop_preview_stack.ps1
  ```

---

## 🧠 Kiến trúc AI Engine v4 (`backend/fastapi` & `ai/`)
1. **Field-Weighted BM25 + Vietnamese Bi-gram + Dense RRF (`text_index.py`, `search.py`)**: Tìm kiếm phân cấp theo trọng số trường (`title`, `characters`, `dialogue`, `visual_summary`, `synopsis`), hỗ trợ tiếng Việt có dấu/không dấu và hiệu chuẩn điểm số.
2. **Grounded RAG CineBot (`chat.py`, `llm_client.py`)**: Trích xuất bằng chứng từ tập phim, phân cảnh, lời thoại kèm mốc thời gian (`timestamp`); hỗ trợ mọi OpenAI-compatible LLM (DeepSeek, OpenAI, hoặc Local Ollama/vLLM/llama.cpp) và tự động fallback về câu trả lời xác định khi offline.
3. **Visual Frame Search (`frame_search.py`)**: Tìm tập phim và mốc thời gian từ ảnh chụp màn hình qua 64-bit DCT Perceptual Hash (`pHash`) kết hợp Color Layout + Edge Grid.
4. **Hybrid Content-Affinity Recommender (`recommend.py`)**: Gợi ý phim dựa trên vector tương đồng nội dung (Genre, Themes, Characters, Mood, Rating) từ hồ sơ người dùng (`likedMovieIds`, `favorites`, `ratings`).

---

## 🧪 Kiểm thử (Verification)

```powershell
# 1. Kiểm thử Python Main + AI v4 (Offline)
.\.venv\Scripts\python.exe -m pytest tests backend/fastapi/tests -q

# 2. Kiểm thử Spring Boot (MySQL compatibility mode)
cd backend/springboot
.\mvnw.cmd test "-Dspring.profiles.active=test"

# 3. Kiểm thử & Build Frontend Next.js
cd ../../frontend
npm test
npm run typecheck
npm run build
```
