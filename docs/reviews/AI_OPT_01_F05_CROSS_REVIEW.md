# ĐÁNH GIÁ CHÉO KIỂM THỬ VÀ HÀNH VI (CROSS-REVIEW): AI-OPT-01-F05

> **Mã nhiệm vụ:** AI-OPT-01-F05  
> **Workspace:** `D:\Class\movie-rcm-system`  
> **Branch:** `dev` | **Git Baseline:** `8ac4aeb2f4e789c994a7fdf7efd62841a90bda22`  
> **Thời điểm xác minh:** 2026-10-20  
> **Tài liệu đầu vào đối chiếu:** `docs/reviews/AI_OPT_01_F04_REVIEW.md` (2 phát hiện trọng yếu: C1 và C2)

---

## 1. MỤC TIÊU & QUY TẮC BẢO TOÀN KIẾN TRÚC

Nhiệm vụ F05 tập trung giải quyết dứt điểm 2 lỗi còn tồn đọng từ đợt đánh giá F04:
1. **C1 (Đồng bộ quyết định từ chối giữa Text và Cards):** Khi hệ thống không có căn cứ trả lời, không được vừa nói “không tìm thấy” trong text vừa đưa card phim không khớp ở `recommendedMovies` hay gợi ý ở `followUps`. Cùng một boundary quyết định căn cứ (`evaluate_candidate_grounding`) phải chi phối đồng nhất: `recommendedMovies` (`[]`), lời giải thích (`text`), số lượng kết quả (`rankedCount = 0`), và câu gợi ý tiếp theo (`followUps` trung tính, không chứa tên tác phẩm bị từ chối). Nếu chỉ một số candidate có căn cứ, chỉ giữ lại các candidate đó.
2. **C2 (Xác thực tình tiết ngắn 2 từ & Bảo vệ động từ chung):** Với truy vấn tình tiết ngắn gồm 2 từ mang tính hành động + đối tượng (ví dụ: `"Jadoo chơi bóng, không phải tập 999"`), việc chỉ khớp một động từ chung (như `"chơi"` trong tiêu đề tập 15 *"Đừng chơi, hãy học"*) hoặc chỉ khớp danh từ phụ (`"bóng"` trong tập ăn kiêng gặp huyền thoại bóng đá Cha Bum-kun) mà thiếu đối tượng/hành động tương ứng tuyệt đối không được coi là có căn cứ (grounded). Phân biệt rõ động từ chung với thực thể cụ thể; khi không có dữ liệu thật trong catalog thì phải từ chối (abstain) và trả card rỗng như C1. Đồng thời kiểm tra qua positive fixture để đảm bảo tập có hành động thật được chấp nhận bình thường.

### Ranh giới tuân thủ nghiêm ngặt:
- **0 model call phụ:** Toàn bộ quá trình đánh giá căn cứ và sinh giải thích dùng quy tắc logic chuẩn hóa; giữ nguyên 1 model call duy nhất ở Tầng 1 (Phase 23 NLU Parser).
- **Trọng số & Schema bất biến:** Giữ nguyên base model `Qwen/Qwen3-4B`, LoRA adapter Phase 23 trên đĩa, schema `dippie.catalog.v1` và 5 file contract 100% nguyên vẹn từng byte.
- **Git Invariant:** Không commit, không push Git; bảo toàn working tree.
- **Tính minh bạch:** Khẳng định rõ tình trạng playback video / browser UI là `UNVERIFIED` do kiểm tra trực tiếp qua HTTP API production.
- **Tài nguyên:** Giải phóng toàn bộ cổng 8000 và bộ nhớ GPU VRAM sau khi hoàn tất kiểm thử.

---

## 2. PHÂN TÍCH KỸ THUẬT VÀ GIẢI PHÁP TRIỂN KHAI

