import { lazy, Suspense, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes, useLocation } from 'react-router';
import { Footer } from '@/components/layout/Footer';
import { Navbar } from '@/components/layout/Navbar';
import { AuthProvider } from '@/lib/context/AuthContext';
import { WatchlistProvider } from '@/lib/context/WatchlistContext';
import HomePage from './page';
import NotFound from './not-found';
import './globals.css';

const SearchPage = lazy(() => import('./search/page'));
const ProfilePage = lazy(() => import('./profile/page'));
const MoviePage = lazy(() => import('./movies/[id]/page'));
const SeriesPage = lazy(() => import('./series/[id]/page'));
const ImportPage = lazy(() => import('./admin/import/page'));

function App() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <>
      <Navbar />
      <Suspense fallback={<main className="page-shell comic-loading" role="status">Đang mở trang…</main>}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/movies/:id" element={<MoviePage />} />
          <Route path="/series/:id" element={<SeriesPage />} />
          <Route path="/admin/import" element={<ImportPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
      <Footer />
    </>
  );
}

createRoot(document.getElementById('root')!).render(
  <BrowserRouter>
    <AuthProvider><WatchlistProvider><App /></WatchlistProvider></AuthProvider>
  </BrowserRouter>,
);
