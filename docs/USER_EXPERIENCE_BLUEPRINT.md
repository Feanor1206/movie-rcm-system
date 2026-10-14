# Thiết kế trải nghiệm và thứ tự phát triển sản phẩm

Ngày: 13/10/2026. Bổ sung theo yêu cầu người dùng: chất lượng trải nghiệm là tiêu chí quyết định ưu tiên; kế hoạch AI/FastAPI phục vụ các hành trình này. Tài liệu mô tả thiết kế đề xuất, chưa phải chức năng đã triển khai.

## 1. Thành công từ góc nhìn người dùng

Người dùng tìm được một phim mình muốn xem, hiểu vì sao nó phù hợp, điều chỉnh dễ và không phải mô tả lại nhu cầu. Khi hệ thống chưa đủ dữ liệu hoặc gặp lỗi, người dùng biết giới hạn và vẫn có đường tiếp tục.

Không tối ưu bằng số model, số service, số phim trả về hoặc số lượt chat. Đánh giá bằng xác nhận tìm được phim phù hợp, thời gian chọn phim, công sức sửa yêu cầu và khả năng hoàn thành hành trình.

Ba lời hứa cốt lõi:

1. Bắt đầu nhanh: khám phá không cần tài khoản, không phải biết viết prompt.
2. Chọn dễ: ít ứng viên, lý do rõ, dễ so sánh và chốt một phim.
3. Kiểm soát được: sửa điều kiện, gu và dữ liệu cá nhân; biết tác động của phản hồi.

## 1.1. Định vị animation và trải nghiệm quan tâm người xem

Yêu cầu bổ sung: website tập trung hoạt hình, nhẹ nhàng và quan tâm người dùng. “Nhẹ nhàng” gồm giao diện ít gây phân tâm, công sức chọn phim thấp và hành vi hệ thống tôn trọng lựa chọn; không mặc định mọi người chỉ thích phim vui hoặc hoạt hình trẻ em.

Phạm vi hiện tại vẫn là khám phá/gợi ý và trợ giúp quyết định xem phim. Playback/hosting video toàn bộ phim chưa nằm trong yêu cầu đã chốt; trailer hoặc nguồn xem chỉ xuất hiện khi có dữ liệu hợp lệ.

### Nhận diện và điều hướng dành cho hoạt hình

- Điều chỉnh ngôn ngữ, hình ảnh và danh mục từ điện ảnh chung sang animation; không giữ các rails Sci-Fi/Crime mẫu như bộ nhận diện chính.
- Lối khám phá theo nhu cầu: ấm áp, phiêu lưu, suy ngẫm, hài hước, kỳ ảo; song song bộ lọc kỹ thuật 2D/3D/stop-motion, thời lượng, studio và độ tuổi khi có metadata.
- Có phim gia đình, teen và adult; phân biệt target audience, age classification và người dùng chọn xem cùng ai. Không coi animation đồng nghĩa dành cho trẻ nhỏ.
- Home giữ một hành động chính và vài lối vào; poster rõ, spacing thoáng, typography dễ đọc, màu nền và độ tương phản cần kiểm tra. “Nhẹ nhàng” không đồng nghĩa pastel chữ mờ hoặc contrast thấp.
- Quyết định màu sắc của người dùng: **tone xanh lá là màu chủ đạo của giao diện**. Áp dụng nhất quán cho nhận diện, nút chính, trạng thái chọn và điểm nhấn; kết hợp màu nền trung tính để giữ cảm giác nhẹ nhàng, chữ dễ đọc và độ tương phản phù hợp. Sắc độ cụ thể sẽ được chọn khi thiết kế UI.
- Không autoplay âm thanh/video trailer; animation trang trí vừa phải, tôn trọng reduced-motion. Preview chỉ chạy khi người dùng chọn.

### Tính năng chăm sóc trải nghiệm và thứ tự ưu tiên