### 2.1. Khắc phục C1 (Synchronized Decision Boundary)
- **Vấn đề ở F04:** Trong `ai_pipeline.py`, Tầng 5 (`ExplanationGeneratorNode`) sinh chuỗi `"Hiện chưa tìm thấy tập phim nào có tình tiết phù hợp..."` khi thiếu overlap, nhưng `CascadingAIPipeline.run()` vẫn gán `recommendedMovies = ranked_top` và sinh `followUps` từ `ranked_top`. Người dùng trên giao diện vừa đọc thấy câu "chưa tìm thấy" vừa nhìn thấy 3 card phim không liên quan (như tập 8, tập 21).
- **Giải pháp chuẩn hóa:**
  - Thiết lập hàm thẩm định căn cứ duy nhất: `ExplanationGeneratorNode.evaluate_candidate_grounding(movie, nlu_output, query) -> Tuple[bool, str]`.
  - Trong `CascadingAIPipeline.run()`, ngay sau Tầng 4 (Ranker), hệ thống lọc toàn bộ ứng viên qua hàm này để tạo ra `grounded_top`:
    ```python
    grounded_top = []
    for m in ranked_top:
        is_grounded, _reason = self.explainer_node.evaluate_candidate_grounding(m, nlu_result, query)
        if is_grounded:
            grounded_top.append(m)
    ```
  - Cả 5 thành phần đầu ra đều đồng bộ từ `grounded_top`:
    1. `explanation_text = self.explainer_node.generate_explanation(grounded_top, ...)`
    2. `"recommendedMovies": grounded_top`
    3. `"rankedCount": len(grounded_top)`
    4. `"diagnostics": collected_diagnostics (từ grounded_top)`
    5. `"followUps": self._build_follow_ups(nlu_result, grounded_top)`
  - Khi `not grounded_top`, `_build_follow_ups` trả về các gợi ý trung tính thay vì chứa tên các tập phim bị loại trừ:
    - `"Gợi ý các tập phim hoạt hình nổi bật"`
    - `"Tìm theo mùa hoặc số tập cụ thể (ví dụ: Mùa 1 Tập 1)"`
    - `"Tìm theo thể loại gia đình hoặc hài hước"`

### 2.2. Khắc phục C2 (Short Plot Verification & Action/Object Guard)
- **Vấn đề ở F04:** Đối với truy vấn 2 từ như `"Jadoo chơi bóng"`, sau khi trừ stopwords còn `['chơi', 'bóng']`. Do logic cũ chỉ xét threshold overlap với `len(content_words) >= 3`, nên với 2 từ, chỉ cần 1 từ bất kỳ trùng tiêu đề (như từ `"chơi"` trong tập 15 *"Đừng chơi, hãy học"*) là đã coi là match.
- **Giải pháp chuẩn hóa trong `evaluate_candidate_grounding()`:**
  - Khởi tạo tập hợp động từ hành động chung `GENERIC_ACTION_VERBS = {"chơi", "ăn", "đi", "làm", "xem", "nói", "thấy", "học", "mua", "bán", "chạy", ...}`.
  - Phân tách `content_words` thành `specific_entities` (không thuộc động từ chung) và generic verbs.
  - Đối với truy vấn tình tiết 2 từ (`len(content_words) == 2`):
    - Bắt buộc phải có đủ cả 2 từ khóa xuất hiện trong metadata (`len(matched_content) >= 2`).
    - Nếu chỉ có 1 từ (chỉ có động từ `"chơi"` mà không có `"bóng"`, hoặc chỉ có `"bóng"` trong cụm bóng đá mà không có hành động `"chơi"`), hệ thống lập tức từ chối với lý do `"insufficient_content_overlap"`.
  - Đối với truy vấn mệnh đề phủ định có chứa số tập ngoài catalog (`"không phải tập 999"`):
    - Đảm bảo nhánh kiểm tra số tập ngoài khoảng chỉ áp dụng cho `pos_scope` (mệnh đề khẳng định). Số tập trong mệnh đề phủ định không làm biến đổi truy vấn tình tiết thành lỗi out-of-range season/episode.

---

## 3. KẾT QUẢ KIỂM THỬ VÀ BẰNG CHỨNG THỰC TẾ

### 3.1. Bộ kiểm thử Unit & Regression (`pytest`)
Chạy toàn bộ 8 test suites trên Python 3.13:
- `tests/test_repro_f05.py`: **9/9 PASSED** (C1 abstention empty cards & neutral followups, C2 2-token verb guard, C2 positive ball-playing fixture, C2 multi-series Pororo, controls exact title/season-ep/genre/segment/Doraemon).
- `tests/test_repro_f04.py`: **10/10 PASSED** (B1/B2 regression).
- `tests/test_repro_f03.py`: **13/13 PASSED** (R1/R2/R3 regression).
- `tests/test_explanation_f02.py`: **12/12 PASSED**.
- `tests/test_parser_telemetry_f02.py`: **8/8 PASSED**.
- `tests/test_retrieval_f02.py`: **8/8 PASSED**.
- `tests/test_repro_f02_adversarial.py`: **7/7 PASSED**.
- `tests/test_adversarial_retrieval.py`: **61/61 PASSED**.
- **Tổng cộng:** **128/128 tests PASSED 100% (0 fail, 0 error)**.

### 3.2. Kiểm thử End-to-End qua HTTP Production Server (`verify_web_f05_pipeline.py`)
Khởi chạy FastAPI full serving mode với model Qwen3-4B LoRA NF4 trên GPU CUDA RTX 3050 và chạy 10 kịch bản kiểm chứng:

