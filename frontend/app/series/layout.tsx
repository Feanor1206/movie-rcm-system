import type { ReactNode } from 'react';
import { Navbar } from '@/components/layout/Navbar';
import { Footer } from '@/components/layout/Footer';

export default function SeriesLayout({ children }: { children: ReactNode }) {
  return <><Navbar />{children}<Footer /></>;
}
