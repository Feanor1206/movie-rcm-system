'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Sparkles, X, Star, ArrowRight, Check, Compass } from 'lucide-react';
import { movies } from '@/lib/data/movies';
import { useWatchlist } from '@/lib/context/WatchlistContext';
import type { Movie } from '@/types/movie';

const VIBES = [
  { id: 'scifi-mind', label: '🚀 Deep Space & Mystery', genres: ['Sci-Fi', 'Mystery'], matchId: 'the-last-orbit' },
  { id: 'noir-late', label: '🌃 Midnight Atmospheric', genres: ['Crime', 'Thriller'], matchId: 'nocturne' },
  { id: 'emotional-deep', label: '🕯️ Quiet & Heartfelt', genres: ['Drama', 'Romance'], matchId: 'quiet-places' },
  { id: 'intellectual-thrill', label: '🧩 Architectures & Mind Games', genres: ['Thriller', 'Sci-Fi'], matchId: 'glass-horizon' },
  { id: 'epic-journey', label: '🌊 Oceanic Odyssey', genres: ['Adventure', 'Drama'], matchId: 'deep-blue' },
];

export function AiRecommendModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [selectedVibe, setSelectedVibe] = useState(VIBES[0].id);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [matchedMovie, setMatchedMovie] = useState<Movie | null>(movies[0]);
  const { isWatchlisted, toggleWatchlist } = useWatchlist();

  if (!isOpen) return null;

  const handleSelectVibe = (vibeId: string) => {
    setSelectedVibe(vibeId);
    setIsAnalyzing(true);
    const target = VIBES.find((v) => v.id === vibeId);
    setTimeout(() => {
      const found = movies.find((m) => m.id === target?.matchId) || movies[0];
      setMatchedMovie(found);
      setIsAnalyzing(false);
    }, 400);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-2xl rounded-2xl border border-cinema-700 bg-cinema-900/95 p-6 sm:p-8 shadow-2xl backdrop-blur-2xl">
        {/* Close Button */}
        <button
          onClick={onClose}
          aria-label="Close AI Recommendation modal"
          className="absolute right-4 top-4 rounded-full p-2 text-cinema-400 transition hover:bg-cinema-800 hover:text-white cursor-pointer"
        >
          <X size={20} />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent-rose/20 text-accent-rose border border-accent-rose/30">
            <Sparkles size={20} />
          </div>
          <div>
            <span className="eyebrow">AI Vibe Matcher</span>
            <h2 className="font-editorial text-2xl sm:text-3xl font-bold text-white">Find Your Tonight's Film</h2>
          </div>
        </div>

        {/* Vibe Chips Selector */}
        <div className="mt-6">
          <label className="font-mono text-xs text-cinema-400 block mb-2.5">
            1. Select what you feel like experiencing:
          </label>
          <div className="flex flex-wrap gap-2">
            {VIBES.map((vibe) => {
              const active = selectedVibe === vibe.id;
              return (
                <button
                  key={vibe.id}
                  onClick={() => handleSelectVibe(vibe.id)}
                  className={`rounded-full px-4 py-2 font-mono text-xs transition-all duration-200 cursor-pointer ${
                    active
                      ? 'border border-accent-rose bg-accent-rose/20 text-white font-semibold shadow-glow-rose'
                      : 'border border-cinema-700 bg-cinema-850 text-cinema-300 hover:border-cinema-500 hover:text-white'
                  }`}
                >
                  {vibe.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Matched Result Area */}
        <div className="mt-6 pt-6 border-t border-cinema-800">
          <label className="font-mono text-xs text-cinema-400 block mb-3">
            2. Recommended AI match result (98% match):
          </label>

          {isAnalyzing ? (
            <div className="flex flex-col items-center justify-center py-10 text-center animate-pulse">
              <Compass className="animate-spin text-accent-rose mb-3" size={32} />
              <p className="font-mono text-xs text-cinema-300">Analyzing semantic patterns and cinematic mood...</p>
            </div>
          ) : matchedMovie ? (
            <div className="flex flex-col sm:flex-row gap-5 rounded-xl border border-cinema-750 bg-cinema-850/80 p-4 transition-all hover:border-cinema-600">
              <div className="relative h-44 w-32 shrink-0 overflow-hidden rounded-lg border border-cinema-700">
                <Image
                  src={matchedMovie.poster}
                  alt={matchedMovie.title}
                  fill
                  className="object-cover"
                  sizes="130px"
                />
                <span className="absolute top-2 left-2 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10px] font-bold text-accent-gold flex items-center gap-1">
                  <Star size={10} className="fill-accent-gold" /> {matchedMovie.rating}
                </span>
              </div>

              <div className="flex flex-col justify-between flex-1">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-accent-rose/20 px-2 py-0.5 font-mono text-[10px] font-bold text-accent-rose border border-accent-rose/30">
                      Top Recommendation
                    </span>
                    <span className="font-mono text-xs text-cinema-400">{matchedMovie.year} · {matchedMovie.runtime}</span>
                  </div>
                  <h3 className="font-editorial text-2xl font-bold text-white mt-1.5">{matchedMovie.title}</h3>
                  <p className="mt-2 text-xs leading-relaxed text-cinema-300 line-clamp-2">
                    {matchedMovie.description}
                  </p>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <Link
                    href={`/movies/${matchedMovie.id}`}
                    onClick={onClose}
                    className="btn-primary py-2 px-4 text-xs font-mono"
                  >
                    View Film Details <ArrowRight size={14} />
                  </Link>

                  <button
                    onClick={() => toggleWatchlist(matchedMovie.id, matchedMovie.title)}
                    className="btn-secondary py-2 px-4 text-xs font-mono"
                  >
                    {isWatchlisted(matchedMovie.id) ? (
                      <>
                        <Check size={14} className="text-accent-rose" /> In Watchlist
                      </>
                    ) : (
                      '+ Add to Watchlist'
                    )}
                  </button>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
