# SNAPSHOT-02-F01 — chấp thuận bản dùng thử với catalog Jadoo

Review19/10/2026, baseline2f205a4. Phạm vi S1/S2 và bản sửa budget đã review; không nghiệm thu production.

## Code và tests

- StorageKeyConfig Drive path không còn Files.exists/fallback; normalize/containment thuần lexical. Các alias cinema-drive/cinema_drive giữ root server allowlist.
- getResourceForPath/getResourceLengthForPath/openChannelForPath gọi fallback và real containment bên trong executeMetadata. Channel open vẫn qua bounded executeOpen và reservation hiện có. S1 đã đóng đúng đường MediaStreamService sử dụng.
- Maven offline với H2 test/JDK25: DrivePathSecurityTest+MediaStreamingIntegrationTest30/30 PASS, gồm2 tests mới.
- Frontend83/83 tests PASS trên cached Node20.20.2. Budget script trên production build hiện tại141307/143360 bytes; dư2053. Build Node20 đã chạy độc lập ở review SNAPSHOT-02; frontend không thay đổi tiếp trong F01.
- Contract và budget script không đổi. Không chạy lại model/Drive/live DB trong review này.

## Bằng chứng web đúng tập

Đã đọc harness/raw JSON và xem ảnh live_jadoo_ep2_playing.png. Trang series hiển thị99 tập, player có hình Jadoo và phần đang chọn là tập2 “Muốn ăn nhưng lại sợ tăng cân”.

Evidence browser ghi asset_jadoo_s01_v0001,1920x1080,time0.36→1.87; seek60 settled60.14→61.66; sau click ep_jadoo_s01_0002 đổi asset_jadoo_s01_v0002 và time0.52→2.04. Cross-reference JSON/path/size hai asset có kết quả khớp. Đây là bằng chứng playback browser của tác giả, reviewer không tự chạy lại stack.

Giới hạn ghi đúng: harness login qua API và inject session localStorage, search bằng URL query rồi click card. Không gọi đây là test login form hoặc nhập query bằng keyboard. Seek đặt currentTime bằng DOM, không chứng minh control timeline UI. Những giới hạn này không chặn xác nhận chọn/phát đúng tập và playback sau seek ở mức dùng thử; không mở thêm vòng task.

## Chuẩn bị commit

Raw evidence có grant URL đầy đủ. Reviewer chỉ che query grant và bỏ token prefix; giữ IDs/path/timing/results. Harness được sửa serialization/log URL để các lần chạy sau không ghi credential. node --check đạt; không thay playback assertions hoặc application logic.

Dữ liệu catalog riêng, DB H2 đã nhập, index/runtime state, model/cache và .env.example ngoài scope không đưa lên Git. Giữ dữ liệu người dùng để dùng tiếp. Báo cáo teardown của tác giả ghi ports/mount đã dừng; reviewer không tác động services/mount.

Chấp thuận commit/push snapshot dùng thử theo yêu cầu. Các bài test tải/mạng/codec rộng và full UI auth không nằm trong acceptance lần này.
