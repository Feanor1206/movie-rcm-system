# Storage priority update — 14/10/2026

User clarification mới nhất: ưu tiên phát/tua mượt tối đa; RAM/CPU/GPU không phải mối lo, có thể mua thêm ổ cứng nếu measurement chứng minh cần. Quyết định này cập nhật ưu tiên trong DRIVE_MEDIA_STORAGE_DESIGN.md nhưng không thay đổi frozen artifact của Round10.

Chưa cần mua hoặc lắp ổ. Sau M3, spike storage đo RAM-only/read-only mount cache-off trước, so bounded SSD disk-cache nếu có dung lượng thật cho thử nghiệm được phép. Chọn theo startup/seek/stall/concurrency và disk growth, không theo một thông số cache hoặc cảm giác. Capacity đo cả internet uplink/quota: ổ lớn hơn không tự giải quyết các giới hạn đó.

Nếu disk cache cải thiện đáng kể và ổ hiện tại không đủ safe headroom, report working-set/cache allocated thực, peak growth, free-space reserve và lợi ích before/after rồi đề xuất dung lượng SSD cần thêm; người dùng quyết định mua. Không tự đổi mount, sync toàn kho, cài WinFsp/OAuth hoặc thay filesystem/OS settings. Không tự chuyển phần storage vào vòng M3 đang sửa. Không tuyên bố đã tối ưu hoặc phát mượt trước benchmark media thực.
