'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import {
  ArrowUpRight,
  ArrowRight,
  BookOpen,
  Bookmark,
  MessageCircle,
  RefreshCw,
  Compass,
  Smile,
  HeartHandshake,
  Sparkles,
} from 'lucide-react';
import { Navbar } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';
import { FilmShelf } from '@/features/movies/components/FilmShelf';
import { ContinueWatching } from '@/features/movies/components/ContinueWatching';
import { browseCatalog } from '@/lib/services/catalogService';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';

const chapters = [
  {
    number: '01',
    title: 'Một chuyến phiêu lưu',
    note: 'Đi xa một chút, tưởng tượng nhiều hơn.',
    tag: 'Khám phá',
    href: '/search?genre=Adventure',
    Icon: Compass,
  },
  {
    number: '02',
    title: 'Cười cùng nhau nhé',
    note: 'Những chuyện bé xíu, những niềm vui to.',
    tag: 'Vui vẻ',
    href: '/search?genre=Comedy',
    Icon: Smile,
  },
  {
    number: '03',
    title: 'Góc nhỏ gia đình',
    note: 'Có những câu chuyện giống như một cái ôm.',
    tag: 'Ấm áp',
    href: '/search?genre=Family',
    Icon: HeartHandshake,
  },
] as const;

const quickTopics = [
  { label: '✦ Ghibli', href: '/search?q=Ghibli' },
  { label: 'Gia đình', href: '/search?genre=Family' },
  { label: 'Phiêu lưu', href: '/search?genre=Adventure' },
  { label: 'Hài hước', href: '/search?genre=Comedy' },
  { label: 'Phép thuật', href: '/search?genre=Fantasy' },
] as const;

