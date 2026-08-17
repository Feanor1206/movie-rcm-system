import type { Metadata, Viewport } from 'next';
import { Inter, Playfair_Display } from 'next/font/google';
import { WatchlistProvider } from '@/lib/context/WatchlistContext';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

const playfair = Playfair_Display({
  subsets: ['latin'],
  variable: '--font-editorial',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Dippie — Curated Cinema & AI Movie Discovery',
  description:
    'Dippie is an OLED-optimized, AI-powered movie discovery and recommendation platform crafted for cinema lovers.',
  keywords: ['movies', 'cinema', 'recommendation system', 'streaming', 'film discovery', 'editorial cinema'],
  authors: [{ name: 'Dippie Cinema' }],
};

export const viewport: Viewport = {
  themeColor: '#09090d',
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
    <html lang="en" className={`${inter.variable} ${playfair.variable} dark`}>
      <body className="min-h-screen bg-cinema-950 font-sans text-foreground antialiased selection:bg-accent-rose selection:text-white">
        <WatchlistProvider>{children}</WatchlistProvider>
      </body>
    </html>
  );
}
