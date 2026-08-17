'use client';

import React, { useMemo, useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { Search, X, SlidersHorizontal, Sparkles, RotateCcw } from 'lucide-react';
import { MovieCard } from '@/features/movies/components/MovieCard';
import { movies } from '@/lib/data/movies';

const ALL_GENRES = ['Sci-Fi', 'Drama', 'Mystery', 'Thriller', 'Adventure', 'Romance', 'Crime'];

type SortOption = 'rating' | 'year' | 'title';

export function SearchExperience() {
  const searchParams = useSearchParams();
  const initialGenre = searchParams.get('genre');

  const [query, setQuery] = useState('');
  const [selectedGenres, setSelectedGenres] = useState<string[]>(initialGenre ? [initialGenre] : []);
  const [sortBy, setSortBy] = useState<SortOption>('rating');

  useEffect(() => {
    if (initialGenre && !selectedGenres.includes(initialGenre)) {
      setSelectedGenres([initialGenre]);
    }
  }, [initialGenre]);

  const toggleGenre = (genre: string) => {
    setSelectedGenres((prev) =>
      prev.includes(genre) ? prev.filter((g) => g !== genre) : [...prev, genre]
    );
  };

  const clearAllFilters = () => {
    setQuery('');
    setSelectedGenres([]);
    setSortBy('rating');
  };

  const filteredMovies = useMemo(() => {
    return movies
      .filter((movie) => {
        // Query match
        const matchesQuery =
          !query.trim() ||
          movie.title.toLowerCase().includes(query.toLowerCase()) ||
          movie.description.toLowerCase().includes(query.toLowerCase()) ||
          movie.genres.some((g) => g.toLowerCase().includes(query.toLowerCase()));

        // Genre match
        const matchesGenre =
          selectedGenres.length === 0 ||
          selectedGenres.every((g) => movie.genres.includes(g));

        return matchesQuery && matchesGenre;
      })
      .sort((a, b) => {
        if (sortBy === 'rating') return b.rating - a.rating;
        if (sortBy === 'year') return b.year - a.year;
        return a.title.localeCompare(b.title);
      });
  }, [query, selectedGenres, sortBy]);

  return (
    <main className="page-shell min-h-[75vh] py-10 sm:py-16">
      {/* Header section */}
      <div>
        <span className="eyebrow">Search & Filter</span>
        <h1 className="font-editorial mt-2 text-4xl font-bold tracking-tight text-white sm:text-5xl lg:text-6xl">
          Explore Film Archive
        </h1>
        <p className="mt-2 text-sm text-cinema-400">
          Discover films across multiple genres, themes, and narrative styles.
        </p>
      </div>

      {/* Search Input Bar */}
      <div className="mt-8">
        <div className="relative flex max-w-3xl items-center rounded-xl border border-cinema-700 bg-cinema-900/80 px-4 py-3.5 shadow-xl focus-within:border-accent-rose focus-within:ring-2 focus-within:ring-accent-rose/20">
          <Search className="text-cinema-400 shrink-0" size={20} />
          <input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by title, storyline keywords, genres..."
            className="w-full bg-transparent px-3 text-sm sm:text-base text-white placeholder:text-cinema-500 focus:outline-none"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="rounded-full p-1 text-cinema-400 hover:bg-cinema-800 hover:text-white cursor-pointer"
              aria-label="Clear search input"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Filter Controls Bar */}
      <div className="mt-6 flex flex-col gap-4 rounded-xl border border-cinema-800 bg-cinema-900/40 p-4 backdrop-blur-md">
        {/* Genre Chips */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono text-xs text-cinema-400 font-semibold uppercase tracking-wider">
              Filter by Genre:
            </span>
            {(selectedGenres.length > 0 || query) && (
              <button
                onClick={clearAllFilters}
                className="flex items-center gap-1 font-mono text-[11px] text-accent-rose hover:underline cursor-pointer"
              >
                <RotateCcw size={12} /> Reset filters
              </button>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {ALL_GENRES.map((genre) => {
              const selected = selectedGenres.includes(genre);
              return (
                <button
                  key={genre}
                  onClick={() => toggleGenre(genre)}
                  className={`rounded-full px-3.5 py-1.5 font-mono text-xs transition-all duration-200 cursor-pointer ${
                    selected
                      ? 'border border-accent-rose bg-accent-rose/20 text-white font-bold shadow-glow-rose'
                      : 'border border-cinema-800 bg-cinema-850 text-cinema-400 hover:border-cinema-600 hover:text-white'
                  }`}
                >
                  {genre} {selected && '✓'}
                </button>
              );
            })}
          </div>
        </div>

        {/* Sort options row */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-cinema-800">
          <div className="flex items-center gap-2 font-mono text-xs text-cinema-400">
            <SlidersHorizontal size={14} />
            <span>Sort by:</span>
            <div className="flex items-center gap-1.5 ml-1">
              {[
                { id: 'rating', label: 'Highest Rated' },
                { id: 'year', label: 'Release Date' },
                { id: 'title', label: 'Title (A-Z)' },
              ].map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setSortBy(opt.id as SortOption)}
                  className={`rounded px-2.5 py-1 text-xs transition-colors cursor-pointer ${
                    sortBy === opt.id
                      ? 'bg-cinema-800 text-white font-semibold'
                      : 'text-cinema-400 hover:text-white'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <span className="font-mono text-xs text-cinema-400">
            Showing <strong className="text-white">{filteredMovies.length}</strong> of {movies.length} films
          </span>
        </div>
      </div>

      {/* Movie Results Grid */}
      <section className="mt-10">
        {filteredMovies.length > 0 ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5 xl:grid-cols-6">
            {filteredMovies.map((movie) => (
              <MovieCard key={movie.id} movie={movie} fluid />
            ))}
          </div>
        ) : (
          /* Empty State Compliant with UX Guidelines */
          <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-cinema-750 bg-cinema-900/30 px-6 py-20 text-center">
            <div className="grid h-14 w-14 place-items-center rounded-full bg-cinema-800 text-cinema-400 mb-4">
              <Search size={26} />
            </div>
            <h3 className="font-editorial text-2xl font-bold text-white">No Matching Films Found</h3>
            <p className="mt-2 max-w-md text-sm text-cinema-400 leading-relaxed">
              We couldn't find any films matching &ldquo;{query}&rdquo; with the selected filters. Try broadening your keywords or exploring popular tags below.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {['Sci-Fi', 'Drama', 'Mystery'].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => {
                    setQuery('');
                    setSelectedGenres([suggestion]);
                  }}
                  className="rounded-full border border-cinema-700 bg-cinema-850 px-3 py-1 font-mono text-xs text-cinema-300 hover:border-accent-rose hover:text-white cursor-pointer"
                >
                  Explore {suggestion}
                </button>
              ))}
              <button
                onClick={clearAllFilters}
                className="btn-primary py-1 px-4 text-xs font-mono"
              >
                Clear All Filters
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
