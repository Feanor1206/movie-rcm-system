import Link from 'next/link';
export function Footer() {
 return <footer className="comic-footer"><div className="page-shell flex flex-col gap-6 py-8 sm:flex-row sm:items-center sm:justify-between"><Link href="/" className="comic-wordmark text-3xl">Dippie<span className="ml-2 text-sage">✳</span></Link><p className="text-sm">Những câu chuyện nhỏ. Những thế giới lớn.</p><nav aria-label="Liên kết cuối trang" className="flex gap-5 text-xs font-semibold"><Link href="/search">Kho phim</Link><Link href="/search?genre=Family">Gia đình</Link><Link href="/profile">Danh sách xem</Link></nav><span className="text-[10px] tracking-widest">© DIPPIE 2026</span></div></footer>;
}
