# SNAPSHOT-01-F01 — đóng hai lỗi launcher cho bản dùng thử

Review18/10/2026. Phạm vi giới hạn L1, L2 và background pipe hang; không mở thêm tiêu chí sản phẩm.

- L1: không còn dùng ProcessStartInfo.ArgumentList; arguments được quote qua helper tương thích Windows PowerShell5.1. Script có BOM; startup/stop evidence chạy đúng powershell.exe5.1.
- L2: state được lưu sau từng spawn; startup nằm trong try/catch, cleanup ngược và xác minh PID/executable/start time. Không stop theo tên. Thất bại cleanup giữ FAILED_NEEDS_CLEANUP.
- Background: mỗi service redirect stdout/stderr sang file, tách khỏi output pipe của harness. Evidence success của tác giả ghi exact command trả0 trong53.36s, services HTTP200, stop trả0 và các PID/ports/state đều giải phóng. Đã đọc log startup/stop tương ứng; không chạy lại toàn stack/model/live DB trong review.

## Test độc lập mới

Sau khi kiểm state không tồn tại và ports8000/8080/3000 trống, chạy:

`powershell.exe -NoProfile -File scripts/start_preview_stack.ps1 -Background -TestInjectFailureAfter FastApiSpawn`

Kết quả exit1 trong10.63s, startup catch cleanup hoạt động, state không còn, ba ports vẫn trống. Không mount. Evidence mới riêng: docs/reviews/evidence/SNAPSHOT_01_F01_REVIEWER.json; log ở temp path ghi trong JSON.

## Giới hạn được ghi nhận

Success-path runtime dựa evidence/log bàn giao; reviewer độc lập chạy failure-path. Không kiểm -MountDrive trong lượt này. JSON/harness tác giả hardcode kết quả testB thay vì tự chạy testB, nên không dùng trường passed đó làm chứng cứ độc lập; failure test mới ở trên mới là bằng chứng reviewer.

Chấp thuận đóng L1/L2 và pipe hang ở mức usable_preview. Không yêu cầu thêm framework hoặc vòng sửa rộng. Các sửa frontend budget đã review trước vẫn giữ nguyên phạm vi; không chạy lại suites không liên quan. Không commit/push hoặc sửa application trong review này.
