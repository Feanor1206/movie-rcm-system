'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Bookmark, Film, Menu, Search, Sparkles, UserRound, X } from 'lucide-react';
import { useWatchlist } from '@/lib/context/WatchlistContext';

export function Navbar() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const { watchlist } = useWatchlist();

  const navLinks = [
    { name: 'Discover', href: '/', number: '01' },
    { name: 'Explore Archive', href: '/search', number: '02' },
    { name: 'Watchlist', href: '/profile', number: '03', count: watchlist.length },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-cinema-800/80 bg-cinema-950/90 backdrop-blur-xl transition-colors">
      <nav className="mx-auto flex h-20 max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand Logo */}
        <Link
          href="/"
          className="group flex items-center gap-2 outline-none focus-visible:ring-2 focus-visible:ring-rose-500 rounded-md p-1"
        >
          <span className="font-editorial text-2xl font-bold tracking-tight text-white transition-colors group-hover:text-rose-400">
            Dippie<span className="text-accent-rose">.</span>
          </span>
          <span className="hidden sm:inline-block rounded border border-cinema-700 bg-cinema-900/60 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.2em] text-cinema-400">
            Cinema / 2026
          </span>
        </Link>

        {/* Desktop Navigation Links */}
        <div className="hidden items-center gap-8 md:flex">
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.name}
                href={link.href}
                className={`group relative flex items-center font-mono text-xs transition-colors duration-200 ${
                  isActive ? 'text-white font-medium' : 'text-cinema-400 hover:text-white'
                }`}
              >
                <span
                  className={`mr-1.5 transition-colors ${
                    isActive ? 'text-accent-rose' : 'text-cinema-600 group-hover:text-accent-rose'
                  }`}
                >
                  {link.number}
                </span>
                {link.name}
                {link.count !== undefined && link.count > 0 && (
                  <span className="ml-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent-rose px-1 text-[9px] font-bold text-white">
                    {link.count}
                  </span>
                )}
                {isActive && (
                  <span className="absolute -bottom-2.5 left-0 right-0 h-[2px] rounded-full bg-accent-rose shadow-glow-rose" />
                )}
              </Link>
            );
          })}
        </div>

        {/* Right CTA / Controls */}
        <div className="hidden items-center gap-3 md:flex">
          <Link
            href="/search"
            aria-label="Search all movies"
            className="flex items-center gap-2 rounded-lg border border-cinema-800 bg-cinema-900/60 px-3.5 py-1.5 font-mono text-xs text-cinema-300 transition-all hover:border-cinema-600 hover:text-white cursor-pointer"
          >
            <Search size={14} className="text-cinema-400" />
            <span>Search</span>
            <kbd className="ml-2 rounded border border-cinema-700 bg-cinema-800/80 px-1.5 py-0.5 text-[9px] text-cinema-400">
              ⌘K
            </kbd>
          </Link>

          <Link
            href="/profile"
            aria-label="Profile and Watchlist"
            className="btn-secondary py-1.5 px-3.5 text-xs font-mono"
          >
            <UserRound size={13} className="text-cinema-400" />
            <span>Profile</span>
            {watchlist.length > 0 && (
              <span className="rounded-full bg-accent-rose/20 px-1.5 py-0.2 text-[10px] text-accent-rose font-bold">
                {watchlist.length}
              </span>
            )}
          </Link>
        </div>

        {/* Mobile Navigation Toggle Button */}
        <button
          aria-label={open ? 'Close menu' : 'Open menu'}
          onClick={() => setOpen(!open)}
          className="rounded-lg border border-cinema-800 bg-cinema-900/80 p-2 text-cinema-300 hover:text-white md:hidden cursor-pointer"
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </nav>

      {/* Mobile Drawer */}
      {open && (
        <div className="animate-slide-up border-b border-cinema-800 bg-cinema-950/98 px-6 py-6 md:hidden">
          <div className="flex flex-col gap-4">
            {navLinks.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.name}
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className={`flex items-center justify-between rounded-lg px-3 py-2.5 font-mono text-sm transition-colors ${
                    isActive ? 'bg-cinema-900 text-white font-semibold' : 'text-cinema-300 hover:bg-cinema-900/60'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span className="text-accent-rose">{link.number}</span>
                    {link.name}
                  </span>
                  {link.count !== undefined && link.count > 0 && (
                    <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-accent-rose px-1.5 text-xs font-bold text-white">
                      {link.count}
                    </span>
                  )}
                </Link>
              );
            })}

            <div className="mt-4 pt-4 border-t border-cinema-800 flex flex-col gap-2">
              <Link
                href="/search"
                onClick={() => setOpen(false)}
                className="btn-secondary w-full justify-center text-xs font-mono"
              >
                <Search size={14} /> Search Archive
              </Link>
              <Link
                href="/profile"
                onClick={() => setOpen(false)}
                className="btn-primary w-full justify-center text-xs font-mono"
              >
                <UserRound size={14} /> My Profile & Watchlist ({watchlist.length})
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
