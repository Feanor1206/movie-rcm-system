import Link from 'next/link';

export function Footer() {
  return (
    <footer className="comic-footer mt-auto border-t border-surface-border bg-surface">
      <div className="page-shell flex flex-col gap-6 py-8 sm:flex-row sm:items-center sm:justify-between text-muted">
        <Link href="/" className="comic-wordmark text-2xl font-bold text-ink hover:text-brand-dark transition-colors">
          Dippie
        </Link>
        <nav aria-label="Liên kết cuối trang" className="flex flex-wrap gap-x-6 gap-y-2 text-xs font-medium">
          <Link href="/search" className="hover:text-ink transition-colors">Kho phim</Link>
          <Link href="/search?genre=Family" className="hover:text-ink transition-colors">Gia đình</Link>
          <Link href="/profile" className="hover:text-ink transition-colors">Danh sách xem</Link>
        </nav>
        <span className="text-xs text-muted">© Dippie 2026</span>
      </div>
    </footer>
  );
}
