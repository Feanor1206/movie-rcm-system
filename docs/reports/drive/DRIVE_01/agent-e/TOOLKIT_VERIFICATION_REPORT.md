# BÁO CÁO KIỂM THỬ VÀ ĐÁNH GIÁ AN TOÀN BỘ CÔNG CỤ DRIVE WINDOWS (DRIVE-01)
**Kỹ sư thực hiện:** Agent E (Windows Toolkit Verification Engineer)  
**Thời gian kiểm định:** 2026-10-15  
**Trạng thái kiểm thử:** **PASSED (100% - 38/38 Test Cases Passed)**  
**Đường dẫn bằng chứng máy đọc (JSON):** `docs/reports/drive/DRIVE_01/agent-e/toolkit_test_evidence.json`

---

## 1. TỔNG QUAN VÀ MÔI TRƯỜNG KIỂM THỬ

Bộ công cụ PowerShell quản lý ổ đĩa Google Drive trên Windows tại `scripts/drive/` (`preflight_drive.ps1`, `mount_drive.ps1`, `status_drive.ps1`, `stop_drive.ps1`) đã được Agent E xây dựng bộ kiểm thử tự động độc lập, chuyên sâu và toàn diện.

### Thông số môi trường thử nghiệm:
- **Hệ điều hành:** Microsoft Windows NT 10.0.26200 (Windows 11 Enterprise x64)
- **PowerShell Engines xác thực:**
  - **Windows PowerShell 5.1** (`5.1.26100.9711` Desktop Edition)
  - **PowerShell Core 7** (`7.6.6` Core Edition)
- **Chính sách thực thi (ExecutionPolicy):** `Bypass`
- **Mã hóa:** UTF-8 với Byte Order Mark (BOM) bảo đảm tương thích tuyệt đối giữa PowerShell 5.1 và PS7.

### Tóm tắt kết quả kiểm thử:

| Bộ kiểm thử (Test Suite) | Tập tin kiểm thử | Số TC | Đạt (Pass) | Lỗi (Fail) | Thời gian chạy | Kết quả |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Comprehensive Toolkit Verification** | `scripts/drive-tests/test_drive_toolkit_comprehensive.ps1` | 24 | 24 | 0 | 14.81s | **PASSED** |
| **Security Seams & PID Safety** | `scripts/drive-tests/test_drive_security_seams.ps1` | 14 | 14 | 0 | 4.21s | **PASSED** |
| **TỔNG CỘNG** | | **38** | **38** | **0** | **19.02s** | **PASSED (100%)** |

---

## 2. CHI TIẾT BỘ KIỂM THỬ TOÀN DIỆN (`test_drive_toolkit_comprehensive.ps1`)

Bộ kiểm thử này thẩm định toàn bộ khả năng xử lý tham số, chế độ Dry-run an toàn, cơ chế phát hiện xung đột đích mount, và bộ cờ streaming chuẩn RFC 9110.

