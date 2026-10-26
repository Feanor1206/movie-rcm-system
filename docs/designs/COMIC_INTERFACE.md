# Giao diện Dippie: một quyển truyện phim

Ngày kiểm tra: 26/10/2026. Trạng thái: bản xem thử giao diện, chưa commit/push.

## Thiết kế

- Nền giấy ngà `#f4f0e5`, giấy sáng `#fbf9f2`, mực `#18241e`, xanh lá dịu `#8dad86` và `#c9ddbd`.
- Trang bìa có minh họa SVG riêng, khung mực, chú thích tranh và mục lục ba chương. Không thêm thư viện hay font tải từ mạng.
- Kệ phim dùng dữ liệu từ backend, giữ trạng thái tải, trống và thử lại khi lỗi. Bìa vẫn hiện khi dữ liệu chưa sẵn sàng.
- Kho phim, thẻ phim, danh sách xem, đăng nhập, CineBot và trang tập phim dùng cùng nền giấy và màu mực. Video giữ nền đen và thông báo có độ tương phản phù hợp.
- Kết quả tìm kiếm hiển thị nhãn tiếng Việt; mã schema và ID nội bộ không còn xuất hiện trong các phần đã chỉnh.
- Trang tập phim có điều hướng chung. Popup đăng nhập chỉ được dựng tại provider toàn cục, tránh hai dialog và hai focus trap cùng hoạt động.

## Kiểm tra

- `npm test`: 104/104 qua.
- `npm run build`: qua, bao gồm kiểm tra kiểu TypeScript.
- `node scripts/compute_build_bytes.cjs`: cả bốn route qua trần 143.360 bytes. `/movies/[id]`: 142.029 gzip bytes; không tăng trần.
- Chrome trên bản production: ảnh trang bìa/kho phim ở 1440px và 375px, danh sách xem, trang Jadoo và CineBot. Không tràn ngang tại các kích thước đã kiểm tra.
- Tương tác thực: bấm kết quả tìm kiếm vào series Jadoo, chọn tập 2, mở/đóng đăng nhập trên mobile, mở/đóng menu, focus và Escape của CineBot; không có runtime exception trong hành trình này.
- Bằng chứng ảnh và JSON lưu ngoài Git tại `target/comic-preview/`.

## Phạm vi bản xem thử

Frontend phục vụ loopback tại `http://127.0.0.1:3000`, backend dùng bản sao H2 riêng ở cổng 8080. Database preview gốc không đổi theo SHA-256 trước/sau chuẩn bị môi trường.

Không chạy lại suy luận Qwen, mount Drive hay giải mã video trong lượt thiết kế này. Kết quả trên không thay thế nghiệm thu backend, tìm kiếm ngữ nghĩa hoặc phát video thật; các thay đổi backend có sẵn trong working tree vẫn cần đánh giá riêng.

Thông tin sở hữu tiến trình và log nằm trong thư mục tạm `dippie-luna-repair-0vpncu_d`, ngoài Git. Không dùng lệnh dừng theo tên tiến trình.
