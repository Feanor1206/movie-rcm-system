'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { ArrowUpRight, Bookmark, Check, Play, Sparkles, Star, Volume2 } from 'lucide-react';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';
import { AiRecommendModal } from './AiRecommendModal';

export function EditorialHero({ movie }: { movie: Movie }) {
  const { isWatchlisted, toggleWatchlist } = useWatchlist();
  const [showAiModal, setShowAiModal] = useState(false);
  const [isPlayingTrailer, setIsPlayingTrailer] = useState(false);

  const inWatchlist = isWatchlisted(movie.id);

  return (
    <>
      <section className="page-shell relative grid gap-10 pb-16 pt-10 lg:grid-cols-[1.2fr_.88fr] lg:gap-14 lg:pt-16">
        {/* Left Column: Editorial Typography & Actions */}
        <div className="flex min-h-[460px] flex-col justify-between lg:min-h-[580px]">
          <div>
            {/* Top Issue Tag */}
            <div className="flex items-center gap-3">
              <span className="eyebrow text-accent-rose">Curated Issue № 08</span>
              <span className="h-px w-8 bg-cinema-700" />
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-cinema-400">
                AI Spotlight / 2026
              </span>
            </div>

            {/* Main Headline */}
            <div className="py-8 sm:py-10">
              <h1 className="font-editorial text-[3.6rem] font-bold leading-[0.88] tracking-[-0.04em] text-white sm:text-[5.4rem] lg:text-[6.8rem] xl:text-[7.6rem]">
                Stories
                <br />
                <em className="font-light italic text-cinema-300">worth staying</em>
                <br />
                up for<span className="text-accent-rose">.</span>
              </h1>
            </div>

            {/* Subtext description */}
            <p className="max-w-xl text-sm sm:text-base leading-relaxed text-cinema-300">
              Hand-curated cinematic wonders analyzed by our recommendation algorithms. 
              Find films shaped by atmosphere, profound dialogue, and visionary cinematography.
            </p>
          </div>

          {/* Action Row */}
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link
              href={`/movies/${movie.id}`}
              className="btn-primary px-6 py-3 text-sm font-semibold"
            >
              <Play size={16} className="fill-current" /> Watch Feature Film
            </Link>

            <button
              onClick={() => toggleWatchlist(movie.id, movie.title)}
              className="btn-secondary px-5 py-3 text-sm font-semibold"
              aria-label={inWatchlist ? 'Remove from Watchlist' : 'Add to Watchlist'}
            >
              {inWatchlist ? (
                <>
                  <Check size={16} className="text-accent-rose" /> In Watchlist
                </>
              ) : (
                <>
                  <Bookmark size={16} /> Add to Watchlist
                </>
              )}
            </button>

            <button
              onClick={() => setShowAiModal(true)}
              className="inline-flex items-center gap-2 rounded-lg border border-accent-rose/40 bg-accent-rose/10 px-4 py-3 font-mono text-xs font-semibold text-rose-300 transition hover:bg-accent-rose/20 hover:text-white cursor-pointer"
            >
              <Sparkles size={14} className="text-accent-rose animate-pulse" />
              <span>AI Vibe Matcher</span>
            </button>
          </div>
        </div>

        {/* Right Column: Hero Spotlight Card */}
        <article className="group relative self-end rounded-2xl border border-cinema-800 bg-cinema-900/90 p-3 sm:p-4 backdrop-blur-xl transition-all duration-300 hover:border-cinema-650 shadow-2xl">
          {/* Visual Container */}
          <div className="relative aspect-[4/3] sm:aspect-[1.1] overflow-hidden rounded-xl bg-cinema-950">
            <Image
              priority
              src={movie.backdrop}
              alt={`${movie.title} still`}
              fill
              sizes="(max-width: 1024px) 100vw, 45vw"
              className="object-cover transition-transform duration-700 group-hover:scale-105"
            />
            {/* Vignette Overlay */}
            <div className="absolute inset-0 bg-gradient-to-t from-cinema-950 via-cinema-950/30 to-transparent" />

            {/* Badges on poster */}
            <div className="absolute left-4 top-4 flex items-center gap-2">
              <span className="rounded-md bg-black/75 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-white backdrop-blur-md border border-white/10">
                Featured Spotlight
              </span>
              <span className="rounded-md bg-accent-rose/90 px-2.5 py-1 font-mono text-[10px] font-bold text-white shadow-glow-rose">
                98% Match
              </span>
            </div>

            {/* Trailer preview / Play button */}
            <Link
              href={`/movies/${movie.id}`}
              aria-label={`Open ${movie.title}`}
              className="absolute bottom-5 right-5 grid h-13 w-13 place-items-center rounded-full bg-accent-rose text-white shadow-glow-rose transition-all duration-300 hover:scale-110 hover:bg-accent-rose-hover cursor-pointer"
            >
              <Play size={20} className="fill-current ml-0.5" />
            </Link>

            {/* Rating pill */}
            <div className="absolute bottom-5 left-5 flex items-center gap-2">
              <span className="flex items-center gap-1 rounded-md bg-black/80 px-2.5 py-1 font-mono text-xs font-bold text-accent-gold backdrop-blur-md border border-white/10">
                <Star size={13} className="fill-accent-gold" /> {movie.rating}
              </span>
              <span className="rounded-md bg-black/80 px-2 py-1 font-mono text-[11px] text-cinema-300 backdrop-blur-md">
                4K Ultra HD
              </span>
            </div>
          </div>

          {/* Bottom Information Card */}
          <div className="mt-4 px-2 pb-2">
            <div className="flex items-center justify-between text-xs text-cinema-400">
              <span className="font-mono uppercase tracking-wider text-accent-rose">Now in Focus</span>
              <span className="font-mono">{movie.year} · {movie.runtime}</span>
            </div>

            <Link
              href={`/movies/${movie.id}`}
              className="mt-2 flex items-center justify-between gap-3 font-editorial text-2xl font-bold leading-tight text-white transition-colors group-hover:text-rose-400 sm:text-3xl"
            >
              <span>{movie.title}</span>
              <ArrowUpRight className="shrink-0 text-cinema-400 group-hover:text-accent-rose transition-colors" size={22} />
            </Link>

            <p className="mt-2 text-xs leading-relaxed text-cinema-400 line-clamp-2">
              {movie.description}
            </p>

            <div className="mt-3 flex flex-wrap gap-1.5">
              {movie.genres.map((genre) => (
                <span
                  key={genre}
                  className="rounded-full border border-cinema-700/60 bg-cinema-850 px-2.5 py-0.5 font-mono text-[10px] text-cinema-300"
                >
                  {genre}
                </span>
              ))}
            </div>
          </div>
        </article>
      </section>

      {/* AI Recommend Modal */}
      <AiRecommendModal isOpen={showAiModal} onClose={() => setShowAiModal(false)} />
    </>
  );
}
