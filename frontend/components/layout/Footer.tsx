import React from 'react';
import Link from 'next/link';

const GENRES: [string, string][] = [
  ['Animation', 'Hoạt hình'],
  ['Fantasy', 'Kỳ ảo'],
  ['Family', 'Gia đình'],
  ['Adventure', 'Phiêu lưu'],
];

export function Footer() {
  return (
    <footer className="border-t border-surface-border bg-background py-6 text-xs text-zinc-500">
      <div className="mx-auto max-w-7xl px-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Link href="/" className="font-bold text-white">DIPPIE</Link>
          <span>· Tuyển chọn phim hoạt hình</span>
        </div>
        <div className="flex flex-wrap gap-4">
          {GENRES.map(([g, l]) => (
            <Link key={g} href={`/search?genre=${g}`} className="text-zinc-400 hover:text-white">{l}</Link>
          ))}
          <Link href="/profile" className="text-zinc-400 hover:text-white">Cá nhân</Link>
        </div>
        <span>© 2026</span>
      </div>
    </footer>
  );
}
