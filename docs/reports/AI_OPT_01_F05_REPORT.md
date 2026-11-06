# BÁO CÁO KẾT QUẢ TRIỂN KHAI: AI-OPT-01-F05
## ĐỒNG BỘ KẾT QUẢ VÀ CÂU TRẢ LỜI, SỬA DỨT ĐIỂM C1/C2

> **Dự án:** Movie Recommendation System (Dippie Cinema)  
> **Mã nhiệm vụ:** `AI-OPT-01-F05`  
> **Workspace:** `D:\Class\movie-rcm-system`  
> **Branch:** `dev` | **Baseline Commit:** `8ac4aeb2f4e789c994a7fdf7efd62841a90bda22`  
> **Ngày hoàn thành:** 2026-10-20  
> **Trạng thái:** **HOÀN THÀNH (10/10 Live HTTP Cases PASS | 128/128 Unit Tests PASS)**

---

## 1. TỔNG QUAN NHIỆM VỤ

Nhiệm vụ **AI-OPT-01-F05** giải quyết dứt điểm 2 vấn đề trọng yếu được nêu trong `docs/reviews/AI_OPT_01_F04_REVIEW.md`:
1. **Lỗi C1 (Đồng bộ ranh giới quyết định kết quả):** Khi hệ thống không có căn cứ trả lời, không được vừa nói “không tìm thấy” trong text vừa đưa card phim không khớp ở `recommendedMovies` hay gợi ý ở `followUps`. Cùng một kết quả grounding phải quyết định cả text lẫn cards/followups.
2. **Lỗi C2 (Xác thực tình tiết ngắn 2 từ & Bảo vệ động từ chung):** Phân biệt động từ chung với thực thể cụ thể; không được khẳng định tìm đúng tình tiết “chơi bóng” chỉ vì tiêu đề có từ “chơi” (như tập 15 *"Đừng chơi, hãy học"*) hoặc chỉ vì từ “bóng” xuất hiện trong cụm từ bóng đá. Thiếu dữ liệu thì abstain và trả 0 card như C1; có fixture chơi bóng thật thì chấp nhận đúng.

---

## 2. RANH GIỚI VÀ CAM KẾT TUÂN THỦ

| Hạng mục cam kết | Trạng thái tuân thủ | Minh chứng kiểm chứng |
|---|:---:|---|
| **Giữ nguyên base model & adapter Phase 23** | **TUÂN THỦ 100%** | Giữ nguyên toàn bộ file trọng số, config và tokenizer trên đĩa tại `ai/models/qwen3-4b-phase23-lora`. |
| **0 model call phụ cho giải thích** | **TUÂN THỦ 100%** | Chỉ duy nhất 1 lần gọi model Phase 23 cho bước NLU Intent Parser; tầng giải thích sinh bằng logic và template chuẩn hóa. |
| **Bảo toàn Schema & 5 Contract Files** | **TUÂN THỦ 100%** | Schema `dippie.catalog.v1` và 5 file contract giữ nguyên từng byte, không sửa đổi. |
| **Không sửa Catalog để làm đẹp kết quả** | **TUÂN THỦ 100%** | Giữ nguyên snapshot dữ liệu `data/catalog.jadoo_all.json`. |
| **Không commit / Không push Git** | **TUÂN THỦ 100%** | Nhánh `dev` giữ nguyên ở baseline `8ac4aeb2f4e789c994a7fdf7efd62841a90bda22`, toàn bộ file ở dạng working tree. |
| **Tài nguyên GPU & Hệ thống** | **TUÂN THỦ 100%** | Đã dừng toàn bộ background server sau khi kiểm thử; GPU VRAM (101 MiB idle) và cổng 8000 sạch 100%. |
| **Tính minh bạch Playback** | **GHI NHẬN RÕ RÀNG** | Ghi chú minh bạch `browser_playback: "UNVERIFIED"` trong evidence và báo cáo. |

---

## 3. CHI TIẾT SỬA ĐỔI KỸ THUẬT

### 3.1. `backend/fastapi/services/ai_pipeline.py`
1. **Thiết lập Single Decision Boundary (C1):**
   - Đưa hàm `ExplanationGeneratorNode.evaluate_candidate_grounding(movie, nlu_output, query) -> Tuple[bool, str]` làm nguồn chân lý duy nhất đánh giá tính hợp lệ của từng candidate.
   - Trong `CascadingAIPipeline.run()`, lọc danh sách ứng viên sau Stage 4 để thu được `grounded_top`:
     ```python
     grounded_top = []
     for m in ranked_top:
         is_grounded, _reason = self.explainer_node.evaluate_candidate_grounding(m, nlu_result, query)
         if is_grounded:
             grounded_top.append(m)
     ```
   - Cả 5 trường payload trả về đều đồng bộ từ `grounded_top`:
     - `text = self.explainer_node.generate_explanation(grounded_top, ...)`
     - `recommendedMovies = grounded_top`
     - `pipelineStages.rankedCount = len(grounded_top)`
     - `pipelineStages.diagnostics = [m.get("diagnostics") for m in grounded_top if m.get("diagnostics")]`
     - `followUps = self._build_follow_ups(nlu_result, grounded_top)`
   - Khi `not grounded_top`, `_build_follow_ups` trả về các gợi ý trung tính không chứa tên tập phim bị từ chối:
     `["Gợi ý các tập phim hoạt hình nổi bật", "Tìm theo mùa hoặc số tập cụ thể (ví dụ: Mùa 1 Tập 1)", "Tìm theo thể loại gia đình hoặc hài hước"]`.

