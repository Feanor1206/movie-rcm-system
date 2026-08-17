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
  title: 'Dippie — Nền tảng gợi ý & khám phá phim điện ảnh',
  description:
    'Dippie là nền tảng khám phá phim chuẩn điện ảnh với trợ lý gợi ý phim thông minh CineBot và giao diện tối giản Đen/Đỏ/Trắng.',
  keywords: ['movies', 'cinema', 'gợi ý phim', 'xem phim', 'film discovery', 'CineBot'],
  authors: [{ name: 'Dippie Cinema' }],
};

export const viewport: Viewport = {
  themeColor: '#000000',
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
      <body className="min-h-screen bg-black font-sans text-foreground antialiased selection:bg-cinema-red selection:text-white">
        <AuthProvider>
          <WatchlistProvider>{children}</WatchlistProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
