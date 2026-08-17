'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import {
  ArrowLeft,
  Bookmark,
  Check,
  Film,
  Heart,
  Play,
  Share2,
  Sparkles,
  Star,
  Tv,
  Volume2,
  Clock,
  Calendar,
} from 'lucide-react';
import type { Movie } from '@/types/movie';
import { useWatchlist } from '@/lib/context/WatchlistContext';
import { MovieSection } from './MovieSection';

export function MovieDetail({
  movie,
  similarMovies,
}: {
  movie: Movie;
  similarMovies: Movie[];
}) {
  const { isWatchlisted, toggleWatchlist, isFavorite, toggleFavorite, getRating, rateMovie } = useWatchlist();
  const [hoverRating, setHoverRating] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const inWatchlist = isWatchlisted(movie.id);
  const favorite = isFavorite(movie.id);
  const currentRating = getRating(movie.id);

  return (
    <main className="min-h-screen bg-cinema-950">
      {/* Hero Backdrop Banner */}
      <section className="relative isolate overflow-hidden border-b border-cinema-800/80">
        {/* Full Backdrop */}
        <div className="absolute inset-0 -z-20 h-full w-full">
          <Image
            src={movie.backdrop}
            alt={`${movie.title} backdrop`}
            fill
            priority
            className="object-cover opacity-30 sm:opacity-40"
          />
          {/* Gradients */}
          <div className="absolute inset-0 bg-gradient-to-t from-cinema-950 via-cinema-950/70 to-cinema-950/40" />
          <div className="absolute inset-0 bg-radial-at-c from-transparent via-cinema-950/60 to-cinema-950" />
        </div>

        {/* Content Shell */}
        <div className="page-shell pb-14 pt-8 sm:pt-12">
          {/* Back link */}
          <Link
            href="/"
            className="inline-flex items-center gap-2 font-mono text-xs text-cinema-400 transition hover:text-white mb-8 cursor-pointer"
          >
            <ArrowLeft size={14} /> Back to Discover
          </Link>

          <div className="flex flex-col gap-8 md:flex-row md:items-end">
            {/* Movie Poster with Card Frame */}
            <div className="relative shrink-0">
              <div className="relative aspect-[2/3] w-48 overflow-hidden rounded-2xl border border-cinema-700 bg-cinema-900 shadow-2xl sm:w-60">
                <Image
                  src={movie.poster}
                  alt={`${movie.title} poster`}
                  fill
                  sizes="(max-width: 640px) 192px, 240px"
                  className="object-cover"
                />
                <span className="absolute top-3 left-3 rounded-md bg-black/80 px-2.5 py-1 font-mono text-xs font-bold text-accent-gold backdrop-blur-md border border-white/10 flex items-center gap-1">
                  <Star size={13} className="fill-accent-gold" /> {movie.rating}
                </span>
              </div>
            </div>

            {/* Movie Info & Primary Actions */}
            <div className="flex-1">
              {/* Badges */}
              <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
                <span className="rounded bg-accent-rose/20 px-2.5 py-1 font-bold text-accent-rose border border-accent-rose/30">
                  Featured Presentation
                </span>
                <span className="rounded bg-cinema-900/80 px-2.5 py-1 text-cinema-300 border border-cinema-750">
                  4K UHD · Dolby Atmos
                </span>
              </div>

              {/* Title */}
              <h1 className="font-editorial mt-3 text-4xl font-bold tracking-tight text-white sm:text-5xl lg:text-6xl">
                {movie.title}
              </h1>

              {/* Metadata row */}
              <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-xs text-cinema-300">
                <span className="flex items-center gap-1 text-white font-semibold">
                  <Star size={14} className="fill-accent-gold text-accent-gold" />
                  {movie.rating} / 10
                </span>
                <span className="flex items-center gap-1 text-cinema-400">
                  <Calendar size={13} /> {movie.year}
                </span>
                <span className="flex items-center gap-1 text-cinema-400">
                  <Clock size={13} /> {movie.runtime}
                </span>
                <span className="text-cinema-400">
                  {movie.genres.join(' • ')}
                </span>
              </div>

              {/* Synopsis */}
              <p className="mt-5 max-w-2xl text-sm sm:text-base leading-relaxed text-cinema-200">
                {movie.description}
              </p>

              {/* Action Buttons */}
              <div className="mt-8 flex flex-wrap items-center gap-3.5">
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  className="btn-primary px-6 py-3"
                >
                  <Play size={16} className="fill-current" />
                  {isPlaying ? 'Pause Film' : 'Play Now'}
                </button>

                <button
                  onClick={() => toggleWatchlist(movie.id, movie.title)}
                  className="btn-secondary px-5 py-3"
                  aria-label={inWatchlist ? 'Remove from Watchlist' : 'Add to Watchlist'}
                >
                  {inWatchlist ? (
                    <>
                      <Check size={16} className="text-accent-rose" /> Saved to Watchlist
                    </>
                  ) : (
                    <>
                      <Bookmark size={16} /> Add to Watchlist
                    </>
                  )}
                </button>

                <button
                  onClick={() => toggleFavorite(movie.id, movie.title)}
                  className={`rounded-lg border p-3 transition-colors cursor-pointer ${
                    favorite
                      ? 'border-accent-rose bg-accent-rose/20 text-accent-rose'
                      : 'border-cinema-700 bg-cinema-900/80 text-cinema-300 hover:border-cinema-500 hover:text-white'
                  }`}
                  aria-label={favorite ? 'Favorited' : 'Add to Favorites'}
                >
                  <Heart size={16} className={favorite ? 'fill-current' : ''} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Main Details & Recommendations Body */}
      <div className="page-shell py-12">
        <div className="grid gap-10 lg:grid-cols-[1fr_360px]">
          {/* Left Column: AI Recommendation Reasoning & Overview */}
          <div className="space-y-10">
            {/* AI Recommendation Reasoning */}
            <div className="rounded-2xl border border-accent-rose/30 bg-cinema-900/70 p-6 backdrop-blur-xl shadow-xl">
              <div className="flex items-center gap-2 text-accent-rose font-mono text-xs font-semibold uppercase tracking-wider">
                <Sparkles size={16} className="animate-pulse" />
                <span>AI Recommendation Insight</span>
              </div>
              <h3 className="font-editorial text-2xl font-bold text-white mt-2">Why This Film Matches You</h3>
              <p className="mt-3 text-sm leading-relaxed text-cinema-300">
                This film shares high thematic affinity with contemplative masterpieces like <em>Blade Runner 2049</em> and <em>Interstellar</em>. 
                Our neural recommendation model detected matching pacing (deliberate), narrative complexity (high), and atmospheric sound design.
              </p>

              <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div className="rounded-lg border border-cinema-800 bg-cinema-950/70 p-3">
                  <span className="font-mono text-[10px] uppercase text-cinema-500 block">Vibe Match</span>
                  <span className="font-mono text-sm font-bold text-white">98.4%</span>
                </div>
                <div className="rounded-lg border border-cinema-800 bg-cinema-950/70 p-3">
                  <span className="font-mono text-[10px] uppercase text-cinema-500 block">Atmosphere</span>
                  <span className="font-mono text-sm font-bold text-accent-gold">Cinematic Noir</span>
                </div>
                <div className="rounded-lg border border-cinema-800 bg-cinema-950/70 p-3 col-span-2 sm:col-span-1">
                  <span className="font-mono text-[10px] uppercase text-cinema-500 block">Audio Master</span>
                  <span className="font-mono text-sm font-bold text-white">Lossless Atmos</span>
                </div>
              </div>
            </div>

            {/* Interactive User Rating Selector */}
            <div className="rounded-2xl border border-cinema-800 bg-cinema-900/50 p-6">
              <span className="eyebrow">Interactive Review</span>
              <h3 className="font-editorial text-xl font-bold text-white mt-1">Rate this Film</h3>
              <p className="mt-1 text-xs text-cinema-400">
                Your rating helps tune your personal recommendation algorithm.
              </p>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((star) => {
                  const isSelected = (currentRating || 0) >= star;
                  const isHovered = (hoverRating || 0) >= star;
                  const active = hoverRating !== null ? isHovered : isSelected;

                  return (
                    <button
                      key={star}
                      onMouseEnter={() => setHoverRating(star)}
                      onMouseLeave={() => setHoverRating(null)}
                      onClick={() => rateMovie(movie.id, star, movie.title)}
                      className={`flex h-9 w-9 items-center justify-center rounded-lg font-mono text-xs font-bold transition-all duration-150 cursor-pointer ${
                        active
                          ? 'border border-accent-gold bg-accent-gold/20 text-accent-gold scale-110 shadow-glow-gold'
                          : 'border border-cinema-800 bg-cinema-850 text-cinema-400 hover:border-cinema-600 hover:text-white'
                      }`}
                      aria-label={`Rate ${star} out of 10`}
                    >
                      {star}
                    </button>
                  );
                })}
              </div>

              {currentRating && (
                <p className="mt-3 font-mono text-xs text-accent-gold flex items-center gap-1.5">
                  <Check size={14} /> You rated this film {currentRating}/10 stars.
                </p>
              )}
            </div>
          </div>

          {/* Right Column: Film Metadata & Specifications */}
          <div className="space-y-6">
            <div className="rounded-2xl border border-cinema-800 bg-cinema-900/60 p-6 backdrop-blur-md">
              <h4 className="font-mono text-xs font-semibold uppercase tracking-wider text-cinema-300 mb-4">
                Film Attributes
              </h4>

              <dl className="space-y-3.5 text-xs">
                <div>
                  <dt className="font-mono text-cinema-500">Genres</dt>
                  <dd className="mt-1 flex flex-wrap gap-1.5">
                    {movie.genres.map((genre) => (
                      <Link
                        key={genre}
                        href={`/search?genre=${encodeURIComponent(genre)}`}
                        className="rounded-md border border-cinema-750 bg-cinema-850 px-2.5 py-0.5 font-mono text-cinema-300 transition hover:border-accent-rose hover:text-white"
                      >
                        {genre}
                      </Link>
                    ))}
                  </dd>
                </div>

                <div className="pt-2 border-t border-cinema-850">
                  <dt className="font-mono text-cinema-500">Release Year</dt>
                  <dd className="mt-0.5 font-sans font-medium text-white">{movie.year}</dd>
                </div>

                <div className="pt-2 border-t border-cinema-850">
                  <dt className="font-mono text-cinema-500">Duration</dt>
                  <dd className="mt-0.5 font-sans font-medium text-white">{movie.runtime}</dd>
                </div>

                <div className="pt-2 border-t border-cinema-850">
                  <dt className="font-mono text-cinema-500">Streaming Quality</dt>
                  <dd className="mt-0.5 font-sans font-medium text-white">4K UHD HDR10+ / Dolby Vision</dd>
                </div>

                <div className="pt-2 border-t border-cinema-850">
                  <dt className="font-mono text-cinema-500">Audio Track</dt>
                  <dd className="mt-0.5 font-sans font-medium text-white">English [Original] (Dolby Atmos 7.1)</dd>
                </div>
              </dl>
            </div>
          </div>
        </div>

        {/* Similar Recommendations Row */}
        <div className="mt-16 pt-10 border-t border-cinema-800">
          <MovieSection
            title="More Like This"
            subtitle="Films with similar thematic resonance and cinematic styling"
            movies={similarMovies}
          />
        </div>
      </div>
    </main>
  );
}