2. **Xác thực tình tiết 2 từ và phân biệt động từ hành động (C2):**
   - Bổ sung tập hợp `GENERIC_ACTION_VERBS` (`chơi`, `ăn`, `đi`, `làm`, `xem`, `học`, `mua`, `bán`, `chạy`, ...).
   - Với truy vấn 2 từ (`len(content_words) == 2`): bắt buộc phải có đủ 2 từ khóa xuất hiện trong metadata (`len(matched_content) >= 2`). Nếu chỉ trùng 1 từ đơn lẻ (như chỉ có từ "chơi" hay chỉ có từ "bóng"), ứng viên bị từ chối với lý do `insufficient_content_overlap`.
   - Với mệnh đề phủ định chứa số tập ngoài danh mục (`không phải tập 999`), kiểm tra số tập ngoài khoảng chỉ kích hoạt trên `pos_scope` (mệnh đề khẳng định).

3. **`backend/fastapi/services/hybrid_retrieval.py`:**
   - Cập nhật pattern nhận diện phủ định bổ sung các cụm `không có`, `không chứa` để tách triệt để các điều kiện phủ định khỏi token tìm kiếm BM25 và Dense.

---

## 4. KẾT QUẢ KIỂM THỬ XÁC MINH

### 4.1. Unit Test Suites (`pytest`)
- Chạy toàn bộ 8 file test suites:
  - `tests/test_repro_f05.py`: **9/9 PASSED**
  - `tests/test_repro_f04.py`: **10/10 PASSED**
  - `tests/test_repro_f03.py`: **13/13 PASSED**
  - `tests/test_explanation_f02.py`: **12/12 PASSED**
  - `tests/test_parser_telemetry_f02.py`: **8/8 PASSED**
  - `tests/test_retrieval_f02.py`: **8/8 PASSED**
  - `tests/test_repro_f02_adversarial.py`: **7/7 PASSED**
  - `tests/test_adversarial_retrieval.py`: **61/61 PASSED**
- **Tổng cộng:** **128/128 tests PASSED 100%**, không có bất kỳ regression nào.

### 4.2. Live HTTP Verification qua Server Thật (`verify_web_f05_pipeline.py`)
Khởi chạy FastAPI full serving mode với GPU CUDA (`qwen3-4b-peft-lora-4bit-nf4`) và chạy bộ 10 ca kiểm chứng HTTP thực tế:
- **10/10 test cases PASSED 100%**:
  1. `f05_b1_q01_generic_family_comedy` (*"Tìm phim hoạt hình gia đình hài hước"*): **PASS** (3 cards).
  2. `f05_b1_q02_fun_for_family` (*"Gợi ý hoạt hình vui nhộn cho gia đình"*): **PASS** (3 cards).
  3. `f05_b1_q03_doraemon_abstention` (*"Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối"*): **PASS** (0 cards, từ chối franchise ngoại lai).
  4. `f05_b2_q04_negation_scope_not_exact` (*"Jadoo chơi bóng, không phải tập 999"*): **PASS** (0 cards, từ chối trung thực do catalog không có tập chơi bóng; không bịa tập 15 hay tập 11; followUps trung tính).
  5. `f05_b2_q05_plot_real_grounding` (*"Tập nào Jadoo muốn ăn ngon nhưng sợ bị tăng cân"*): **PASS** (1 card: `ep_jadoo_s01_0002` khớp chuẩn xác).
  6. `f05_b2_q06_plot_fabricated_ungrounded` (*"Tập nào Jadoo lái tàu ngầm xuống đáy đại dương bắt cá mập trắng khổng lồ"*): **PASS** (0 cards, rankedCount=0, từ chối trung thực; followUps không chứa ep 8 hay các card bị loại bỏ).
  7. `f05_ctrl_q07_exact_title`: **PASS** (1 card: `ep_jadoo_s01_0001`).
  8. `f05_ctrl_q08_exact_season_ep`: **PASS** (1 card: `ep_jadoo_s01_0001`).
  9. `f05_ctrl_q09_segment`: **PASS** (1 card: `seg_jadoo_s01_008a`).
  10. `f05_ctrl_q10_condition_violence`: **PASS** (1 card: `ep_jadoo_s06_0006`, bảo lưu dữ liệu bạo lực chưa xác minh).

- Bằng chứng JSON chi tiết: [`docs/reviews/evidence/AI_OPT_01_F05_WEB_VERIFICATION.json`](file:///D:/Class/movie-rcm-system/docs/reviews/evidence/AI_OPT_01_F05_WEB_VERIFICATION.json).

---

## 5. TÀI LIỆU VÀ TRẠNG THÁI BÀN GIAO

1. **Báo cáo và đánh giá bàn giao:**
   - [`docs/reports/AI_OPT_01_F05_REPORT.md`](file:///D:/Class/movie-rcm-system/docs/reports/AI_OPT_01_F05_REPORT.md)
   - [`docs/reviews/AI_OPT_01_F05_CROSS_REVIEW.md`](file:///D:/Class/movie-rcm-system/docs/reviews/AI_OPT_01_F05_CROSS_REVIEW.md)
   - [`docs/reports/AI_OPT_01_F05_STATUS.json`](file:///D:/Class/movie-rcm-system/docs/reports/AI_OPT_01_F05_STATUS.json)
   - [`docs/reviews/evidence/AI_OPT_01_F05_WEB_VERIFICATION.json`](file:///D:/Class/movie-rcm-system/docs/reviews/evidence/AI_OPT_01_F05_WEB_VERIFICATION.json)
2. **Trạng thái hệ thống:**
   - Cổng 8000 đã giải phóng hoàn toàn.
   - Bộ nhớ GPU VRAM sạch sẽ (101 MiB).
   - Zero commits, zero pushes. Sẵn sàng bàn giao cho người dùng chạy thử trực tiếp trên Web.