| STT | Case ID | Query Thực Tế | Cards Trả Về | Ranked Count | FollowUps | Trạng Thái Phản Hồi & Giải Thích | Verdict |
|---|---|---|:---:|:---:|---|---|:---:|
| 01 | `f05_b1_q01_generic_family_comedy` | *"Tìm phim hoạt hình gia đình hài hước"* | 3 cards (`seg_022b`) | 3 | Gợi ý theo tập | Tiểu phẩm hoạt hình gia đình phù hợp | **PASS** |
| 02 | `f05_b1_q02_fun_for_family` | *"Gợi ý hoạt hình vui nhộn cho gia đình"* | 3 cards (`ep_0012`) | 3 | Gợi ý theo tập | Tập phim vui nhộn trong catalog | **PASS** |
| 03 | `f05_b1_q03_doraemon_abstention` | *"Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối"* | EMPTY (0) | 0 | Trung tính | Từ chối franchise ngoài catalog | **PASS** |
| 04 | `f05_b2_q04_negation_scope_not_exact` | *"Jadoo chơi bóng, không phải tập 999"* | **EMPTY (0)** | **0** | **Trung tính** | **Từ chối trung thực (không có tập chơi bóng, không trả ep 15 hay ep 11)** | **PASS** |
| 05 | `f05_b2_q05_plot_real_grounding` | *"Tập nào Jadoo muốn ăn ngon nhưng sợ bị tăng cân"* | 1 card (`ep_0002`) | 1 | Gợi ý theo tập | Khớp đúng tập *"Muốn ăn nhưng lại sợ tăng cân"* | **PASS** |
| 06 | `f05_b2_q06_plot_fabricated_ungrounded` | *"Tập nào Jadoo lái tàu ngầm xuống đáy đại dương bắt cá mập trắng khổng lồ"* | **EMPTY (0)** | **0** | **Trung tính (không có ep 8)** | **Từ chối trung thực, tuyệt đối không trả card không khớp** | **PASS** |
| 07 | `f05_ctrl_q07_exact_title` | *"Tìm tập Anh sẽ mua cho em tất cả những gì em muốn ăn"* | 1 card (`ep_0001`) | 1 | Gợi ý theo tập | Trả đúng Mùa 1, Tập 1 | **PASS** |
| 08 | `f05_ctrl_q08_exact_season_ep` | *"Xin Chào Jadoo Mùa 1 Tập 1"* | 1 card (`ep_0001`) | 1 | Gợi ý theo tập | Trả đúng Mùa 1, Tập 1 | **PASS** |
| 09 | `f05_ctrl_q09_segment` | *"Truyện ngắn Cứu cá vàng và cuộc tình với chàng Romy"* | 1 card (`seg_008a`) | 1 | Gợi ý theo tập | Trả đúng tiểu phẩm, ghi nhận thuộc tập cha | **PASS** |
| 10 | `f05_ctrl_q10_condition_violence` | *"Phim hoạt hình Jadoo phát hành năm 2021 không có bạo lực"* | 1 card (`ep_s06_0006`) | 1 | Gợi ý theo tập | Kèm ghi chú bảo lưu dữ liệu an toàn/bạo lực chưa xác minh | **PASS** |

**Tổng kết:** **10/10 Live HTTP Cases PASSED 100%**.  
File bằng chứng JSON lưu tại: [`docs/reviews/evidence/AI_OPT_01_F05_WEB_VERIFICATION.json`](file:///D:/Class/movie-rcm-system/docs/reviews/evidence/AI_OPT_01_F05_WEB_VERIFICATION.json).

---

## 4. KẾT LUẬN

1. Lỗi C1 được giải quyết triệt để tại boundary quyết định kết quả (`CascadingAIPipeline.run` & `evaluate_candidate_grounding`). Khi câu trả lời là không tìm thấy, `recommendedMovies` bảo đảm là `[]`, `rankedCount = 0`, và `followUps` không còn lộ danh sách card bị loại trừ.
2. Lỗi C2 được giải quyết dứt điểm: phân biệt rõ động từ chung và thực thể cụ thể; truy vấn 2 từ không còn bị lọt do trùng 1 từ đơn lẻ trong tiêu đề. Catalog không có tập chơi bóng thì từ chối trung thực với 0 card; fixture có chơi bóng thật vẫn được chấp nhận chính xác.
3. Toàn bộ tài nguyên máy chủ và GPU VRAM đã được thu hồi sạch sẽ; hệ thống sẵn sàng bàn giao cho người dùng chạy thử.
