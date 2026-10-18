# BÁO CÁO NHIỆM VỤ: SNAPSHOT-01-F01 — SỬA GỌN 2 LỖI LAUNCHER

- **Mã Checkpoint**: `SNAPSHOT-01-F01-CHECKPOINT-01`
- **Thời gian**: 18/10/2026
- **Workspace**: `D:\Class\movie-rcm-system`
- **Branch**: `dev`
- **Baseline Git Commit**: `d538fa33d54f3f319d4651b573e016ef12ea3c19`
- **Cấp độ phát hành (Release Level)**: `usable_preview` *(Bản dùng thử — không tự nhận production-ready)*
- **Tài liệu tham chiếu đánh giá**: `docs/reviews/SNAPSHOT_01_REVIEW.md`
- **Bằng chứng thực thi (Evidence)**: `docs/reviews/evidence/SNAPSHOT_01_F01_LAUNCHER.json`

---

## 1. TỔNG QUAN VÀ NGUYÊN NHÂN GỐC

Trong đợt nghiệm thu `SNAPSHOT_01_REVIEW.md`, hai lỗi trọng yếu liên quan đến launcher đã được ghi nhận:
1. **Lỗi L1 (Tương thích Windows PowerShell 5.1)**: Lệnh hướng dẫn người dùng `powershell -File scripts/start_preview_stack.ps1` gặp ngoại lệ do thuộc tính `ProcessStartInfo.ArgumentList` chỉ có từ .NET Core, không tồn tại trên .NET Framework 4.8 / Windows PowerShell 5.1 (mặc định trên Windows).
2. **Lỗi L2 (Dọn dẹp khi Startup thất bại)**: Trước đây script chỉ lưu state file sau khi cả 3 dịch vụ đều sẵn sàng. Khi startup gặp sự cố giữa chừng, các tiến trình đã tạo bị bỏ rơi ở trạng thái mồ côi (orphaned), chiếm dụng cổng mạng mà `stop_preview_stack.ps1` không nắm được quyền sở hữu để dọn dẹp.
3. **Phát hiện bổ sung (Pipe Handle Inheritance)**: Khi script chạy ở chế độ nền qua harness kiểm thử tự động (`subprocess.run(capture_output=True)`), các tiến trình con kế thừa anonymous pipe handle stdout/stderr từ PowerShell, khiến harness chờ EOF vô tận dù launcher PowerShell đã kết thúc thành công.

---

## 2. CHI TIẾT CÁC THAY ĐỔI KỸ THUẬT

### 2.1. Khắc Phục Lỗi L1 — Tương thích Tuyệt đối Windows PowerShell 5.1
- **Cơ chế truyền ArgumentList & Quoting**: Xây dựng hàm `Format-NativeArgument` chuẩn hóa regex xử lý dấu backslash và dấu ngoặc kép trên Windows command line. Ghép các tham số thành một chuỗi duy nhất gán vào `ProcessStartInfo.Arguments` hoặc truyền cho `Start-Process -ArgumentList $argString`.
- **Gán Biến Môi Trường**: Loại bỏ biểu thức wrap collection của PowerShell 5.1, gán trực tiếp qua `$psi.EnvironmentVariables[$key]` và `[System.Environment]::SetEnvironmentVariable($key, $val, "Process")`.
- **Bảo toàn Mã hóa UTF-8 BOM**: Lưu các tệp script PowerShell (`.ps1`) với UTF-8 BOM (`EF BB BF`) để Windows PowerShell 5.1 trên mã trang CP1252 phân giải chính xác các chuỗi tiếng Việt có dấu, không gây lỗi cú pháp parser.
- **Tránh Trùng Biến Hệ Thống `$PID`**: Thay đổi biến trong vòng lặp dọn dẹp sang `$procId`, loại bỏ xung đột với biến tự động chỉ đọc `$PID` của PowerShell.

