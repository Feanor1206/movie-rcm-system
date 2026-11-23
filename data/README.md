# Danh mục phim

| Gói | Phạm vi | Nguồn |
| --- | --- | --- |
| [Jadoo](catalog.jadoo_all.json) | 99 tập thuộc bốn mùa | Phát từ tệp hoặc Google Drive |
| [Larva](catalog.larva.json) | 104 tập mùa 1, 56 tập có tóm tắt đã đối chiếu | [Playlist Larva TUBA](https://www.youtube.com/playlist?list=PLxrv_vTPuZ6Qi6Hx868jli1m5CDCEDfxj) |
| [Công chúa Ori](catalog.ori.json) | 180 tập, 37 tập có tóm tắt đã đối chiếu | [Playlist do The Child sắp xếp](https://www.youtube.com/playlist?list=PLMtVgyZo_WBIoqfvWtlg9_F7J1Xz53bB4), video do MYKINGDOM đăng |
| [Doraemon](catalog.doraemon.json) | 46 tập mùa 12 lồng tiếng Việt, 7 tập có tóm tắt đã đối chiếu | [Playlist POPS Kids](https://www.youtube.com/playlist?list=PLdhrcCVXurgJrmtUIdeeOJlwN0O8UAZx4) |
| [Doraemon bổ sung](catalog.doraemon_s05_s11.json) | 291 tập lồng tiếng Việt ở mùa 5, 6, 7, 9, 10 và 11 | Các playlist của POPS Kids, gồm [mùa 5](https://www.youtube.com/playlist?list=PLdhrcCVXurgJB_9uBT0wWJfLLiF7tHgJu) và [mùa 11](https://www.youtube.com/playlist?list=PLdhrcCVXurgKG1lEhpBuosfSwIptJAcVM) |
| [Trạng Quỳnh Thời Nhí Nhố](catalog.trang_quynh.json) | 35 tập, 30 tập có tóm tắt đã đối chiếu | [Playlist gốc](https://www.youtube.com/playlist?list=PLJscQ6PJLmu3zd6RfLDVUxP4EfahF2OKO) và [kênh phát hành](https://www.youtube.com/channel/UCndGTJ1ZllgoBXRUR-xfDUQ) |
| [Chuẩn hóa metadata theo mẫu Jadoo](catalog.episode_metadata.json) | Cập nhật 133 tập đã có, gồm 54 Larva, 37 Ori, 7 Doraemon và 35 Trạng Quỳnh | Tóm tắt đã đối chiếu, phụ đề ASR và khung hình từ video phát hành |

Bản ghi lưu số tập, vị trí trong playlist, thời lượng và nguồn. Ngày đăng video nằm trong `youtube_upload_date` khi có. Larva dùng dữ liệu phân tích hình và tiếng từ Gemini để đối chiếu với nguồn theo tập. Tập Kem có hai mốc đã kiểm tra trên video ở 00:33 và 01:22. Mốc trong bản nháp Gemini chờ đối chiếu.

Ori có 136 tập dùng trình phát nhúng và 44 tập mở qua liên kết gốc. Khi khởi tạo kho phim, nhập Jadoo, Larva, Ori, hai gói Doraemon, Trạng Quỳnh Thời Nhí Nhố rồi gói cập nhật metadata.

Ngày 23/11/2026, gói Doraemon bổ sung đối chiếu số tập và thời lượng theo playlist của POPS Kids. YouTube trả metadata nhúng cho 291 video. Các tập trong gói này chờ bổ sung tóm tắt và mốc cảnh.

## Hai gói thêm ngày 22/11/2026

Box Office Vietnam ghi nhận khoảng 205,3 tỷ đồng doanh thu nội địa của Doraemon Movie 45. Tập 23 của Trạng Quỳnh Thời Nhí Nhố có khoảng 8 triệu lượt xem trên kênh gốc. Hai số liệu đo lần lượt doanh thu chiếu rạp ở Việt Nam và tổng lượt xem của một video YouTube. [Box Office Vietnam](https://v1.boxofficevietnam.com/movie/doraemon-movie-45-2026-nobita-va-lau-dai-duoi-day-bien/) · [Trạng Quỳnh tập 23](https://www.youtube.com/watch?v=beq0O5ugcAM)

Cả 81 video đều công khai và cho phép nhúng theo metadata của YouTube lúc đối chiếu. Danh mục giữ số tập do kênh đặt, kể cả các khoảng trống. Phần tóm tắt Doraemon mô tả truyện nêu trong tiêu đề tập của POPS Kids, đối chiếu với TV Asahi. Phần tóm tắt Trạng Quỳnh dựa vào mô tả của kênh. [Ví dụ tóm tắt TV Asahi](https://www.tv-asahi.co.jp/doraemon/story/0468/) · [Ví dụ mô tả tập 1 Trạng Quỳnh](https://www.youtube.com/watch?v=GnCfwuHRGgk)

## Chuẩn hóa theo mẫu Jadoo

Gói cập nhật giữ ID tập, số thứ tự, thời lượng và nguồn phát. Từ khóa mô tả đồ vật, tình tiết hoặc nhân vật. Chủ đề giúp tìm các tập có nội dung gần nhau. Trạng Quỳnh có tóm tắt riêng cho cả 35 tập sau cập nhật.

Doraemon 579 có tóm tắt cho cả hai truyện trong tập và hai đoạn thoại có mốc đối chiếu. Bốn tập Trạng Quỳnh có thêm mốc từ phụ đề tự động. Tập 16 được đối chiếu bằng khung hình. [Nội dung Doraemon 579 trên TV Asahi](https://www.tv-asahi.co.jp/doraemon/story/0468/) · [Trạng Quỳnh tập 16](https://www.youtube.com/watch?v=dzxjaprCieA)

Kiểm tra các gói mới từ thư mục gốc.

```powershell
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.larva.json
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.ori.json
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.doraemon.json --report
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.doraemon_s05_s11.json --report
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.trang_quynh.json --report
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.episode_metadata.json --report
```
