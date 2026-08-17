'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { CineBot, CineBotFloatingTrigger } from '@/features/chat/components/CineBot';

type Toast = {
  id: string;
  message: string;
  type?: 'success' | 'info';
};

type WatchlistContextType = {
  watchlist: string[];
  favorites: string[];
  ratings: Record<string, number>;
  toggleWatchlist: (id: string, title?: string) => void;
  toggleFavorite: (id: string, title?: string) => void;
  rateMovie: (id: string, rating: number, title?: string) => void;
  isWatchlisted: (id: string) => boolean;
  isFavorite: (id: string) => boolean;
  getRating: (id: string) => number | undefined;
  toasts: Toast[];
  dismissToast: (id: string) => void;
  isChatOpen: boolean;
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
};

const WatchlistContext = createContext<WatchlistContextType | undefined>(undefined);

export function WatchlistProvider({ children }: { children: React.ReactNode }) {
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);

  useEffect(() => {
    try {
      const savedWatchlist = localStorage.getItem('dippie_watchlist');
      const savedFavorites = localStorage.getItem('dippie_favorites');
      const savedRatings = localStorage.getItem('dippie_ratings');

      if (savedWatchlist) setWatchlist(JSON.parse(savedWatchlist));
      else setWatchlist(['afterlight', 'quiet-places']);

      if (savedFavorites) setFavorites(JSON.parse(savedFavorites));
      else setFavorites(['the-last-orbit']);

      if (savedRatings) setRatings(JSON.parse(savedRatings));
      else setRatings({ 'the-last-orbit': 9 });
    } catch {
      // ignore
    } finally {
      setIsLoaded(true);
    }
  }, []);

  useEffect(() => {
    if (!isLoaded) return;
    try {
      localStorage.setItem('dippie_watchlist', JSON.stringify(watchlist));
    } catch {}
  }, [watchlist, isLoaded]);

  useEffect(() => {
    if (!isLoaded) return;
    try {
      localStorage.setItem('dippie_favorites', JSON.stringify(favorites));
    } catch {}
  }, [favorites, isLoaded]);

  useEffect(() => {
    if (!isLoaded) return;
    try {
      localStorage.setItem('dippie_ratings', JSON.stringify(ratings));
    } catch {}
  }, [ratings, isLoaded]);

  const showToast = (message: string, type: 'success' | 'info' = 'success') => {
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
    setToasts((prev) => [...prev.slice(-3), { id, message, type }]);
    setTimeout(() => {
      dismissToast(id);
    }, 2800);
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const toggleWatchlist = (id: string, title?: string) => {
    setWatchlist((prev) => {
      const exists = prev.includes(id);
      if (exists) {
        showToast(`Đã xóa ${title || 'phim'} khỏi Danh sách xem`, 'info');
        return prev.filter((item) => item !== id);
      } else {
        showToast(`Đã thêm ${title || 'phim'} vào Danh sách xem`, 'success');
        return [...prev, id];
      }
    });
  };

  const toggleFavorite = (id: string, title?: string) => {
    setFavorites((prev) => {
      const exists = prev.includes(id);
      if (exists) {
        showToast(`Đã bỏ thích ${title || 'phim'}`, 'info');
        return prev.filter((item) => item !== id);
      } else {
        showToast(`Đã thêm ${title || 'phim'} vào Yêu thích`, 'success');
        return [...prev, id];
      }
    });
  };

  const rateMovie = (id: string, rating: number, title?: string) => {
    setRatings((prev) => {
      const next = { ...prev, [id]: rating };
      showToast(`Đã chấm ${title || 'phim'} ${rating}/10 điểm ★`, 'success');
      return next;
    });
  };

  const isWatchlisted = (id: string) => watchlist.includes(id);
  const isFavorite = (id: string) => favorites.includes(id);
  const getRating = (id: string) => ratings[id];

  const openChat = () => setIsChatOpen(true);
  const closeChat = () => setIsChatOpen(false);
  const toggleChat = () => setIsChatOpen((prev) => !prev);

  return (
    <WatchlistContext.Provider
      value={{
        watchlist,
        favorites,
        ratings,
        toggleWatchlist,
        toggleFavorite,
        rateMovie,
        isWatchlisted,
        isFavorite,
        getRating,
        toasts,
        dismissToast,
        isChatOpen,
        openChat,
        closeChat,
        toggleChat,
      }}
    >
      {children}

      {/* Global CineBot Widget & Modal */}
      {!isChatOpen && <CineBotFloatingTrigger onClick={openChat} />}
      <CineBot isOpen={isChatOpen} onClose={closeChat} />

      {/* Global Toast Container */}
      <div className="fixed bottom-20 right-6 z-50 flex flex-col gap-2 pointer-events-none sm:bottom-6 sm:right-36">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-center justify-between gap-3 rounded-lg border px-4 py-2.5 text-xs sm:text-sm font-medium shadow-2xl backdrop-blur-xl animate-slide-up transition-all ${
              toast.type === 'success'
                ? 'border-cinema-red/50 bg-zinc-950/95 text-white'
                : 'border-zinc-700 bg-zinc-950/95 text-zinc-300'
            }`}
          >
            <span>{toast.message}</span>
            <button
              onClick={() => dismissToast(toast.id)}
              className="ml-2 text-zinc-400 hover:text-white cursor-pointer"
              aria-label="Đóng thông báo"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </WatchlistContext.Provider>
  );
}

export function useWatchlist() {
  const context = useContext(WatchlistContext);
  if (!context) {
    throw new Error('useWatchlist must be used within a WatchlistProvider');
  }
  return context;
}
