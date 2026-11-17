# Danh mục phim

| Gói | Phạm vi | Nguồn |
| --- | --- | --- |
| [Jadoo](catalog.jadoo_all.json) | 99 tập thuộc bốn mùa | Phát từ tệp hoặc Google Drive |
| [Larva](catalog.larva.json) | 104 tập mùa 1, 56 tập có tóm tắt đã đối chiếu | [Playlist Larva TUBA](https://www.youtube.com/playlist?list=PLxrv_vTPuZ6Qi6Hx868jli1m5CDCEDfxj) |
| [Công chúa Ori](catalog.ori.json) | 180 tập, 37 tập có tóm tắt đã đối chiếu | [Playlist do The Child sắp xếp](https://www.youtube.com/playlist?list=PLMtVgyZo_WBIoqfvWtlg9_F7J1Xz53bB4), video do MYKINGDOM đăng |

Bản ghi lưu số tập, vị trí trong playlist, thời lượng và nguồn. Ngày đăng video nằm trong `youtube_upload_date` khi có. Larva dùng dữ liệu phân tích hình và tiếng từ Gemini để đối chiếu với nguồn theo tập. Tập Kem có hai mốc đã kiểm tra trên video ở 00:33 và 01:22. Mốc trong bản nháp Gemini chờ đối chiếu.

Ori có 136 tập dùng trình phát nhúng và 44 tập mở qua liên kết gốc. Khi khởi tạo kho phim, nhập Jadoo trước, sau đó nhập Larva và Ori.

Kiểm tra các gói mới từ thư mục gốc.

```powershell
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.larva.json
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.ori.json
```
