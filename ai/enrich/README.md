# Xử lý dữ liệu thử nghiệm

Chạy các lệnh từ thư mục gốc. Nhóm thử nghiệm gồm tối đa năm tập loại `regular`, dài ít nhất 10 phút theo danh mục. Bộ chọn tự động ưu tiên tập dài 10–40 phút ở các mùa khác nhau; chọn thủ công có thể dùng tập dài hơn.

Bước kiểm kê đối chiếu ID và số byte trên Drive trước khi lấy video, sau đó dùng FFprobe đo thời lượng. Kết quả cũng ghi tài nguyên còn thiếu và các tập không đạt điều kiện.

## Chuẩn bị

Dùng môi trường Python riêng với `ai/enrich/requirements.txt`. Cài FFmpeg, FFprobe và rclone nếu đọc từ Drive.

Nhận dạng lời thoại trên Windows cần CUDA và cuDNN tương thích CTranslate2. Trình chạy có thể tìm DLL trong bản Torch hỗ trợ CUDA trên máy. Tải mô hình CTranslate2 Whisper turbo vào `ai/artifacts/models/whisper-turbo` trước khi chạy. ASR dùng GPU 0, `int8_float16`, VAD tiếng Việt và từ gợi ý trong danh mục.

## Chạy các bước

```powershell
python -m ai.enrich.inventory --rclone-root 'gdrive:VideoDieppie' --stage
python -m ai.enrich.asr
python -m ai.enrich.keyframes
python -m ai.enrich.scenes
python -m ai.enrich.caption --dry-run
python -m ai.enrich.summarize --dry-run
python -m ai.enrich.export --dialogue-only
```

Dùng `--media-root` thay `--rclone-root` khi video nằm trong thư mục hoặc ổ đĩa đã gắn. Lặp `--pilot-episode` năm lần để chọn cố định năm tập.

Video được lưu tại `ai/artifacts/media-mirror/<episode-id>/media.mp4`. Tệp sẵn có được kiểm tra kích thước và thời lượng. Nguồn cùng ổ đĩa được tạo hard link; khác ổ được sao chép một lần. Giữ tệp gốc để tái sử dụng khung hình cũ sau khi tạo hard link.

Tệp tải mới được tiếp tục theo từng phần và đối chiếu MD5 trên Drive. Chọn cấu hình rclone bằng `--rclone-config <path>` hoặc `RCLONE_CONFIG`; đặt client ID và secret Drive của bạn trong cấu hình đó. Khi gặp giới hạn dung lượng hoặc tần suất, bước tải dừng, giữ phần đã hoàn thành và báo lỗi gốc. Lỗi kết nối tạm thời được thử lại tối đa hai lần.

Để tiếp tục nhóm năm tập hiện tại, giữ nguyên các ID. Thêm `--rclone-config` nếu remote nằm trong tệp cấu hình khác:

```powershell
python -m ai.enrich.inventory --rclone-root 'gdrive:VideoDieppie' --stage --pilot-episode ep_jadoo_s01_0022 --pilot-episode ep_jadoo_s04_0021 --pilot-episode ep_jadoo_s04_0011 --pilot-episode ep_jadoo_s03_0008 --pilot-episode ep_jadoo_s01_0007
```

ASR và xử lý ảnh lưu kết quả riêng từng tập, tái sử dụng khi đầu vào khớp. Trích khung hình và nhóm cảnh chạy trên CPU. Khung hình ghi định danh video và mốc thời gian; nhóm cảnh đọc các đoạn ASR và mã băm khung hình.

`asr_run.json` ghi đỉnh bộ nhớ GPU lấy mẫu trong cả bước. Tệp `asr.json` mới ghi thêm số đo từng tập; tệp cũ được giữ nguyên. Trên Windows, số đo gồm bộ nhớ thiết bị mà các tiến trình khác đang dùng.

## Mô tả ảnh và tóm tắt

`--dry-run` chỉ lưu kế hoạch yêu cầu và số ảnh trên máy. Đặt `TEACHER_BASE_URL`, `TEACHER_API_KEY` và `TEACHER_MODEL` để dùng dịch vụ tương thích OpenAI. Khi được phép gọi dịch vụ, chạy với `--execute --max-requests N --run-id NAME`. Hai bước dùng chung giới hạn yêu cầu đã lưu nếu cùng mã lần chạy và thư mục kết quả. Bước tóm tắt cần mô tả ảnh hoàn chỉnh.

