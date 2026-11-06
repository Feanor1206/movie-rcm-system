# AI & Machine Learning Pipeline (`movie-rcm-system/ai`)

Tài liệu hướng dẫn phát triển và mở rộng hệ thống **Cascading Multi-Stage AI Recommendation Pipeline**:

```text
Qwen 4B (NLU) ➔ Embedding / Retrieval ➔ Qwen 0.6B Recommender ➔ Qwen 0.6B Ranker ➔ Qwen 4B (Explanation)
```

---

## 📁 Cấu trúc thư mục & Vai trò

```text
ai/
├── 📁 datasets/
│   ├── preprocess_data.py          # Script tiền xử lý dữ liệu phim và lịch sử người dùng
│   ├── raw/                        # Dữ liệu thô (MovieLens, TMDB, crawl)
│   └── processed/                  # Dữ liệu sau khi trích xuất vector đặc trưng
│
├── 📁 training/
│   ├── train_recommender.py        # Huấn luyện / Fine-tune Qwen 0.6B Recommender (LoRA)
│   └── train_ranker.py             # Huấn luyện / Fine-tune Qwen 0.6B Ranker (Re-ranking)
│
├── 📁 models/
│   ├── qwen-0.6b/                  # Trọng số model Qwen 0.6B local (.gguf / .safetensors)
│   └── checkpoints/                # Các adapter LoRA đã huấn luyện
│
└── 📁 evaluation/
    └── evaluate_metrics.py         # Đo lường chất lượng: NDCG@K, Hit Rate@K, Precision, Recall
```

---

## 🚀 Hướng dẫn phát triển thêm trong tương lai

### 1. Tiền xử lý dữ liệu mới
```bash
python ai/datasets/preprocess_data.py --input raw/my_movies.json --output processed/
```

### 2. Huấn luyện 0.6B Recommender & 0.6B Ranker
```bash
# Train Recommender (Candidate Filtering)
python ai/training/train_recommender.py --base_model Qwen/Qwen2.5-0.5B-Instruct

# Train Ranker (Fine-grained Re-ranking)
python ai/training/train_ranker.py --base_model Qwen/Qwen2.5-0.5B-Instruct
```

### 3. Đánh giá chất lượng mô hình (Benchmarking)
```bash
python ai/evaluation/evaluate_metrics.py
```

### 4. Kết nối vào FastAPI Online Inference
File [`backend/fastapi/services/ai_pipeline.py`](file:///d:/movie-rcm-system/backend/fastapi/services/ai_pipeline.py) đã được chia sẵn thành 5 lớp Node độc lập (`NLUUnderstandingNode`, `EmbeddingRetrievalNode`, `Recommender06BNode`, `Ranker06BNode`, `ExplanationGeneratorNode`). Khi bạn hoàn thiện mô hình mới ở thư mục `ai/`, chỉ cần cập nhật trọng số trong các lớp Node tương ứng!
