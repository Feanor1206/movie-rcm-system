'use client';

import { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { MovieCard } from '@/features/movies/components/MovieCard';
import { movies } from '@/lib/data/movies';

export function SearchExperience() {
  const [query, setQuery] = useState('');
  const found = useMemo(() => movies.filter((movie) => `${movie.title} ${movie.genres.join(' ')}`.toLowerCase().includes(query.toLowerCase())), [query]);
  return <main className="page-shell min-h-[70vh] py-14 sm:py-16"><p className="eyebrow">Search the archive</p><h1 className="font-editorial mt-3 text-5xl leading-none tracking-[-.05em] sm:text-6xl">Find your next film</h1><p className="mt-3 text-sm text-zinc-500">Search by title or genre.</p><label className="mt-8 flex max-w-2xl items-center gap-3 border-b border-zinc-600 bg-zinc-900/40 px-4 py-4 focus-within:border-rose-600"><Search className="text-zinc-400" size={20}/><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search movies, genres..." className="w-full bg-transparent text-base outline-none placeholder:text-zinc-500"/></label><section className="mt-12"><h2 className="section-title mb-6">{query ? `Results for “${query}”` : 'Browse all movies'}</h2>{found.length ? <div className="grid grid-cols-2 gap-x-3 gap-y-6 sm:grid-cols-3 sm:gap-x-4 lg:grid-cols-5 xl:grid-cols-6">{found.map((movie) => <MovieCard key={movie.id} movie={movie} fluid/>)}</div> : <div className="border border-dashed border-zinc-700 py-16 text-center"><p className="font-medium">No movies found</p><p className="mt-2 text-sm text-zinc-500">Try searching for another title, actor, genre, or keyword.</p></div>}</section></main>;
}
