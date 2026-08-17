'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Bookmark, Heart, Star, Film, ArrowRight } from 'lucide-react';
import { MovieCard } from '@/features/movies/components/MovieCard';
import { movies } from '@/lib/data/movies';
import { useWatchlist } from '@/lib/context/WatchlistContext';

type Tab = 'watchlist' | 'favorites' | 'ratings';

export function ProfileOverview() {
  const [activeTab, setActiveTab] = useState<Tab>('watchlist');
  const { watchlist, favorites, ratings, openChat } = useWatchlist();

  const watchlistMovies = movies.filter((m) => watchlist.includes(m.id));
  const favoriteMovies = movies.filter((m) => favorites.includes(m.id));
  const ratedMovies = movies.filter((m) => ratings[m.id] !== undefined);

  // Genre analysis
  const genreCounts: Record<string, number> = {};
  [...watchlistMovies, ...favoriteMovies, ...ratedMovies].forEach((movie) => {
    movie.genres.forEach((genre) => {
      genreCounts[genre] = (genreCounts[genre] || 0) + 1;
    });
  });
  const topGenres = Object.entries(genreCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);

  const displayedMovies =
    activeTab === 'watchlist'
      ? watchlistMovies
      : activeTab === 'favorites'
      ? favoriteMovies
      : ratedMovies;

  return (
    <main className="page-shell min-h-[75vh] py-8 sm:py-12">
      {/* Profile Header */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6 sm:p-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="grid h-12 w-12 place-items-center rounded-md bg-cinema-red text-base font-bold text-white shadow-red-sm">
              AM
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-cinema-red uppercase tracking-wider">
                  Thành viên Cinephile
                </span>
                <span className="text-zinc-500">•</span>
                <span className="text-xs text-zinc-400">Level 3</span>
              </div>
              <h1 className="mt-1 text-2xl font-bold tracking-tight text-white sm:text-3xl">
                Alex Morgan
              </h1>
              <p className="text-xs text-zinc-400">
                Thành viên khám phá và lưu trữ phim điện ảnh
              </p>
            </div>
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-3 gap-2.5">
            <div className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2.5 text-center">
              <span className="text-lg font-bold text-white block">{watchlist.length}</span>
              <span className="text-[10px] uppercase text-zinc-400">Watchlist</span>
            </div>
            <div className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2.5 text-center">
              <span className="text-lg font-bold text-cinema-red block">{favorites.length}</span>
              <span className="text-[10px] uppercase text-zinc-400">Yêu thích</span>
            </div>
            <div className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2.5 text-center">
              <span className="text-lg font-bold text-amber-400 block">{Object.keys(ratings).length}</span>
              <span className="text-[10px] uppercase text-zinc-400">Đã chấm</span>
            </div>
          </div>
        </div>

        {/* Top Genre breakdown */}
        {topGenres.length > 0 && (
          <div className="mt-6 pt-5 border-t border-zinc-800">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block mb-2.5">
              Phân tích gu thể loại:
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {topGenres.map(([genre, count]) => {
                const percentage = Math.min(100, count * 25);
                return (
                  <div key={genre} className="rounded-md border border-zinc-800 bg-zinc-900 p-2.5">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-white font-medium">{genre}</span>
                      <span className="text-cinema-red font-bold">{percentage}%</span>
                    </div>
                    <div className="h-1.5 w-full rounded bg-zinc-800 overflow-hidden">
                      <div
                        className="h-full bg-cinema-red"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="mt-8 flex items-center gap-2 border-b border-zinc-800 pb-3">
        {[
          { id: 'watchlist', label: 'Danh sách xem', icon: Bookmark, count: watchlistMovies.length },
          { id: 'favorites', label: 'Yêu thích', icon: Heart, count: favoriteMovies.length },
          { id: 'ratings', label: 'Lịch sử đánh giá', icon: Star, count: ratedMovies.length },
        ].map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as Tab)}
              className={`flex items-center gap-1.5 rounded-md px-3.5 py-2 text-xs font-medium transition-colors cursor-pointer ${
                active
                  ? 'bg-zinc-800 text-white font-bold'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
              }`}
            >
              <Icon size={14} className={active ? 'text-cinema-red' : ''} />
              <span>{tab.label}</span>
              <span className="text-[11px] text-zinc-400 font-normal">
                ({tab.count})
              </span>
            </button>
          );
        })}
      </div>

      {/* Grid List */}
      <section className="mt-6">
        {displayedMovies.length > 0 ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5 xl:grid-cols-6">
            {displayedMovies.map((movie) => (
              <MovieCard key={movie.id} movie={movie} fluid />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-800 bg-zinc-950 px-6 py-14 text-center">
            <Film className="text-zinc-600 mb-2.5" size={28} />
            <h3 className="text-base font-bold text-white">Chưa có bộ phim nào trong danh mục này</h3>
            <p className="mt-1 text-xs text-zinc-400">
              Hãy khám phá các tác phẩm trên trang chủ hoặc trò chuyện cùng CineBot để lưu thêm phim.
            </p>
            <div className="mt-4 flex gap-2">
              <Link href="/" className="btn-primary text-xs">
                Khám phá phim <ArrowRight size={13} />
              </Link>
              <button
                onClick={openChat}
                className="btn-secondary text-xs"
              >
                Nhờ CineBot gợi ý
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
