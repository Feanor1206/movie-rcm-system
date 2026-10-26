import type { Metadata, Viewport } from 'next';
import { AuthProvider } from '@/lib/context/AuthContext';
import { WatchlistProvider } from '@/lib/context/WatchlistContext';
import './globals.css';

export const metadata: Metadata = {
  title: 'Dippie — Tạp chí truyện phim hoạt hình',
  description: 'Mở từng trang truyện, khám phá những bộ phim hoạt hình đáng nhớ cùng Dippie.',
  keywords: ['hoạt hình', 'animation', 'anime', 'gợi ý hoạt hình', 'khám phá phim', 'CineBot'],
  authors: [{ name: 'Dippie Animation' }],
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
    <html lang="vi">
      <body className="min-h-screen bg-background font-sans text-foreground antialiased selection:bg-mint selection:text-ink">
        <AuthProvider>
          <WatchlistProvider>{children}</WatchlistProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
