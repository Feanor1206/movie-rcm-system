import React from 'react';
import { Footer } from '@/components/layout/Footer';
import { Navbar } from '@/components/layout/Navbar';
import { EditorialHero } from '@/features/home/components/EditorialHero';
import { MovieSection } from '@/features/movies/components/MovieSection';
import { featuredMovie, movies } from '@/lib/data/movies';
import Link from 'next/link';
import { Compass, Sparkles, TrendingUp, Trophy } from 'lucide-react';

export default function HomePage() {
  const trendingMovies = movies;
  const recommendedMovies = [...movies].reverse();
  const topRatedMovies = [...movies].sort((a, b) => b.rating - a.rating);

  return (
    <>
      <Navbar />
      <main>
        {/* Editorial Spotlight */}
        <EditorialHero movie={featuredMovie} />

        {/* Categories Bar */}
        <div className="border-y border-cinema-800/80 bg-cinema-900/40 py-4 backdrop-blur-md">
          <div className="page-shell flex items-center justify-between overflow-x-auto gap-4 scrollbar-none">
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-cinema-400 shrink-0">
              Browse by Vibe:
            </span>
            <div className="flex items-center gap-2">
              {['Sci-Fi', 'Drama', 'Mystery', 'Thriller', 'Adventure', 'Romance', 'Crime'].map((genre) => (
                <Link
                  key={genre}
                  href={`/search?genre=${encodeURIComponent(genre)}`}
                  className="rounded-full border border-cinema-800 bg-cinema-900/80 px-3.5 py-1 font-mono text-xs text-cinema-300 transition-all hover:border-accent-rose hover:text-white shrink-0 cursor-pointer"
                >
                  {genre}
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Content Shell with Carousels */}
        <div className="page-shell space-y-4 pt-6 pb-12">
          {/* Trending Now */}
          <MovieSection
            title="Trending in Cinema"
            subtitle="Most watched stories across our community this week"
            movies={trendingMovies}
          />

          {/* AI Recommended */}
          <div className="relative overflow-hidden rounded-2xl border border-accent-rose/20 bg-gradient-to-r from-accent-rose/5 via-cinema-900/70 to-cinema-900/40 p-6 backdrop-blur-xl">
            <div className="flex items-center gap-2 text-accent-rose font-mono text-xs font-semibold uppercase tracking-wider">
              <Sparkles size={14} className="animate-pulse" />
              <span>Personalized For You</span>
            </div>
            <MovieSection
              title="Recommended Matches"
              subtitle="Algorithmically ranked based on mood, themes, and viewing history"
              movies={recommendedMovies}
            />
          </div>

          {/* Top Rated Masterpieces */}
          <MovieSection
            title="Critically Acclaimed"
            subtitle="Award-winning cinema scoring 8.0+ by global reviewers"
            movies={topRatedMovies}
          />
        </div>
      </main>
      <Footer />
    </>
  );
}
