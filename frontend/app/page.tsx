'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight, ArrowRight, BookOpen, Bookmark, MessageCircle, RefreshCw } from 'lucide-react';
import { Navbar } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';
import { MovieSection } from '@/features/movies/components/MovieSection';
import { browseCatalog } from '@/lib/services/catalogService';
import { useWatchlist } from '@/lib/context/WatchlistContext';
import type { Movie } from '@/types/movie';

const chapters = [
  { number: '01', title: 'Một chuyến phiêu lưu', note: 'Đi xa một chút, tưởng tượng nhiều hơn.', genre: 'Adventure' },
  { number: '02', title: 'Cười cùng nhau nhé', note: 'Những chuyện bé xíu, những niềm vui to.', genre: 'Comedy' },
  { number: '03', title: 'Góc nhỏ gia đình', note: 'Có những câu chuyện giống như một cái ôm.', genre: 'Family' },
];

export default function HomePage() {
  const { openChat, watchlist } = useWatchlist();
  const [recent, setRecent] = useState<Movie[]>([]);
  const [favorites, setFavorites] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(false);
    Promise.all([
      browseCatalog({ animationOnly: true, sort: 'year', direction: 'desc', size: 8, signal: controller.signal }),
      browseCatalog({ animationOnly: true, sort: 'rating', direction: 'desc', size: 8, signal: controller.signal }),
    ]).then(([a,b]) => { if (!controller.signal.aborted) { setRecent(a.items); setFavorites(b.items); setLoading(false); } })
      .catch((e) => { if (!controller.signal.aborted && e?.name !== 'AbortError' && !e?.isCanceled) { setError(true); setLoading(false); } });
    return () => controller.abort();
  }, [retry]);
  return <>
    <Navbar />
    <main className="comic-book">
      <div className="edition-line"><span>MỘT GÓC NHỎ DÀNH CHO TRÍ TƯỞNG TƯỢNG</span><span>HOẠT HÌNH · NHỮNG CÂU CHUYỆN · BẠN</span></div>
      <section className="cover-grid" aria-labelledby="cover-title">
        <div className="cover-copy">
          <span className="chapter-kicker"><span className="ink-square" /> CHƯƠNG MỚI, NIỀM VUI MỚI</span>
          <h1 id="cover-title">Lật một trang.<br/>Mở một trời<br/><em>phiêu lưu.</em><svg aria-hidden="true" viewBox="0 0 260 18"><path d="M3 11Q120-2 255 9M30 16Q136 5 238 14" fill="none" stroke="currentColor" strokeWidth="3"/></svg></h1>
          <p>Gác lại bộn bề. Ghé vào thế giới hoạt hình,<br className="hidden sm:block"/> nơi những điều nhỏ bé cũng trở nên diệu kỳ.</p>
          <Link href="/search" className="cover-cta">Bắt đầu khám phá <ArrowUpRight size={19}/></Link>
          <div className="cover-footnote"><span className="hand-arrow">↳</span> Không cần lớn lên hôm nay.</div>
        </div>
        <div className="cover-art-panel"><div className="panel-index">KHUNG HÌNH / 01</div><img src="/illustrations/dippie-cover.svg" alt="Nét vẽ truyện tranh: một bạn nhỏ và thỏ mang sách đi qua khu rừng xanh đến rạp chiếu phim" width="760" height="580"/><div className="art-caption"><span>Đích đến: một thế giới khác.</span><span>TO BE CONTINUED…</span></div></div>
      </section>
      <div className="story-strip"><span>CHUYỆN HÔM NAY</span><p>Một bộ phim hay. Một chiếc ghế êm. Thế là đủ.</p><span className="strip-star" aria-hidden="true">✳</span></div>
      <section className="chapter-grid" aria-label="Mục lục khám phá">
        {chapters.map((c) => <Link key={c.number} href={`/search?genre=${c.genre}`} className="chapter-panel"><span className="chapter-number">{c.number}</span><div><span className="chapter-small">LẬT ĐẾN CHƯƠNG</span><h2>{c.title}</h2><p>{c.note}</p></div><ArrowUpRight size={22} className="chapter-link-icon"/></Link>)}
      </section>
      <div className="catalog-chapter-head"><span className="chapter-kicker">TRÊN KỆ PHIM</span><span className="page-number">TRANG 02 — 03</span></div>
      {loading ? <div className="comic-loading" role="status"><BookOpen size={26}/><p>Đang sắp những câu chuyện lên kệ…</p></div> : error ? <div className="comic-loading" role="alert"><BookOpen size={26}/><p>Kệ phim đang nghỉ một chút. Bạn thử mở lại nhé.</p><button className="btn-secondary" onClick={() => setRetry(n=>n+1)}><RefreshCw size={15}/>Tải lại kệ phim</button></div> : <>
        <MovieSection title="Những câu chuyện mới" subtitle="Chọn một khung hình. Bắt đầu một câu chuyện." movies={recent} exploreHref="/search?sort=year"/>
        <MovieSection title="Để dành một buổi chiều" subtitle="Thêm vào danh sách để không bỏ lỡ lần ghé thăm sau." movies={favorites} exploreHref="/search?sort=rating"/>
      </>}
      <section className="closing-panels">
        <div className="reading-note"><span className="chapter-kicker">GHI CHÚ BÊN LỀ</span><h2>Chưa biết xem gì?<br/><em>Kể tớ nghe.</em></h2><p>Một tình tiết bạn nhớ, một nhân vật bạn thích.<br/>CineBot sẽ cùng bạn tìm lại câu chuyện ấy.</p><button className="text-action" onClick={openChat}>Trò chuyện với CineBot <MessageCircle size={18}/></button><span className="note-doodle" aria-hidden="true">✳</span></div>
        <Link href="/profile" className="bookmark-note"><Bookmark size={30} strokeWidth={1.3}/><span className="chapter-kicker">KẸP TRANG CỦA BẠN</span><h2>Hẹn ở<br/>chương sau.</h2><p>{watchlist.length ? `${watchlist.length} câu chuyện đang chờ bạn quay lại.` : 'Giữ lại những bộ phim bạn muốn xem.'}</p><span className="text-action">Mở danh sách xem <ArrowRight size={18}/></span></Link>
      </section>
      <div className="end-page"><span>HẾT TRANG. CHƯA HẾT CHUYỆN.</span><span aria-hidden="true">✦</span><span>DIPPIE / MỘT THẾ GIỚI NHO NHỎ</span></div>
    </main><Footer/>
  </>;
}
