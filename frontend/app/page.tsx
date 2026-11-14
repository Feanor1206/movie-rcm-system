'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { RefreshCw } from 'lucide-react';
import { Navbar } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';
import { FilmShelf } from '@/features/movies/components/FilmShelf';
import { ContinueWatching } from '@/features/movies/components/ContinueWatching';
import { browseCatalog } from '@/lib/services/catalogService';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';

const quickTopics = [
  { label: 'Ghibli', href: '/search?q=Ghibli' },
  { label: 'Gia đình', href: '/search?genre=Family' },
  { label: 'Phiêu lưu', href: '/search?genre=Adventure' },
  { label: 'Hài', href: '/search?genre=Comedy' },
  { label: 'Giả tưởng', href: '/search?genre=Fantasy' },
];

export default function HomePage() {
  const { openChat } = useWatchlist();
  const [movies, setMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);

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
        <section className="cover-grid" aria-labelledby="cover-title">
          <div className="cover-copy">
            <h1 id="cover-title">Kho phim<br /><em>hoạt hình</em></h1>

            <div className="hero-cta-group">
              <Link href="/search" className="cover-cta">Tìm phim</Link>
              <button type="button" onClick={openChat} className="cover-secondary-cta">Hỏi CineBot</button>
            </div>

            <nav className="topics-list" aria-label="Gợi ý tìm phim">
              {quickTopics.map((topic) => (
                <Link key={topic.label} href={topic.href} className="topic-chip">
                  {topic.label}
                </Link>
              ))}
            </nav>
          </div>

          <div className="cover-art-panel">
            <img
              src="/illustrations/dippie-cover.svg"
              alt="Bạn nhỏ và thỏ đi đến rạp chiếu phim trong rừng"
              width="760"
              height="580"
            />
          </div>
        </section>

        <ContinueWatching />

        {loading ? (
          <div className="comic-loading" role="status">
            <p>Đang tải phim…</p>
          </div>
        ) : error ? (
          <div className="comic-loading" role="alert">
            <p>Không thể tải phim. Vui lòng thử lại.</p>
            <button className="btn-secondary" onClick={() => setRetry((n) => n + 1)}>
              <RefreshCw size={15} /> Thử lại
            </button>
          </div>
        ) : (
          <FilmShelf movies={movies} title="Phim trong kho" subtitle="" />
        )}
      </main>
      <Footer />
    </>
  );
}
