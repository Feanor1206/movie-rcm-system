'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { Sparkles, Compass, BookmarkCheck, ArrowRight, RefreshCw, AlertCircle, Film } from 'lucide-react';
import { Footer } from '@/components/layout/Footer';
import { Navbar } from '@/components/layout/Navbar';
import { EditorialHero } from '@/features/home/components/EditorialHero';
import { MovieSection } from '@/features/movies/components/MovieSection';
import { browseCatalog, CatalogApiError } from '@/lib/services/catalogService';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';

export default function HomePage() {
  const { openChat, watchlist } = useWatchlist();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryTrigger, setRetryTrigger] = useState(0);

  const [featured, setFeatured] = useState<Movie | null>(null);
  const [recentMovies, setRecentMovies] = useState<Movie[]>([]);
  const [highRatedMovies, setHighRatedMovies] = useState<Movie[]>([]);
  const [familyFantasyMovies, setFamilyFantasyMovies] = useState<Movie[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    // Bounded queries for Home rails strictly constrained to animationOnly=true
    Promise.all([
      // 1. High-rated animation (used for Spotlight Hero & High-rated rail)
      browseCatalog({
        animationOnly: true,
        sort: 'rating',
        direction: 'desc',
        size: 10,
        signal: controller.signal,
      }),
      // 2. Recent animation releases
      browseCatalog({
        animationOnly: true,
        sort: 'year',
        direction: 'desc',
        size: 10,
        signal: controller.signal,
      }),
      // 3. Adventure & Fantasy animation rail
      browseCatalog({
        animationOnly: true,
        genres: ['Adventure', 'Fantasy'],
        size: 10,
        signal: controller.signal,
      }),
    ])
      .then(([ratedRes, recentRes, familyRes]) => {
        const topRated = ratedRes.items;
        const recent = recentRes.items;
        const family = familyRes.items;

        setHighRatedMovies(topRated);
        setRecentMovies(recent);
        setFamilyFantasyMovies(family);

        // Featured spotlight picks the highest-rated animation or first recent
        const spotlight = topRated.length > 0 ? topRated[0] : recent.length > 0 ? recent[0] : null;
        setFeatured(spotlight);
        setLoading(false);
      })
      .catch((err: any) => {
        if (err?.isCanceled || err?.name === 'AbortError') {
          return; // Intentional cleanup / component unmount
        }
        setError(err?.message || 'Không thể kết nối đến máy chủ danh mục phim hoạt hình');
        setLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [retryTrigger]);

  const animationGenreTabs = [
    { label: 'Tất cả hoạt hình', genre: 'Animation' },
    { label: 'Phiêu lưu', genre: 'Adventure' },
    { label: 'Kỳ ảo', genre: 'Fantasy' },
    { label: 'Gia đình', genre: 'Family' },
    { label: 'Lãng mạn & Cảm xúc', genre: 'Romance' },
    { label: 'Hài hước', genre: 'Comedy' },
  ];

  const totalLoaded = recentMovies.length + highRatedMovies.length + familyFantasyMovies.length;

  return (
    <>
      <Navbar />
      <main className="bg-background min-h-screen text-foreground">
        {/* Loading State Skeleton for Hero */}
        {loading ? (
          <section className="relative min-h-[420px] sm:min-h-[500px] flex items-center border-b border-surface-border bg-surface animate-pulse">
            <div className="page-shell py-12 max-w-2xl space-y-4">
              <div className="h-4 w-36 rounded bg-zinc-800" />
              <div className="h-10 w-3/4 rounded bg-zinc-800" />
              <div className="h-4 w-1/2 rounded bg-zinc-800" />
              <div className="h-16 w-full rounded bg-zinc-800" />
              <div className="flex gap-3 pt-4">
                <div className="h-10 w-28 rounded bg-zinc-800" />
                <div className="h-10 w-36 rounded bg-zinc-800" />
              </div>
            </div>
          </section>
        ) : error ? (
          /* Error State Banner with Retry */
          <section className="border-b border-red-500/30 bg-red-950/20 py-12 text-center">
            <div className="page-shell max-w-xl mx-auto">
              <div className="grid h-12 w-12 place-items-center rounded bg-red-900/40 text-red-400 mx-auto mb-3">
                <AlertCircle size={22} />
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-white">Không thể nạp danh mục hoạt hình</h2>
              <p className="mt-2 text-xs sm:text-sm text-zinc-400">{error}</p>
              <div className="mt-5 flex justify-center gap-3">
                <button
                  onClick={() => setRetryTrigger((c) => c + 1)}
                  className="btn-primary flex items-center gap-1.5 text-xs"
                >
                  <RefreshCw size={12} /> Thử kết nối lại
                </button>
                <Link href="/search?genre=Animation" className="btn-secondary text-xs">
                  Tìm kiếm trực tiếp
                </Link>
              </div>
            </div>
          </section>
        ) : featured ? (
          /* Spotlight Hero from Backend Record */
          <EditorialHero movie={featured} />
        ) : (
          /* Empty Animation Catalog State */
          <section className="border-b border-surface-border bg-surface/30 py-12 text-center">
            <div className="page-shell max-w-xl mx-auto">
              <div className="grid h-12 w-12 place-items-center rounded bg-zinc-850 text-zinc-400 mx-auto mb-3">
                <Film size={22} />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-white">Kho phim hoạt hình</h1>
              <p className="mt-2 text-xs sm:text-sm text-zinc-400">
                Hiện chưa có tác phẩm hoạt hình nào trong danh mục tiêu điểm của máy chủ. Bạn có thể duyệt tìm kiếm hoặc trò chuyện cùng CineBot.
              </p>
              <div className="mt-5 flex justify-center gap-3">
                <Link href="/search?genre=Animation" className="btn-primary text-xs">
                  Khám phá danh mục
                </Link>
                <button onClick={openChat} className="btn-secondary text-xs">
                  Hỏi CineBot gợi ý
                </button>
              </div>
            </div>
          </section>
        )}

        {/* Quick Discovery Pathways */}
        <section className="border-b border-surface-border bg-surface/60 py-6 sm:py-8">
          <div className="page-shell">
            <div className="mb-4">
              <h2 className="text-lg sm:text-xl font-bold tracking-tight text-white flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-brand" />
                Hôm nay bạn muốn xem phim hoạt hình nào?
              </h2>
              <p className="mt-1 text-xs sm:text-sm text-zinc-400">
                Lựa chọn nhanh theo nhu cầu thực tế hoặc trò chuyện tự nhiên với trợ lý CineBot.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {/* Pathway 1: Explore full animation catalog */}
              <Link
                href="/search?genre=Animation"
                className="group flex flex-col justify-between rounded-xl border border-surface-border bg-surface p-4 transition-all hover:border-brand/40 hover:bg-surface-elevated hover:shadow-brand-sm"
              >
                <div className="flex items-center gap-3">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand/15 text-brand border border-brand/25">
                    <Compass size={18} />
                  </div>
                  <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-white group-hover:text-brand transition-colors">
                      Khám phá kho hoạt hình
                    </h3>
                    <p className="mt-0.5 text-[11px] sm:text-xs text-zinc-400">
                      Duyệt tuyển tập hoạt hình 2D, 3D, Anime chính thức từ máy chủ
                    </p>
                  </div>
                </div>
                <div className="mt-3 flex items-center gap-1 text-[11px] font-medium text-brand">
                  <span>Mở danh mục</span>
                  <ArrowRight size={12} className="transition-transform group-hover:translate-x-0.5" />
                </div>
              </Link>

              {/* Pathway 2: Ask CineBot with natural language */}
              <button
                type="button"
                onClick={openChat}
                className="group flex flex-col justify-between text-left rounded-xl border border-surface-border bg-surface p-4 transition-all hover:border-brand/40 hover:bg-surface-elevated hover:shadow-brand-sm cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand/15 text-brand border border-brand/25">
                    <Sparkles size={18} />
                  </div>
                  <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-white group-hover:text-brand transition-colors">
                      Gợi ý cùng CineBot
                    </h3>
                    <p className="mt-0.5 text-[11px] sm:text-xs text-zinc-400">
                      Tìm theo mô tả, thể loại, mốc năm hoặc phim tương đồng
                    </p>
                  </div>
                </div>
                <div className="mt-3 flex items-center gap-1 text-[11px] font-medium text-brand">
                  <span>Mở trợ lý</span>
                  <ArrowRight size={12} className="transition-transform group-hover:translate-x-0.5" />
                </div>
              </button>

              {/* Pathway 3: Saved Watchlist */}
              <Link
                href="/profile"
                className="group flex flex-col justify-between rounded-xl border border-surface-border bg-surface p-4 transition-all hover:border-brand/40 hover:bg-surface-elevated hover:shadow-brand-sm"
              >
                <div className="flex items-center gap-3">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand/15 text-brand border border-brand/25">
                    <BookmarkCheck size={18} />
                  </div>
                  <div>
                    <h3 className="text-xs sm:text-sm font-semibold text-white group-hover:text-brand transition-colors">
                      Danh sách đã lưu
                    </h3>
                    <p className="mt-0.5 text-[11px] sm:text-xs text-zinc-400">
                      Xem lại các phim bạn đã đánh dấu ({watchlist.length} phim)
                    </p>
                  </div>
                </div>
                <div className="mt-3 flex items-center gap-1 text-[11px] font-medium text-brand">
                  <span>Xem danh sách</span>
                  <ArrowRight size={12} className="transition-transform group-hover:translate-x-0.5" />
                </div>
              </Link>
            </div>
          </div>
        </section>

        {/* Categories Bar: Clean tabs strictly for Animation facets */}
        <div className="border-b border-surface-border bg-surface/40 py-3">
          <div className="page-shell flex items-center justify-between overflow-x-auto gap-4 scrollbar-none">
            <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400 shrink-0">
              Chủ đề hoạt hình:
            </span>
            <div className="flex items-center gap-1.5">
              {animationGenreTabs.map((tab) => (
                <Link
                  key={tab.genre}
                  href={`/search?genre=${encodeURIComponent(tab.genre)}`}
                  className="rounded-md border border-surface-border bg-surface-elevated px-3 py-1 text-xs text-zinc-300 transition-colors hover:border-brand/40 hover:text-white shrink-0 cursor-pointer"
                >
                  {tab.label}
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Main Animation Rails */}
        <div className="page-shell space-y-4 pt-4 pb-16">
          {loading ? (
            <div className="space-y-8 py-6">
              {[1, 2, 3].map((sectionIndex) => (
                <div key={sectionIndex} className="space-y-3">
                  <div className="h-6 w-48 rounded bg-zinc-800 animate-pulse" />
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5 xl:grid-cols-6">
                    {[1, 2, 3, 4, 5, 6].map((cardIndex) => (
                      <div key={cardIndex} className="aspect-[2/3] w-full rounded-lg bg-surface-elevated animate-pulse" />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : !error && totalLoaded === 0 ? (
            <div className="rounded-xl border border-dashed border-surface-border bg-surface p-10 text-center text-zinc-400 text-sm">
              Hiện tại danh mục máy chủ chưa có dữ liệu phim hoạt hình. Vui lòng thử lại sau.
            </div>
          ) : (
            <>
              {/* Section 1: Recent Animation Releases */}
              {recentMovies.length > 0 && (
                <MovieSection
                  title="Khám phá phim hoạt hình mới nhất"
                  subtitle="Các tác phẩm hoạt hình được cập nhật theo năm phát hành mới nhất"
                  movies={recentMovies}
                  exploreHref="/search?sort=year&direction=desc"
                />
              )}

              {/* Section 2: Adventure & Fantasy Animation */}
              {familyFantasyMovies.length > 0 && (
                <div className="rounded-xl border border-surface-border bg-surface/50 p-4 sm:p-6">
                  <MovieSection
                    title="Hoạt hình phiêu lưu & kỳ ảo"
                    subtitle="Các tác phẩm hoạt hình thuộc nhóm thể loại Phiêu lưu và Kỳ ảo"
                    movies={familyFantasyMovies}
                    exploreHref="/search?genres=Adventure,Fantasy"
                  />
                </div>
              )}

              {/* Section 3: High-rated Animation */}
              {highRatedMovies.length > 0 && (
                <MovieSection
                  title="Tuyệt tác hoạt hình đánh giá cao"
                  subtitle="Các kiệt tác điện ảnh hoạt hình có điểm đánh giá hàng đầu từ máy chủ"
                  movies={highRatedMovies}
                  exploreHref="/search?sort=rating&direction=desc"
                />
              )}
            </>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
