# Danh mục phim

## Catalog theo từng bộ

Các gói trong `catalog-by-series/` dùng schema `dippie.catalog.v1` như catalog Jadoo. Mỗi file tự chứa bộ phim, các mùa, tập, nhân vật và nguồn tham chiếu. Mục `segments` lưu tên, tóm tắt, từ khóa và khoảng thời gian của từng đoạn. Nhập trực tiếp tám gói này khi tạo kho mới.

| Catalog | Tập | Tập có phụ đề | Phân đoạn mới |
| --- | ---: | ---: | ---: |
| [Xin Chào Jadoo](catalog-by-series/catalog.jadoo.json) | 99 | 98 | 276 |
| [Larva](catalog-by-series/catalog.larva.json) | 104 | 83 | 0 |
| [Công chúa Ori](catalog-by-series/catalog.ori.json) | 180 | 131 | 363 |
| [Doraemon](catalog-by-series/catalog.doraemon.json) | 337 | 310 | 887 |
| [Trạng Quỳnh Thời Nhí Nhố](catalog-by-series/catalog.trang_quynh.json) | 35 | 35 | 51 |
| [Pokémon](catalog-by-series/catalog.pokemon.json) | 479 | 0 | 0 |
| [Mr Bean hoạt hình](catalog-by-series/catalog.mr_bean_animated.json) | 87 | 0 | 0 |
| [Heo Peppa](catalog-by-series/catalog.peppa_pig.json) | 51 | 51 | 100 |
| **Tổng** | **1.372** | **708** | **1.677** |

Đợt rà ngày 23/11/2026 bổ sung 1.677 phân đoạn cho 610 tập. Sáu tập Jadoo có phụ đề đã được phủ bởi các phân đoạn đã lưu trước đó. 92 track còn lại chỉ có âm thanh hoặc lời thoại quá ít để mô tả tình tiết. YouTube không trả track cho 98 video khác và báo 566 video Pokémon, Mr Bean không khả dụng từ kết nối kiểm tra.

Sau đợt này, 1.237 trong 1.372 tập đạt bộ kiểm metadata cấp tập. Tổng cộng 617 tập có mốc phân đoạn.

Phân đoạn mới dùng lời thoại đã đối chiếu bằng hai lượt tự động. Mốc đầu và cuối lấy từ phụ đề của đúng video. Mỗi nguồn lưu ngôn ngữ, đường dẫn và SHA-256 để đối chiếu lại. Những track chủ yếu ghi nhạc hoặc tiếng động được lưu tham chiếu nguồn.

## Các gói nhập trước đây

