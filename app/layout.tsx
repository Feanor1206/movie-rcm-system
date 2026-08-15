import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'Dippie — Find your next favorite film', description: 'Dippie is a cinematic movie discovery platform for finding stories worth staying for.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
