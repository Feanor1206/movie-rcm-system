'use client';

import React, { useState } from 'react';
import { X, Lock, User, Mail, Loader2, ArrowRight } from 'lucide-react';
import { useAuth } from '@/lib/context/AuthContext';
import { useWatchlist } from '@/lib/context/WatchlistContext';

export function AuthModal() {
  const { isAuthModalOpen, closeAuthModal, authModalMode, openAuthModal, login, register } = useAuth();
  const { showToast } = useWatchlist();

  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isAuthModalOpen) return null;

  const isLogin = authModalMode === 'login';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    setError(null);
    setIsSubmitting(true);

    try {
      if (isLogin) {
        const res = await login(username, password);
        if (res.success) {
          showToast('Đăng nhập thành công! Chào mừng bạn trở lại.');
          closeAuthModal();
        } else {
          setError(res.message || 'Tên đăng nhập hoặc mật khẩu không chính xác.');
        }
      } else {
        const res = await register(username, email, password, fullName);
        if (res.success) {
          showToast('Đăng ký tài khoản thành công!');
          closeAuthModal();
        } else {
          setError(res.message || 'Đăng ký không thành công. Vui lòng thử lại.');
        }
      }
    } catch {
      setError('Đã xảy ra sự cố kết nối. Vui lòng kiểm tra lại đường truyền.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in"
      onKeyDown={(e) => {
        if (e.key === 'Escape' && !isSubmitting) closeAuthModal();
      }}
    >
      <div className="relative w-full max-w-md overflow-hidden rounded-xl border border-surface-border bg-surface p-6 sm:p-8 shadow-2xl">
        {/* Close Button */}
        <button
          type="button"
          onClick={closeAuthModal}
          disabled={isSubmitting}
          className="absolute right-4 top-4 rounded-md p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-white transition-colors cursor-pointer disabled:opacity-50"
          aria-label="Đóng popup"
        >
          <X size={18} />
        </button>

        {/* Brand Header */}
        <div className="mb-6">
          <div className="flex items-center gap-1.5 font-bold tracking-tight text-xl text-white">
            <span className="tracking-tighter font-extrabold text-2xl">DIPPIE</span>
            <span className="h-2 w-2 rounded-full bg-brand shadow-brand-sm" />
          </div>
          <h2 id="auth-modal-title" className="mt-2 text-xl font-bold tracking-tight text-white">
            {isLogin ? 'Đăng nhập tài khoản' : 'Tạo tài khoản mới'}
          </h2>
          <p className="mt-1 text-xs text-zinc-400">
            {isLogin
              ? 'Lưu trữ Watchlist và đồng bộ điểm đánh giá phim của bạn'
              : 'Tham gia khám phá phim hoạt hình và nhận đề xuất cá nhân hóa'}
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="grid grid-cols-2 gap-1 rounded-lg border border-surface-border bg-surface-muted p-1 mb-6">
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => {
              setError(null);
              openAuthModal('login');
            }}
            className={`rounded-md py-1.5 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-60 ${
              isLogin ? 'bg-zinc-800 text-white font-bold' : 'text-zinc-400 hover:text-white'
            }`}
          >
            Đăng nhập
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => {
              setError(null);
              openAuthModal('register');
            }}
            className={`rounded-md py-1.5 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-60 ${
              !isLogin ? 'bg-zinc-800 text-white font-bold' : 'text-zinc-400 hover:text-white'
            }`}
          >
            Đăng ký
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-4 rounded-md border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-400 leading-relaxed">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                Họ và tên
              </label>
              <div className="relative flex items-center rounded-md border border-surface-border bg-surface-muted px-3 py-2 focus-within:border-brand">
                <User size={15} className="text-zinc-500 mr-2 shrink-0" />
                <input
                  type="text"
                  disabled={isSubmitting}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Nguyễn Văn A"
                  className="w-full bg-transparent text-xs sm:text-sm text-white placeholder:text-zinc-600 focus:outline-none disabled:opacity-50"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">
              {isLogin ? 'Tên đăng nhập hoặc Email' : 'Tên đăng nhập'}
            </label>
            <div className="relative flex items-center rounded-md border border-surface-border bg-surface-muted px-3 py-2 focus-within:border-brand">
              <User size={15} className="text-zinc-500 mr-2 shrink-0" />
              <input
                type="text"
                required
                disabled={isSubmitting}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={isLogin ? 'Nhập tên đăng nhập hoặc email' : 'tentaikhoan'}
                autoComplete={isLogin ? 'username' : 'new-username'}
                className="w-full bg-transparent text-xs sm:text-sm text-white placeholder:text-zinc-600 focus:outline-none disabled:opacity-50"
              />
            </div>
          </div>

          {!isLogin && (
            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                Email
              </label>
              <div className="relative flex items-center rounded-md border border-surface-border bg-surface-muted px-3 py-2 focus-within:border-brand">
                <Mail size={15} className="text-zinc-500 mr-2 shrink-0" />
                <input
                  type="email"
                  required
                  disabled={isSubmitting}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="email@vidu.com"
                  autoComplete="email"
                  className="w-full bg-transparent text-xs sm:text-sm text-white placeholder:text-zinc-600 focus:outline-none disabled:opacity-50"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">
              Mật khẩu
            </label>
            <div className="relative flex items-center rounded-md border border-surface-border bg-surface-muted px-3 py-2 focus-within:border-brand">
              <Lock size={15} className="text-zinc-500 mr-2 shrink-0" />
              <input
                type="password"
                required
                disabled={isSubmitting}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete={isLogin ? 'current-password' : 'new-password'}
                className="w-full bg-transparent text-xs sm:text-sm text-white placeholder:text-zinc-600 focus:outline-none disabled:opacity-50"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="btn-primary w-full justify-center py-2.5 text-xs sm:text-sm font-bold shadow-brand-sm disabled:opacity-50 cursor-pointer"
          >
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <Loader2 size={15} className="animate-spin" /> Đang xử lý...
              </span>
            ) : isLogin ? (
              <span className="flex items-center gap-1.5">
                Đăng nhập <ArrowRight size={14} />
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                Tạo tài khoản <ArrowRight size={14} />
              </span>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