| Gói | Phạm vi | Nguồn |
| --- | --- | --- |
| [Jadoo](catalog.jadoo_all.json) | 99 tập thuộc bốn mùa | Phát từ tệp hoặc Google Drive |
| [Larva](catalog.larva.json) | 104 tập mùa 1, 56 tập có tóm tắt đã đối chiếu | [Playlist Larva TUBA](https://www.youtube.com/playlist?list=PLxrv_vTPuZ6Qi6Hx868jli1m5CDCEDfxj) |
| [Công chúa Ori](catalog.ori.json) | 180 tập, 37 tập có tóm tắt đã đối chiếu | [Playlist do The Child sắp xếp](https://www.youtube.com/playlist?list=PLMtVgyZo_WBIoqfvWtlg9_F7J1Xz53bB4), video do MYKINGDOM đăng |
| [Doraemon](catalog.doraemon.json) | 46 tập mùa 12 lồng tiếng Việt, 7 tập có tóm tắt đã đối chiếu | [Playlist POPS Kids](https://www.youtube.com/playlist?list=PLdhrcCVXurgJrmtUIdeeOJlwN0O8UAZx4) |
| [Doraemon bổ sung](catalog.doraemon_s05_s11.json) | 291 tập lồng tiếng Việt ở mùa 5, 6, 7, 9, 10 và 11 | Các playlist của POPS Kids, gồm [mùa 5](https://www.youtube.com/playlist?list=PLdhrcCVXurgJB_9uBT0wWJfLLiF7tHgJu) và [mùa 11](https://www.youtube.com/playlist?list=PLdhrcCVXurgKG1lEhpBuosfSwIptJAcVM) |
| [Trạng Quỳnh Thời Nhí Nhố](catalog.trang_quynh.json) | 35 tập, 30 tập có tóm tắt đã đối chiếu | [Playlist gốc](https://www.youtube.com/playlist?list=PLJscQ6PJLmu3zd6RfLDVUxP4EfahF2OKO) và [kênh phát hành](https://www.youtube.com/channel/UCndGTJ1ZllgoBXRUR-xfDUQ) |
| [Chuẩn hóa metadata theo mẫu Jadoo](catalog.episode_metadata.json) | Cập nhật 133 tập đã có, gồm 54 Larva, 37 Ori, 7 Doraemon và 35 Trạng Quỳnh | Tóm tắt đã đối chiếu, phụ đề ASR và khung hình từ video phát hành |
| [Pokémon TV](catalog.pokemon_tv.json) | 479 tập từ mùa 1 đến mùa 11 với tóm tắt tiếng Việt | [Pokémon TV](https://www.youtube.com/channel/UC8wrbl5viYtQmRUgdFdf4ew), [TVmaze](https://www.tvmaze.com/shows/590/pokemon/episodeguide) |
| [Mr Bean hoạt hình](catalog.mr_bean_animated.json) | 87 tập từ ba mùa đầu theo cách đánh số của kênh | [Mr Bean](https://www.youtube.com/channel/UCkAGrHCLFmlK3H2kd6isipg), [TVmaze](https://www.tvmaze.com/shows/5251/mr-bean/episodeguide) |
| [Heo Peppa](catalog.peppa_pig.json) | 51 tập đầy đủ với tóm tắt tiếng Việt | [Peppa Pig Pretend Play](https://www.youtube.com/channel/UCoCSjc-4JCGqOxuhuw-xjSw), [TVmaze](https://www.tvmaze.com/shows/4972/peppa-pig/episodeguide) |
| [Metadata từ phụ đề ASR](catalog.episode_metadata_asr.json) | Cập nhật 193 tập Doraemon và 68 tập Ori đã có | Phụ đề tự động tiếng Việt của từng video đã lưu trong danh mục |

Bản ghi lưu số tập, vị trí trong playlist, thời lượng và nguồn. Ngày đăng video nằm trong `youtube_upload_date` khi có. Larva dùng dữ liệu phân tích hình và tiếng từ Gemini để đối chiếu với nguồn theo tập. Tập Kem có hai mốc đã kiểm tra trên video ở 00:33 và 01:22. Mốc trong bản nháp Gemini chờ đối chiếu.

Ori có 136 tập dùng trình phát nhúng và 44 tập mở qua liên kết gốc. Các gói trong bảng trên ghi lại từng đợt nhập trước khi tạo catalog đầy đủ theo bộ.

Ngày 23/11/2026, gói Doraemon bổ sung đối chiếu số tập và thời lượng theo playlist của POPS Kids. YouTube trả metadata nhúng cho 291 video. Gói metadata ASR cập nhật tóm tắt cho những tập có đủ bằng chứng từ lời thoại.

## Hai gói thêm ngày 22/11/2026

Box Office Vietnam ghi nhận khoảng 205,3 tỷ đồng doanh thu nội địa của Doraemon Movie 45. Tập 23 của Trạng Quỳnh Thời Nhí Nhố có khoảng 8 triệu lượt xem trên kênh gốc. Hai số liệu đo lần lượt doanh thu chiếu rạp ở Việt Nam và tổng lượt xem của một video YouTube. [Box Office Vietnam](https://v1.boxofficevietnam.com/movie/doraemon-movie-45-2026-nobita-va-lau-dai-duoi-day-bien/) · [Trạng Quỳnh tập 23](https://www.youtube.com/watch?v=beq0O5ugcAM)

Cả 81 video đều công khai và cho phép nhúng theo metadata của YouTube lúc đối chiếu. Danh mục giữ số tập do kênh đặt, kể cả các khoảng trống. Phần tóm tắt Doraemon mô tả truyện nêu trong tiêu đề tập của POPS Kids, đối chiếu với TV Asahi. Phần tóm tắt Trạng Quỳnh dựa vào mô tả của kênh. [Ví dụ tóm tắt TV Asahi](https://www.tv-asahi.co.jp/doraemon/story/0468/) · [Ví dụ mô tả tập 1 Trạng Quỳnh](https://www.youtube.com/watch?v=GnCfwuHRGgk)

## Chuẩn hóa theo mẫu Jadoo

Gói cập nhật giữ ID tập, số thứ tự, thời lượng và nguồn phát. Từ khóa mô tả đồ vật, tình tiết hoặc nhân vật. Chủ đề giúp tìm các tập có nội dung gần nhau. Trạng Quỳnh có tóm tắt riêng cho cả 35 tập sau cập nhật.

Doraemon 579 có tóm tắt cho cả hai truyện trong tập và hai đoạn thoại có mốc đối chiếu. Bốn tập Trạng Quỳnh có thêm mốc từ phụ đề tự động. Tập 16 được đối chiếu bằng khung hình. [Nội dung Doraemon 579 trên TV Asahi](https://www.tv-asahi.co.jp/doraemon/story/0468/) · [Trạng Quỳnh tập 16](https://www.youtube.com/watch?v=dzxjaprCieA)

### Lô 1.000 tập

Ở đợt này, SQLite demo có 1.372 tập ở trạng thái `ready`, trong đó 1.017 tập đạt bộ kiểm metadata cấp tập. Mỗi tập đạt có mùa và số tập, thời lượng, tóm tắt riêng, ID nhân vật, từ khóa, chủ đề và nguồn phát. Lô này bổ sung 617 tập và cập nhật metadata cho 261 tập đã có.

Gemini 3.1 Flash-Lite biên tập tóm tắt tiếng Việt. Với Doraemon và Ori, mỗi tóm tắt dựa trên phụ đề ASR của đúng video. Câu dẫn được so lại với phụ đề, sau đó nội dung được kiểm lại bằng một lượt riêng. Dấu thời gian và mã SHA-256 của phụ đề được lưu ở nguồn tham chiếu. Tập Doraemon có hai truyện được trình bày theo từng truyện khi tiêu đề và lời thoại đủ rõ.

Pokémon và Mr Bean giữ mùa và số tập trên kênh phát hành. Heo Peppa dùng mùa và số tập của TVmaze. Cả ba gói đối chiếu tên tập với mục TVmaze và kiểm tra metadata nhúng của từng video. Tóm tắt tiếng Việt là bản biên tập từ mô tả TVmaze, với đường dẫn từng tập trong `sources`. Phần dữ liệu chuyển thể từ TVmaze theo giấy phép CC BY-SA của nguồn. [Giấy phép API TVmaze](https://www.tvmaze.com/api#licensing)

Mốc lời thoại ở nguồn ASR phục vụ đối chiếu tóm tắt. Bộ kiểm xác nhận 13 tập có mốc đoạn hoặc cảnh công bố trong danh mục.

Kiểm tra các gói mới từ thư mục gốc.

```powershell
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.larva.json
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.ori.json
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.doraemon.json --report
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.doraemon_s05_s11.json --report
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.trang_quynh.json --report
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.episode_metadata.json --report
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.pokemon_tv.json --report
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.mr_bean_animated.json --report
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.peppa_pig.json --report
python docs/contracts/animation-catalog-v1/validate_catalog.py data/catalog.episode_metadata_asr.json --report
```
