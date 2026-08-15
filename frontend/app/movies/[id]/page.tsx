import { notFound } from 'next/navigation';
import { Footer } from '@/components/layout/Footer';
import { Navbar } from '@/components/layout/Navbar';
import { MovieDetail } from '@/features/movies/components/MovieDetail';
import { movies } from '@/lib/data/movies';

export default async function MovieDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const movie = movies.find((item) => item.id === id);
  if (!movie) notFound();
  return <><Navbar/><MovieDetail movie={movie} similarMovies={movies.filter((item) => item.id !== movie.id).slice(0, 5)}/><Footer/></>;
}
