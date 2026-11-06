# SNAPSHOT-01 — budget đạt, launcher cần sửa trước khi khuyến nghị

Review18/10/2026, baseline d538fa3. Chỉ kiểm ở mức usable_preview; không mở rộng nghiệm thu production.

## Đã xác minh độc lập

- Frontend83/83 tests PASS trên Node26 và cached Node20.20.2, không cài thêm runtime.
- Build production bằng Node20.20.2 thành công; script compute_build_bytes.cjs nguyên trạng PASS mọi route. /movies/[id]=143298 gzip bytes, ngưỡng143360, dư62 bytes. Lỗi budget trước đã sửa; dư ít là lưu ý, không tạo thêm gate.
- Thay đổi application chủ yếu cắt markup/CSS và đơn giản hóa media helper; tests hiện hành không phát hiện regression. Không yêu cầu chạy lại toàn bộ backend vì không đổi backend application trong checkpoint này.
- Evidence smoke bàn giao có initial Drive playback/time advance, import/sync/search. Reviewer chỉ đọc script/JSON, không chạy lại model/Drive hoặc launcher thật vì các lỗi dưới đây có thể gây side effect trước khi thất bại.

## L1 — P1: lệnh start được hướng dẫn không chạy trên Windows PowerShell5.1

Report/runbook hướng dẫn `powershell -File scripts/start_preview_stack.ps1 -MountDrive`. `powershell` trên máy là5.1.26100.9711. Script dùng `$faStartInfo.ArgumentList.Add($arg)` (và tương tự Spring/Next), trong khi ProcessStartInfo của runtime này không có ArgumentList.

Repro không spawn process hoặc mount:
`powershell -NoProfile -Command 'Set-StrictMode -Version Latest; $p=New-Object System.Diagnostics.ProcessStartInfo; $p.ArgumentList.Add("-m")'`

Kết quả: property ArgumentList cannot be found. Vì mount ở bước5 trước spawn ở bước6, lệnh -MountDrive còn có thể mount xong rồi mới lỗi. Smoke Python dùng subprocess.Popen riêng, không kiểm entry point PowerShell nên PASS của smoke không đóng lỗi launcher.

Sửa gọn: hỗ trợ quoting/Arguments đúng trên5.1, hoặc preflight/relaunch bằng pwsh7 đã có và hướng dẫn đúng executable; phải fail trước side effects nếu runtime không hỗ trợ. Không tự cài runtime mới.

## L2 — P1: lỗi startup giữa chừng không cleanup hoặc lưu ownership

start_preview_stack.ps1 chỉ ghi stateFile sau khi cả3 services ready; try/finally cleanup chỉ bao vòng giữ phiên cuối file. Nếu FastAPI đã spawn nhưng readiness fail, hoặc Spring/Next lỗi, script throw trước khi có state và trước finally. stop_preview_stack không biết các PID đã tạo; mount có thể bị bỏ lại.

Sửa gọn: ghi ownership tăng dần và bọc toàn bộ mount/start/readiness trong try/catch/finally; startup fail cleanup đúng process/mount mình vừa tạo, giữ record nếu cleanup chưa xong. Một test inject lỗi sau spawn đầu tiên đủ chứng minh nhánh này, không cần matrix lớn. Không kill theo tên.

## Hai cấu hình nhỏ nên sửa cùng launcher

- FastAPI env sao chép từ shell, chỉ đặt FASTAPI_SYNC_SECRET. Production main ưu tiên CATALOG_SYNC_TOKEN nếu có. Khi hai env khác nhau hoặc dùng -SyncSecret trong shell đã có CATALOG_SYNC_TOKEN, Spring và FastAPI nhận secret khác nhau. Đặt cả hai theo secret đã chọn cho child process, không print secret.
- NEXT_PUBLIC_* đã bake vào production build. Đặt lúc next start không tự đổi endpoint trong browser bundle; custom SpringPort/FastApiPort có thể hiện health OK nhưng web gọi cổng cũ. Build theo endpoint đã chọn hoặc từ chối cấu hình không khớp; kiểm BUILD_ID thay vì chỉ thư mục .next để quyết định next start.

## Giới hạn evidence, không mở thêm blocker sản phẩm

Smoke mới vẫn đặt currentTime rồi chỉ kiểm nó gần60/120; không đo time advance sau seek dù report mô tả đã đo. Initial playback advance có bằng chứng; post-seek continued playback chưa được chứng minh. Sửa mô tả hoặc bổ sung hai sample sau seek vào test có sẵn, không cần suite mới.

## Kết luận

Chấp nhận bản sửa JS budget. Chưa khuyến nghị lệnh khởi động một lần cho người dùng vì L1/L2 là lỗi vận hành cụ thể. Chỉ cần một lượt sửa launcher/config nhỏ và smoke gọi chính launcher, không cần quay lại kiến trúc catalog/Drive/ownership.

Không sửa application trong review, không chạy CLI agent/automation, không commit/push. Build outputs thay đổi là kết quả test; các thay đổi ngoài scope được giữ nguyên.
