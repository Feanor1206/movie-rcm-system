import React, { Suspense } from 'react';
import { Footer } from '@/components/layout/Footer';
import { Navbar } from '@/components/layout/Navbar';
import { SearchExperience } from '@/features/search/components/SearchExperience';

export default function SearchPage() {
  return (
    <>
      <Navbar />
      <Suspense
        fallback={
          <div className="page-shell min-h-[75vh] py-16 flex items-center justify-center">
            <div className="font-mono text-sm text-brand animate-pulse">
              Đang tải kho phim hoạt hình...
            </div>
          </div>
        }
      >
        <SearchExperience />
      </Suspense>
      <Footer />
    </>
  );
}
