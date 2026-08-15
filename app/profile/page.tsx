import { Navbar } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';
import { MovieCard } from '@/components/movie/MovieCard';
import { movies } from '@/lib/movies';

export default function Profile() {
  return <><Navbar/><main className="page-shell min-h-[70vh] py-14 sm:py-16"><div className="flex items-center gap-4 border-b border-zinc-800 pb-9"><div className="grid h-14 w-14 place-items-center rounded-full bg-rose-600 text-lg font-bold">A</div><div><p className="eyebrow">Personal archive</p><h1 className="font-editorial mt-1 text-4xl leading-none tracking-[-.04em]">Alex Morgan</h1><p className="mt-2 text-sm text-zinc-500">Movie explorer</p></div></div><section className="mt-11"><h2 className="section-title">Your watchlist</h2><p className="mt-1.5 text-sm text-zinc-500">Keep track of stories you want to see.</p><div className="mt-7 grid grid-cols-2 gap-x-3 gap-y-6 sm:grid-cols-3 sm:gap-x-4 lg:grid-cols-5 xl:grid-cols-6">{movies.slice(1).map((movie) => <MovieCard key={movie.id} movie={movie} fluid/>)}</div></section></main><Footer/></>;
}
