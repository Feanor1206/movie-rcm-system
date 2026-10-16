# Dữ liệu gốc cho hoạt hình nhiều tập — dippie.catalog.v1

Đây là **contract dữ liệu đề xuất**, có JSON Schema và validator độc lập. Ứng dụng hiện tại **chưa có importer cho contract này**. Các file này không import DB, không mở video, không tạo embedding và không sửa source ứng dụng. Importer cần được triển khai theo contract trước khi website dùng được dữ liệu.

## Các file

- `dippie.catalog.v1.schema.json`: JSON Schema Draft2020-12; khai báo các trường, kiểu, enum và nullability.
- `catalog.example.json`: mẫu đầy đủ với bộ/phần/tập/truyện ngắn/nhân vật/video/phụ đề/cảnh. **Toàn bộ nội dung mẫu là hư cấu, trạng thái draft; không phải metadata phim hay video thật.**
- `catalog.blank.json`: gói trống hợp lệ để điền dữ liệu thật; gói trống không tạo ra nội dung trên web.
- `validate_catalog.py`: kiểm tra schema, ID, references, scale, thứ tự, timestamps và một số ràng buộc liên bảng. Cần Python có `jsonschema`; không tự cài dependency.

## Tổ chức lưu trữ bên ngoài

Nên chuẩn bị một gói JSON self-contained cho mỗi bộ hoặc một nhóm tập. Tất cả ID mà gói tham chiếu phải có trong chính gói, kể cả nguồn/thể loại/nhân vật; ID chung có thể xuất hiện lại ở gói khác để importer upsert cùng bản ghi. Importer phải kiểm tra revision và xung đột dữ liệu trước khi update.

Ví dụ:

```text
my-catalog/
  bo-thu-nhat/catalog.json
  bo-thu-hai/catalog.json
  subtitles/...
```

Video vẫn lưu ở Drive. `relative_path` tính từ root của `storage_key` do máy chủ cấu hình, không phải đường dẫn tuyệt đối trên máy bạn. `animation_drive` trong mẫu là tên cấu hình logic, không tự động tương đương một remote rclone đã có.

## Các nhóm dữ liệu

| Nhóm | Ý nghĩa và trường chính |
| --- | --- |
| `package` | Danh tính/revision/ngày tạo gói, ngôn ngữ mặc định; `import_mode=upsert`, `reference_scope=self_contained`. Không có lệnh xóa. |
| `genres` | Bộ từ điển thể loại: ID, nhãn nhiều ngôn ngữ, bí danh. Các entity dùng `genre_ids`. |
| `attribute_scales` | Định nghĩa/version/thang/levels cho darkness, pacing hoặc thuộc tính bổ sung. |
| `sources` | Nguồn metadata: manual/official/catalog/subtitle/transcript/video observation/model output, URL/reference, ngôn ngữ, ngày lấy. |
| `series` | Bộ hoạt hình: tên, tên gốc, bí danh/bản dịch, tóm tắt, thể loại, từ khóa/chủ đề, xuất xứ/ngôn ngữ, năm, trạng thái phát hành, tác giả/studio/network, nhân vật, thuộc tính, rating, artwork, IDs ngoài. |
| `seasons` | Phần/mùa/collection: bộ cha, số phần có thể null, tên, mô tả, năm, artwork, external IDs. Không có season thì `episodes.season_id=null`. |
| `episodes` | Tập logic: bộ/phần cha, số tập hoặc null, production code, tên/bí danh/bản dịch, loại tập, ngày phát, thời lượng, nhiều thứ tự xem, nội dung/tình tiết/nhân vật, attributes/ratings, advisory/artwork, liên kết tập, external IDs. |
| `segments` | Truyện ngắn trong một tập: thứ tự, tên/bí danh, tóm tắt, nhân vật, tình tiết/từ khóa/chủ đề, thuộc tính, timestamp logic nếu biết. Một tập có thể chứa nhiều segment. |
| `characters` | Nhân vật dùng ID ổn định: thuộc bộ nào, tên/bí danh, mô tả/vai trò/đặc điểm, quan hệ, lồng tiếng theo ngôn ngữ, artwork, external IDs. |
| `media_assets` | File video/audio: provider/root logic/path/Drive IDs, dung lượng/hash/thời lượng, edition/ngôn ngữ, technical metadata, mapping `coverage`, access policy và enabled. |
| `text_tracks` | Phụ đề/transcript/OCR: gắn với asset, ngôn ngữ/format, cues inline hoặc reference tới file SRT/VTT/JSON ngoài. |
| `scenes` | Cảnh trong asset: khoảng thời gian, tập/truyện liên quan, tóm tắt hình ảnh, nhân vật/từ khóa/chủ đề/sound events, cue references và spoiler level. |

