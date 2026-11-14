import type { Metadata, Viewport } from 'next';
import { AuthProvider } from '@/lib/context/AuthContext';
import { WatchlistProvider } from '@/lib/context/WatchlistContext';
import './globals.css';

export const metadata: Metadata = {
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
    <html lang="vi">
      <body className="min-h-screen bg-background font-sans text-foreground antialiased selection:bg-mint selection:text-ink">
        <AuthProvider>
          <WatchlistProvider>{children}</WatchlistProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
