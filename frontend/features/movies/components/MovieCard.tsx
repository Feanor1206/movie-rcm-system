'use client';

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Bookmark, Check, Play, Star } from 'lucide-react';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';

type MovieCardProps = {
  movie: Movie;
  fluid?: boolean;
};

export function MovieCard({ movie, fluid = false }: MovieCardProps) {
  const { isWatchlisted, toggleWatchlist } = useWatchlist();
  const inWatchlist = isWatchlisted(movie.id);

  return (
    <div
      className={`group relative block outline-none transition-transform duration-300 hover:-translate-y-1.5 ${
        fluid ? 'w-full' : 'w-[160px] shrink-0 sm:w-[190px] md:w-[210px]'
      }`}
    >
      <article className="overflow-hidden rounded-xl border border-cinema-800/90 bg-cinema-900/80 backdrop-blur-md transition-all duration-300 group-hover:border-cinema-650 group-hover:shadow-card-hover">
        {/* Poster Media Box */}
        <div className="relative aspect-[2/3] w-full overflow-hidden bg-cinema-950">
          <Image
            src={movie.poster}
            alt={`${movie.title} poster`}
            fill
            sizes={
              fluid
                ? '(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw'
                : '(max-width: 640px) 160px, (max-width: 1024px) 190px, 210px'
            }
            className="object-cover transition-transform duration-500 group-hover:scale-105"
          />

          {/* Vignette Gradients */}
          <div className="absolute inset-0 bg-gradient-to-t from-cinema-950 via-transparent to-black/20 opacity-80" />

          {/* Quick Rating Badge */}
          <span className="absolute top-2.5 left-2.5 flex items-center gap-1 rounded-md bg-black/75 px-2 py-0.5 font-mono text-[11px] font-bold text-accent-gold backdrop-blur-md border border-white/10">
            <Star size={11} className="fill-accent-gold" />
            {movie.rating}
          </span>

          {/* Quick Watchlist Bookmark Button */}
          <button
            type="button"
            aria-label={inWatchlist ? `Remove ${movie.title} from watchlist` : `Add ${movie.title} to watchlist`}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              toggleWatchlist(movie.id, movie.title);
            }}
            className={`absolute top-2.5 right-2.5 rounded-full p-2 backdrop-blur-md transition-all duration-200 cursor-pointer ${
              inWatchlist
                ? 'bg-accent-rose text-white shadow-glow-rose'
                : 'bg-black/60 text-cinema-300 opacity-85 hover:bg-accent-rose hover:text-white group-hover:opacity-100'
            }`}
          >
            {inWatchlist ? <Check size={14} /> : <Bookmark size={14} />}
          </button>

          {/* Hover Play Button Overlay */}
          <Link
            href={`/movies/${movie.id}`}
            aria-label={`View details for ${movie.title}`}
            className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 backdrop-blur-[2px] transition-opacity duration-300 group-hover:opacity-100 cursor-pointer"
          >
            <span className="grid h-12 w-12 place-items-center rounded-full bg-accent-rose text-white shadow-glow-rose transition-transform duration-200 hover:scale-110">
              <Play size={18} className="fill-current ml-0.5" />
            </span>
          </Link>
        </div>

        {/* Content Meta */}
        <div className="flex min-h-[90px] flex-col justify-between p-3.5">
          <div>
            <Link
              href={`/movies/${movie.id}`}
              className="block truncate font-sans text-sm font-semibold text-white transition-colors hover:text-rose-400 focus-visible:underline"
            >
              {movie.title}
            </Link>
            <p className="mt-1 flex items-center gap-1.5 font-mono text-[11px] text-cinema-400">
              <span>{movie.year}</span>
              <span className="text-cinema-700">•</span>
              <span>{movie.runtime}</span>
            </p>
          </div>

          <div className="mt-2 flex flex-wrap gap-1">
            {movie.genres.slice(0, 2).map((genre) => (
              <span
                key={genre}
                className="rounded bg-cinema-850 px-1.5 py-0.5 font-mono text-[9px] text-cinema-400"
              >
                {genre}
              </span>
            ))}
          </div>
        </div>
      </article>
    </div>
  );
}
