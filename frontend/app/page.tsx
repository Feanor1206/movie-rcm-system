'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight, ArrowRight, BookOpen, Bookmark, MessageCircle, RefreshCw } from 'lucide-react';
import { Navbar } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';
import { SeriesShelf } from '@/features/series/SeriesShelf';
import { ContinueWatching } from '@/features/series/ContinueWatching';
import { getCatalogSeriesList, type CatalogSeriesSummary } from '@/lib/services/catalogService';
import { useWatchlist } from '@/lib/context/WatchlistContext';

const chapters = [
  { number: '01', title: 'Một chuyến phiêu lưu', note: 'Đi xa một chút, tưởng tượng nhiều hơn.' },
  { number: '02', title: 'Cười cùng nhau nhé', note: 'Những chuyện bé xíu, những niềm vui to.' },
  { number: '03', title: 'Góc nhỏ gia đình', note: 'Có những câu chuyện giống như một cái ôm.' },
];

export default function HomePage() {
  const { openChat, watchlist } = useWatchlist();
  const [series, setSeries] = useState<CatalogSeriesSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(false);
    getCatalogSeriesList(undefined, controller.signal)
      .then((items) => { if (!controller.signal.aborted) { setSeries(items); setLoading(false); } })
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
      <div className="story-strip"><span>CHUYỆN HÔM NAY</span><p>Một bộ hoạt hình hay. Một chiếc ghế êm. Thế là đủ.</p><span className="strip-star" aria-hidden="true">✳</span></div>
      <section className="chapter-grid" aria-label="Mục lục khám phá">
        {chapters.map((c) => <Link key={c.number} href="/search" className="chapter-panel"><span className="chapter-number">{c.number}</span><div><span className="chapter-small">LẬT ĐẾN CHƯƠNG</span><h2>{c.title}</h2><p>{c.note}</p></div><ArrowUpRight size={22} className="chapter-link-icon"/></Link>)}
      </section>
      <ContinueWatching />
      <div className="catalog-chapter-head"><span className="chapter-kicker">TRÊN KỆ HOẠT HÌNH</span><span className="page-number">BỘ · MÙA · TẬP</span></div>
      {loading ? <div className="comic-loading" role="status"><BookOpen size={26}/><p>Đang sắp những câu chuyện lên kệ…</p></div> : error ? <div className="comic-loading" role="alert"><BookOpen size={26}/><p>Kệ truyện đang nghỉ một chút. Bạn thử mở lại nhé.</p><button className="btn-secondary" onClick={() => setRetry(n=>n+1)}><RefreshCw size={15}/>Tải lại kệ truyện</button></div> : <SeriesShelf series={series} title="Những bộ hoạt hình trong kho" subtitle="Chọn một bộ để xem mùa và tập." />}
      <section className="closing-panels">
        <div className="reading-note"><span className="chapter-kicker">GHI CHÚ BÊN LỀ</span><h2>Chưa biết xem gì?<br/><em>Kể tớ nghe.</em></h2><p>Một tình tiết bạn nhớ, một nhân vật bạn thích.<br/>CineBot sẽ cùng bạn tìm lại câu chuyện ấy.</p><button className="text-action" onClick={openChat}>Trò chuyện với CineBot <MessageCircle size={18}/></button><span className="note-doodle" aria-hidden="true">✳</span></div>
        <Link href="/profile" className="bookmark-note"><Bookmark size={30} strokeWidth={1.3}/><span className="chapter-kicker">KẸP TRANG CỦA BẠN</span><h2>Hẹn ở<br/>chương sau.</h2><p>{watchlist.length ? `${watchlist.length} câu chuyện đang chờ bạn quay lại.` : 'Giữ lại những bộ hoạt hình bạn muốn xem.'}</p><span className="text-action">Mở danh sách xem <ArrowRight size={18}/></span></Link>
      </section>
      <div className="end-page"><span>HẾT TRANG. CHƯA HẾT CHUYỆN.</span><span aria-hidden="true">✦</span><span>DIPPIE / MỘT THẾ GIỚI NHO NHỎ</span></div>
    </main><Footer/>
  </>;
}
