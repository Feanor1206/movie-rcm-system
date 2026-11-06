# <TICKET> — Báo cáo ready for review

## 1. Vấn đề và phạm vi

- Người dùng được cải thiện điều gì?
- Contract/ticket nào được thực hiện?
- Baseline branch và thay đổi có sẵn; scope của lượt này.

## 2. Files và thay đổi

Liệt kê files/hunks của lượt này, không nhận toàn bộ git diff đã có là patch mới. Với file untracked có sẵn, mô tả phần đã sửa. Nêu API/DB/artifact compatibility khi có.

## 3. Ma trận nghiệm thu

| Acceptance case | Expected | Actual | Evidence | Passed / Failed / Not checked |
|---|---|---|---|---|

Bao gồm failure cases quan trọng, ownership/unknown/idempotency khi liên quan. UI có mobile/keyboard/loading/error và media/labels trung thực.

## 4. Kiểm tra thực hiện

- Interpreter/runtime, cwd và env flags không chứa secrets.
- Exact commands, exit codes, passed/skipped/failed và duration.
- Mock/unit, provider integration và live-model inference ghi riêng.
- Report/data fixtures/ảnh có đường dẫn tồn tại thật.
- Check không chạy được: command/error và ảnh hưởng kết luận.

## 5. Kết quả và limitations

- Phần đạt và chưa đạt.
- Chưa kiểm tra gì? Có thay đổi ngoài scope không?
- Data/model assumptions và migration/rollback khi liên quan.

## 6. Bàn giao

Trạng thái: ready for review. Không tự accepted, commit hoặc push. Codex đưa verdict riêng dựa trên source/diff và evidence.
