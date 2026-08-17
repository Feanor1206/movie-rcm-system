import React from 'react';
import { Footer } from '@/components/layout/Footer';
import { Navbar } from '@/components/layout/Navbar';
import { EditorialHero } from '@/features/home/components/EditorialHero';
import { MovieSection } from '@/features/movies/components/MovieSection';
import { featuredMovie, movies } from '@/lib/data/movies';
import Link from 'next/link';

export default function HomePage() {
  const trendingMovies = movies;
  const recommendedMovies = [...movies].reverse();
  const topRatedMovies = [...movies].sort((a, b) => b.rating - a.rating);

  return (
    <>
      <Navbar />
      <main className="bg-black">
        {/* Spotlight Hero with prominent backdrop */}
        <EditorialHero movie={featuredMovie} />

        {/* Categories Bar: Clean rectangular tabs (No pill badges) */}
        <div className="border-b border-zinc-800 bg-zinc-950 py-3">
          <div className="page-shell flex items-center justify-between overflow-x-auto gap-4 scrollbar-none">
            <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400 shrink-0">
              Thể loại:
            </span>
            <div className="flex items-center gap-1.5">
              {['Sci-Fi', 'Drama', 'Mystery', 'Thriller', 'Adventure', 'Romance', 'Crime'].map((genre) => (
                <Link
                  key={genre}
                  href={`/search?genre=${encodeURIComponent(genre)}`}
                  className="rounded-md border border-zinc-800 bg-zinc-900/80 px-3 py-1 text-xs text-zinc-300 transition-colors hover:border-zinc-600 hover:text-white shrink-0 cursor-pointer"
                >
                  {genre}
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Main Content Sections */}
        <div className="page-shell space-y-4 pt-6 pb-16">
          {/* Trending */}
          <MovieSection
            title="Thịnh hành hôm nay"
            subtitle="Các bộ phim được cộng đồng xem nhiều nhất trong tuần"
            movies={trendingMovies}
          />

          {/* Recommended */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 sm:p-6">
            <MovieSection
              title="Đề xuất dành riêng cho bạn"
              subtitle="Lựa chọn dựa trên thể loại và lịch sử xem của bạn"
              movies={recommendedMovies}
            />
          </div>

          {/* Top Rated */}
          <MovieSection
            title="Được đánh giá cao nhất"
            subtitle="Các kiệt tác điện ảnh đạt từ 8.0/10 điểm trở lên"
            movies={topRatedMovies}
          />
        </div>
      </main>
      <Footer />
    </>
  );
}
