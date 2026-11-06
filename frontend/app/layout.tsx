import type { Metadata, Viewport } from 'next';
import { Inter } from 'next/font/google';
import { AuthProvider } from '@/lib/context/AuthContext';
import { WatchlistProvider } from '@/lib/context/WatchlistContext';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Dippie — Khám phá phim hoạt hình & gợi ý thông minh',
  description:
    'Dippie là nền tảng khám phá phim hoạt hình nhẹ nhàng, không spoil, hỗ trợ chọn phim nhanh với trợ lý thông minh CineBot và giao diện xanh lá tinh tế.',
  keywords: ['hoạt hình', 'animation', 'anime', 'gợi ý hoạt hình', 'khám phá phim', 'CineBot'],
  authors: [{ name: 'Dippie Animation' }],
};

export const viewport: Viewport = {
  themeColor: '#090d0b',
  colorScheme: 'dark',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className={`${inter.variable} dark`}>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased selection:bg-brand selection:text-white">
        <AuthProvider>
          <WatchlistProvider>{children}</WatchlistProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
