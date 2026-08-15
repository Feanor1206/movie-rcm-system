import Image from 'next/image';
import Link from 'next/link';
import { ArrowUpRight, Play } from 'lucide-react';
import type { Movie } from '@/lib/movies';

export function EditorialHero({ movie }: { movie: Movie }) {
  return <section className="page-shell grid gap-10 pb-16 pt-14 lg:grid-cols-[1.25fr_.85fr] lg:gap-14 lg:pt-24">
    <div className="flex min-h-[440px] flex-col justify-between lg:min-h-[590px]">
      <div className="flex items-center gap-4 text-[10px] uppercase tracking-[.24em] text-rose-500">
        <span>Issue 06</span><span className="h-px w-10 bg-rose-700"/><span>Selected stories for tonight</span>
      </div>
      <div className="py-10 lg:py-0">
        <p className="font-editorial text-6xl leading-[.68] text-zinc-500 sm:text-8xl lg:text-9xl">A</p>
        <h1 className="font-editorial mt-4 max-w-3xl text-[4.1rem] leading-[.77] tracking-[-.065em] text-zinc-100 sm:text-[6.4rem] lg:text-[8rem] xl:text-[9.4rem]">
          Stories<br/><em className="font-light text-zinc-400">worth staying</em><br/>up for
        </h1>
      </div>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm text-zinc-400">
        <span className="text-zinc-100">Featured: {movie.title}</span><span>{movie.year}</span><span>{movie.genres.join(' / ')}</span>
      </div>
    </div>
    <article className="group relative self-end bg-zinc-950 p-3 sm:p-4">
      <div className="relative aspect-[.78] overflow-hidden bg-zinc-900">
        <Image priority src={movie.backdrop} alt={`${movie.title} still`} fill sizes="(max-width: 1024px) 100vw, 40vw" className="object-cover transition duration-700 group-hover:scale-[1.03]"/>
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/25"/>
        <span className="absolute left-4 top-4 bg-black px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-zinc-100">Feature · Nº 01</span>
        <span className="absolute right-4 top-4 bg-rose-700 px-3 py-2 font-mono text-[10px] font-bold">{movie.year}</span>
        <Link href={`/movies/${movie.id}`} aria-label={`Watch ${movie.title}`} className="absolute bottom-5 left-5 grid h-11 w-11 place-items-center rounded-full bg-rose-600 transition hover:scale-110 hover:bg-rose-500"><Play size={17} fill="currentColor"/></Link>
      </div>
      <div className="-mt-2 relative mx-0 bg-zinc-900 px-5 py-5 sm:-mt-5 sm:mx-4">
        <p className="font-mono text-[9px] uppercase tracking-[.2em] text-rose-400">Now in focus</p>
        <Link href={`/movies/${movie.id}`} className="mt-2 flex items-end justify-between gap-3 font-editorial text-2xl leading-none text-zinc-100 transition hover:text-rose-400 sm:text-3xl"><span>{movie.title} <em className="font-light text-zinc-500">— {movie.runtime}</em></span><ArrowUpRight className="mb-1 shrink-0" size={18}/></Link>
      </div>
    </article>
  </section>;
}