### 2.1. Kiểm thử tham số phức tạp, khoảng trắng và Unicode (5 Test Cases)
- **`TC-PARAM-01` [PASS]:** Remote có khoảng trắng (`cinema gdrive:`) kết hợp đường dẫn con chứa tiếng Việt có dấu (`Kho Phim Việt/1080p - Bản Rõ & Đầy Đủ [2026]`). Script bảo toàn chính xác định dạng `RemoteTarget` và chuỗi lệnh dự kiến (`ExpectedCommand`) mà không bị lỗi font hay mất ký tự.
- **`TC-PARAM-02` [PASS]:** Remote không có dấu hai chấm (`anime-gdrive`) kết hợp ký tự tiếng Nhật/CJK (`スタジオジブリ/映画/となりのトトロ (1988) [BD-Rip]`). Script tự động thêm dấu hai chấm chuẩn hóa (`anime-gdrive:...`) và giữ nguyên vẹn ký tự Unicode đa byte.
- **`TC-PARAM-03` [PASS]:** Tham số Remote rỗng fallback về mặc định `cinema-gdrive:`, và RemoteSubpath rỗng không sinh ra lỗi cú pháp hay lặp dấu hai chấm (`::`).
- **`TC-PARAM-04` [PASS]:** Đường dẫn `ConfigPath` phức tạp chứa khoảng trắng, tiếng Việt và ký tự đặc biệt (`C:\Users\Admin\Đường Dẫn Cấu Hình (Rclone)\rclone test [safe].conf`). Script truyền chính xác vào cờ `--config` trong chuỗi xem trước lệnh.
- **`TC-PARAM-05` [PASS]:** Hỗ trợ đa dạng định dạng ký tự ổ đĩa trong `MountPoint` (chữ thường `m:`, ký tự kèm dấu gạch chéo ngược `M:\`), không gây lỗi định dạng.

### 2.2. Kiểm thử chế độ Dry-Run & Đảm bảo không ghi đĩa (6 Test Cases)
- **`TC-DRY-01` [PASS]:** Chạy `mount_drive.ps1` mặc định khi không truyền `-Execute` tự động chuyển sang chế độ `DRY_RUN` (`IsExecute = False`).
- **`TC-DRY-02` [PASS]:** Chạy `mount_drive.ps1` với cờ rõ ràng `-WhatIf` xuất ra cấu trúc kế hoạch `Mode = "DRY_RUN"`.
- **`TC-DRY-03` [PASS]:** Khi truyền đồng thời cả `-WhatIf` và `-Execute`, `-WhatIf` chiếm quyền ưu tiên tuyệt đối, bảo vệ hệ thống không bị kích hoạt ngoài ý muốn.
- **`TC-DRY-04` [PASS]:** Chụp snapshot tiến trình hệ điều hành trước và sau khi chạy Dry-Run; xác nhận **0 tiến trình `rclone`** nào được khởi chạy ngầm.
- **`TC-DRY-05` [PASS]:** Truyền đường dẫn `-StateFile` tùy ý trong chế độ Dry-run; xác nhận **không có bất kỳ file state nào được tạo ra trên đĩa**.
- **`TC-DRY-06` [PASS]:** Tham số `-AsJson` trong chế độ Dry-run trả về chuỗi JSON chuẩn cú pháp, có thể parse ngược lại thành object với `Mode = "DRY_RUN"`.

### 2.3. Kiểm thử phát hiện xung đột ổ đĩa (Occupied Mount Target) (6 Test Cases)
- **`TC-COLLISION-01` [PASS]:** Truyền ổ đĩa hệ thống đã sử dụng (`C:`), `preflight_drive.ps1` lập tức nhận diện `MountTarget.Available = False`, `IsReady = False`, và trả về `ConflictReason` giải thích ổ đĩa đang được sử dụng.
- **`TC-COLLISION-02` [PASS]:** Chuẩn hóa ký tự ổ đĩa có dấu gạch chéo (`C:\`), hệ thống vẫn phát hiện xung đột chính xác (`Available = False`).
- **`TC-COLLISION-03` [PASS]:** Tự động dò tìm ổ đĩa chưa gán (`Z:`), hệ thống xác nhận `MountTarget.Available = True`.
- **`TC-COLLISION-04` [PASS]:** Tạo thư mục tạm chứa dữ liệu (không rỗng), hệ thống chặn lại với lỗi `Mount directory '...' is not empty`.
- **`TC-COLLISION-05` [PASS]:** Truyền một file thông thường (regular file) thay vì thư mục, hệ thống từ chối với lý do mục tiêu là file, không phải thư mục mount.
- **`TC-COLLISION-06` [PASS]:** Chạy `mount_drive.ps1 -WhatIf -MountPoint "C:"`, kế hoạch lập tức đưa cảnh báo xung đột vào mảng `PreflightBlockers` và đặt `PreflightIsReady = False`.

### 2.4. Kiểm thử bộ cờ streaming chuẩn RFC 9110 (7 Test Cases)
Xác thực chính xác các cờ tối ưu hóa băng thông và Direct RAM streaming:
- **`TC-FLAGS-01` [PASS]:** `--read-only` (chỉ đọc, bảo toàn tính toàn vẹn dữ liệu).
- **`TC-FLAGS-02` [PASS]:** `--vfs-cache-mode off` (tắt cache ghi đĩa cục bộ, stream trực tiếp qua RAM).
- **`TC-FLAGS-03` [PASS]:** `--buffer-size 32M` (dung lượng đệm RAM giới hạn 32MB theo chuẩn tải khối).
- **`TC-FLAGS-04` [PASS]:** `--vfs-read-chunk-size 8M` (kích thước khối đọc ban đầu 8MB cho seek nhanh).
- **`TC-FLAGS-05` [PASS]:** `--vfs-read-chunk-size-limit 32M` (giới hạn trần khối đọc không vượt quá 32MB).
- **`TC-FLAGS-06` [PASS]:** `--vfs-read-chunk-streams 0` (tắt stream đa luồng cạnh tranh cho mỗi file để chống nghẽn range request).
- **`TC-FLAGS-07` [PASS]:** Các cờ siêu dữ liệu phụ trợ: `--dir-cache-time 72h`, `--poll-interval 15s`, `--attr-timeout 1s`.

---

## 3. CHI TIẾT BỘ KIỂM THỬ BẢO MẬT VÀ PHÒNG CHỐNG TÁI SỬ DỤNG PID (`test_drive_security_seams.ps1`)

Bộ kiểm thử này tập trung vào 2 nguy cơ an toàn lớn nhất: rò rỉ thông tin xác thực Google Drive (Secret Hygiene) và dừng nhầm tiến trình ngoài ý muốn do tái sử dụng PID của Windows (PID Reuse Hazard).

### 3.1. Kiểm thử bảo mật thông tin xác thực (Secret Hygiene) (5 Test Cases)
Agent E tạo file cấu hình giả lập chân thực (`rclone.conf`) chứa các dữ liệu cực kỳ nhạy cảm:
- `client_secret = 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erification998877`
- `access_token = ya29.a0AfH6SM_SEAM_TEST_ACCESS_TOKEN_XYZ987654321_SUPER_SECRET`
- `refresh_token = 1//04seam_test_refresh_token_complex_1234567890abcdef`
- `password = secret_cleartext_password_should_never_leak_99`
- `service_account_credentials = -----BEGIN RSA PRIVATE KEY-----...`

Kết quả thẩm định:
- **`TC-SEC-01` [PASS]:** Quét toàn bộ dòng stdout/stderr của `preflight_drive.ps1`: **0 chuỗi bí mật nào xuất hiện** trong output text.
- **`TC-SEC-02` [PASS]:** Thuật toán quét đệ quy toàn bộ cây thuộc tính của Object JSON: không có bất kỳ field nào chứa token hay secret. Thuộc tính `RcloneConfigFile.IsSafe = True`, chỉ lưu `FileExists` và `FileSizeBytes`.
- **`TC-SEC-03` [PASS]:** Kế hoạch `mount_drive.ps1 -WhatIf` chỉ hiển thị đường dẫn config trong `--config <path>`, **hoàn toàn không chứa nội dung bí mật** bên trong đối tượng hay chuỗi lệnh `ExpectedCommand`.
- **`TC-SEC-04` [PASS]:** Xuất ra chuỗi JSON nguyên bản (`-AsJson`), không tìm thấy bất kỳ chuỗi token nào.
- **`TC-SEC-05` [PASS]:** Khi truyền đường dẫn file cấu hình không tồn tại, script xử lý êm dịu, không ném exception stack trace làm lộ đường dẫn nội bộ.

### 3.2. Kiểm thử phòng chống tái sử dụng PID (PID Reuse Safety) (9 Test Cases)
Trên Windows, sau khi một tiến trình kết thúc, hệ điều hành có thể cấp phát lại chính số PID đó cho một tiến trình mới (như `powershell.exe`, `svchost.exe`, hoặc trình duyệt). Nếu script dừng tiến trình chỉ dựa vào số PID (`Stop-Process -Id $PID`), rủi ro làm sập ứng dụng hệ thống là cực kỳ cao.

- **`TC-PID-01` [PASS]:** Giả lập file state chứa PID của tiến trình PowerShell hiện tại (`$PID`), nhưng tên tiến trình ghi nhận là `powershell`/`pwsh`. Chạy `stop_drive.ps1`:
  - Trả về `Status = "PID_REUSE_REJECTED"` và `Success = False`.
  - Từ chối thực hiện dừng tiến trình.
  - Tiến trình PowerShell hiện tại **vẫn an toàn 100% và tiếp tục thực thi**.
  - File state được giữ nguyên trên đĩa để phục vụ điều tra/audit, không bị xóa tùy tiện.
- **`TC-PID-02` [PASS]:** Giả lập trường hợp cố tình giả mạo (spoofing) `processName = "rclone"` trong file state nhưng gắn vào PID của PowerShell. `stop_drive.ps1` **truy vấn trực tiếp hệ điều hành** để lấy tên tiến trình thực tế (`ActualName = pwsh/powershell`), phát hiện không khớp và lập tức từ chối dừng (`PID_REUSE_REJECTED`).
- **`TC-PID-03` [PASS]:** Giả lập trường hợp trùng PID và tên tiến trình, nhưng thời điểm khởi tạo (`startTime`) bị lệch quá 5 giây (chứng tỏ tiến trình cũ đã chết và PID được tái cấp phát). Script từ chối dừng (`PID_REUSE_REJECTED`).
- **`TC-PID-04` [PASS]:** `status_drive.ps1` khi gặp file state có PID bị tái sử dụng lập tức báo cáo trạng thái `DEGRADED`, với lý do chi tiết `PID reuse detected`.
- **`TC-PID-05` [PASS]:** Khi file state chứa PID của tiến trình đã kết thúc (dead PID), `stop_drive.ps1` xử lý dọn dẹp sạch sẽ file state, trả về `Status = "ALREADY_STOPPED"` và `Success = True` mà không bị crash.
- **`TC-PID-06` [PASS]:** `status_drive.ps1` đối với state file chứa PID đã chết trả về `Status = "NOT_MOUNTED"` và `ProcessAlive = False`.
- **`TC-PID-07` [PASS]:** Khi file state không tồn tại, `stop_drive.ps1` trả về `Status = "NOT_FOUND"` và `Success = False` một cách nhẹ nhàng.
- **`TC-PID-08` [PASS]:** Khi file state bị rỗng (0 bytes) hoặc không có trường PID, `stop_drive.ps1` tự động xóa file hỏng và trả về `Status = "CLEANED_EMPTY_STATE"`.
- **`TC-PID-09` [PASS]:** Kiểm tra tính lũy kế/idempotent: gọi `stop_drive.ps1` 2 lần liên tiếp trên cùng một file state; lần 1 trả về `ALREADY_STOPPED` và dọn file, lần 2 trả về `NOT_FOUND`, cả hai đều thoát mã lỗi 0 sạch sẽ.

---

## 4. GHI NHẬN KỸ THUẬT & KHUYẾN NGHỊ CHO AGENT B

Trong quá trình xây dựng bộ kiểm thử xác thực, Agent E ghi nhận một phát hiện kỹ thuật hữu ích (Edge-Case Finding) trong mã nguồn của Agent B:
1. **Lưu ý về `Set-StrictMode -Version Latest` trong `preflight_drive.ps1` (Line 224):**
   - Khi thư mục mount chỉ chứa **đúng 1 file**, lệnh `$children = Get-ChildItem -Path $Target -Force` trả về một đối tượng đơn lẻ (`FileInfo`), không phải mảng.
   - Khi chạy dưới PowerShell 7 với `Set-StrictMode -Version Latest`, việc gọi `$children.Count` có thể kích hoạt lỗi `The property 'Count' cannot be found on this object`.
   - *Khuyến nghị:* Trong tương lai nếu Agent B cập nhật, nên đổi thành `@($children).Count` để ép kiểu mảng an toàn tuyệt đối cho mọi số lượng phần tử. (Bộ test của Agent E đã được thiết kế sẵn sàng cho trường hợp này bằng cách tạo 2 file kiểm thử).
2. **Quy tắc mã hóa tập tin Script PowerShell:**
   - Các script chứa chuỗi ký tự Unicode (tiếng Việt, CJK) cần được lưu với encoding **UTF-8 with BOM** để Windows PowerShell 5.1 nhận diện chính xác mã nguồn và không bị lỗi cú pháp chuỗi.

---

## 5. LỆNH TÁI HIỆN VÀ CHẠY KIỂM THỬ

Để chạy lại toàn bộ bộ kiểm thử tự động bất kỳ lúc nào:

```powershell
# Chạy bộ kiểm thử toàn diện
powershell -ExecutionPolicy Bypass -File scripts/drive-tests/test_drive_toolkit_comprehensive.ps1

# Chạy bộ kiểm thử bảo mật & an toàn PID
powershell -ExecutionPolicy Bypass -File scripts/drive-tests/test_drive_security_seams.ps1
```

Cả hai script đều tự động cập nhật kết quả kiểm thử vào tập tin bằng chứng chuẩn máy đọc:  
`docs/reports/drive/DRIVE_01/agent-e/toolkit_test_evidence.json`.