export default function HomePage() {
  const { openChat, watchlist } = useWatchlist();
  const [movies, setMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);

  const handleRetry = useCallback(() => {
    setRetry((n) => n + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(false);

    browseCatalog({ animationOnly: true, size: 24, signal: controller.signal })
      .then((page) => {
        if (!controller.signal.aborted) {
          setMovies(page.items);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted && e?.name !== 'AbortError' && !e?.isCanceled) {
          setError(true);
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [retry]);

  return (
    <>
      <Navbar />
      <main className="comic-book">
        <div className="edition-line">
          <span>MỘT GÓC NHỎ DÀNH CHO TRÍ TƯỞNG TƯỢNG</span>
          <span>HOẠT HÌNH · NHỮNG CÂU CHUYỆN · BẠN</span>
        </div>

        <section className="cover-grid" aria-labelledby="cover-title">
          <div className="cover-copy">
            <div>
              <span className="chapter-kicker">
                <span className="ink-square" /> CHƯƠNG MỚI, NIỀM VUI MỚI · TUYỂN TẬP 2026
              </span>
              <h1 id="cover-title">
                Lật một trang.
                <br />
                Mở một trời
                <br />
                <em>phiêu lưu.</em>
                <svg aria-hidden="true" viewBox="0 0 260 18">
                  <path
                    d="M3 11Q120-2 255 9M30 16Q136 5 238 14"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinecap="round"
                  />
                </svg>
              </h1>
              <p>
                Gác lại bộn bề. Ghé vào thế giới hoạt hình diệu kỳ,
                <br className="hidden sm:block" />
                nơi những điều nhỏ bé cũng trở nên ấm áp và đáng nhớ.
              </p>

              <div className="hero-cta-group">
                <Link href="/search" className="cover-cta group">
                  <span>Bắt đầu khám phá</span>
                  <ArrowUpRight
                    size={19}
                    className="transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                  />
                </Link>
                <button type="button" onClick={openChat} className="cover-secondary-cta group">
                  <MessageCircle size={18} className="text-[#52704a]" />
                  <span>Trò chuyện cùng CineBot</span>
                </button>
              </div>
            </div>

            <div>
              <div className="hero-quick-topics">
                <span className="topics-label">
                  <Sparkles size={12} className="text-[#52704a]" />
                  Gợi ý nhanh:
                </span>
                <div className="topics-list">
                  {quickTopics.map((topic) => (
                    <Link key={topic.label} href={topic.href} className="topic-chip">
                      {topic.label}
                    </Link>
                  ))}
                </div>
              </div>

              <div className="cover-footnote">
                <span className="hand-arrow" aria-hidden="true">
                  ↳
                </span>
                Không cần lớn lên hôm nay. Thong thả thưởng thức từng thước phim.
              </div>
            </div>
          </div>

          <div className="cover-art-panel">
            <div className="panel-index">KHUNG HÌNH / 01 · TUYỂN CHỌN</div>
            <img
              src="/illustrations/dippie-cover.svg"
              alt="Nét vẽ truyện tranh: một bạn nhỏ và thỏ mang sách đi qua khu rừng xanh đến rạp chiếu phim"
              width={760}
              height={580}
              loading="eager"
              fetchPriority="high"
            />
            <div className="art-caption">
              <span>Đích đến: một thế giới khác.</span>
              <span>✦ TO BE CONTINUED…</span>
            </div>
          </div>
        </section>

        <div className="story-strip">
          <span>CHUYỆN HÔM NAY</span>
          <p>Một bộ hoạt hình hay. Một chiếc ghế êm. Thế là đủ.</p>
          <span className="strip-star" aria-hidden="true">
            ✳
          </span>
        </div>

        <section className="chapter-grid" aria-label="Mục lục khám phá">
          {chapters.map(({ number, title, note, tag, href, Icon }) => (
            <Link key={number} href={href} className="chapter-panel group">
              <div className="chapter-number-col">
                <span className="chapter-number">{number}</span>
                <span className="chapter-icon-stamp" aria-hidden="true">
                  <Icon size={14} strokeWidth={2} />
                </span>
              </div>
              <div>
                <span className="chapter-badge">{tag}</span>
                <span className="chapter-small block">LẬT ĐẾN CHƯƠNG</span>
                <h2>{title}</h2>
                <p>{note}</p>
              </div>
              <ArrowUpRight
                size={20}
                className="chapter-link-icon transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
              />
            </Link>
          ))}
        </section>

        <ContinueWatching />

        <div className="catalog-chapter-head">
          <span className="chapter-kicker">
            <span className="ink-square" /> TRÊN KỆ HOẠT HÌNH
          </span>
          <span className="page-number">BỘ · MÙA · TẬP</span>
        </div>

        {loading ? (
          <div className="comic-loading" role="status" aria-live="polite">
            <div className="inline-flex items-center gap-2.5 text-ink font-medium">
              <BookOpen size={22} className="animate-pulse text-[#52704a]" />
              <span>Đang sắp những thước phim lên kệ…</span>
            </div>
            <div className="comic-skeleton-row" aria-hidden="true">
              <div className="comic-skeleton-card" />
              <div className="comic-skeleton-card" />
              <div className="comic-skeleton-card" />
              <div className="comic-skeleton-card" />
            </div>
          </div>
        ) : error ? (
          <div className="comic-loading" role="alert">
            <BookOpen size={26} className="text-[#52704a]" />
            <p className="m-0">Kệ phim đang nghỉ một chút. Bạn thử mở lại trang truyện nhé.</p>
            <button type="button" className="btn-secondary" onClick={handleRetry}>
              <RefreshCw size={15} /> Tải lại kệ phim
            </button>
          </div>
        ) : (
          <FilmShelf
            movies={movies}
            title="Phim hoạt hình trong kho"
            subtitle="Chọn một phim để xem."
          />
        )}

        <section className="closing-panels">
          <div className="reading-note">
            <span className="chapter-kicker">
              <span className="ink-square" /> GHI CHÚ BÊN LỀ
            </span>
            <h2>
              Chưa biết xem gì?
              <br />
              <em>Kể tớ nghe.</em>
            </h2>
            <p>
              Một tình tiết bạn nhớ, một nhân vật bạn thích.
              <br />
              CineBot sẽ cùng bạn tìm lại câu chuyện ấy.
            </p>
            <button type="button" className="text-action cursor-pointer" onClick={openChat}>
              <span>Trò chuyện với CineBot</span>
              <MessageCircle size={18} />
            </button>
            <span className="note-doodle" aria-hidden="true">
              ✳
            </span>
          </div>

          <Link href="/profile" className="bookmark-note group">
            <div className="bookmark-ribbon" aria-hidden="true">
              <Bookmark size={20} strokeWidth={1.75} />
            </div>
            <div>
              <span className="chapter-kicker">
                <span className="ink-square" /> KẸP TRANG CỦA BẠN
              </span>
              <h2>
                Hẹn ở
                <br />
                chương sau.
              </h2>
              <p>
                {watchlist.length > 0
                  ? `${watchlist.length} câu chuyện đang chờ bạn quay lại.`
                  : 'Giữ lại những bộ hoạt hình bạn muốn xem.'}
              </p>
            </div>
            <span className="text-action group-hover:underline">
              <span>Mở danh sách xem</span>
              <ArrowRight
                size={18}
                className="transition-transform duration-200 group-hover:translate-x-1"
              />
            </span>
          </Link>
        </section>

        <div className="end-page">
          <span>HẾT TRANG. CHƯA HẾT CHUYỆN.</span>
          <span aria-hidden="true">✦</span>
          <span>DIPPIE / MỘT THẾ GIỚI NHO NHỎ</span>
        </div>
      </main>
      <Footer />
    </>
  );
}