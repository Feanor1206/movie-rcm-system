# Xử lý dữ liệu và tìm kiếm

Mã trong `ai/` chuẩn bị dữ liệu, mô hình và đánh giá. API phục vụ nằm ở `backend/fastapi/services`.

Tìm kiếm dùng BM25 theo trọng số trường và cụm từ tiếng Việt. Khi có mô hình cục bộ, hệ thống kết hợp vector ONNX qua RRF, xếp hạng lại bằng TorchScript và hiệu chuẩn điểm. Tìm bằng ảnh dùng pHash 64 bit từ kho khung hình.

CineBot lấy bằng chứng từ danh mục, hỗ trợ API LLM tương thích OpenAI trên máy hoặc qua HTTPS. Cấu hình dịch vụ và phạm vi tập phim nằm trong [hướng dẫn FastAPI](../backend/fastapi/README.md).

## Chuẩn bị dữ liệu tập phim

Quy trình thử nghiệm gồm nhận dạng lời thoại bằng Whisper, trích khung hình, nhóm cảnh, tạo mô tả ảnh, tóm tắt tập và xuất danh mục. Mỗi bước có đầu vào và kết quả riêng; xem [hướng dẫn xử lý dữ liệu](enrich/README.md).

Lệnh sau dùng bản ghi lời thoại đã có để trích khung hình, nhóm cảnh và xuất danh mục cho một tập:

```powershell
python -m ai.enrich.pipeline --episode ep_jadoo_s01_0022 --dialogue-only
```

## Tạo vector văn bản

Chạy từ thư mục gốc sau khi chuẩn bị mô hình ONNX:

```powershell
python ai/build_text_embeddings.py --catalog data/catalog.jadoo_all.json --artifact ai/models/text-onnx --device cpu
```

## Đánh giá tìm kiếm

Chuẩn bị nhãn do người viết độc lập trước khi chạy. Tệp CSV mẫu hiện chỉ có tên cột.

```powershell
python -m ai.evaluation.retrieval_gate --labels ai/datasets/gold/search_queries_v1.csv --original-catalog data/catalog.jadoo_all.json --enriched-catalog ai/artifacts/pilot-enriched.json --encoder ai/models/text-onnx
```

Cách tính chỉ số và điều kiện đánh giá nằm trong [hướng dẫn đánh giá](evaluation/README.md).