| Tính năng | Cách người dùng sử dụng | Quy tắc và ưu tiên |
|---|---|---|
| Nhu cầu hôm nay | Chọn cảm giác muốn có, thời gian và xem một mình/gia đình/bạn bè | Tùy chọn, không cần trả lời đủ; session-only mặc định. P0 |
| Kiểm soát spoiler | Đọc tóm tắt không spoil; mở nội dung sâu hơn bằng hành động rõ | Spoiler ẩn mặc định; search snippets/explanations cũng phải tuân thủ. P0 |
| Thông tin nội dung cần cân nhắc | Xem tags về mức đáng sợ, tone nặng, mất mát hoặc các yếu tố có nguồn | Có provenance/unknown; không chẩn đoán cảm xúc hoặc đảm bảo phù hợp tuyệt đối. P0 cho dữ liệu đã có |
| Phù hợp người xem cùng | Chọn xem cùng trẻ/gia đình hoặc người trưởng thành | Dùng phân loại độ tuổi theo nguồn/khu vực khi có; thiếu dữ liệu ghi rõ, không gắn nhãn “an toàn cho trẻ” từ suy đoán LLM. P0 |
| Tránh nội dung không muốn | Đặt ưu tiên hoặc điều kiện bắt buộc, ví dụ không musical | Scope hôm nay/lâu dài rõ; unknown không được diễn giải là đáp ứng. P0 |
| Đã xem và xem lại | Ẩn phim đã xem trong gợi ý hoặc bật “muốn xem lại” | Title retrieval vẫn tìm phim đã xem; history do người dùng xác nhận. P0 |
| Tìm theo kỹ thuật/phong cách | 2D, 3D, stop-motion; tone/theme/visual facets | Chỉ hiển thị lựa chọn có dữ liệu engine hỗ trợ. P0/P1 theo coverage |
| Ngôn ngữ dễ quyết định | Aliases/tên Việt; metadata về audio/subtitle nếu có nguồn theo edition/platform | Không khẳng định có lồng tiếng/phụ đề từ country/language gốc. P1, phụ thuộc nguồn |
| Gu có thể thay đổi | Xem/edit declared và inferred preferences, bỏ signal hoặc reset | Rating thấp/skip không tự suy trạng thái tâm lý; reset có mô tả tác động. P1 |
| Bộ sưu tập theo mục đích | “Tối mưa”, “xem với gia đình”, “muốn xem lại” | Private mặc định; tên do người dùng chọn, không gán mood tự động. P1 |
| Tiếp tục lựa chọn dang dở | Trở về phiên/shortlist gần nhất và biết vì sao đã lưu | Không gọi là xem tiếp nếu không quản lý playback. P1 |
| Báo dữ liệu sai | Báo spoiler, sai thời lượng, tag thiếu hoặc link hỏng | Có tiếp nhận thật phía backend/admin, không toast thành công giả. P1 |

Tự động weather/context chỉ là lựa chọn opt-in. Không suy người dùng đang buồn từ giờ đêm, mưa hoặc lịch sử phim. Không ép onboarding, streak, thông báo hay lời nhắc quay lại để tăng thời gian dùng.

### Tối ưu hiệu năng và khả năng sử dụng

- Home/catalog/detail/library không chờ Qwen để tải hoặc hoạt động. Chọn filters và feedback có phản hồi trạng thái sớm.
- Media dùng kích thước phù hợp thiết bị, reserve layout space, lazy-load phần ngoài màn hình; không tải trailer/video nền nặng cho mọi visit.
- Hiển thị kết quả và evidence đã có trước optional LLM explanation khi cho phép. Queue/model failure không khóa thư viện hoặc chức năng tìm catalog.
- Mobile một tay, touch targets dễ bấm, keyboard/focus và screen-reader labels được nghiệm thu trên flow thật.
- Không mặc định đổi ngôn ngữ, theme, autoplay hoặc preferences sau khi người dùng đã chọn; lưu lựa chọn với scope rõ.
- Thiết kế empty/error rõ nhưng bình tĩnh: nói điều gì đang thiếu và hành động tiếp theo, tránh blaming hoặc technical stack traces.

### Gate cho bản animation đầu tiên

Một người mới phải chọn được một phim hoạt hình mà không đăng nhập, xem lý do không spoil, sửa điều kiện, rồi lưu đúng trạng thái. Một người quay lại phải thấy profile/rewatch/preferences của mình đúng; khi AI lỗi vẫn dùng catalog/library được.

Usability review phải bao gồm người mới, người dùng mobile và người chọn xem cùng gia đình. Đo usefulness và effort; không tự kết luận thiết kế tối ưu chỉ vì giao diện trông đẹp.

## 2. Trang chủ là nơi bắt đầu quyết định

Thứ tự nội dung đề xuất:

- Một câu mời rõ: “Bạn muốn xem gì hôm nay?” và ô nhập tự do có ví dụ.
- Bốn lối vào: Chọn phim tối nay / Tìm lại phim / Giống phim tôi thích / Gợi ý theo gu.
- Quick controls tùy chọn: thời gian có thể xem, cảm giác muốn có, xem cùng ai.
- Người có dữ liệu: một rail cá nhân hóa có lý do; người mới: lựa chọn khởi đầu có nhãn đúng.
- Tiếp tục phiên khám phá hoặc watchlist gần nhất khi có, không gọi là playback “xem tiếp”.

