# Kiểm tra bản dùng thử hiện tại — 18/10/2026

Commit: d538fa33d54f3f319d4651b573e016ef12ea3c19, branch dev. Không sửa application, không commit/push trong lượt test này.

## Kết quả mới

- Spring: mvnw.cmd -o test -Dspring.profiles.active=test —178 tests,0 failures/errors/skipped, BUILD SUCCESS. H2 test, JDK25.0.3 cài sẵn; chưa xác nhận lại Linux/JDK17. Ban đầu shell thiếu JAVA_HOME; chỉ đặt cho process test, không đổi cấu hình OS.
- Ownership5 tests + matrix12 scenarios: pytest6 test functions PASS. Một warning test_matrix trả dict thay vì None, không phải assertion failure.
- Frontend npm test:83 PASS.
- npm run build: thành công, gồm TypeScript/build checks.
- Baseline catalog preview3 cases PASS; fixture contract validation VALID, không chứng minh media/factual truth.
- **Route JS budget FAIL:** /movies/[id]144261 gzip bytes >143360, vượt901 bytes (140.88KiB >140KiB). Đây là phép đo local bằng script CI trên build vừa tạo, chưa khẳng định số byte Linux/Node20 giống hệt.

## HTTP smoke thực

Entry: docs/reviews/repro/SNAPSHOT_F09_HTTP_SMOKE.py.
Evidence: docs/reviews/evidence/SNAPSHOT_F09_CURRENT_HTTP.json.

Production Spring dùng target/classes vừa compile bằng Maven test và cached dependencies; Next dùng production build vừa tạo. Ports8080/3008 kiểm tra trống trước spawn. DB H2, media copy và snapshot path trong temp directory riêng.

PASS: Spring startup, login admin HTTP, validate/import, search exact ser_rehearsal_01, public Range206/1024 bytes, anonymous protected deny, protected grant Range206/1024 bytes, Next production pages /admin/import,/search,/series/ser_rehearsal_01 trả200.

Đây là HTTP smoke, không browser UI/decoder. Worker sync token trống và destination riêng không có receiver; không tính outbox READY PASS. FastAPI sync/model, Drive và browser decode/seek NOT_RUN trong lượt này. Không dùng fixture local thay cho bằng chứng Drive.

Owned processes đã dừng; logs/DB test giữ ở temp path trong JSON. Không mount, không đọc token/config Drive, không đụng live DB hoặc services người dùng.

## Việc tiếp theo có giới hạn

1. Sửa JS budget route /movies/[id], giữ ngưỡng143360 và behavior; kiểm Node20 theo CI.
2. Làm hướng dẫn/entry point khởi động bản dùng thử đúng remote cinema-drive, root-folder-id, jar moviercm-backend, JAVA_HOME local và secret đồng bộ ngoài Git. Không dùng draft/private contract example như dữ liệu tìm/phát thật.
3. Một smoke gọn cho startup/import/sync/search/playback trên môi trường riêng, ghi rõ mode model và gate chưa chạy. Không mở lại matrix nghiệm thu production hoặc thêm tính năng.

Giữ F09 làm mốc dùng thử; lỗi JS budget là blocker kiểm tra build hiện tại, không bằng chứng toàn bộ ứng dụng không dùng được.
