# F09 — chấp thuận lưu bản dùng thử

Review ngày17/10/2026, baseline d620bfc. Phạm vi: usable preview, không nghiệm thu production.

## Kết quả

- 42/42 entries manifest khớp lúc bắt đầu; contract5 files giống byte-for-byte ZIP gốc; reverse patch check exit0.
- Chạy nguyên function run() của reviewer repro F08 với code F09, lưu evidence mới riêng: retained_snapshot_mutated=false. Snapshot A giữ catalog/index/payload A sau publish B bằng setter thật. Không ghi đè repro/evidence F08.
- 5 ownership regressions PASS; matrix F08 chạy lại cùng suite pytest. Frontend83/83 tests PASS và TypeScript exit0.
- Source startup/recovery/default bootstrap dùng manager riêng; guard cô lập singleton nếu truyền nhầm. Sửa tối thiểu phù hợp lỗi đã tái hiện; không yêu cầu đổi kiến trúc thêm.
- Kế thừa evidence F08 cho login/import/search UI, initial video decode/Drive HTTP và backend restarts. Không chạy lại model/GPU/services/Drive trong review này. Không khẳng định đã chạy browser trên F09.

## Giới hạn chấp nhận cho bản dùng thử

- Drive3 seeks gồm gần cuối, post-seek decode và browser sau restart chưa có đầy đủ evidence. F08 có initial Drive playback/time advance và seek60s; local synthetic3 seeks là bằng chứng riêng, không chuyển thành Drive3 seeks.
- Negative security matrix mở rộng, tải lớn, nhiều codec, mạng đứt và rapid switching chưa kiểm đầy đủ. Không xem thiếu test là lỗi chức năng đã chứng minh.
- Gói này chưa tự chứa video/model/credentials/runtime DB/cache. Cần môi trường và dữ liệu đã cấu hình. Không deploy như bản production.

## Đính chính hướng dẫn bàn giao

Các lệnh trong báo cáo F09 có chỗ không khớp code; không dùng chúng nguyên xi:
- Remote đã dùng trong rehearsal là cinema-drive, không phải gdrive-anim. Folder ID phải truyền qua --drive-root-folder-id, không đặt như một path sau remote.
- Mount cần --read-only --vfs-cache-mode off, kiểm tra ổ trống/ownership và giới hạn RAM như toolkit hiện hành. Không tự mount đèX:.
- Tên artifact theo pom là target/moviercm-backend-0.0.1-SNAPSHOT.jar, không phải movie-rcm-backend.
- Token sync hai service phải cấu hình khớp ngoài Git; secret minh họa không dùng cho production.
- catalog.example.json là draft/private/hư cấu, chỉ dùng validation. Để search/play video hãy dùng catalog người dùng đã cấu hình media hoặc fixture rehearsal có đúng local/Drive mapping và đủ điều kiện publish.

Các sai sót tài liệu trên được ghi rõ tại đây, không sửa frozen report/manifest để làm mất dấu bàn giao. Runbook và rehearsal hiện có vẫn cần áp dụng đúng môi trường, không mặc định mọi lệnh báo cáo đều tái lập trên máy sạch.

## Quyết định

Lỗi ownership chặn F08 đã đóng bằng repro độc lập. Chấp thuận commit bản dùng thử kèm giới hạn trên; không mở thêm nhiệm vụ và không tuyên bố hoàn hảo/production-ready.

Commit chỉ gồm code/catalog tests/rehearsal/docs/evidence thuộc checkpoint. Loại backend/fastapi/.env.example ngoài scope, runtime data, DB, weights/cache, build outputs và các artifact đánh giá khác không liên quan. Không chạy agent CLI hoặc automation.