### 2.2. Khắc Phục Lỗi L2 — Ghi Nhận Ownership Tăng Dần & Auto-Cleanup Theo Thứ Tự Ngược Lại
- **Ghi nhận ngay khi spawn (Progressive Tracking)**: Ngay sau khi mount Google Drive hoặc spawn bất kỳ tiến trình nào (FastAPI, Spring Boot, Next.js), hàm `Save-StackState` được gọi ngay lập tức để cập nhật danh sách `Processes` (gồm `Name`, `PID`, `StartTime`, `ExecutablePath`, `Port`, `LogFile`).
- **Khối xử lý lỗi an toàn (Try / Catch Cleanup)**: Bọc toàn bộ các bước khởi động và readiness polling bằng khối `try / catch`. Khi phát hiện lỗi hoặc ngoại lệ:
  1. Kích hoạt khối dọn dẹp khẩn cấp.
  2. Duyệt ngược danh sách tiến trình (`Next.js` $\rightarrow$ `SpringBoot` $\rightarrow$ `FastAPI`).
  3. Xác minh danh tính 3 lớp qua `Win32_Process` (khớp PID, khớp `ExecutablePath`, thời gian tạo `CreationDate` lệch `StartTime` $\le$ 3.0 giây). **Tuyệt đối không kill theo tên (no kill-by-name)**.
  4. Gửi tín hiệu dừng an toàn và chờ tiến trình giải phóng cổng.
  5. Tháo gắn Google Drive nếu đã được gắn trong phiên đó.
  6. Nếu toàn bộ tài nguyên được dọn dẹp thành công: xóa tệp `target/preview_stack.json`.
  7. Nếu có tài nguyên chưa dừng được: đánh dấu trạng thái `FAILED_NEEDS_CLEANUP` và bảo toàn state file để hỗ trợ người dùng chẩn đoán.
- **Không Ghi Đè Stack Đang Hoạt Động**: Kiểm tra preflight nếu phát hiện state file cũ có tiến trình đang thực sự sống thì từ chối khởi động đè.
- **Bảo Mật Secret**: Thiết lập đồng thời cả `FASTAPI_SYNC_SECRET` và `CATALOG_SYNC_TOKEN` cho tiến trình con nhưng không in secret ra console.

### 2.3. Ngắt Kế Thừa Pipe Handle & Redirect Log Từng Dịch Vụ
- Bổ sung thư mục `target/preview_logs/` cho toàn bộ stack.
- Mỗi dịch vụ nền được redirect độc lập sang tệp log riêng:
  - FastAPI: `target/preview_logs/fastapi.stdout.log` & `fastapi.stderr.log`
  - Spring Boot: `target/preview_logs/springboot.stdout.log` & `springboot.stderr.log`
  - Next.js: `target/preview_logs/nextjs.stdout.log` & `nextjs.stderr.log`
- Cơ chế khởi chạy qua `Start-Process -RedirectStandardOutput -RedirectStandardError -PassThru -NoNewWindow` tách biệt hoàn toàn standard stream của các tiến trình con khỏi pipe của PowerShell, cho phép tham số `-Background` trả về ngay lập tức với exit code 0 khi readiness hoàn tất.
- Bổ sung timeout hữu hạn cho test harness `scripts/verify_preview_launcher.py`.

---

## 3. KẾT QUẢ KIỂM THỬ THỰC TẾ TRÊN MÁY

### 3.1. Test B: Kiểm Tra Giả Lập Lỗi & Tự Động Dọn Dẹp (Failure Cleanup)
Thực thi trực tiếp bằng `powershell.exe -NoProfile -File scripts/start_preview_stack.ps1 -Background`:

1. **Giả lập lỗi ngay sau khi FastAPI vừa spawn (`-TestInjectFailureAfter FastApiSpawn`)**:
   - Exit code trả về: `1` (Non-zero, fail-closed chuẩn xác).
   - Tiến trình FastAPI vừa tạo (PID 8420) được định danh và dừng thành công.
   - Cổng 8000 được giải phóng lập tức, tệp `target/preview_stack.json` được xóa sạch.
2. **Giả lập lỗi ngay sau khi Spring Boot vừa spawn (`-TestInjectFailureAfter SpringBootSpawn`)**:
   - Exit code trả về: `1`.
   - Cơ chế dọn dẹp theo thứ tự ngược lại kích hoạt: Dừng Spring Boot (PID 13768) trước $\rightarrow$ Dừng FastAPI (PID 13148) sau.
   - Toàn bộ cổng 8000, 8080 được giải phóng, không để lại tiến trình mồ côi.

### 3.2. Test A: Kiểm Tra Khởi Động Đầy Đủ & Dừng Chuẩn Xác (Success Path & Clean Stop)
Thực thi trọn vẹn qua lệnh hướng dẫn người dùng:
```powershell
powershell -NoProfile -File scripts/start_preview_stack.ps1 -Background
```

