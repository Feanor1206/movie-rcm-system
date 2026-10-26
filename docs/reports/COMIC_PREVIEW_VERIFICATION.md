# Chốt bản dùng thử giao diện truyện tranh

Ngày kiểm tra: 27/10/2026. Nhánh: `dev`. Mức phát hành: `usable_preview`.

## Các lỗi đã xử lý

- Trang tập phim có điều hướng chung; thẻ từ kho phim và CineBot dùng cùng bộ tạo deep link theo series, tập, tiểu phẩm, phân cảnh và asset.
- Tách thời gian file của phân cảnh khỏi thời gian logic của tập. Từ chối offset không hợp lệ, sai tập và thời điểm nằm ngoài coverage; hai interval liền nhau không còn cùng nhận một điểm biên.
- Chỉ dựng một popup đăng nhập để tránh hai focus trap và hai khóa cuộn hoạt động cùng lúc.
- Đồng bộ màu giấy, màu mực và xanh lá; giữ độ tương phản của thông báo trên nền video đen. CineBot hiển thị chữ nhấn mạnh thay vì dấu Markdown thô.
- Khi dịch vụ hội thoại tắt hoặc bận, gateway trả 503/429 rõ ràng và hướng người xem về Kho phim; không đưa hostname, cổng, lỗi nội bộ hay stack trace ra giao diện. Có giới hạn thời gian chờ hữu hạn và kiểm tra JSON/câu hỏi rỗng.
- Parser xử lý JSON sai kiểu, số vô hạn và số lượng phân số mà không crash hoặc tách chuỗi thể loại thành ký tự.
- Catalog bootstrap generation 0 được coi là sẵn sàng khi đã load. Snapshot giữ bản sao dữ liệu lồng nhau; catalog riêng của một request không ghi đè index dùng chung. Telemetry được tách theo thread/request; session mặc định không chia sẻ intent giữa khách.
- Đồng bộ catalog so sánh token theo constant-time, từ chối Bearer sai định dạng và token Unicode sai mà không gây lỗi 500.
- Launcher khôi phục môi trường cha dù spawn thất bại, truyền secret qua môi trường con, kiểm tra độ mới của `pom.xml`, và chạy dịch vụ nền ở chế độ cửa sổ ẩn.

## Kiểm tra

- Spring Boot với profile `test`, H2 riêng: **180/180 qua**. Máy kiểm tra dùng JDK 25; CI hiện cấu hình JDK 17, chưa có kết quả CI cho commit này tại thời điểm lập báo cáo.
- Frontend: **110/110 qua** trên Node 26 và Node 20.20.2; production build Node 20 qua, gồm kiểm tra TypeScript.
- JS budget: `/` 138.933 B; `/search` 140.123 B; `/movies/[id]` 142.119 B; `/profile` 140.551 B. Cả bốn dưới 143.360 gzip bytes, không tăng trần.
- Preview catalog: 3/3 ca dry-run qua.
- Launcher helper trên Windows PowerShell 5.1: qua; không khởi động lại toàn stack vì người dùng đang dùng Drive và dành GPU cho việc khác.
- Unit serving offline: **23/23 qua**, model generate/tokenizer được mock; không nạp trọng số 4B.
- Hồi quy parser/catalog mới: **16/16 qua** trên CPU.
- Ma trận publication/concurrency: **12/12 qua**, gồm rollback, generation conflict, snapshot reader isolation và restart recovery.
- Bộ hồi quy CPU mở rộng: **161/161 qua**, gồm 16 ca parser/catalog mới nêu trên. Dùng encoder E5 trên CPU với hai thread, không gọi model 4B; thời gian 455,70 giây. Không cộng 16 ca lần nữa vào tổng này.

## Video thật trên giao diện mới

`docs/reviews/evidence/COMIC_PREVIEW_GUEST_PLAYBACK.json` ghi nhận phiên browser không token, không đăng nhập: tìm Jadoo, phát đúng tập 1/2, giải mã 1920×1080, frame/time tăng, pause/resume và tua tới 60s, 300s, gần cuối. HEAD 200, Range 206, range ngoài file 416. Đây là lượt có cache phía browser/rclone đã ấm, không dùng số đo này làm benchmark khởi động lạnh.

Các lần tua trong bằng chứng này dùng `HTMLMediaElement.currentTime` trên video production. Lượt bấm native timeline trước đó được ghi riêng trong tài liệu `docs/designs/COMIC_LIVE_PLAYBACK.md`.

`docs/reviews/evidence/COMIC_PREVIEW_OFFLINE_CHAT.json` xác nhận dịch vụ hội thoại tắt trả 503 với thông báo ngắn gọn. Không chạy lại Qwen theo chỉ đạo người dùng.

## Giới hạn và dữ liệu riêng

- Chưa nghiệm thu toàn bộ suy luận Qwen/GPU. Phiên trước có ba ca tìm đúng và phát đúng tập nhưng tiến trình model sau đó dừng chưa xác định nguyên nhân; không ghi thành PASS toàn hệ thống.
- Chính sách public cho 99 video được lưu trong catalog cục bộ revision 3 và đã import vào database riêng đang phục vụ bản xem thử. Audio vẫn private. Nếu dùng database gốc cần import catalog revision 3 vào database đó; không đổi ACL của Google Drive.
- Catalog thật, database, trọng số, token, cache, log vận hành và cấu hình riêng không nằm trong commit. Các báo cáo/evidence cũ chưa liên quan và `.env.example` ngoài phạm vi được để nguyên.
- Frontend, backend riêng và Drive đang giữ chạy để người dùng xem thử; cổng model 8000 tắt. Không dừng job DAPU hoặc sửa trọng số/schema.

## Ghi nhận bổ sung

Các gate trong phạm vi trên đã hoàn tất. Không có lỗi test còn thất bại trong các bộ đã chạy. Đây là bản dùng thử; không suy diễn kết quả offline thành nghiệm thu Qwen/GPU hoặc toàn bộ hệ thống production.