Không ép người dùng đi qua onboarding hoặc chat để nhận kết quả đầu tiên. Không đặt nhiều rails giống nhau hoặc gọi danh sách đảo thứ tự là personalized.

## 3. Hành trình quan trọng nhất: chọn phim tối nay

1. Chọn hoặc nhập nhu cầu. Các controls có thể bỏ qua; không có mood mặc định giả.
2. Nhìn thấy điều kiện được hiểu dưới dạng chips, sửa từng chip được.
3. Nhận ba ứng viên khi đủ dữ liệu, có xem thêm. Khi ít hơn ba phim hợp lệ, hiển thị số thực và giải thích.
4. Mỗi card có thời lượng, lý do theo yêu cầu, điểm có thể không hợp và dữ liệu cần để quyết định.
5. Hành động chính: “Chọn phim này”; hành động phụ: lưu, đã xem, không hợp, so sánh.
6. Khi chọn, hiện tóm tắt lựa chọn, tùy chọn lưu và nguồn xem/trailer nếu có dữ liệu được quản lý. Không biến chọn phim thành watched history.
7. “Đổi phương án” giữ các điều kiện; không yêu cầu nhập lại.

Chips phải phân biệt bắt buộc/ưu tiên bằng chữ và trạng thái, không chỉ màu. Thay đổi filter dùng cùng effective intent với chat.

## 4. Kết quả giúp quyết định

Card ưu tiên thông tin: title/year, poster, runtime, 1–2 lý do khớp, một tradeoff khi dữ liệu hỗ trợ, hành động.

Ví dụ hình thức lý do: “82 phút, đáp ứng giới hạn 90 phút; tone nhẹ nhàng theo metadata.” Đây là ví dụ UI, không phải khẳng định về phim cụ thể.

Không hiển thị “99% hợp gu” khi chưa calibration. Không đưa model names, raw scores, pipeline logs lên card.

So sánh 2–3 phim theo runtime, tone, themes, visual technique và evidence của nhu cầu hiện tại. Trường thiếu ghi chưa biết. “Chọn giúp tôi” chọn từ kết quả hợp lệ, có lý do và đổi được.

Các quick refinement dùng hành động có ý nghĩa: ngắn hơn, nhẹ nhàng hơn, khác gu hơn, bỏ thể loại, giữ/đổi phim tham chiếu. Chỉ cung cấp controls mà engine và dữ liệu thực sự hỗ trợ.

## 5. Tìm lại phim là một hành trình riêng

- Người dùng nhập manh mối; không phải khai báo gu.
- Kết quả có chi tiết khớp, năm và tên thay thế để xác nhận.
- Nếu cần làm rõ, hỏi một câu có tác dụng phân biệt các ứng viên; tránh hỏi lại điều người dùng đã nói.
- “Đúng phim này” mở detail; “chưa đúng” giữ manh mối và cho bổ sung.
- Phim đã xem hoặc không hợp gu vẫn được trả về nếu khớp danh tính.

## 6. Cá nhân hóa có ích và có quyền kiểm soát

Onboarding có thể bỏ qua: chọn vài phim thích và một vài điều muốn tránh. Có kết quả ngay bằng content profile; CF/MF bổ sung khi dữ liệu đủ.

Mỗi phản hồi có ngữ nghĩa:

| Hành động | Ảnh hưởng |
|---|---|
| Lưu watchlist | Ý định xem, không tự coi là yêu thích mạnh |
| Favorite/rating | Cập nhật gu theo signal rõ và có thể sửa/xóa |
| Đã xem | Watched history; exclude khi mode/policy yêu cầu, có rewatch |
| Không hợp hôm nay | Chỉ session hiện tại |
| Không thích thể loại này | Chỉ lưu gu lâu dài khi người dùng chọn rõ |
| Mở detail/bỏ qua | Signal yếu; không suy watched hoặc dislike |

Hiển thị “vì bạn thích X” chỉ khi ranking dùng reference/signal đó thật. Profile editor phân biệt sở thích khai báo và suy luận; reset gu suy luận không bắt buộc xóa library.

Guest dùng được discovery; đăng nhập tại thời điểm muốn đồng bộ lâu dài. Account switch/logout không lẫn dữ liệu. Lỗi backend không tạo user giả hoặc báo lưu thành công.

