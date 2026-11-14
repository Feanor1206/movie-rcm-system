import Link from 'next/link';

export default function NotFound() {
  return (
    <main className="grid min-h-dvh place-items-center p-6 text-center">
      <div>
        <h1 className="comic-heading text-3xl font-bold">Không tìm thấy trang</h1>
        <Link href="/" className="btn-primary mt-6">Về trang chủ</Link>
      </div>
    </main>
  );
}
