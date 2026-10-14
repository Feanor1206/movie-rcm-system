import React from 'react';
import Link from 'next/link';

export function Footer() {
  return (
    <footer className="border-t border-surface-border bg-background">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid gap-8 sm:grid-cols-2 md:grid-cols-4">
          {/* Logo & Intro */}
          <div className="sm:col-span-2">
            <Link href="/" className="inline-flex items-center gap-1.5 font-bold tracking-tight text-xl text-white">
              <span className="font-extrabold tracking-tighter text-2xl">DIPPIE</span>
              <span className="h-2 w-2 rounded-full bg-brand" />
            </Link>
            <p className="mt-2.5 max-w-md text-xs leading-relaxed text-zinc-400">
              Nền tảng tuyển chọn và gợi ý phim hoạt hình thông minh, đem lại trải nghiệm khám phá nhẹ nhàng, không spoil và tôn trọng người xem.
            </p>
          </div>

          {/* Quick links */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-300">Khám phá hoạt hình</h4>
            <ul className="mt-2.5 space-y-1.5 text-xs">
              <li>
                <Link href="/search?genre=Animation" className="text-zinc-400 hover:text-white transition-colors">
                  Toàn bộ phim hoạt hình
                </Link>
              </li>
              <li>
                <Link href="/search?genre=Fantasy" className="text-zinc-400 hover:text-white transition-colors">
                  Kỳ ảo & Thần tiên
                </Link>
              </li>
              <li>
                <Link href="/search?genre=Family" className="text-zinc-400 hover:text-white transition-colors">
                  Hoạt hình gia đình
                </Link>
              </li>
              <li>
                <Link href="/search?genre=Adventure" className="text-zinc-400 hover:text-white transition-colors">
                  Phiêu lưu kỳ thú
                </Link>
              </li>
            </ul>
          </div>

          {/* User Account */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-300">Cá nhân</h4>
            <ul className="mt-2.5 space-y-1.5 text-xs">
              <li>
                <Link href="/profile" className="text-zinc-400 hover:text-white transition-colors">
                  Danh sách xem (Watchlist)
                </Link>
              </li>
              <li>
                <Link href="/profile" className="text-zinc-400 hover:text-white transition-colors">
                  Phim yêu thích
                </Link>
              </li>
              <li>
                <Link href="/profile" className="text-zinc-400 hover:text-white transition-colors">
                  Hồ sơ & Đánh giá
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-8 flex flex-col items-center justify-between gap-4 border-t border-surface-border pt-6 text-xs text-zinc-500 sm:flex-row">
          <p>© {new Date().getFullYear()} Dippie Animation. Mọi quyền được bảo lưu.</p>
          <div className="flex items-center gap-4">
            <span className="text-brand font-medium">Tone Xanh Lá Nhẹ Nhàng · Khám Phá Hoạt Hình</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