Lần thử DeepSeek dùng S01E22 và S04E21, tối đa 40 yêu cầu gồm cả lần thử ảnh. Nhập thông tin kết nối cục bộ qua `scripts/configure_llm.ps1`. Lệnh mặc định chỉ lập kế hoạch; `--execute` gửi một khung hình nhỏ tới dịch vụ.

Nếu dịch vụ từ chối ảnh rõ ràng, quy trình dùng llama-server cục bộ để mô tả ảnh và DeepSeek để tóm tắt văn bản. Đặt `LOCAL_VISION_BASE_URL` thành URL `/v1` trên máy và `LOCAL_VISION_MODEL` thành tên mô hình trước khi tiếp tục. Kết quả thử ảnh chưa rõ sẽ dừng lần chạy và giữ trạng thái để kiểm tra.

```powershell
python -m ai.enrich.deepseek_offline
python -m ai.enrich.deepseek_offline --execute
python -m ai.enrich.teacher_audit --episode ep_jadoo_s01_0022 --episode ep_jadoo_s04_0021 --run-id pilot-two-episodes --output ai/artifacts/pilot-teacher-audit.json
```

Bản xuất mặc định cần mô tả ảnh và tóm tắt cho đủ năm tập. `--dialogue-only` xuất lời thoại ASR kèm nguồn dữ liệu, giữ nguyên cảnh và tóm tắt gốc.

## Duyệt và nhập danh mục

`publish_preview` tạo bản nháp và tệp duyệt. Dùng `--dialogue-only` để duyệt ASR trước khi có mô tả ảnh; lặp `--episode` để giới hạn tập:

```powershell
python -m ai.enrich.publish_preview --dialogue-only --episode ep_jadoo_s01_0022 --episode ep_jadoo_s04_0021 --output ai/artifacts/dialogue-review-draft.json --review-template ai/artifacts/dialogue-review.json
```

Đối chiếu từng bản ghi với nguồn, nhập tên người duyệt và chỉ đặt `approved` thành `true` cho bản ghi đạt yêu cầu. Giữ nguyên mã băm đã sinh. Lệnh xuất kiểm tra đủ bản ghi đã duyệt, nguồn dữ liệu và tính hợp lệ của gói; gói giữ nguồn mô hình cùng thông tin người duyệt.

Bỏ `--dialogue-only` ở cả hai lệnh để đưa mô tả ảnh, cảnh và tóm tắt vào gói khi đã có. Lưu bản đã duyệt tại `ai/artifacts/pilot-published.json` để hội thoại qua dịch vụ LLM dùng bằng chứng đã công bố độc lập với cơ sở dữ liệu Spring.

```powershell
python -m ai.enrich.publish_preview --dialogue-only --episode ep_jadoo_s01_0022 --episode ep_jadoo_s04_0021 --output ai/artifacts/dialogue-ready.json --review ai/artifacts/dialogue-review.json
.\scripts\import_preview_catalog.ps1 -CatalogPath ai/artifacts/dialogue-ready.json -ApiBaseUrl http://127.0.0.1:18081/api -PreviewStateFile ai/artifacts/preview-stack.json
```

Khởi động bản chạy thử riêng với `-SpringPort 18081`, `-StateFile ai/artifacts/preview-stack.json` và `-DataDirectory` riêng trong `ai/artifacts/`. Script nhập kiểm tra đúng tiến trình Spring và cổng cục bộ trước khi đăng nhập và trước khi nhập.

Nếu Spring trả `CACHE_REQUIRED`, chạy lệnh tạo bộ nhớ đệm với bộ mã hóa đã chọn cho bản thử, rồi thử lại bản danh mục từ trang quản trị. Lệnh so sánh có thể đưa bản nháp vào bộ nhớ để chẩn đoán ngoại tuyến.

Xem [chuẩn bị bộ mã hóa](../EMBEDDING_CACHE.md) và [đánh giá tìm kiếm](../evaluation/README.md).
