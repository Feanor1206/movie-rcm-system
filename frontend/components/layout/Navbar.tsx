'use client';

import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Menu, Search, User, X, LogOut, Bookmark, UserCheck } from 'lucide-react';
import { useWatchlist } from '@/lib/context/WatchlistContext';
import { useAuth } from '@/lib/context/AuthContext';

export function Navbar() {
  const [open, setOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  const { watchlist, openChat } = useWatchlist();
  const { user, isAuthenticated, openAuthModal, logout } = useAuth();

  const navLinks = [
    { name: 'Khám phá', href: '/' },
    { name: 'Kho phim', href: '/search' },
    { name: 'Danh sách xem', href: '/profile', count: watchlist.length },
  ];

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setUserDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getInitials = (name?: string) => {
    if (!name) return 'U';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    return name.slice(0, 2).toUpperCase();
  };

  return (
    <header className="sticky top-0 z-40 border-b border-zinc-800 bg-black/90 backdrop-blur-md">
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Left: Brand Logo & Links */}
        <div className="flex items-center gap-8">
          <Link
            href="/"
            className="flex items-center gap-1.5 font-bold tracking-tight text-xl text-white outline-none focus-visible:ring-2 focus-visible:ring-cinema-red rounded px-1"
          >
            <span className="tracking-tighter font-extrabold text-2xl">DIPPIE</span>
            <span className="h-2 w-2 rounded-full bg-cinema-red" />
          </Link>

          {/* Desktop Nav Items */}
          <div className="hidden md:flex items-center gap-6">
            {navLinks.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.name}
                  href={link.href}
                  className={`text-sm font-medium transition-colors ${
                    isActive ? 'text-white font-semibold' : 'text-zinc-400 hover:text-white'
                  }`}
                >
                  {link.name}
                  {link.count !== undefined && link.count > 0 && (
                    <span className="ml-1 text-xs text-zinc-500 font-normal">
                      ({link.count})
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        </div>

        {/* Right: Actions */}
        <div className="hidden md:flex items-center gap-3">
          {/* Chatbot Trigger */}
          <button
            onClick={openChat}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3.5 py-1.5 text-xs font-semibold text-zinc-200 transition-colors hover:border-cinema-red hover:text-white cursor-pointer"
          >
            Hỏi CineBot
          </button>

          {/* Search Button */}
          <Link
            href="/search"
            aria-label="Tìm kiếm phim"
            className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/60 px-3 py-1.5 text-xs text-zinc-400 transition-colors hover:border-zinc-600 hover:text-white cursor-pointer"
          >
            <Search size={14} />
            <span>Tìm kiếm</span>
          </Link>

          {/* User Auth Section */}
          {isAuthenticated && user ? (
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-xs text-zinc-200 hover:border-zinc-600 hover:text-white transition-colors cursor-pointer"
              >
                <div className="grid h-6 w-6 place-items-center rounded bg-cinema-red text-[11px] font-bold text-white">
                  {getInitials(user.fullName || user.username)}
                </div>
                <span className="font-medium max-w-[100px] truncate">
                  {user.fullName || user.username}
                </span>
              </button>

              {/* Dropdown Menu */}
              {userDropdownOpen && (
                <div className="absolute right-0 mt-2 w-52 rounded-lg border border-zinc-800 bg-zinc-950 p-2 shadow-2xl animate-fade-in z-50">
                  <div className="px-2.5 py-2 border-b border-zinc-850">
                    <p className="text-xs font-bold text-white truncate">{user.fullName || user.username}</p>
                    <p className="text-[11px] text-zinc-400 truncate">{user.email}</p>
                  </div>

                  <div className="mt-1.5 space-y-0.5">
                    <Link
                      href="/profile"
                      onClick={() => setUserDropdownOpen(false)}
                      className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-zinc-300 hover:bg-zinc-900 hover:text-white transition-colors"
                    >
                      <UserCheck size={14} /> Hồ sơ cá nhân
                    </Link>
                    <Link
                      href="/profile"
                      onClick={() => setUserDropdownOpen(false)}
                      className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-zinc-300 hover:bg-zinc-900 hover:text-white transition-colors"
                    >
                      <Bookmark size={14} /> Watchlist ({watchlist.length})
                    </Link>
                  </div>

                  <div className="mt-1.5 pt-1.5 border-t border-zinc-850">
                    <button
                      onClick={() => {
                        setUserDropdownOpen(false);
                        logout();
                      }}
                      className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-red-400 hover:bg-red-500/10 transition-colors cursor-pointer"
                    >
                      <LogOut size={14} /> Đăng xuất
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={() => openAuthModal('login')}
              className="rounded-md bg-zinc-900 border border-zinc-700 px-3 py-1.5 text-xs font-semibold text-white hover:border-cinema-red hover:bg-cinema-red transition-all cursor-pointer"
            >
              Đăng nhập
            </button>
          )}
        </div>

        {/* Mobile Toggle */}
        <div className="flex items-center gap-2 md:hidden">
          {isAuthenticated ? (
            <Link
              href="/profile"
              className="grid h-8 w-8 place-items-center rounded bg-cinema-red text-xs font-bold text-white"
            >
              {getInitials(user?.fullName || user?.username)}
            </Link>
          ) : (
            <button
              onClick={() => openAuthModal('login')}
              className="rounded bg-cinema-red px-2.5 py-1 text-xs font-bold text-white cursor-pointer"
            >
              Đăng nhập
            </button>
          )}

          <button
            aria-label={open ? 'Đóng menu' : 'Mở menu'}
            onClick={() => setOpen(!open)}
            className="rounded-md border border-zinc-800 bg-zinc-900 p-2 text-zinc-300 hover:text-white cursor-pointer"
          >
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </nav>

      {/* Mobile Drawer */}
      {open && (
        <div className="border-b border-zinc-800 bg-black px-5 py-5 md:hidden animate-slide-up">
          <div className="flex flex-col gap-3">
            {navLinks.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.name}
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className={`flex items-center justify-between rounded-md px-3 py-2 text-sm font-medium ${
                    isActive ? 'bg-zinc-900 text-white font-bold' : 'text-zinc-300 hover:bg-zinc-900/60'
                  }`}
                >
                  <span>{link.name}</span>
                  {link.count !== undefined && link.count > 0 && (
                    <span className="text-xs text-zinc-400 font-semibold">
                      ({link.count})
                    </span>
                  )}
                </Link>
              );
            })}

            <div className="pt-3 mt-2 border-t border-zinc-800 flex flex-col gap-2">
              <button
                onClick={() => {
                  setOpen(false);
                  openChat();
                }}
                className="btn-primary w-full justify-center text-xs"
              >
                Hỏi CineBot gợi ý phim
              </button>
              <Link
                href="/search"
                onClick={() => setOpen(false)}
                className="btn-secondary w-full justify-center text-xs"
              >
                Tìm kiếm phim
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
