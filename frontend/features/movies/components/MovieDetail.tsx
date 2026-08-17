'use client';

import React, { useState, useRef } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import {
  ArrowLeft,
  Check,
  Heart,
  Play,
  Star,
  Clock,
  Calendar,
  X,
  Maximize2,
  Volume2,
  VolumeX,
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
  const {
    isWatchlisted,
    toggleWatchlist,
    isFavorite,
    toggleFavorite,
    getRating,
    rateMovie,
    openChat,
  } = useWatchlist();
  const [hoverRating, setHoverRating] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const inWatchlist = isWatchlisted(movie.id);
  const favorite = isFavorite(movie.id);
  const currentRating = getRating(movie.id);

  const videoSource = movie.videoUrl || `/videos/${movie.id}.mp4`;

  return (
    <main className="min-h-screen bg-black">
      {/* Video Player Modal / Player Overlay */}
      {isPlaying && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/95 backdrop-blur-md p-4 sm:p-8 animate-fade-in">
          <div className="relative w-full max-w-5xl overflow-hidden rounded-xl border border-zinc-800 bg-black shadow-2xl">
            {/* Player Header Bar */}
            <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950 px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-cinema-red" />
                <h3 className="text-sm font-bold text-white truncate">{movie.title}</h3>
                <span className="text-xs text-zinc-400">• Đang phát 4K HD</span>
              </div>
              <button
                onClick={() => setIsPlaying(false)}
                className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-white transition-colors cursor-pointer"
                aria-label="Đóng trình phát"
              >
                <X size={18} />
              </button>
            </div>

            {/* Video Container */}
            <div className="relative aspect-video w-full bg-black">
              <video
                ref={videoRef}
                src={videoSource}
                controls
                autoPlay
                className="h-full w-full object-contain"
              >
                Trình duyệt của bạn không hỗ trợ thẻ video HTML5.
              </video>
            </div>
          </div>
        </div>
      )}

      {/* Hero Backdrop */}
      <section className="relative overflow-hidden border-b border-zinc-800 bg-black">
        {/* Backdrop Image Layer */}
        <div className="absolute inset-0 z-0 h-full w-full">
          <Image
            src={movie.backdrop}
            alt={movie.title}
            fill
            priority
            className="object-cover opacity-75 sm:opacity-85"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black via-black/80 to-black/30" />
          <div className="absolute inset-0 bg-gradient-to-r from-black via-black/75 to-transparent" />
        </div>

        {/* Content Layer */}
        <div className="page-shell relative z-10 pb-12 pt-6 sm:pt-10">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-zinc-400 transition hover:text-white mb-6 cursor-pointer"
          >
            <ArrowLeft size={14} /> Quay lại trang chủ
          </Link>

          <div className="flex flex-col gap-6 md:flex-row md:items-end">
            {/* Poster */}
            <div className="relative shrink-0">
              <div className="relative aspect-[2/3] w-44 overflow-hidden rounded-lg border border-zinc-700 bg-zinc-900 shadow-2xl sm:w-56">
                <Image
                  src={movie.poster}
                  alt={movie.title}
                  fill
                  sizes="(max-width: 640px) 176px, 224px"
                  className="object-cover"
                />
                <span className="absolute top-2.5 left-2.5 flex items-center gap-1 rounded bg-black/80 px-2 py-0.5 text-xs font-bold text-amber-400 border border-white/10">
                  <Star size={12} className="fill-amber-400" /> {movie.rating}
                </span>
              </div>
            </div>

            {/* Info */}
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded bg-cinema-red px-2 py-0.5 font-bold text-white uppercase text-[10px]">
                  Bản phát hành chính thức
                </span>
                <span className="rounded bg-zinc-800 border border-zinc-700 px-2 py-0.5 text-zinc-300">
                  4K UHD · HDR10+ · Dolby 5.1
                </span>
              </div>

              <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-white sm:text-5xl drop-shadow-md">
                {movie.title}
              </h1>

              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs sm:text-sm text-zinc-300">
                <span className="flex items-center gap-1 text-white font-bold">
                  <Star size={14} className="fill-amber-400 text-amber-400" />
                  {movie.rating} / 10
                </span>
                <span className="flex items-center gap-1 text-zinc-400">
                  <Calendar size={13} /> {movie.year}
                </span>
                <span className="flex items-center gap-1 text-zinc-400">
                  <Clock size={13} /> {movie.runtime}
                </span>
                <span className="text-zinc-400">
                  {movie.genres.join(', ')}
                </span>
              </div>

              <p className="mt-4 max-w-2xl text-sm sm:text-base leading-relaxed text-zinc-200 drop-shadow">
                {movie.description}
              </p>

              {/* Action Buttons */}
              <div className="mt-6 flex flex-wrap items-center gap-3">
                <button
                  onClick={() => setIsPlaying(true)}
                  className="btn-primary px-6 py-2.5 text-sm font-bold shadow-red-sm"
                >
                  <Play size={16} className="fill-current" />
                  Xem phim ngay
                </button>

                <button
                  onClick={() => toggleWatchlist(movie.id, movie.title, movie.poster)}
                  className="btn-secondary px-4 py-2.5 text-sm font-semibold"
                  aria-label={inWatchlist ? 'Xóa khỏi Watchlist' : 'Thêm vào Watchlist'}
                >
                  {inWatchlist ? (
                    <>
                      <Check size={15} className="text-cinema-red" /> Đã lưu Watchlist
                    </>
                  ) : (
                    '+ Thêm vào Watchlist'
                  )}
                </button>

                <button
                  onClick={() => toggleFavorite(movie.id, movie.title)}
                  className={`rounded-md border p-2.5 transition-colors cursor-pointer ${
                    favorite
                      ? 'border-cinema-red bg-cinema-red/15 text-cinema-red'
                      : 'border-zinc-700 bg-zinc-900 text-zinc-300 hover:border-zinc-500 hover:text-white'
                  }`}
                  aria-label={favorite ? 'Đã yêu thích' : 'Thêm vào Yêu thích'}
                >
                  <Heart size={16} className={favorite ? 'fill-current' : ''} />
                </button>

                <button
                  onClick={openChat}
                  className="rounded-md border border-zinc-700 bg-zinc-900 px-3.5 py-2.5 text-xs font-medium text-zinc-300 hover:border-cinema-red hover:text-white cursor-pointer"
                >
                  Hỏi CineBot
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Main Details Body */}
      <div className="page-shell py-10">
        <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
          {/* Left: Overview & Rating Selector */}
          <div className="space-y-8">
            {/* Interactive Rating Selector */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 sm:p-6">
              <h2 className="text-base font-bold text-white">Đánh giá bộ phim này</h2>
              <p className="mt-1 text-xs text-zinc-400">
                Chấm điểm giúp hệ thống hiểu rõ gu phim của bạn hơn.
              </p>

              <div className="mt-4 flex flex-wrap items-center gap-1.5">
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
                      className={`flex h-9 w-9 items-center justify-center rounded-md text-xs font-bold transition-all duration-150 cursor-pointer ${
                        active
                          ? 'bg-amber-400 text-black scale-105'
                          : 'border border-zinc-800 bg-zinc-900 text-zinc-400 hover:border-zinc-600 hover:text-white'
                      }`}
                      aria-label={`Chấm ${star} trên 10 sao`}
                    >
                      {star}
                    </button>
                  );
                })}
              </div>

              {currentRating && (
                <p className="mt-3 text-xs text-amber-400 flex items-center gap-1 font-medium">
                  <Check size={14} /> Bạn đã chấm bộ phim này {currentRating}/10 điểm.
                </p>
              )}
            </div>

            {/* Synopsis Section */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 sm:p-6">
              <h2 className="text-base font-bold text-white mb-2">Tóm tắt nội dung</h2>
              <p className="text-sm text-zinc-300 leading-relaxed">
                {movie.description} Tác phẩm được ghi hình ở độ phân giải gốc 4K với hệ thống âm thanh vòm không gian đa kênh sống động, mang lại trải nghiệm xem phim chất lượng cao tại nhà.
              </p>
            </div>
          </div>

          {/* Right: Technical Attributes */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 sm:p-6 h-fit">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 mb-3">
              Thông tin phát hành
            </h3>

            <dl className="space-y-3 text-xs">
              <div>
                <dt className="text-zinc-500">Thể loại</dt>
                <dd className="mt-1 flex flex-wrap gap-1">
                  {movie.genres.map((genre) => (
                    <Link
                      key={genre}
                      href={`/search?genre=${encodeURIComponent(genre)}`}
                      className="rounded bg-zinc-900 border border-zinc-800 px-2 py-0.5 text-zinc-300 hover:border-cinema-red hover:text-white transition-colors"
                    >
                      {genre}
                    </Link>
                  ))}
                </dd>
              </div>

              <div className="pt-2 border-t border-zinc-800">
                <dt className="text-zinc-500">Năm sản xuất</dt>
                <dd className="text-white font-medium mt-0.5">{movie.year}</dd>
              </div>

              <div className="pt-2 border-t border-zinc-800">
                <dt className="text-zinc-500">Thời lượng</dt>
                <dd className="text-white font-medium mt-0.5">{movie.runtime}</dd>
              </div>

              <div className="pt-2 border-t border-zinc-800">
                <dt className="text-zinc-500">Chất lượng hình ảnh</dt>
                <dd className="text-white font-medium mt-0.5">4K Ultra HD (HDR10+ / Dolby Vision)</dd>
              </div>

              <div className="pt-2 border-t border-zinc-800">
                <dt className="text-zinc-500">Âm thanh</dt>
                <dd className="text-white font-medium mt-0.5">Dolby Atmos 5.1 / 7.1 Surround</dd>
              </div>
            </dl>
          </div>
        </div>

        {/* Similar Movies */}
        <div className="mt-12 pt-8 border-t border-zinc-800">
          <MovieSection
            title="Phim tương tự"
            subtitle="Các tác phẩm có phong cách và chủ đề tương tự"
            movies={similarMovies}
          />
        </div>
      </div>
    </main>
  );
}
