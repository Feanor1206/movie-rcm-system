import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';
import type { Movie } from '@/types/movie';
import { MovieCard } from './MovieCard';

type MovieSectionProps = { title: string; subtitle?: string; movies: Movie[] };

export function MovieSection({ title, subtitle, movies }: MovieSectionProps) {
  return <section className="py-10 sm:py-12"><div className="mb-6 flex items-end justify-between gap-4"><div><h2 className="section-title">{title}</h2>{subtitle && <p className="mt-1.5 text-sm leading-5 text-zinc-500">{subtitle}</p>}</div><Link href="/search" className="flex shrink-0 items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-zinc-400 transition hover:text-white">View all <ArrowUpRight size={14}/></Link></div><div className="movie-row -mx-5 flex gap-3 overflow-x-auto px-5 pb-2 sm:mx-0 sm:px-0 sm:gap-4">{movies.map((movie) => <MovieCard key={movie.id} movie={movie}/>)}</div></section>;
}