Mọi entity nội dung có `record`: status, revision, created_at, updated_at, provenance. `draft` được phép thiếu thông tin nullable; `ready` cần source và provenance được human/source verified theo validator. Validator không chứng minh nội dung đã được người thật kiểm tra.

## Quy tắc điền

1. Dùng ID ổn định, duy nhất trong gói, không dùng tên file hay số thứ tự mảng làm ID. Mẫu: `ser_shin`, `sea_shin_01`, `ep_shin_0001`, `seg_shin_0001a`, `asset_shin_0001`, `char_shin`, `src_manual_001`.
2. **Không đổi ID khi đổi tên phim/tập hoặc di chuyển file.** Sửa path/metadata, tăng revision; giữ liên kết cũ.
3. Schema cố ý khai báo đủ trường và không cho key lạ. Trường chưa biết để `null` nếu schema cho phép; danh sách chưa có để `[]`. Không tự chèn0/chuỗi giả cho rating, năm, trait hoặc duration. Không bỏ key bắt buộc.
4. `title` là tên hiển thị chính; `original_title` là tên gốc; `aliases` dùng để tìm kiếm; `translations` chứa title/synopsis ngôn ngữ khác. Ngôn ngữ dùng nhãn như `vi`, `ja`, `en`, `vi-VN`.
5. `episodes.number` không phải ID. Dùng `orders` để phân biệt broadcast/release/chronological/platform/custom; không ép số phát sóng thành thứ tự nội dung.
6. Tập thường, special, OVA, recap, short hoặc pilot vẫn là episode; nhiều truyện nhỏ trong một tập là segments. Không tạo series mới chỉ vì một tập có ba truyện.
7. Phim/tập chưa có video vẫn lưu metadata được: chưa tạo media asset. Một tập có thể có nhiều file/edition; một file có thể chứa nhiều tập. Dùng coverage, không nhân bản metadata tập theo từng file.
8. Các trường kỹ thuật video có thể để null và điền sau bằng công cụ đọc metadata offline. JSON không chứa nội dung nhị phân của video.
9. `access_policy` chỉ là yêu cầu metadata; importer/server phải enforce quyền thật. Mẫu mặc định private. Không tự biến mọi dữ liệu nhập thành public.

## Timestamps và mapping video

**Tất cả thời gian đều là integer milliseconds, không dùng giây hoặc chuỗi HH:MM:SS.** Ví dụ01:02.500 =62500. Khoảng thời gian theo quy ước `[start_ms,end_ms)`, end phải lớn hơn start.

- `episodes.duration_ms` là thời lượng tập logic.
- `media_assets.duration_ms` là thời lượng của file thực.
- `coverage.source_in_ms/source_out_ms` là đoạn trong file. `source_out_ms=null` nghĩa đến hết file; nếu chưa biết duration thì chưa xác định được endpoint.
- `coverage.episode_in_ms` là vị trí đoạn đó bắt đầu trong tập logic; null nghĩa chưa biết offset, không tự coi là0.
- `coverage.sequence` là thứ tự phần phát trong tập/edition. Nhiều bản lồng tiếng có thể cùng offset; không coi đó là phần phát tiếp theo.
- `segments.episode_start_ms/episode_end_ms` là khoảng trong tập logic; cả hai null nếu chưa xác minh.
- `scenes.start_ms/end_ms` và `text_tracks.cues.start_ms/end_ms` luôn tính theo **file media_asset_id**, không theo timestamp của tập hay bản cắt khác.
- Phụ đề/cảnh phải khớp đúng bản video. Bản cắt/intro khác không được dùng lại timestamp nếu chưa căn chỉnh.
- Cùng một truyện có thể được chia file hoặc nằm trong tập tổng hợp; giữ segment ID, khai báo coverage của từng file tương ứng.