| Tiêu chí | Kết quả thực tế | Trạng thái |
| :--- | :--- | :--- |
| **Preflight Ports** | Cả 3 cổng 8000, 8080, 3000 đều FREE trước khi chạy | **PASS** |
| **Thời gian khởi động** | Hoàn thành sau 53.36 giây, exit code = 0 | **PASS** |
| **State File** | Tạo `target/preview_stack.json`, Status = `READY`, ReleaseLevel = `usable_preview` | **PASS** |
| **FastAPI Process** | PID: 4612, Port 8000, Log: `fastapi.stdout.log` | **PASS** |
| **SpringBoot Process** | PID: 8544, Port 8080, Log: `springboot.stdout.log` | **PASS** |
| **NextFrontend Process** | PID: 9144, Port 3000, Log: `nextjs.stdout.log` | **PASS** |
| **HTTP FastAPI Root** | `http://127.0.0.1:8000/` $\rightarrow$ **HTTP 200 OK** | **PASS** |
| **HTTP FastAPI Health** | `http://127.0.0.1:8000/health` $\rightarrow$ **HTTP 200 OK** | **PASS** |
| **HTTP SpringBoot Health** | `http://127.0.0.1:8080/api/health` $\rightarrow$ **HTTP 200 OK** | **PASS** |
| **HTTP SpringBoot Movies** | `http://127.0.0.1:8080/api/movies` $\rightarrow$ **HTTP 200 OK** | **PASS** |
| **HTTP Next.js Home** | `http://127.0.0.1:3000` $\rightarrow$ **HTTP 200 OK** | **PASS** |
| **Lệnh Dừng** | `powershell.exe -NoProfile -File scripts/stop_preview_stack.ps1` $\rightarrow$ Exit code 0 (2.15s) | **PASS** |
| **Xác minh PID sau dừng** | Cả 3 PID 4612, 8544, 9144 đều đã kết thúc (`alive: False`) | **PASS** |
| **Giải phóng Cổng** | Toàn bộ 3 cổng 8000, 8080, 3000 đều trở về trạng thái FREE | **PASS** |
| **Xóa State File** | Tệp `target/preview_stack.json` được xóa sạch sau khi stack dừng | **PASS** |

---

## 4. BẢNG TỔNG HỢP TRẠNG THÁI TỆP TIN

| Tệp tin | Vai trò | Thay đổi chính |
| :--- | :--- | :--- |
| `scripts/start_preview_stack.ps1` | Launcher chính | Tương thích PS 5.1, quoting an toàn, progressive state tracking, try/catch auto-cleanup ngược thứ tự, redirect logs riêng. |
| `scripts/stop_preview_stack.ps1` | Script dừng stack | Giữ nguyên xác minh danh tính 3 lớp (PID, StartTime delta < 3s, ExecutablePath), xóa state an toàn. |
| `scripts/verify_preview_launcher.py` | Test harness tái hiện | Bọc gọi launcher với timeout hữu hạn, kiểm tra 5 HTTP endpoints 200 OK, xác thực dừng stack và giải phóng cổng. |
| `docs/reviews/evidence/SNAPSHOT_01_F01_LAUNCHER.json` | Bằng chứng thực thi | Lưu trữ toàn bộ thông số thực tế của Test A và Test B. |
| `docs/reports/SNAPSHOT_01_F01_STATUS.json` | Trạng thái máy đọc | Metadata tiến độ hoàn thành checkpoint. |

---

## 5. HƯỚNG DẪN VẬN HÀNH CHO NGƯỜI DÙNG

Người dùng có thể khởi động và dừng bản dùng thử trực tiếp bằng Windows PowerShell 5.1 tiêu chuẩn:

1. **Khởi động chạy nền**:
   ```powershell
   powershell -File scripts/start_preview_stack.ps1 -Background
   ```
2. **Khởi động chạy foreground (nhấn Ctrl+C để dừng)**:
   ```powershell
   powershell -File scripts/start_preview_stack.ps1
   ```
3. **Dừng toàn bộ stack một cách an toàn**:
   ```powershell
   powershell -File scripts/stop_preview_stack.ps1
   ```
4. **Kiểm tra nhật ký riêng từng dịch vụ**:
   Các tệp log được lưu tại thư mục `target/preview_logs/`:
   - `fastapi.stdout.log` / `fastapi.stderr.log`
   - `springboot.stdout.log` / `springboot.stderr.log`
   - `nextjs.stdout.log` / `nextjs.stderr.log`
