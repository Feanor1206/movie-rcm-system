# Đánh giá bản dùng thử F05

Ngày 20/10/2026. Chấp nhận bản dùng thử trong phạm vi C1/C2; không xác nhận production-ready hoặc mọi truy vấn đều đúng.

## Kết quả

Quyết định `evaluate_candidate_grounding` được áp dụng trước khi trả kết quả: text, recommendedMovies, rankedCount, diagnostics và followUps dùng cùng grounded_top. Hai ca đã chặn F04 (chơi bóng không có căn cứ và tình tiết tàu ngầm/cá mập) hiện có text từ chối, không card và follow-up trung tính trong evidence HTTP. Positive fixture chơi bóng có dữ liệu thật vẫn có kết quả.

Đã đối chiếu code, verifier và đủ 10 responses của `AI_OPT_01_F05_WEB_VERIFICATION.json`; bốn source hash prefix trong status khớp. Các ca thể loại gia đình, Doraemon, đúng tên tập, đúng mùa/tập, segment và giới hạn dữ liệu bạo lực có kết quả phù hợp phạm vi dùng thử. Chạy lại tám suite: 128 passed in 135.85s; regression snapshot ownership: 5/5 pass.

## Giới hạn và đính chính

- Bảng tóm tắt bàn giao ghi 1 card cho exact title, mùa/tập, segment và điều kiện bạo lực không khớp raw evidence: các ca đó lần lượt trả 2, 3, 3 và 3 card. Top result đúng ca kiểm soát; card phụ vẫn có thể không đáp ứng toàn bộ yêu cầu. Chưa xác nhận strict filtering cho mọi kiểu truy vấn.
- Guard grounding vẫn là heuristic từ khóa; chưa phải chứng minh hiểu mọi tình tiết hay đồng nghĩa. Không diễn giải thiếu dữ liệu catalog thành chắc chắn phim không có tình tiết đó.
- Không xác nhận các mức tăng tốc lịch sử cho code F05: bằng chứng lần này kiểm hành vi; max_new_tokens hiện là 512. Chưa đo lại hiệu năng đối chiếu.
- Một số test dùng catalog Jadoo riêng tại `data/catalog.jadoo_all.json` và encoder trong cache. Chúng là kiểm tra môi trường địa phương; catalog/cache không được đưa vào Git. Không coi chúng là CI tự chứa.
- Không chạy lại server/GPU inference, UI hoặc Drive; bằng chứng HTTP là lượt chạy được bàn giao. Browser playback vẫn UNVERIFIED cho nhiệm vụ này.
- Không đưa launcher thử nghiệm `scripts/run_fastapi.ps1` có sync secret cố định, dữ liệu runtime, benchmark chứa dữ liệu riêng hoặc thay đổi `.env.example` ngoài phạm vi vào commit.

Những giới hạn trên không chặn lưu bản dùng thử đã sửa C1/C2. Bước tiếp theo phù hợp là dùng thử trên web với dữ liệu thực, ghi lại query/result chưa đúng; không cần mở thêm đợt refactor chung.
