# Kiểm tra video Drive trên giao diện truyện tranh

Ngày: 26/10/2026. Phạm vi: bản dùng thử tại `http://127.0.0.1:3000`.

## Quyền xem

Theo yêu cầu, 99 video Jadoo được đổi từ `private` sang `public`. 99 asset audio riêng vẫn giữ `private`. Đây là quyền xem tại ứng dụng; không đổi quyền chia sẻ Google Drive.

Catalog cục bộ `data/catalog.jadoo_all.json` được cập nhật package revision 3; các record video tăng revision từ 2 lên 3. Schema, đường dẫn, metadata và trọng số model không thay đổi. Bản gốc được sao lưu tại `target/comic-live/catalog-before-public.json`.

Đã validate bằng contract Python và endpoint quản trị, không có xung đột, rồi import qua API vào database riêng của phiên xem thử đang chạy. Database gốc `backend/springboot/data/moviercm_db.mv.db` chưa thay đổi. Nếu chuyển về database đó, cần import catalog revision 3 để áp dụng cùng quyền xem.

## Bằng chứng khách chưa đăng nhập

`target/comic-live/guest-public-evidence.json`: `GUEST_PUBLIC_PLAYBACK_PASS`.

- Xóa toàn bộ storage của browser test; xác nhận không có token đăng nhập.
- Tìm Jadoo trên web, chọn tập 1; giải mã 1920×1080 và frame/time tăng.
- Pause/resume qua; tua tại 60s, 300s và gần cuối 2012s, tiếp tục giải mã sau mỗi lần tua.
- Chuyển tập 2, xác nhận asset `asset_jadoo_s01_v0002`, frame/time tăng ở 1920×1080.
- Không gửi Authorization hoặc grant: HEAD 200, Range 206 với 1024 bytes đúng, range ngoài file 416.
- Audio private vẫn trả 404 cho khách; không bỏ kiểm soát quyền toàn cục.

Ba lần tua dùng `HTMLMediaElement.currentTime` trên player thật. Một lượt kiểm tra trước khi đổi public cũng đã bấm timeline native bằng pointer và xác nhận phát tiếp; bằng chứng `target/comic-live/native-seek.json`.

## Drive và Qwen

Drive gắn `X:` chỉ đọc, đúng folder VideoDieppie, `vfs-cache-mode off`, buffer 32 MiB và chunk 8–32 MiB. Kích thước file tập 1, 2 khớp catalog; không ghi/upload hoặc đổi quyền trên Drive. Thư mục cache được đo không chứa file media.

Trước khi người dùng yêu cầu hoãn Qwen, ba ca CineBot qua HTTP và UI đã trả đúng tập và phát đúng asset: Mùa 1 Tập 2, tình tiết sợ tăng cân, Mùa 3 Tập 1. Thời gian tương ứng khoảng 21,5 / 31,7 / 23,0 giây, không phải benchmark p95.

Tiến trình Qwen test dừng sau ba ca, chưa xác định nguyên nhân. Ca ngoài catalog nhận lỗi kết nối 500. Không coi lượt Qwen là nghiệm thu đầy đủ. Sau chỉ đạo của người dùng, không khởi động/gọi Qwen thêm. Job DAPU bên ngoài không bị dừng hay sửa đổi.

Frontend, backend riêng và Drive đang giữ chạy cho xem thử; Qwen tắt. Danh tính tiến trình và bằng chứng lưu tại `target/comic-live/ownership.json`; không dừng tiến trình theo tên.