## 7. AI chậm, lỗi và không có kết quả

Structured discovery sử dụng filters/profile không cần Qwen parse; đây là năng lực thật của engine. Natural-language discovery dùng Qwen theo policy đã chốt.

Với tác vụ dài: xác nhận đã nhận yêu cầu, hiển thị phase thực và cho người dùng rời màn hình/quay lại job. Kết quả/evidence sẵn có được hiển thị trước optional verbalization khi pipeline cho phép; không chờ thêm một lượt LLM chỉ để diễn đạt lời mở đầu.

Không dùng tiến độ phần trăm giả hoặc spinner vô thời hạn. Cancel pending và cancel running khác nhau; UI phải phản ánh backend đã dừng hay chỉ đã nhận yêu cầu hủy.

Model/parser lỗi trả lỗi rõ; có lựa chọn chuyển sang bộ lọc thủ công. Không tự dùng deterministic parser rồi trình bày như Qwen thành công. Retry có idempotency và giới hạn.

No-results có thông tin điều kiện gây tắc khi xác định được và đề xuất thay đổi cụ thể. Người dùng xác nhận mới relax hard constraints. Thiếu dữ liệu được trình bày khác không có phim phù hợp.

## 8. Nghiệm thu usability

Mỗi vòng thử một nhóm nhỏ người dùng mục tiêu; ban đầu đề xuất 5–8 người cho quan sát định tính, không coi đó là bằng chứng thống kê đại diện. Dùng cả guest, người mới và người có profile. Không chỉ hỏi họ thích giao diện hay không.

Các task:

1. Chọn một phim cho tối nay có giới hạn thời gian.
2. Tìm lại một phim từ manh mối.
3. Chọn phim giống reference nhưng giảm một facet.
4. Sửa kết quả bằng một follow-up mà không nhập lại điều kiện.
5. So sánh và chốt một phim.
6. Lưu, sửa phản hồi, đổi tài khoản và kiểm tra dữ liệu.

Quan sát: có cần người hướng dẫn không, hiểu chips/lý do không, có biết vì sao không có kết quả không, gặp chỗ chờ/nhầm/lặp nào. Ghi task completion, time-to-choice, corrections, useful-choice confirmation và failure states.

Time-to-choice chỉ tính một lựa chọn được xác nhận; watchlist click không tự là chọn thành công. Không tối ưu tốc độ bằng cách ép người dùng chọn. Latency báo theo mode và p50/p95, tách queue/model/engine; target chốt sau baseline.

Mobile/keyboard, contrast/focus, readable typography và trạng thái không chỉ phân biệt bằng màu phải được kiểm tra trên flow hoàn chỉnh.

## 9. Ưu tiên release theo trải nghiệm

| Ưu tiên | Lát cắt | Điều kiện hoàn thành |
|---|---|---|
| UX-01 | Chọn tối nay → chips → ba kết quả → chọn/lưu | Catalog thật, constraints đúng, evidence cơ bản, loading/error và save thật |
| UX-02 | Onboarding → gợi ý theo gu → feedback → kết quả cập nhật | Profile tác động thật, session feedback tách long-term, account isolation |
| UX-03 | Tìm lại phim và tìm giống reference | Manh mối/evidence đúng, ambiguous reference được làm rõ |
| UX-04 | Refinement → compare → choose-one → đổi phương án | Giữ điều kiện, không lặp vô ích, giảm công sức quyết định |
| UX-05 | Jobs/performance và polished mobile flows | Chờ/hủy/retry có trạng thái thật, p95/capacity đo được |
| UX-06 | Group, context, why-not/counterfactual | Có nhu cầu và evidence, core flows không suy giảm |

Reliability và feedback scope triển khai từ UX-01; UX-05 tập trung tối ưu sau khi có số đo, không trì hoãn failure UX đến cuối.

AI nghiên cứu CF/MF/hybrid tiếp tục theo kế hoạch kỹ thuật, nhưng release tính năng không phải chờ tất cả experiments hoàn thành. Content-based personalization đủ bằng chứng có thể phục vụ trước; thêm model khi cải thiện relevance/coverage/cold-start thật.

Kỹ sư trưởng kiểm tra từng ticket bằng câu hỏi: người dùng đang khó ở đâu, thay đổi giảm khó thế nào, kết quả quan sát được là gì và nếu AI/data lỗi thì họ tiếp tục ra sao?
