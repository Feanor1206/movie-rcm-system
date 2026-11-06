# DATA-01 — Pilot catalog hoạt hình và pipeline validation thực

Chỉ giao sau CONTRACT-01 accepted. Áp dụng hướng dẫn chung; đọc contract accepted trước các gợi ý trong prompt này. Nếu contract khác, ghi mapping và tuân thủ contract, không tự đổi.

## Mục tiêu

Có catalog animation factual để UI, Spring Boot và FastAPI dùng chung ID/schema. Thay preprocessing đang xuất sáu phim giả bằng pipeline đọc dữ liệu input, normalize/validate và tạo snapshot có version. Không làm database migration hoặc đổi UI ở ticket này.

## Đọc và phạm vi

- `docs/contracts/ANIMATION_DISCOVERY_V1.md`, JSON Schemas và examples.
- `ai/datasets/preprocess_data.py`, current frontend catalog, SQL seeds, Movie/MovieResponse và DEFAULT_MOVIES trong qwen_service.
- Project Bible phần representation/taxonomy, UX blueprint.

Sửa/bổ sung trong `ai/datasets/`; nếu cần validator core không phụ thuộc framework có thể thêm package nhỏ tại `ai/core/` và tests liên quan. Tạo `docs/data/ANIMATION_CATALOG_V1.md` và `docs/reports/DATA-01_REPORT.md`. Không sửa model/tokenizer/adapters, backend business schema, frontend hoặc current serving loader.

## Công việc

1. Audit các IDs/data hiện có: factual animation / fiction demo / metadata thiếu. Không xóa hoặc đổi ID đang được account data tham chiếu; nêu migration mapping cho CAT-01.
2. Chọn và xác minh nguồn từ thông tin gốc, ghi URLs, ngày truy cập, access/key requirements và điều kiện sử dụng dữ liệu/media. Không nhận toàn bộ dataset bất kỳ là dùng được cho mọi mục đích.
3. Tạo pilot mục tiêu khoảng **20 phim thật** có identity/runtime/year/genres/summary phù hợp. Đây là pilot để kiểm tra pipeline, sau đó mở rộng 100–200 ở đợt data tiếp theo. Nếu không xác minh đủ, báo số thực và missing fields; không bịa để đủ số lượng.
4. Mỗi record có stable internal ID, external source IDs/provenance, aliases khi đã xác minh, numeric runtime và status. Trường thiếu nullable/unknown. Không biến title slug thành ID duy nhất dễ thay đổi hoặc tự merge hai phim cùng tên.
5. Summary tiếng Việt không spoil: bản tóm tắt tự viết từ factual metadata được đối chiếu và ghi review/provenance; không copy dài nguyên văn nguồn.
6. Tone/technique/audience/scariness optional. Nếu tự annotation, có rubric, annotation source và trạng thái human-review; chưa có review không coi như fact chắc chắn. Không gán age rating từ phỏng đoán.
7. Poster/backdrop/trailer optional và có source. Không dùng ảnh phong cảnh chung như poster thật hoặc fallback sang file `/videos/<id>.mp4` không tồn tại. Không tải/redistribute media chưa xác định quyền sử dụng.
8. ETL đọc input file qua CLI, validate rồi xuất normalized snapshot/manifest/validation report; không hard-code six sample catalog vào pipeline. Config IDs/taxonomy mapping rõ, output UTF-8, order/normalization deterministic.
9. Không overwrite input hoặc artifact đang phục vụ. Viết output version mới, báo invalid rows theo record/source; policy fail/quarantine và publish-only records được ghi rõ.

## Acceptance cases

- Source record hợp lệ → movie snapshot đúng contract.
- Missing runtime/facet/media giữ unknown/null; no fabricated defaults.
- Duplicate ID, title collision khác year/source, invalid runtime/year/genre/status đều báo được.
- Danh sách output cùng input/config tạo cùng normalized records/version content checksum; generated timestamp tách checksum nếu cần.
- Synthetic bad fixtures tách pilot factual catalog.
- Snapshot và manifest validate schemas accepted; mỗi factual pilot row có source identity trace.
- Không có user credentials/PII trong artifacts; không thay test-gold Phase23 hoặc adapter.

## Báo cáo

Ghi số input/valid/quarantined, missing coverage, actual pilot count, nguồn/giới hạn, identity mapping và lệnh rerun. Không coi 20 phim là đủ để nghiệm thu recommendation quality hoặc collaborative training.

Giao snapshot path/version cho CAT-01 import và AI-01 evaluation. Dừng để Codex kiểm tra data/ETL; không tự làm CAT-01.
