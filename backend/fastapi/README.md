# FastAPI AI Recommendation Service (Qwen 0.6B / 0.5B)

Dịch vụ Backend AI phụ trách xử lý hội thoại thông minh (CineBot) và tính toán gợi ý phim sử dụng model **Qwen 0.6B / 0.5B**.

---

## 🚀 Hướng dẫn cài đặt & Khởi chạy

### 1. Tạo môi trường ảo Python & Cài đặt thư viện

```bash
cd backend/fastapi

# Tạo virtual environment
python -m venv venv

# Kích hoạt môi trường (Windows PowerShell)
.\venv\Scripts\Activate.ps1
# Hoặc trên Linux/macOS:
# source venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt
```

---

### 2. Cấu hình Model Qwen của bạn

Sao chép file `.env.example` thành `.env`:
```bash
cp .env.example .env
```

Mở file `.env` và cấu hình đường dẫn model:
- **Nếu đã tải model về máy**:
  ```env
  MODEL_NAME_OR_PATH=C:/path/to/your/qwen-0.6b
  ```
- **Nếu muốn tự động tải từ HuggingFace**:
  ```env
  MODEL_NAME_OR_PATH=Qwen/Qwen2.5-0.5B-Instruct
  ```

---

### 3. Chạy Server FastAPI

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- API Docs (Swagger UI): [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

---

## 📡 API Endpoints

- `POST /api/chat`: Nhận câu hỏi từ Chatbot frontend và trả lời kèm danh sách phim phù hợp.
- `POST /api/recommend`: Gợi ý danh sách phim theo thể loại/phim đã thích.
- `GET /health`: Trạng thái tải model và thông tin phần cứng.