Ví dụ một file chứa hai tập: thêm hai coverage entry với episode_id khác nhau và source intervals khác nhau. Một tập chia hai file: hai assets cùng episode_id, sequence1/2 và episode_in_ms phù hợp. Không tự suy ra offset nếu dữ liệu thiếu.

## Nội dung để tìm kiếm

- `synopsis`: tóm tắt có thông tin, không chỉ “tập phim vui nhộn”.
- `plot_facts`: các tình tiết cụ thể, mỗi fact có ID/provenance riêng.
- `characters`: tên và alias nhất quán, references bằng ID.
- `keywords/themes`: từ khóa/chủ đề của nội dung, không spam từ không xuất hiện.
- `scenes`: hành động và hình ảnh có timestamp nếu muốn tìm đến đúng cảnh.
- `text_tracks`: lời thoại OCR/transcript/subtitle không thay thế toàn bộ thông tin hình ảnh.

Đủ để bắt đầu: series + episode + synopsis/keywords/characters + source; thêm media asset nếu cần phát. Season/segment/scene/transcript có thể để mảng rỗng khi chưa có. Gói vẫn phải giữ đầy đủ các key root.

## Nguồn, độ tin cậy và thuộc tính so sánh

`provenance.origin` phân biệt manual/imported/machine_generated/unknown. `verification` phân biệt unverified/human_verified/source_verified/disputed. Lưu tool/model/revision nếu metadata được sinh máy; không tự đánh dấu verified chỉ vì output JSON hợp lệ.

`confidence` là mức tin cậy annotation nếu có căn cứ, không phải xác suất phim phù hợp người xem. Không có căn cứ thì để null. Nguồn không chỉ là URL: có thể là ghi chú kiểm tra video, phụ đề hoặc tài liệu nội bộ.

Darkness/pacing phải dùng cùng scale/version/definition để so sánh. Hai thang trong mẫu chỉ là rubric biên tập khởi đầu, chưa phải số đo đã hiệu chuẩn. Giá trị mẫu để null. Không suy ra từ genre/rating; không mặc định unknown=0. Thuộc tính của bộ không tự động là thuộc tính của mọi tập.

Không lưu token/OAuth/secrets/signed playback URLs trong JSON. `storage_key` ánh xạ tới cấu hình root/remote ở server, credentials giữ ngoài catalog. Importer phải kiểm tra root containment và symlink khi thật sự mở file; validator này chỉ kiểm tra metadata/path string.

## Kiểm tra trước khi nhập

Từ repository root, dùng Python có sẵn `jsonschema`:

```powershell
python docs/contracts/animation-catalog-v1/validate_catalog.py D:/du-lieu/bo-thu-nhat/catalog.json
```

Exit0 nghĩa schema và các quan hệ/timestamps được kiểm tra hợp lệ; **không có nghĩa video tồn tại, metadata đúng sự thật hoặc web đã nhập dữ liệu**. Exit1 nghĩa cần sửa lỗi hiển thị.

Importer tương lai còn phải: dry-run, upsert transaction, revision/conflict policy, kiểm tra storage_key được cho phép, phân quyền, ngăn ghi live DB, publish/index chỉ nội dung đủ điều kiện và báo lỗi theo record. Việc bỏ một record khỏi gói không có nghĩa xóa bản ghi trong DB. Không dùng import JSON làm lệnh xóa hay thay toàn bộ catalog.

Database giữ dữ liệu vận hành sau khi import. JSON là nguồn/trao đổi/backup có version. Embedding index được sinh offline từ nội dung phù hợp, có encoder/revision/dimension/preprocessing/content hash riêng; không nhét vector, model weights, video hay user history/session vào catalog này.
