'use client';

import Image from 'next/image';
import Link from 'next/link';
import { BookmarkPlus, Play, Star } from 'lucide-react';
import type { Movie } from '@/lib/movies';

export function MovieCard({ movie, fluid = false }: { movie: Movie; fluid?: boolean }) {
  return <Link href={`/movies/${movie.id}`} className={`group block outline-none ${fluid ? 'w-full' : 'w-[158px] shrink-0 sm:w-[184px]'}`}>
    <article className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900/60 transition duration-200 group-hover:-translate-y-1 group-hover:border-zinc-600 group-focus-visible:ring-2 group-focus-visible:ring-rose-600">
      <div className="relative aspect-[2/3] overflow-hidden">
        <Image src={movie.poster} alt={`${movie.title} poster`} fill sizes={fluid ? '(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw' : '(max-width: 640px) 158px, (max-width: 1024px) 184px, 210px'} className="object-cover transition duration-300 group-hover:scale-[1.035]"/>
        <div className="absolute inset-0 flex items-center justify-center bg-black/45 opacity-0 transition group-hover:opacity-100"><span className="rounded-full bg-rose-600 p-3 shadow-xl"><Play size={18} fill="currentColor"/></span></div>
        <button aria-label={`Add ${movie.title} to watchlist`} onClick={(event)=>event.preventDefault()} className="absolute right-2 top-2 rounded-full bg-black/50 p-2 opacity-0 transition hover:bg-rose-600 group-hover:opacity-100"><BookmarkPlus size={15}/></button>
      </div>
      <div className="min-h-[84px] p-3"><h3 className="truncate text-sm font-semibold leading-5">{movie.title}</h3><p className="mt-1 flex items-center gap-1 text-xs text-zinc-400"><Star size={12} className="fill-rose-500 text-rose-500"/>{movie.rating} <span className="text-zinc-600">•</span> {movie.year}</p><p className="mt-1 truncate text-xs text-zinc-500">{movie.genres.join(' · ')}</p></div>
    </article>
  </Link>;
}
