const GENRE_LABELS: Record<string, string> = {
  action: 'Hành động',
  adventure: 'Phiêu lưu',
  animation: 'Hoạt hình',
  comedy: 'Hài',
  crime: 'Tội phạm',
  documentary: 'Tài liệu',
  drama: 'Chính kịch',
  family: 'Gia đình',
  fantasy: 'Giả tưởng',
  horror: 'Kinh dị',
  music: 'Âm nhạc',
  musical: 'Nhạc kịch',
  mystery: 'Bí ẩn',
  romance: 'Lãng mạn',
  'sci-fi': 'Khoa học viễn tưởng',
  sport: 'Thể thao',
  sports: 'Thể thao',
  thriller: 'Giật gân',
};

export function genreLabel(genre: string): string {
  const key = genre.trim().toLowerCase();
  return Object.prototype.hasOwnProperty.call(GENRE_LABELS, key) ? GENRE_LABELS[key] : genre;
}

export function formatRuntime(runtime = ''): string {
  const match = runtime.trim().match(/^(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?$/i);
  if (!match || !match.slice(1).some(Boolean)) return runtime;
  return [match[1] && `${Number(match[1])} giờ`, match[2] && `${Number(match[2])} phút`, match[3] && `${Number(match[3])} giây`]
    .filter(Boolean)
    .join(' ');
}

const DEMO_SYNOPSIS = new Map<string, string>([
  ['Tập phim hoạt hình Shin Cậu Bé Bút Chì được phát và giải mã trực tiếp từ Google Drive storage.', 'Tập phim Shin Cậu Bé Bút Chì phát từ Google Drive.'],
  ['A lone astronaut discovers that the signal guiding her home may be the final memory of a world already gone.', 'Một nữ phi hành gia lần theo tín hiệu dẫn cô về nhà. Đó có thể là ký ức cuối cùng của một thế giới đã mất.'],
  ['A young girl wanders into a magical bathhouse ruled by spirits and witches, where she must find the courage to free her parents.', 'Một cô bé lạc vào nhà tắm của các linh hồn và phù thủy. Cô phải tìm cách cứu cha mẹ.'],
  ['Two teenagers share a profound, magical connection upon discovering they are swapping bodies across time and space.', 'Hai thiếu niên phát hiện họ có thể hoán đổi thân xác dù sống ở những nơi và thời điểm khác nhau.'],
  ['Teen Miles Morales becomes the Spider-Man of his universe and crosses paths with five counterparts from other dimensions.', 'Miles Morales trở thành Người Nhện và gặp năm Người Nhện đến từ các chiều không gian khác.'],
  ['Set in dystopian Japan, a young boy journeys to Trash Island in a stop-motion quest to rescue his exiled dog Spots.', 'Một cậu bé ở Nhật Bản đến đảo rác để tìm Spots, chú chó bị đày khỏi thành phố.'],
  ['An adventurous 11-year-old girl finds another world that is a strangely idealized version of her frustrating home, but it has sinister secrets.', 'Coraline, 11 tuổi, tìm thấy một thế giới giống nhà mình đến kỳ lạ. Nơi tưởng chừng hoàn hảo ấy che giấu những bí mật đáng sợ.'],
  ['A timeless collection of animated interpretations of great works of Western classical music.', 'Tuyển tập hoạt hình lấy cảm hứng từ các tác phẩm nhạc cổ điển phương Tây.'],
  ['In a city where night never ends, a photographer follows one impossible beam of sunlight.', 'Trong thành phố chìm trong đêm, một nhiếp ảnh gia lần theo tia nắng duy nhất.'],
  ['A brilliant architect is asked to design a city that no one is meant to leave.', 'Một kiến trúc sư được giao thiết kế một thành phố mà cư dân không thể rời đi.'],
  ['Two estranged sisters cross an unmapped ocean in search of their father.', 'Hai chị em xa cách cùng vượt qua vùng biển chưa có trên bản đồ để tìm cha.'],
  ['A composer returns to the town she fled and finds an old song waiting for her.', 'Một nữ nhạc sĩ trở về thị trấn từng bỏ đi và tìm lại một ca khúc cũ.'],
  ['A detective investigates a string of elegant crimes committed at midnight.', 'Một thám tử điều tra chuỗi vụ án xảy ra đúng nửa đêm.'],
]);

export function movieSynopsis(text: string): string {
  return DEMO_SYNOPSIS.get(text) ?? text;
}
