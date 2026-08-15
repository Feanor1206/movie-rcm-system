import { Footer } from '@/components/layout/Footer';
import { Navbar } from '@/components/layout/Navbar';
import { EditorialHero } from '@/features/home/components/EditorialHero';
import { MovieSection } from '@/features/movies/components/MovieSection';
import { featuredMovie, movies } from '@/lib/data/movies';

export default function HomePage() {
  return <><Navbar/><main><EditorialHero movie={featuredMovie}/><div className="page-shell border-t border-zinc-800"><MovieSection title="Trending now" movies={movies}/><MovieSection title="Recommended for you" subtitle="Movies selected based on your interests" movies={[...movies].reverse()}/><MovieSection title="Top rated" movies={movies.slice(0, 5)}/></div></main><Footer/></>;
}
