# AI & Machine Learning Pipeline (`movie-rcm-system/ai`)

Hệ thống AI của **Dippie** bao gồm 3 trụ cột chính:
1. **Retrieval & Multimodal Indexing (`backend/fastapi/services`)**:
   - **Field-Weighted BM25 + Bi-gram Phrase Index**: Ưu tiên khớp chính xác tên phim, tập phim, nhân vật, bí danh, từ khóa và cụm từ tiếng Việt.
   - **Dense ONNX Hybrid RRF + Cross-Encoder Reranker + Score Calibration**: Kết hợp BM25 và vector ngữ nghĩa BGE-M3 (ONNX CPU) qua Reciprocal Rank Fusion, xếp hạng lại bằng TorchScript Reranker và chuẩn hóa xác suất khớp (`calibratedScore`).
   - **Visual Frame Search (`frame_search.py`)**: Tìm kiếm phân cảnh bằng hình ảnh dựa trên 64-bit DCT Perceptual Hash (pHash) từ kho keyframes.
2. **CineBot Grounded RAG & Unified LLM (`chat.py`, `llm_client.py`)**:
   - Hỗ trợ đồng thời **Cloud LLM** (`https://`: DeepSeek, OpenAI, OpenRouter...) và **Local LLM** (`http://localhost` / `http://127.0.0.1`: Ollama, vLLM, LM Studio, llama-server).
   - Xác thực chống ảo giác (Anti-Hallucination Grounding) dựa trên bằng chứng catalog và tự động sinh gợi ý hội thoại tiếp theo (`followUps`).
3. **Unified Offline Enrichment Pipeline (`ai/enrich/pipeline.py`)**:
   - Quy trình làm giàu dữ liệu đa phương thức cho bất kỳ số lượng tập phim nào: Whisper ASR ➔ 1fps Keyframes (pHash deduplication) ➔ Scene Grouping ➔ Vision Captioning ➔ Episode Summarization ➔ Catalog Export.

---

## 🚀 Các lệnh thường dùng

### 1. Chạy trọn gói Offline Enrichment Pipeline
```powershell
python -m ai.enrich.pipeline --episode ep_jadoo_s01_0022 --dialogue-only
```

### 2. Chuẩn bị Dense Embeddings Offline cho Catalog lớn
```powershell
python ai/build_text_embeddings.py --catalog data/catalog.jadoo_all.json --artifact ai/models/text-onnx --device cpu
```

### 3. Đánh giá chất lượng Retrieval (Quality Gate)
```powershell
python -m ai.evaluation.retrieval_gate --labels ai/datasets/gold/search_queries_v1.csv --original-catalog data/catalog.jadoo_all.json --enriched-catalog ai/artifacts/pilot-enriched.json --encoder ai/models/text-onnx
```
