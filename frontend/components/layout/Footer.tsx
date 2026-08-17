import React from 'react';
import Link from 'next/link';
import { Film, Github, Sparkles, Heart } from 'lucide-react';

export function Footer() {
  return (
    <footer className="mt-20 border-t border-cinema-800/80 bg-cinema-950/60 transition-colors">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-8 sm:grid-cols-2 md:grid-cols-4">
          {/* Brand & Manifesto */}
          <div className="sm:col-span-2">
            <Link href="/" className="inline-block font-editorial text-2xl font-bold tracking-tight text-white">
              Dippie<span className="text-accent-rose">.</span>
            </Link>
            <p className="mt-3 max-w-md text-sm leading-relaxed text-cinema-400">
              A curated cinema recommendation engine powered by advanced contextual matching. 
              Designed for stories worth staying for.
            </p>
            <div className="mt-4 flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-cinema-700/80 bg-cinema-900/60 px-3 py-1 font-mono text-[10px] text-cinema-300">
                <Sparkles size={11} className="text-accent-rose" />
                UI UX Pro Max Design System v2.0
              </span>
            </div>
          </div>

          {/* Quick Links */}
          <div>
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.15em] text-cinema-300">Explore</p>
            <ul className="mt-3 space-y-2 text-xs">
              <li>
                <Link href="/" className="text-cinema-400 transition hover:text-white">
                  Trending Releases
                </Link>
              </li>
              <li>
                <Link href="/search" className="text-cinema-400 transition hover:text-white">
                  Browse All Films
                </Link>
              </li>
              <li>
                <Link href="/search?genre=Sci-Fi" className="text-cinema-400 transition hover:text-white">
                  Sci-Fi & Cyberpunk
                </Link>
              </li>
              <li>
                <Link href="/search?genre=Drama" className="text-cinema-400 transition hover:text-white">
                  Cinematic Drama
                </Link>
              </li>
            </ul>
          </div>

          {/* User & Tech */}
          <div>
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.15em] text-cinema-300">Account & Tech</p>
            <ul className="mt-3 space-y-2 text-xs">
              <li>
                <Link href="/profile" className="text-cinema-400 transition hover:text-white">
                  My Watchlist
                </Link>
              </li>
              <li>
                <Link href="/profile" className="text-cinema-400 transition hover:text-white">
                  Ratings & Favorites
                </Link>
              </li>
              <li>
                <span className="text-cinema-500">Next.js 15 App Router</span>
              </li>
              <li>
                <span className="text-cinema-500">OLED Dark Architecture</span>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-cinema-850 pt-8 sm:flex-row text-xs text-cinema-500">
          <p>© {new Date().getFullYear()} Dippie Cinema. Crafted with care for cinephiles.</p>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1 text-cinema-400">
              <span>Made with</span>
              <Heart size={12} className="fill-accent-rose text-accent-rose inline" />
              <span>& AI Intelligence</span>
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
