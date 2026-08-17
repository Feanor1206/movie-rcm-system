'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Bookmark, Heart, Sparkles, Star, User, Film, ArrowRight } from 'lucide-react';
import { MovieCard } from '@/features/movies/components/MovieCard';
import { movies } from '@/lib/data/movies';
import { useWatchlist } from '@/lib/context/WatchlistContext';

type Tab = 'watchlist' | 'favorites' | 'ratings';

export function ProfileOverview() {
  const [activeTab, setActiveTab] = useState<Tab>('watchlist');
  const { watchlist, favorites, ratings } = useWatchlist();

  const watchlistMovies = movies.filter((m) => watchlist.includes(m.id));
  const favoriteMovies = movies.filter((m) => favorites.includes(m.id));
  const ratedMovies = movies.filter((m) => ratings[m.id] !== undefined);

  // Calculate genre affinities
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
    <main className="page-shell min-h-[75vh] py-10 sm:py-16">
      {/* Profile Header */}
      <div className="rounded-2xl border border-cinema-800 bg-cinema-900/60 p-6 sm:p-8 backdrop-blur-xl shadow-xl">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-5">
            <div className="grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-accent-rose to-rose-800 text-xl font-bold text-white shadow-glow-rose">
              AM
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="eyebrow text-accent-rose">Cinephile Member</span>
                <span className="rounded bg-cinema-800 px-2 py-0.5 font-mono text-[10px] text-cinema-400">
                  Level 3
                </span>
              </div>
              <h1 className="font-editorial mt-1 text-3xl font-bold tracking-tight text-white sm:text-4xl">
                Alex Morgan
              </h1>
              <p className="mt-1 text-xs text-cinema-400 font-mono">
                Curating & rating contemplative cinema since 2024
              </p>
            </div>
          </div>

          {/* User Quick Stats */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl border border-cinema-800 bg-cinema-950/80 px-4 py-3 text-center">
              <span className="font-mono text-xl font-bold text-white">{watchlist.length}</span>
              <p className="mt-0.5 font-mono text-[10px] uppercase text-cinema-400">Watchlist</p>
            </div>
            <div className="rounded-xl border border-cinema-800 bg-cinema-950/80 px-4 py-3 text-center">
              <span className="font-mono text-xl font-bold text-accent-rose">{favorites.length}</span>
              <p className="mt-0.5 font-mono text-[10px] uppercase text-cinema-400">Favorites</p>
            </div>
            <div className="rounded-xl border border-cinema-800 bg-cinema-950/80 px-4 py-3 text-center">
              <span className="font-mono text-xl font-bold text-accent-gold">
                {Object.keys(ratings).length}
              </span>
              <p className="mt-0.5 font-mono text-[10px] uppercase text-cinema-400">Rated</p>
            </div>
          </div>
        </div>

        {/* Genre Affinity Visualizer */}
        {topGenres.length > 0 && (
          <div className="mt-8 pt-6 border-t border-cinema-800">
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-cinema-400 block mb-3">
              Your Genre Taste Breakdown:
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {topGenres.map(([genre, count]) => {
                const percentage = Math.min(100, count * 25);
                return (
                  <div key={genre} className="rounded-lg border border-cinema-800 bg-cinema-950/60 p-3">
                    <div className="flex justify-between text-xs font-mono mb-1.5">
                      <span className="text-white font-medium">{genre}</span>
                      <span className="text-accent-rose">{percentage}%</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-cinema-800">
                      <div
                        className="h-full rounded-full bg-accent-rose"
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

      {/* Tabs Navigation */}
      <div className="mt-10 flex items-center gap-2 border-b border-cinema-800 pb-4">
        {[
          { id: 'watchlist', label: 'Watchlist', icon: Bookmark, count: watchlistMovies.length },
          { id: 'favorites', label: 'Favorites', icon: Heart, count: favoriteMovies.length },
          { id: 'ratings', label: 'Rated History', icon: Star, count: ratedMovies.length },
        ].map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as Tab)}
              className={`flex items-center gap-2 rounded-lg px-4 py-2.5 font-mono text-xs transition-all duration-200 cursor-pointer ${
                active
                  ? 'border border-accent-rose bg-accent-rose/15 text-white font-semibold shadow-glow-rose'
                  : 'border border-transparent text-cinema-400 hover:bg-cinema-900 hover:text-white'
              }`}
            >
              <Icon size={14} className={active ? 'text-accent-rose' : ''} />
              <span>{tab.label}</span>
              <span className="rounded-full bg-cinema-800 px-1.5 py-0.2 text-[10px] text-cinema-300">
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Movies Grid / Empty State */}
      <section className="mt-8">
        {displayedMovies.length > 0 ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5 xl:grid-cols-6">
            {displayedMovies.map((movie) => (
              <MovieCard key={movie.id} movie={movie} fluid />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-cinema-800 bg-cinema-900/20 px-6 py-16 text-center">
            <Film className="text-cinema-600 mb-3" size={32} />
            <h3 className="font-editorial text-xl font-bold text-white">
              No films in this collection yet
            </h3>
            <p className="mt-1.5 max-w-sm text-xs text-cinema-400">
              Browse the discovery catalog or search archive to save films for later.
            </p>
            <Link href="/" className="btn-primary mt-6 text-xs font-mono">
              Explore Discover <ArrowRight size={14} />
            </Link>
          </div>
        )}
      </section>
    </main>
  );
}
