# Đánh giá tìm kiếm

Kiểm thử API và đồng bộ danh mục chạy bằng pytest. Các tình huống từ bản tìm kiếm cũ có thể giữ nguồn `source: "legacy-regression"` và chạy qua `run_cases(search_fn, cases)`, `measure(cases, predictions)`. Số đo này chỉ dùng kiểm tra hồi quy.

Để báo cáo chất lượng mô hình, cần bộ truy vấn do người viết độc lập, chốt trước khi tinh chỉnh và có `source: "human"` ở mọi dòng. Các tập đánh giá phải tách khỏi tập huấn luyện và hiệu chuẩn. Dự án chưa kèm bộ nhãn người viết.

## So sánh bốn cấu hình

[Mẫu truy vấn](../datasets/gold/search_queries_v1.csv) hiện chỉ có tên cột. Điền nhãn theo [hướng dẫn viết](../datasets/gold/README.md) trước khi chạy; CSV rỗng làm lệnh dừng trước khi nạp mô hình và danh mục.

Từ thư mục gốc, thay đường dẫn bằng bản danh mục đã xuất và mô hình BGE-M3 ONNX trên máy:

```powershell
python ai/evaluation/retrieval_gate.py --labels ai/datasets/gold/search_queries_v1.csv --original-catalog data/catalog.jadoo_all.json --enriched-catalog ai/artifacts/pilot-enriched.json --encoder ai/artifacts/models/bge-m3-onnx/int8 --output ai/artifacts/pilot_retrieval_metrics.json
```

Lệnh so sánh BM25 và tìm kiếm kết hợp vector trên hai bản danh mục, dùng chung nhãn và phạm vi tập phim. Các tập được lấy từ bản danh mục thử nghiệm riêng hoặc suy ra từ lời thoại, cảnh đã đổi trong bản đầy đủ. Có thể lặp `--episode-id` để chọn rõ một đến năm ID có trong cả hai bản.

Hai lần chạy kết hợp dùng cùng bộ mã hóa cục bộ, lưu bộ nhớ đệm riêng trong `data/indices/pilot_evaluation`, không áp dụng mô hình xếp hạng lại hay hiệu chuẩn. Dùng `pilot-dialogue.json` khi chỉ đánh giá ASR.

Bản nháp của các tập được chọn có thể được đưa vào bộ nhớ để đánh giá khi gói danh mục, nguồn từng bản ghi và video công khai khớp nhau. `projectedDrafts` ghi số bản ghi được đưa vào theo cách này; trạng thái duyệt của danh mục gốc được giữ nguyên.

Cả bốn cấu hình trả chỉ số tổng hợp và `perEpisode` kèm số truy vấn cho từng tập có nhãn. Truy vấn có nhiều tập đúng được chấm riêng với từng tập trong phần này. Tập chưa có nhãn được bỏ qua.

| Chỉ số | Cách tính |
| --- | --- |
| Recall@1, Recall@5, MRR | Xếp hạng theo tập duy nhất. |
| `timeHitRateAt5` | Tỷ lệ tập đúng trong năm kết quả đầu có nhãn thời gian và `startMs` lệch tối đa 30 giây. Thiếu thời gian dự đoán tính là trượt; kết quả là `null` nếu không tìm được tập có nhãn thời gian. |
| `momentRecallAt5` | Tính cả truy vấn không tìm được tập đúng vào mẫu số. |

## Kiểm tra ngưỡng chất lượng

Công cụ nhận CSV hoặc JSONL, mỗi dòng là một truy vấn đã gán nhãn:

```json
{"id":"q1","query":"tập nào làm vỡ bình hoa","episodeIds":["episode-12"],"moments":[{"episodeId":"episode-12","startMs":520000}],"source":"human"}
```

Dự đoán và kết quả đối chiếu dùng cùng ID truy vấn:

```json
{"id":"q1","results":[{"episodeId":"episode-12","startMs":525000}]}
```

Đặt ngưỡng trong tệp JSON với `recallAt5`, `mrr`, `momentRecallAt5`, mỗi giá trị từ 0 đến 1 theo yêu cầu dự án. Công cụ không đặt ngưỡng mặc định.

Một mốc đúng cần khớp tập và lệch thời gian bắt đầu tối đa 30 giây, kể cả biên. Recall@5 là trung bình tỷ lệ tập đúng trên từng truy vấn. MRR dùng toàn bộ thứ hạng trả về. Độ thu hồi mốc thời gian dùng năm kết quả đầu của các truy vấn có nhãn thời gian.

```powershell
python ai/evaluation/retrieval_gate.py --labels ai/datasets/search_test.jsonl --predictions artifacts/search_predictions.jsonl --baseline artifacts/search_baseline.jsonl --thresholds ai/datasets/search_thresholds.json --output artifacts/search_gate.json
```

Mã thoát bằng 0 khi đạt mọi ngưỡng và từng chỉ số đều tăng so với bản đối chiếu. Thiếu dữ liệu, ID trùng, bộ ID truy vấn lệch nhau, thiếu nhãn thời gian hoặc thiếu ngưỡng đều làm kiểm tra thất bại.

Chưa có kết quả đo chất lượng hoặc độ trễ trên RTX 3050. Cần mô hình thực, nhãn độc lập và phép đo trên phần cứng đó để báo cáo.

## So sánh độ chính xác ONNX

Phép đo so sánh ba cấu hình: tài liệu FP32 với truy vấn FP32, tài liệu FP32 với truy vấn INT8, tài liệu INT8 với truy vấn INT8. Mọi cửa sổ lời thoại trong các tập được chọn làm truy vấn trên toàn bộ chỉ mục của nhóm; tài liệu lời thoại trùng truy vấn được loại ra.

Độ trùng top 10 được báo theo từng tập, đối chiếu với FP32 ONNX. Kết quả bằng điểm giữ thứ tự chỉ mục. Vector tài liệu dùng float16 như chỉ mục phục vụ, vector truy vấn dùng float32. Số đo thể hiện mức khớp giữa các mức chính xác.

Lệnh dưới dùng bản nháp hai tập chưa duyệt, đưa hai bản lời thoại vào bộ nhớ để đánh giá. Các tập dự kiến còn lại nằm ngoài phép đo. Trạng thái công bố và cấu hình phục vụ được giữ nguyên.

Ma trận vector được lưu theo dấu vân tay mô hình, loại đầu vào và nội dung văn bản. Độ trễ CPU đo một truy vấn mỗi lần sau khi làm nóng mô hình, gồm tách từ và chuẩn hóa:

```powershell
python ai/evaluation/precision_benchmark.py --original-catalog data/catalog.jadoo_all.json --enriched-catalog ai/artifacts/partial-dialogue-preview.json --episode-id ep_jadoo_s01_0022 --episode-id ep_jadoo_s04_0021 --fp32 E:/Dippie-offline/bge-m3/onnx/fp32 --int8 E:/Dippie-offline/bge-m3/onnx/int8 --cache-dir ai/artifacts/precision-cache --output ai/artifacts/precision-two-episodes.json
```

Thay các đường dẫn mô hình bằng vị trí trên máy của bạn. Thử nghiệm 200 văn bản trước đây dùng PyTorch FP32 làm mốc; phép đo này dùng FP32 ONNX. CSV truy vấn vẫn chưa có nhãn độc lập để tính Recall, MRR và độ đúng của mốc thời gian.
