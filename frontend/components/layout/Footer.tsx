import React from 'react';
import Link from 'next/link';

export function Footer() {
  return (
    <footer className="border-t border-zinc-850 bg-black">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid gap-8 sm:grid-cols-2 md:grid-cols-4">
          {/* Logo & Intro */}
          <div className="sm:col-span-2">
            <Link href="/" className="inline-flex items-center gap-1.5 font-bold tracking-tight text-xl text-white">
              <span className="font-extrabold tracking-tighter text-2xl">DIPPIE</span>
              <span className="h-2 w-2 rounded-full bg-cinema-red" />
            </Link>
            <p className="mt-2.5 max-w-md text-xs leading-relaxed text-zinc-400">
              Nền tảng tuyển chọn và gợi ý phim điện ảnh thông minh, đem lại trải nghiệm khám phá phim sâu sắc và tinh tế.
            </p>
          </div>

          {/* Quick links */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-300">Khám phá</h4>
            <ul className="mt-2.5 space-y-1.5 text-xs">
              <li>
                <Link href="/" className="text-zinc-400 hover:text-white transition-colors">
                  Phim thịnh hành
                </Link>
              </li>
              <li>
                <Link href="/search" className="text-zinc-400 hover:text-white transition-colors">
                  Tất cả kho phim
                </Link>
              </li>
              <li>
                <Link href="/search?genre=Sci-Fi" className="text-zinc-400 hover:text-white transition-colors">
                  Phim Khoa học viễn tưởng
                </Link>
              </li>
              <li>
                <Link href="/search?genre=Drama" className="text-zinc-400 hover:text-white transition-colors">
                  Phim Tâm lý - Xã hội
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
                  Lịch sử đánh giá
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-8 flex flex-col items-center justify-between gap-4 border-t border-zinc-850 pt-6 text-xs text-zinc-500 sm:flex-row">
          <p>© {new Date().getFullYear()} Dippie Cinema. Mọi quyền được bảo lưu.</p>
          <div className="flex items-center gap-4">
            <span>Tone Đen · Đỏ · Trắng Chuẩn Điện Ảnh</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
