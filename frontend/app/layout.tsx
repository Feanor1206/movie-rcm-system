import type { Metadata, Viewport } from 'next';
import { Be_Vietnam_Pro, Newsreader, JetBrains_Mono } from 'next/font/google';
import { AuthProvider } from '@/lib/context/AuthContext';
import { WatchlistProvider } from '@/lib/context/WatchlistContext';
import './globals.css';

const fontSans = Be_Vietnam_Pro({
  subsets: ['vietnamese', 'latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-sans',
  display: 'swap',
});

const fontSerif = Newsreader({
  subsets: ['vietnamese', 'latin'],
  weight: ['600', '700', '800'],
  style: ['normal', 'italic'],
  variable: '--font-serif',
  display: 'swap',
});

const fontMono = JetBrains_Mono({
  subsets: ['vietnamese', 'latin'],
  weight: ['500', '600'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'Dippie — Tạp chí truyện phim hoạt hình',
    template: '%s | Dippie',
  },
  description: 'Mở từng trang truyện, khám phá những bộ phim hoạt hình đáng nhớ cùng Dippie.',
  keywords: ['hoạt hình', 'animation', 'anime', 'gợi ý hoạt hình', 'khám phá phim', 'CineBot'],
  authors: [{ name: 'Dippie Animation' }],
  openGraph: {
    title: 'Dippie — Tạp chí truyện phim hoạt hình',
    description: 'Mở từng trang truyện, khám phá những bộ phim hoạt hình đáng nhớ cùng Dippie.',
    type: 'website',
    locale: 'vi_VN',
  },
  title: 'Dippie — Phim hoạt hình',
  description: 'Tìm và xem phim hoạt hình cùng Dippie.',
  keywords: ['phim hoạt hình', 'gợi ý phim', 'CineBot'],
  authors: [{ name: 'Dippie' }],
};

export const viewport: Viewport = {
  themeColor: '#f4f0e5',
  colorScheme: 'light',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="vi"
      className={`${fontSans.variable} ${fontSerif.variable} ${fontMono.variable}`}
    >
      <body className="min-h-screen bg-[var(--paper)] font-sans text-[var(--ink)] antialiased selection:bg-mint selection:text-ink">
        <AuthProvider>
          <WatchlistProvider>{children}</WatchlistProvider>
        </AuthProvider>
      </body>
    </html>
  );
}