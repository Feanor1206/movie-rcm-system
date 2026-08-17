'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Menu, Search, User, X } from 'lucide-react';
import { useWatchlist } from '@/lib/context/WatchlistContext';

export function Navbar() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const { watchlist, openChat } = useWatchlist();

  const navLinks = [
    { name: 'Khám phá', href: '/' },
    { name: 'Kho phim', href: '/search' },
    { name: 'Danh sách xem', href: '/profile', count: watchlist.length },
  ];

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
          {/* Chatbot Trigger (Clean button, no unnecessary robot icon) */}
          <button
            onClick={openChat}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3.5 py-1.5 text-xs font-semibold text-zinc-200 transition-colors hover:border-cinema-red hover:text-white cursor-pointer"
          >
            Hỏi CineBot
          </button>

          {/* Search Button (Clean, no ⌘K pill badge) */}
          <Link
            href="/search"
            aria-label="Tìm kiếm phim"
            className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/60 px-3 py-1.5 text-xs text-zinc-400 transition-colors hover:border-zinc-600 hover:text-white cursor-pointer"
          >
            <Search size={14} />
            <span>Tìm kiếm</span>
          </Link>

          {/* Profile */}
          <Link
            href="/profile"
            aria-label="Trang cá nhân"
            className="grid h-8 w-8 place-items-center rounded-md border border-zinc-800 bg-zinc-900 text-zinc-300 hover:border-zinc-600 hover:text-white transition-colors"
          >
            <User size={14} />
          </Link>
        </div>

        {/* Mobile Toggle */}
        <div className="flex items-center gap-2 md:hidden">
          <button
            onClick={openChat}
            className="rounded-md bg-cinema-red px-3 py-1.5 text-xs font-bold text-white cursor-pointer"
          >
            CineBot
          </button>
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
