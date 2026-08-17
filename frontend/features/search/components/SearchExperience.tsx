'use client';

import React, { useMemo, useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { Search, X, SlidersHorizontal, RotateCcw } from 'lucide-react';
import { MovieCard } from '@/features/movies/components/MovieCard';
import { movies } from '@/lib/data/movies';
import { useWatchlist } from '@/lib/context/WatchlistContext';

const ALL_GENRES = ['Sci-Fi', 'Drama', 'Mystery', 'Thriller', 'Adventure', 'Romance', 'Crime'];

type SortOption = 'rating' | 'year' | 'title';

export function SearchExperience() {
  const searchParams = useSearchParams();
  const initialGenre = searchParams.get('genre');
  const { openChat } = useWatchlist();

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
        const matchesQuery =
          !query.trim() ||
          movie.title.toLowerCase().includes(query.toLowerCase()) ||
          movie.description.toLowerCase().includes(query.toLowerCase()) ||
          movie.genres.some((g) => g.toLowerCase().includes(query.toLowerCase()));

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
    <main className="page-shell min-h-[75vh] py-8 sm:py-12">
      {/* Title */}
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
          Kho phim điện ảnh
        </h1>
        <p className="mt-1.5 text-sm text-zinc-400">
          Tìm kiếm và lọc phim theo tên, cốt truyện hoặc thể loại yêu thích.
        </p>
      </div>

      {/* Search Input Bar */}
      <div className="mt-6">
        <div className="relative flex max-w-2xl items-center rounded-md border border-zinc-700 bg-zinc-900 px-3.5 py-3 shadow-lg focus-within:border-cinema-red">
          <Search className="text-zinc-400 shrink-0" size={18} />
          <input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Nhập tên phim, thể loại hoặc từ khóa..."
            className="w-full bg-transparent px-3 text-sm text-white placeholder:text-zinc-500 focus:outline-none"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="rounded p-1 text-zinc-400 hover:bg-zinc-800 hover:text-white cursor-pointer"
              aria-label="Xóa từ khóa"
            >
              <X size={15} />
            </button>
          )}
        </div>
      </div>

      {/* Filter Bar: Clean rectangular badges */}
      <div className="mt-5 flex flex-col gap-3 rounded-lg border border-zinc-800 bg-zinc-950 p-4">
        {/* Genre Chips */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Lọc theo thể loại:
            </span>
            {(selectedGenres.length > 0 || query) && (
              <button
                onClick={clearAllFilters}
                className="flex items-center gap-1 text-xs text-cinema-red hover:underline cursor-pointer"
              >
                <RotateCcw size={12} /> Đặt lại bộ lọc
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
                  className={`rounded-md px-3 py-1 text-xs font-medium transition-colors cursor-pointer ${
                    selected
                      ? 'bg-cinema-red text-white font-bold'
                      : 'border border-zinc-800 bg-zinc-900 text-zinc-300 hover:border-zinc-600 hover:text-white'
                  }`}
                >
                  {genre} {selected && '✓'}
                </button>
              );
            })}
          </div>
        </div>

        {/* Sort */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-zinc-850 text-xs text-zinc-400">
          <div className="flex items-center gap-2">
            <SlidersHorizontal size={14} />
            <span>Sắp xếp theo:</span>
            <div className="flex items-center gap-1 ml-1">
              {[
                { id: 'rating', label: 'Điểm cao nhất' },
                { id: 'year', label: 'Năm mới nhất' },
                { id: 'title', label: 'Tên (A-Z)' },
              ].map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setSortBy(opt.id as SortOption)}
                  className={`rounded px-2.5 py-1 transition-colors cursor-pointer ${
                    sortBy === opt.id
                      ? 'bg-zinc-800 text-white font-bold'
                      : 'hover:text-white'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <span>
            Tìm thấy <strong className="text-white">{filteredMovies.length}</strong> / {movies.length} phim
          </span>
        </div>
      </div>

      {/* Grid Results */}
      <section className="mt-8">
        {filteredMovies.length > 0 ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5 xl:grid-cols-6">
            {filteredMovies.map((movie) => (
              <MovieCard key={movie.id} movie={movie} fluid />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-zinc-800 bg-zinc-950 px-6 py-16 text-center">
            <div className="grid h-12 w-12 place-items-center rounded bg-zinc-900 text-zinc-400 mb-3">
              <Search size={20} />
            </div>
            <h3 className="text-base font-bold text-white">Không tìm thấy bộ phim nào</h3>
            <p className="mt-1 max-w-md text-xs sm:text-sm text-zinc-400">
              Không có phim nào khớp với từ khóa &ldquo;{query}&rdquo;. Bạn có thể thử tìm từ khóa khác hoặc nhờ trợ lý CineBot gợi ý.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <button
                onClick={openChat}
                className="btn-primary text-xs"
              >
                Hỏi CineBot gợi ý ngay
              </button>
              <button
                onClick={clearAllFilters}
                className="btn-secondary text-xs"
              >
                Xem toàn bộ kho phim
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
