'use client';

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import Link from 'next/link';
import {
  Bookmark,
  Heart,
  Star,
  Film,
  ArrowRight,
  Loader2,
  RefreshCw,
  AlertCircle,
  Trash2,
  User,
  ShieldAlert,
} from 'lucide-react';
import { MovieCard } from '@/features/movies/components/MovieCard';
import { useWatchlist } from '@/lib/context/WatchlistContext';
import { useAuth } from '@/lib/context/AuthContext';
import type { Movie } from '@/types/movie';
import { getCatalogMovieById, CatalogApiError } from '@/lib/services/catalogService';

type Tab = 'watchlist' | 'favorites' | 'ratings';

type HydrationStatus = 'loading' | 'found' | 'not_found' | 'error';
type HydratedItem = {
  movie?: Movie;
  status: HydrationStatus;
  expiresAt?: number;
};

// Bounded in-memory metadata cache for public catalog movies (max 200 entries, 5-min TTL)
// Strictly stores public movie metadata; never user-specific state or account lists.
const METADATA_TTL_MS = 5 * 60 * 1000;
const profileMetadataCache = new Map<string, { movie: Movie; expiresAt: number }>();

export function clearProfileMetadataCache() {
  profileMetadataCache.clear();
}

export function ProfileOverview() {
  const [activeTab, setActiveTab] = useState<Tab>('watchlist');
  const {
    watchlist,
    favorites,
    ratings,
    openChat,
    isLibraryLoading,
    libraryError,
    refetchLibrary,
    isGuestMode,
    toggleWatchlist,
    toggleFavorite,
    rateMovie,
    removeRating,
    isActionPending,
    isActionUnconfirmed,
    getActionIntent,
    getUnconfirmedRating,
    showToast,
  } = useWatchlist();

  const { user, status, openAuthModal, retryVerify } = useAuth();

  // Remote catalog hydration for canonical IDs (no static fixture dependency)
  const [remoteMovies, setRemoteMovies] = useState<Record<string, HydratedItem>>({});

  const allItemIds = useMemo(() => {
    const set = new Set<string>();
    watchlist.forEach((id) => set.add(id));
    favorites.forEach((id) => set.add(id));
    Object.keys(ratings).forEach((id) => set.add(id));
    return Array.from(set);
  }, [watchlist, favorites, ratings]);

  const activeHydrationAbortControllersRef = useRef<Map<string, AbortController>>(new Map());

  const fetchRemoteMovie = useCallback(async (id: string) => {
    const now = Date.now();
    // Check bounded metadata cache first
    const cached = profileMetadataCache.get(id);
    if (cached && cached.expiresAt > now) {
      setRemoteMovies((prev) => ({
        ...prev,
        [id]: { movie: cached.movie, status: 'found', expiresAt: cached.expiresAt },
      }));
      return;
    } else if (cached && cached.expiresAt <= now) {
      profileMetadataCache.delete(id);
    }

    const existingCtrl = activeHydrationAbortControllersRef.current.get(id);
    if (existingCtrl) {
      existingCtrl.abort();
    }

    const abortCtrl = new AbortController();
    activeHydrationAbortControllersRef.current.set(id, abortCtrl);

    setRemoteMovies((prev) => ({ ...prev, [id]: { status: 'loading' } }));

    try {
      const movie = await getCatalogMovieById(id, {
        signal: abortCtrl.signal,
        timeoutMs: 6000,
      });

      if (!movie) {
        // HTTP 404: Orphan item not found in backend catalog
        setRemoteMovies((prev) => ({ ...prev, [id]: { status: 'not_found' } }));
      } else {
        const expiresAt = Date.now() + METADATA_TTL_MS;
        // Enforce bounded cache size
        if (profileMetadataCache.size >= 200) {
          const oldestKey = profileMetadataCache.keys().next().value;
          if (oldestKey) profileMetadataCache.delete(oldestKey);
        }
        profileMetadataCache.set(id, { movie, expiresAt });

        setRemoteMovies((prev) => ({ ...prev, [id]: { movie, status: 'found', expiresAt } }));
      }
    } catch (err: any) {
      if (err?.isCanceled || err?.name === 'AbortError') {
        return; // Caller unmounted or cancelled
      }
      // Server error / network error / timeout: mark as 'error', preserve item in library!
      setRemoteMovies((prev) => ({ ...prev, [id]: { status: 'error' } }));
    } finally {
      activeHydrationAbortControllersRef.current.delete(id);
    }
  }, []);

  useEffect(() => {
    return () => {
      for (const ctrl of activeHydrationAbortControllersRef.current.values()) {
        try {
          ctrl.abort();
        } catch {}
      }
      activeHydrationAbortControllersRef.current.clear();
    };
  }, []);

  // Cleanup removed IDs from remoteMovies and abort in-flight hydration
  useEffect(() => {
    const currentIdSet = new Set(allItemIds);
    for (const [id, ctrl] of activeHydrationAbortControllersRef.current.entries()) {
      if (!currentIdSet.has(id)) {
        try {
          ctrl.abort();
        } catch {}
        activeHydrationAbortControllersRef.current.delete(id);
      }
    }
    setRemoteMovies((prev) => {
      const keys = Object.keys(prev);
      const staleKeys = keys.filter((k) => !currentIdSet.has(k));
      if (staleKeys.length === 0) return prev;
      const next = { ...prev };
      for (const k of staleKeys) {
        delete next[k];
      }
      return next;
    });
  }, [allItemIds]);

  // Hydrate missing or expired catalog metadata for current library items
  useEffect(() => {
    const now = Date.now();
    const staleOrMissing = allItemIds.filter((id) => {
      const cached = profileMetadataCache.get(id);
      if (cached && cached.expiresAt > now) {
        return false;
      }
      const remote = remoteMovies[id];
      if (!remote) return true;
      if (remote.status === 'loading') return false;
      if (remote.status === 'found' && remote.expiresAt && remote.expiresAt <= now) {
        return true;
      }
      return false;
    });

    staleOrMissing.forEach((id) => {
      fetchRemoteMovie(id);
    });
  }, [allItemIds, remoteMovies, fetchRemoteMovie]);

  // Window focus listener: revalidate expired items upon returning to tab without background polling
  useEffect(() => {
    const handleRevalidateStale = () => {
      const now = Date.now();
      const needsRevalidation = allItemIds.filter((id) => {
        const cached = profileMetadataCache.get(id);
        if (cached && cached.expiresAt <= now) profileMetadataCache.delete(id);
        const remote = remoteMovies[id];
        return remote?.status === 'found' && remote.expiresAt && remote.expiresAt <= now;
      });
      needsRevalidation.forEach((id) => {
        fetchRemoteMovie(id);
      });
    };

    if (typeof window !== 'undefined') {
      window.addEventListener('focus', handleRevalidateStale);
      return () => {
        window.removeEventListener('focus', handleRevalidateStale);
      };
    }
  }, [allItemIds, remoteMovies, fetchRemoteMovie]);

  const resolveMovieItem = useCallback(
    (id: string): HydratedItem => {
      const now = Date.now();
      const cached = profileMetadataCache.get(id);
      if (cached) {
        if (cached.expiresAt > now) {
          return { movie: cached.movie, status: 'found', expiresAt: cached.expiresAt };
        } else {
          profileMetadataCache.delete(id);
        }
      }
      const remote = remoteMovies[id];
      if (remote) {
        if (remote.status === 'found' && remote.expiresAt && remote.expiresAt <= now) {
          return { status: 'loading' };
        }
        return remote;
      }
      return { status: 'loading' };
    },
    [remoteMovies]
  );

  const watchlistItems = useMemo(
    () => watchlist.map((id) => ({ id, ...resolveMovieItem(id) })),
    [watchlist, resolveMovieItem]
  );

  const favoriteItems = useMemo(
    () => favorites.map((id) => ({ id, ...resolveMovieItem(id) })),
    [favorites, resolveMovieItem]
  );

  const ratingItems = useMemo(
    () =>
      Object.entries(ratings).map(([id, rating]) => ({
        id,
        rating,
        ...resolveMovieItem(id),
      })),
    [ratings, resolveMovieItem]
  );

  // Genre analysis on known movies
  const genreCounts: Record<string, number> = {};
  [...watchlistItems, ...favoriteItems, ...ratingItems].forEach((item) => {
    if (item.movie) {
      item.movie.genres.forEach((genre) => {
        genreCounts[genre] = (genreCounts[genre] || 0) + 1;
      });
    }
  });

  const topGenres = Object.entries(genreCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);

  const getInitials = (name?: string) => {
    if (!name) return 'K';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    return name.slice(0, 2).toUpperCase();
  };

  const handleRemoveMissingItem = async (id: string, tab: Tab, title?: string) => {
    if (tab === 'watchlist') {
      await toggleWatchlist(id, title);
    } else if (tab === 'favorites') {
      await toggleFavorite(id, title);
    } else if (tab === 'ratings') {
      if (isActionUnconfirmed(id, 'rating')) {
        const intent = getActionIntent(id, 'rating');
        if (intent === 'rate') {
          const score = getUnconfirmedRating(id);
          if (typeof score === 'number' && Number.isFinite(score) && score >= 1 && score <= 10) {
            await rateMovie(id, score, title);
          } else {
            showToast('Không tìm thấy điểm số đánh giá hợp lệ để thử lại', 'error');
          }
          return;
        }
        if (intent === 'remove_rating') {
          await removeRating(id, title);
          return;
        }
      }
      // Confirmed removal or normal deletion
      await removeRating(id, title);
    }
  };

  return (
    <main className="page-shell min-h-[75vh] py-8 sm:py-12">
      {/* Session Unavailable Alert */}
      {status === 'unavailable' && (
        <div className="mb-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-200">
          <div className="flex items-center gap-3">
            <AlertCircle size={20} className="shrink-0 text-amber-400" />
            <div className="text-xs sm:text-sm">
              <span className="font-bold">Không thể kết nối đến máy chủ xác thực:</span> Dữ liệu cá nhân chưa thể đồng bộ trực tiếp.
            </div>
          </div>
          <button
            onClick={() => retryVerify()}
            className="flex items-center gap-1.5 rounded-md bg-amber-500/20 px-3 py-1.5 text-xs font-semibold text-amber-300 hover:bg-amber-500/30 transition-colors cursor-pointer"
          >
            <RefreshCw size={13} /> Thử kết nối lại
          </button>
        </div>
      )}

      {/* Profile Header */}
      <div className="rounded-xl border border-surface-border bg-surface p-6 sm:p-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="grid h-12 w-12 place-items-center rounded-md bg-brand text-base font-bold text-zinc-950 shadow-brand-sm">
              {isGuestMode ? <User size={22} /> : getInitials(user?.fullName || user?.username)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-brand uppercase tracking-wider">
                  {isGuestMode ? 'Chế độ khách' : 'Thành viên Dippie'}
                </span>
                <span className="text-zinc-500">•</span>
                <span className="text-xs text-zinc-400">
                  {isGuestMode ? 'Lưu trữ cục bộ trên thiết bị' : user?.email || 'Tài khoản đám mây'}
                </span>
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-white mt-0.5">
                {isGuestMode ? 'Khách ghé thăm' : user?.fullName || user?.username}
              </h1>
            </div>
          </div>

          {/* Quick CTA */}
          <div className="flex items-center gap-3">
            {isGuestMode ? (
              <button
                onClick={() => openAuthModal('register')}
                className="btn-primary text-xs w-full sm:w-auto"
              >
                Đăng ký để đồng bộ đám mây
              </button>
            ) : (
              <button onClick={openChat} className="btn-secondary text-xs w-full sm:w-auto">
                Tư vấn gu phim với CineBot
              </button>
            )}
          </div>
        </div>

        {/* Stats Row */}
        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4 border-t border-surface-border pt-6">
          <div className="rounded-lg border border-surface-border bg-surface-muted p-3 sm:p-4">
            <div className="flex items-center gap-2 text-zinc-400 text-xs">
              <Bookmark size={14} className="text-brand" />
              <span>Watchlist</span>
            </div>
            <p className="mt-1 text-lg sm:text-2xl font-bold text-white">{watchlist.length}</p>
          </div>

          <div className="rounded-lg border border-surface-border bg-surface-muted p-3 sm:p-4">
            <div className="flex items-center gap-2 text-zinc-400 text-xs">
              <Heart size={14} className="text-brand" />
              <span>Yêu thích</span>
            </div>
            <p className="mt-1 text-lg sm:text-2xl font-bold text-white">{favorites.length}</p>
          </div>

          <div className="rounded-lg border border-surface-border bg-surface-muted p-3 sm:p-4">
            <div className="flex items-center gap-2 text-zinc-400 text-xs">
              <Star size={14} className="text-brand" />
              <span>Đã chấm điểm</span>
            </div>
            <p className="mt-1 text-lg sm:text-2xl font-bold text-white">
              {Object.keys(ratings).length}
            </p>
          </div>

          <div className="rounded-lg border border-surface-border bg-surface-muted p-3 sm:p-4">
            <div className="flex items-center gap-2 text-zinc-400 text-xs">
              <Film size={14} className="text-brand" />
              <span>Thể loại ưu tiên</span>
            </div>
            <p className="mt-1 text-xs sm:text-sm font-semibold text-white truncate">
              {topGenres.length > 0 ? topGenres.map((g) => g[0]).join(', ') : 'Chưa xác định'}
            </p>
          </div>
        </div>
      </div>

      {/* Tabs Section */}
      <section className="mt-8">
        <div className="flex border-b border-surface-border">
          <button
            onClick={() => setActiveTab('watchlist')}
            className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs sm:text-sm font-bold transition-colors cursor-pointer ${
              activeTab === 'watchlist'
                ? 'border-brand text-brand'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Bookmark size={15} /> Watchlist ({watchlist.length})
          </button>

          <button
            onClick={() => setActiveTab('favorites')}
            className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs sm:text-sm font-bold transition-colors cursor-pointer ${
              activeTab === 'favorites'
                ? 'border-brand text-brand'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Heart size={15} /> Yêu thích ({favorites.length})
          </button>

          <button
            onClick={() => setActiveTab('ratings')}
            className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs sm:text-sm font-bold transition-colors cursor-pointer ${
              activeTab === 'ratings'
                ? 'border-brand text-brand'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Star size={15} /> Đã chấm điểm ({Object.keys(ratings).length})
          </button>
        </div>

        {/* Guest Mode notice */}
        {isGuestMode && (
          <div className="my-4 flex items-center justify-between rounded-lg border border-surface-border bg-surface-muted px-4 py-3 text-xs text-zinc-400">
            <span>
              Dữ liệu danh sách đang lưu trên trình duyệt của thiết bị này. Đăng nhập để bảo lưu và mở khóa gợi ý cá nhân hóa sâu.
            </span>
            <button
              onClick={() => openAuthModal('login')}
              className="font-bold text-brand hover:underline cursor-pointer shrink-0 ml-3"
            >
              Đăng nhập ngay
            </button>
          </div>
        )}

        {/* Persistent Library / Reconciliation Error Alert Banner */}
        {libraryError && (
          <div
            data-testid="library-error-banner"
            className="my-4 flex items-center justify-between rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-300"
          >
            <div className="flex items-center gap-2">
              <AlertCircle size={16} className="text-red-400 shrink-0" />
              <span>{libraryError}</span>
            </div>
            <button
              onClick={() => {
                const now = Date.now();
                for (const [id, cached] of profileMetadataCache.entries()) {
                  if (cached.expiresAt <= now) profileMetadataCache.delete(id);
                }
                refetchLibrary();
              }}
              className="flex items-center gap-1 rounded bg-red-500/20 px-3 py-1 font-semibold text-red-200 hover:bg-red-500/30 transition-colors cursor-pointer shrink-0"
              aria-label="Thử tải lại thư viện"
            >
              <RefreshCw size={12} /> Thử tải lại
            </button>
          </div>
        )}

        {/* Tab Content Panels */}
        <div className="mt-6">
          {isLibraryLoading && watchlist.length === 0 && favorites.length === 0 && Object.keys(ratings).length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-zinc-400">
              <Loader2 className="animate-spin text-brand mb-3" size={28} />
              <p className="text-xs">Đang tải thư viện cá nhân từ máy chủ...</p>
            </div>
          ) : (
            /* Data Grid */
            <>
              {activeTab === 'watchlist' && (
                watchlistItems.length > 0 ? (
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5 xl:grid-cols-6">
                    {watchlistItems.map((item) =>
                      item.status === 'found' && item.movie ? (
                        <MovieCard key={item.id} movie={item.movie} fluid />
                      ) : item.status === 'loading' ? (
                        <div
                          key={item.id}
                          className="flex h-56 flex-col items-center justify-center rounded-lg border border-zinc-800 bg-surface-muted p-4 text-xs"
                        >
                          <Loader2 size={18} className="animate-spin text-brand mb-2" />
                          <span className="text-zinc-500 text-[11px]">Đang tải dữ liệu...</span>
                        </div>
                      ) : item.status === 'error' ? (
                        <div
                          key={item.id}
                          className="flex flex-col justify-between rounded-lg border border-amber-900/40 bg-surface-muted p-4 text-xs"
                        >
                          <div>
                            <div className="flex items-center gap-1 text-[11px] text-amber-400 font-semibold mb-1">
                              <AlertCircle size={12} /> Lỗi kết nối
                            </div>
                            <p className="font-bold text-white truncate">{item.id}</p>
                            <p className="text-[11px] text-zinc-400 mt-1">
                              Không thể kết nối máy chủ để tải thông tin phim.
                            </p>
                          </div>
                          <div className="mt-3 flex flex-col gap-1.5">
                            <button
                              onClick={() => fetchRemoteMovie(item.id)}
                              className="flex items-center justify-center gap-1 rounded bg-zinc-800 py-1.5 text-[11px] text-zinc-300 hover:bg-zinc-700 transition-colors cursor-pointer"
                            >
                              <RefreshCw size={12} /> Thử tải lại
                            </button>
                            <button
                              disabled={isActionPending(item.id, 'watchlist')}
                              onClick={() => handleRemoveMissingItem(item.id, 'watchlist')}
                              className={`flex items-center justify-center gap-1 rounded py-1.5 text-[11px] transition-colors cursor-pointer disabled:opacity-50 ${
                                isActionUnconfirmed(item.id, 'watchlist')
                                  ? 'bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-400/40'
                                  : 'bg-zinc-800 text-red-300 hover:bg-red-500/20'
                              }`}
                              aria-label={
                                isActionPending(item.id, 'watchlist')
                                  ? 'Đang xử lý...'
                                  : isActionUnconfirmed(item.id, 'watchlist')
                                  ? getActionIntent(item.id, 'watchlist') === 'add'
                                    ? 'Chưa xác nhận lưu • Thử lưu lại vào danh sách'
                                    : 'Chưa xác nhận xóa • Thử xóa lại khỏi danh sách'
                                  : 'Xóa khỏi danh sách'
                              }
                              title={
                                isActionUnconfirmed(item.id, 'watchlist')
                                  ? getActionIntent(item.id, 'watchlist') === 'add'
                                    ? 'Chưa xác nhận lưu • Nhấn để thử lưu lại'
                                    : 'Chưa xác nhận xóa • Nhấn để thử xóa lại'
                                  : undefined
                              }
                            >
                              {isActionPending(item.id, 'watchlist') ? (
                                <Loader2 size={12} className="animate-spin" />
                              ) : isActionUnconfirmed(item.id, 'watchlist') ? (
                                <RefreshCw size={12} className="text-amber-400 stroke-[2.5]" />
                              ) : (
                                <Trash2 size={12} />
                              )}{' '}
                              {isActionUnconfirmed(item.id, 'watchlist')
                                ? getActionIntent(item.id, 'watchlist') === 'add'
                                  ? 'Thử lưu lại'
                                  : 'Thử xóa lại'
                                : 'Xóa khỏi danh sách'}
                            </button>
                          </div>
                        </div>
                      ) : (
                        /* Movie absent from catalog (404) */
                        <div
                          key={item.id}
                          className="flex flex-col justify-between rounded-lg border border-zinc-800 bg-surface-muted p-4 text-xs"
                        >
                          <div>
                            <div className="flex items-center gap-1 text-[11px] text-amber-400 font-semibold mb-1">
                              <AlertCircle size={12} /> Không có trong catalog (404)
                            </div>
                            <p className="font-bold text-white truncate">{item.id}</p>
                            <p className="text-[11px] text-zinc-500 mt-1">
                              Tác phẩm này không còn tồn tại trong danh mục phim.
                            </p>
                          </div>
                          <button
                            disabled={isActionPending(item.id, 'watchlist')}
                            onClick={() => handleRemoveMissingItem(item.id, 'watchlist')}
                            className={`mt-3 flex items-center justify-center gap-1 rounded py-1.5 text-[11px] transition-colors cursor-pointer disabled:opacity-50 ${
                              isActionUnconfirmed(item.id, 'watchlist')
                                ? 'bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-400/40'
                                : 'bg-zinc-800 text-red-300 hover:bg-red-500/20'
                            }`}
                            aria-label={
                              isActionPending(item.id, 'watchlist')
                                ? 'Đang xử lý...'
                                : isActionUnconfirmed(item.id, 'watchlist')
                                ? getActionIntent(item.id, 'watchlist') === 'add'
                                  ? 'Chưa xác nhận lưu • Thử lưu lại vào danh sách'
                                  : 'Chưa xác nhận xóa • Thử xóa lại khỏi danh sách'
                                : 'Xóa khỏi danh sách'
                            }
                            title={
                              isActionUnconfirmed(item.id, 'watchlist')
                                ? getActionIntent(item.id, 'watchlist') === 'add'
                                  ? 'Chưa xác nhận lưu • Nhấn để thử lưu lại'
                                  : 'Chưa xác nhận xóa • Nhấn để thử xóa lại'
                                : undefined
                            }
                          >
                            {isActionPending(item.id, 'watchlist') ? (
                              <Loader2 size={12} className="animate-spin" />
                            ) : isActionUnconfirmed(item.id, 'watchlist') ? (
                              <RefreshCw size={12} className="text-amber-400 stroke-[2.5]" />
                            ) : (
                              <Trash2 size={12} />
                            )}{' '}
                            {isActionUnconfirmed(item.id, 'watchlist')
                              ? getActionIntent(item.id, 'watchlist') === 'add'
                                ? 'Thử lưu lại'
                                : 'Thử xóa lại'
                              : 'Xóa khỏi danh sách'}
                          </button>
                        </div>
                      )
                    )}
                  </div>
                ) : libraryError ? (
                  <div className="flex flex-col items-center justify-center rounded-xl border border-red-500/20 bg-red-500/5 py-12 px-4 text-center">
                    <AlertCircle size={28} className="text-red-400 mb-2" />
                    <p className="text-sm font-bold text-red-300">{libraryError}</p>
                    <p className="text-xs text-zinc-400 mt-1 mb-4">
                      Không thể đồng bộ danh sách từ máy chủ. Vui lòng kiểm tra kết nối mạng.
                    </p>
                    <button
                      onClick={() => refetchLibrary()}
                      className="btn-secondary text-xs flex items-center gap-1.5"
                    >
                      <RefreshCw size={13} /> Thử lại
                    </button>
                  </div>
                ) : (
                  <EmptyState
                    title="Danh sách xem đang trống"
                    description="Lưu lại các bộ phim bạn muốn xem sau bằng nút Bookmark trên thẻ phim."
                    openChat={openChat}
                  />
                )
              )}

              {activeTab === 'favorites' && (
                favoriteItems.length > 0 ? (
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5 xl:grid-cols-6">
                    {favoriteItems.map((item) =>
                      item.status === 'found' && item.movie ? (
                        <MovieCard key={item.id} movie={item.movie} fluid />
                      ) : item.status === 'loading' ? (
                        <div
                          key={item.id}
                          className="flex h-56 flex-col items-center justify-center rounded-lg border border-zinc-800 bg-surface-muted p-4 text-xs"
                        >
                          <Loader2 size={18} className="animate-spin text-brand mb-2" />
                          <span className="text-zinc-500 text-[11px]">Đang tải dữ liệu...</span>
                        </div>
                      ) : item.status === 'error' ? (
                        <div
                          key={item.id}
                          className="flex flex-col justify-between rounded-lg border border-amber-900/40 bg-surface-muted p-4 text-xs"
                        >
                          <div>
                            <div className="flex items-center gap-1 text-[11px] text-amber-400 font-semibold mb-1">
                              <AlertCircle size={12} /> Lỗi kết nối
                            </div>
                            <p className="font-bold text-white truncate">{item.id}</p>
                            <p className="text-[11px] text-zinc-400 mt-1">
                              Không thể kết nối máy chủ để tải thông tin phim.
                            </p>
                          </div>
                          <div className="mt-3 flex flex-col gap-1.5">
                            <button
                              onClick={() => fetchRemoteMovie(item.id)}
                              className="flex items-center justify-center gap-1 rounded bg-zinc-800 py-1.5 text-[11px] text-zinc-300 hover:bg-zinc-700 transition-colors cursor-pointer"
                            >
                              <RefreshCw size={12} /> Thử tải lại
                            </button>
                            <button
                              disabled={isActionPending(item.id, 'favorite')}
                              onClick={() => handleRemoveMissingItem(item.id, 'favorites')}
                              className={`flex items-center justify-center gap-1 rounded py-1.5 text-[11px] transition-colors cursor-pointer disabled:opacity-50 ${
                                isActionUnconfirmed(item.id, 'favorite')
                                  ? 'bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-400/40'
                                  : 'bg-zinc-800 text-red-300 hover:bg-red-500/20'
                              }`}
                              aria-label={
                                isActionPending(item.id, 'favorite')
                                  ? 'Đang xử lý...'
                                  : isActionUnconfirmed(item.id, 'favorite')
                                  ? getActionIntent(item.id, 'favorite') === 'add'
                                    ? 'Chưa xác nhận thích • Thử thêm lại vào yêu thích'
                                    : 'Chưa xác nhận bỏ thích • Thử xóa lại khỏi yêu thích'
                                  : 'Xóa khỏi yêu thích'
                              }
                              title={
                                isActionUnconfirmed(item.id, 'favorite')
                                  ? getActionIntent(item.id, 'favorite') === 'add'
                                    ? 'Chưa xác nhận thích • Nhấn để thử thêm lại'
                                    : 'Chưa xác nhận bỏ thích • Nhấn để thử xóa lại'
                                  : undefined
                              }
                            >
                              {isActionPending(item.id, 'favorite') ? (
                                <Loader2 size={12} className="animate-spin" />
                              ) : isActionUnconfirmed(item.id, 'favorite') ? (
                                <RefreshCw size={12} className="text-amber-400 stroke-[2.5]" />
                              ) : (
                                <Trash2 size={12} />
                              )}{' '}
                              {isActionUnconfirmed(item.id, 'favorite')
                                ? getActionIntent(item.id, 'favorite') === 'add'
                                  ? 'Thử thêm lại'
                                  : 'Thử xóa lại'
                                : 'Xóa khỏi yêu thích'}
                            </button>
                          </div>
                        </div>
                      ) : (
                        /* Movie absent from catalog (404) */
                        <div
                          key={item.id}
                          className="flex flex-col justify-between rounded-lg border border-zinc-800 bg-surface-muted p-4 text-xs"
                        >
                          <div>
                            <div className="flex items-center gap-1 text-[11px] text-amber-400 font-semibold mb-1">
                              <AlertCircle size={12} /> Không có trong catalog (404)
                            </div>
                            <p className="font-bold text-white truncate">{item.id}</p>
                            <p className="text-[11px] text-zinc-500 mt-1">
                              Tác phẩm này không còn tồn tại trong danh mục phim.
                            </p>
                          </div>
                          <button
                            disabled={isActionPending(item.id, 'favorite')}
                            onClick={() => handleRemoveMissingItem(item.id, 'favorites')}
                            className={`mt-3 flex items-center justify-center gap-1 rounded py-1.5 text-[11px] transition-colors cursor-pointer disabled:opacity-50 ${
                              isActionUnconfirmed(item.id, 'favorite')
                                ? 'bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-400/40'
                                : 'bg-zinc-800 text-red-300 hover:bg-red-500/20'
                            }`}
                            aria-label={
                              isActionPending(item.id, 'favorite')
                                ? 'Đang xử lý...'
                                : isActionUnconfirmed(item.id, 'favorite')
                                ? getActionIntent(item.id, 'favorite') === 'add'
                                  ? 'Chưa xác nhận thích • Thử thêm lại vào yêu thích'
                                  : 'Chưa xác nhận bỏ thích • Thử xóa lại khỏi yêu thích'
                                : 'Xóa khỏi yêu thích'
                            }
                            title={
                              isActionUnconfirmed(item.id, 'favorite')
                                ? getActionIntent(item.id, 'favorite') === 'add'
                                  ? 'Chưa xác nhận thích • Nhấn để thử thêm lại'
                                  : 'Chưa xác nhận bỏ thích • Nhấn để thử xóa lại'
                                : undefined
                            }
                          >
                            {isActionPending(item.id, 'favorite') ? (
                              <Loader2 size={12} className="animate-spin" />
                            ) : isActionUnconfirmed(item.id, 'favorite') ? (
                              <RefreshCw size={12} className="text-amber-400 stroke-[2.5]" />
                            ) : (
                              <Trash2 size={12} />
                            )}{' '}
                            {isActionUnconfirmed(item.id, 'favorite')
                              ? getActionIntent(item.id, 'favorite') === 'add'
                                ? 'Thử thêm lại'
                                : 'Thử xóa lại'
                              : 'Xóa khỏi yêu thích'}
                          </button>
                        </div>
                      )
                    )}
                  </div>
                ) : libraryError ? (
                  <div className="flex flex-col items-center justify-center rounded-xl border border-red-500/20 bg-red-500/5 py-12 px-4 text-center">
                    <AlertCircle size={28} className="text-red-400 mb-2" />
                    <p className="text-sm font-bold text-red-300">{libraryError}</p>
                    <p className="text-xs text-zinc-400 mt-1 mb-4">
                      Không thể đồng bộ danh sách từ máy chủ. Vui lòng kiểm tra kết nối mạng.
                    </p>
                    <button
                      onClick={() => refetchLibrary()}
                      className="btn-secondary text-xs flex items-center gap-1.5"
                    >
                      <RefreshCw size={13} /> Thử lại
                    </button>
                  </div>
                ) : (
                  <EmptyState
                    title="Chưa có phim yêu thích"
                    description="Nhấn biểu tượng Trái tim trên trang chi tiết phim để đánh dấu những tác phẩm tâm đắc nhất."
                    openChat={openChat}
                  />
                )
              )}

              {activeTab === 'ratings' && (
                ratingItems.length > 0 ? (
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5 xl:grid-cols-6">
                    {ratingItems.map((item) => (
                      <div key={item.id} className="relative group">
                        {item.status === 'found' && item.movie ? (
                          <div>
                            <MovieCard movie={item.movie} fluid />
                            <div className="mt-1 flex items-center justify-between px-1 text-xs">
                              <span className="text-zinc-400 text-[11px]">Điểm của bạn:</span>
                              <div className="flex items-center gap-2">
                                <span className="flex items-center gap-0.5 font-bold text-amber-400">
                                  <Star size={11} className="fill-amber-400" /> {item.rating}/10
                                </span>
                                {isActionUnconfirmed(item.id, 'rating') && (
                                  <span
                                    data-testid="rating-unconfirmed-badge"
                                    className="rounded bg-amber-500/20 px-1 py-0.5 text-[9px] font-bold text-amber-300 border border-amber-400/30"
                                    title={getActionIntent(item.id, 'rating') === 'rate' ? 'Chưa xác nhận điểm' : 'Chưa xác nhận xóa điểm'}
                                  >
                                    Chưa xác nhận
                                  </span>
                                )}
                                <button
                                  disabled={isActionPending(item.id, 'rating')}
                                  onClick={() => handleRemoveMissingItem(item.id, 'ratings', item.movie?.title)}
                                  className={`transition-colors cursor-pointer p-0.5 disabled:opacity-50 ${
                                    isActionUnconfirmed(item.id, 'rating')
                                      ? 'text-amber-400 hover:text-amber-300'
                                      : 'text-zinc-500 hover:text-red-400'
                                  }`}
                                  title={
                                    isActionUnconfirmed(item.id, 'rating')
                                      ? getActionIntent(item.id, 'rating') === 'rate'
                                        ? 'Chưa xác nhận điểm • Thử lưu lại'
                                        : 'Chưa xác nhận xóa • Thử xóa lại'
                                      : 'Xóa đánh giá'
                                  }
                                  aria-label={
                                    isActionPending(item.id, 'rating')
                                      ? 'Đang xử lý...'
                                      : isActionUnconfirmed(item.id, 'rating')
                                      ? getActionIntent(item.id, 'rating') === 'rate'
                                        ? 'Chưa xác nhận điểm • Thử lưu lại điểm đánh giá'
                                        : 'Chưa xác nhận xóa • Thử xóa lại điểm đánh giá'
                                      : 'Xóa đánh giá'
                                  }
                                >
                                  {isActionPending(item.id, 'rating') ? (
                                    <Loader2 size={11} className="animate-spin" />
                                  ) : isActionUnconfirmed(item.id, 'rating') ? (
                                    <RefreshCw size={11} className="stroke-[2.5]" />
                                  ) : (
                                    <Trash2 size={11} />
                                  )}
                                </button>
                              </div>
                            </div>
                          </div>
                        ) : item.status === 'loading' ? (
                          <div className="flex h-56 flex-col items-center justify-center rounded-lg border border-zinc-800 bg-surface-muted p-4 text-xs">
                            <Loader2 size={18} className="animate-spin text-brand mb-2" />
                            <span className="text-zinc-500 text-[11px]">Đang tải dữ liệu...</span>
                          </div>
                        ) : item.status === 'error' ? (
                          <div className="flex flex-col justify-between rounded-lg border border-amber-900/40 bg-surface-muted p-4 text-xs">
                            <div>
                              <div className="flex items-center gap-1 text-[11px] text-amber-400 font-semibold mb-1">
                                <AlertCircle size={12} /> Lỗi kết nối
                              </div>
                              <p className="font-bold text-white truncate">{item.id}</p>
                              <p className="text-amber-400 font-semibold mt-1">
                                Điểm đã chấm: {item.rating}/10 ★
                              </p>
                              <p className="text-[11px] text-zinc-400 mt-1">
                                Không thể kết nối máy chủ để tải thông tin phim.
                              </p>
                            </div>
                            <div className="mt-3 flex flex-col gap-1.5">
                              <button
                                onClick={() => fetchRemoteMovie(item.id)}
                                className="flex items-center justify-center gap-1 rounded bg-zinc-800 py-1.5 text-[11px] text-zinc-300 hover:bg-zinc-700 transition-colors cursor-pointer"
                              >
                                <RefreshCw size={12} /> Thử tải lại
                              </button>
                              <button
                                disabled={isActionPending(item.id, 'rating')}
                                onClick={() => handleRemoveMissingItem(item.id, 'ratings', remoteMovies[item.id]?.movie?.title || item.movie?.title)}
                                className={`flex items-center justify-center gap-1 rounded py-1.5 text-[11px] transition-colors cursor-pointer disabled:opacity-50 ${
                                  isActionUnconfirmed(item.id, 'rating')
                                    ? 'bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-400/40'
                                    : 'bg-zinc-800 text-red-300 hover:bg-red-500/20'
                                }`}
                                aria-label={
                                  isActionPending(item.id, 'rating')
                                    ? 'Đang xử lý...'
                                    : isActionUnconfirmed(item.id, 'rating')
                                    ? getActionIntent(item.id, 'rating') === 'rate'
                                      ? 'Chưa xác nhận điểm • Thử lưu lại điểm đánh giá'
                                      : 'Chưa xác nhận xóa • Thử xóa lại điểm đánh giá'
                                    : 'Xóa điểm đánh giá'
                                }
                                title={
                                  isActionUnconfirmed(item.id, 'rating')
                                    ? getActionIntent(item.id, 'rating') === 'rate'
                                      ? 'Chưa xác nhận điểm • Nhấn để thử lưu lại'
                                      : 'Chưa xác nhận xóa • Nhấn để thử xóa lại'
                                    : undefined
                                }
                              >
                                {isActionPending(item.id, 'rating') ? (
                                  <Loader2 size={12} className="animate-spin" />
                                ) : isActionUnconfirmed(item.id, 'rating') ? (
                                  <RefreshCw size={12} className="text-amber-400 stroke-[2.5]" />
                                ) : (
                                  <Trash2 size={12} />
                                )}{' '}
                                {isActionUnconfirmed(item.id, 'rating')
                                  ? getActionIntent(item.id, 'rating') === 'rate'
                                    ? 'Thử lưu lại'
                                    : 'Thử xóa lại'
                                  : 'Xóa điểm đánh giá'}
                              </button>
                            </div>
                          </div>
                        ) : (
                          /* Absent from catalog (404) */
                          <div className="flex flex-col justify-between rounded-lg border border-zinc-800 bg-surface-muted p-4 text-xs">
                            <div>
                              <div className="flex items-center gap-1 text-[11px] text-amber-400 font-semibold mb-1">
                                <AlertCircle size={12} /> Không có trong catalog (404)
                              </div>
                              <p className="font-bold text-white truncate">{item.id}</p>
                              <p className="text-amber-400 font-semibold mt-1">
                                Điểm đã chấm: {item.rating}/10 ★
                              </p>
                              <p className="text-[11px] text-zinc-500 mt-1">
                                Tác phẩm này không còn tồn tại trong danh mục phim.
                              </p>
                            </div>
                            <button
                              disabled={isActionPending(item.id, 'rating')}
                              onClick={() => handleRemoveMissingItem(item.id, 'ratings', remoteMovies[item.id]?.movie?.title || item.movie?.title)}
                              className={`mt-3 flex items-center justify-center gap-1 rounded py-1.5 text-[11px] transition-colors cursor-pointer disabled:opacity-50 ${
                                isActionUnconfirmed(item.id, 'rating')
                                  ? 'bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-400/40'
                                  : 'bg-zinc-800 text-red-300 hover:bg-red-500/20'
                              }`}
                              aria-label={
                                isActionPending(item.id, 'rating')
                                  ? 'Đang xử lý...'
                                  : isActionUnconfirmed(item.id, 'rating')
                                  ? getActionIntent(item.id, 'rating') === 'rate'
                                    ? 'Chưa xác nhận điểm • Thử lưu lại điểm đánh giá'
                                    : 'Chưa xác nhận xóa • Thử xóa lại điểm đánh giá'
                                  : 'Xóa điểm đánh giá'
                              }
                              title={
                                isActionUnconfirmed(item.id, 'rating')
                                  ? getActionIntent(item.id, 'rating') === 'rate'
                                    ? 'Chưa xác nhận điểm • Nhấn để thử lưu lại'
                                    : 'Chưa xác nhận xóa • Nhấn để thử xóa lại'
                                  : undefined
                              }
                            >
                              {isActionPending(item.id, 'rating') ? (
                                <Loader2 size={12} className="animate-spin" />
                              ) : isActionUnconfirmed(item.id, 'rating') ? (
                                <RefreshCw size={12} className="text-amber-400 stroke-[2.5]" />
                              ) : (
                                <Trash2 size={12} />
                              )}{' '}
                              {isActionUnconfirmed(item.id, 'rating')
                                ? getActionIntent(item.id, 'rating') === 'rate'
                                  ? 'Thử lưu lại'
                                  : 'Thử xóa lại'
                                : 'Xóa điểm đánh giá'}
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : libraryError ? (
                  <div className="flex flex-col items-center justify-center rounded-xl border border-red-500/20 bg-red-500/5 py-12 px-4 text-center">
                    <AlertCircle size={28} className="text-red-400 mb-2" />
                    <p className="text-sm font-bold text-red-300">{libraryError}</p>
                    <p className="text-xs text-zinc-400 mt-1 mb-4">
                      Không thể đồng bộ danh sách từ máy chủ. Vui lòng kiểm tra kết nối mạng.
                    </p>
                    <button
                      onClick={() => refetchLibrary()}
                      className="btn-secondary text-xs flex items-center gap-1.5"
                    >
                      <RefreshCw size={13} /> Thử lại
                    </button>
                  </div>
                ) : (
                  <EmptyState
                    title="Chưa có phim nào được chấm điểm"
                    description="Hãy chấm điểm các phim bạn đã xem để CineBot hiểu rõ gu và gợi ý chuẩn xác hơn."
                    openChat={openChat}
                  />
                )
              )}
            </>
          )}
        </div>
      </section>
    </main>
  );
}

function EmptyState({
  title,
  description,
  openChat,
}: {
  title: string;
  description: string;
  openChat: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-surface-border bg-surface px-6 py-14 text-center">
      <Film className="text-zinc-500 mb-2.5" size={28} />
      <h3 className="text-base font-bold text-white">{title}</h3>
      <p className="mt-1 max-w-md text-xs text-zinc-400">{description}</p>
      <div className="mt-4 flex gap-2">
        <Link href="/" className="btn-primary text-xs">
          Khám phá phim <ArrowRight size={13} />
        </Link>
        <button onClick={openChat} className="btn-secondary text-xs">
          Nhờ CineBot gợi ý
        </button>
      </div>
    </div>
  );
}
