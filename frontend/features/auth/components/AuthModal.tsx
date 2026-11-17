import React, { useState, useRef, useEffect } from 'react';
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

  const modalRef = useRef<HTMLDivElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const firstInputRef = useRef<HTMLInputElement | null>(null);
  useEffect(() => {
    if (!isAuthModalOpen) return;
    if (document.activeElement && (!modalRef.current || !modalRef.current.contains(document.activeElement))) {
      openerRef.current = document.activeElement as HTMLElement | null;
    }
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const timer = setTimeout(() => {
      firstInputRef.current?.focus();
    }, 50);
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSubmitting) {
        e.preventDefault();
        closeAuthModal();
        return;
      }

      if (e.key === 'Tab' && modalRef.current) {
        const focusableElements = modalRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (!modalRef.current.contains(document.activeElement)) {
          e.preventDefault();
          if (e.shiftKey) lastElement.focus();
          else firstElement.focus();
          return;
        }

        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      clearTimeout(timer);
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
      openerRef.current?.focus();
    };
  }, [isAuthModalOpen, isSubmitting, closeAuthModal]);

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
          showToast('Đăng nhập thành công.');
          closeAuthModal();
        } else {
          setError(res.message || 'Tên đăng nhập hoặc mật khẩu không chính xác.');
        }
      } else {
        const res = await register(username, email, password, fullName);
        if (res.success) {
          showToast('Đăng ký thành công.');
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
      ref={modalRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in"
    >
      <div className="relative w-full max-w-md overflow-hidden rounded-2xl border border-surface-border bg-surface p-6 sm:p-8 shadow-2xl">

        <button
          type="button"
          onClick={closeAuthModal}
          disabled={isSubmitting}
          className="absolute right-3.5 top-3.5 flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg px-3 text-xs font-semibold text-muted hover:bg-surface-elevated hover:text-ink cursor-pointer disabled:opacity-50"
          aria-label="Đóng cửa sổ"
        >
          Đóng
        </button>


        <div className="mb-6">
          <div className="flex items-center gap-1.5 font-bold tracking-tight text-xl text-ink">
            <span className="tracking-tight font-extrabold text-2xl text-brand-dark">Dippie</span>
          </div>
          <h2 id="auth-modal-title" className="mt-2 text-xl font-bold tracking-tight text-ink">
            {isLogin ? 'Đăng nhập' : 'Đăng ký'}
          </h2>
        </div>


        <div className="grid grid-cols-2 gap-1 rounded-xl border border-surface-border bg-surface-muted p-1 mb-6">
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => {
              setError(null);
              openAuthModal('login');
            }}
            className={`rounded-lg py-2 text-xs font-semibold transition-all cursor-pointer disabled:opacity-60 ${
              isLogin ? 'bg-surface-elevated text-ink font-bold shadow-sm' : 'text-muted hover:text-ink'
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
            className={`rounded-lg py-2 text-xs font-semibold transition-all cursor-pointer disabled:opacity-60 ${
              !isLogin ? 'bg-surface-elevated text-ink font-bold shadow-sm' : 'text-muted hover:text-ink'
            }`}
          >
            Đăng ký
          </button>
        </div>


        {error && (
          <div className="mb-4 rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-800 leading-relaxed">
            {error}
          </div>
        )}


        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <div>
              <label htmlFor="auth-full-name" className="block text-xs font-medium text-muted mb-1.5">
                Họ và tên
              </label>
              <div className="relative flex items-center rounded-lg border border-surface-border bg-surface-muted px-3 py-2.5 focus-within:border-brand focus-within:ring-1 focus-within:ring-brand">

                <input
                  id="auth-full-name"
                  ref={!isLogin ? firstInputRef : undefined}
                  type="text"
                  disabled={isSubmitting}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Nguyễn Văn A"
                  className="w-full bg-transparent text-base sm:text-sm text-ink placeholder:text-muted focus:outline-none focus-visible:shadow-none disabled:opacity-50"
                />
              </div>
            </div>
          )}

          <div>
            <label htmlFor="auth-username" className="block text-xs font-medium text-muted mb-1.5">
              {isLogin ? 'Tên đăng nhập hoặc Email' : 'Tên đăng nhập'}
            </label>
            <div className="relative flex items-center rounded-lg border border-surface-border bg-surface-muted px-3 py-2.5 focus-within:border-brand focus-within:ring-1 focus-within:ring-brand">

              <input
                id="auth-username"
                ref={isLogin ? firstInputRef : undefined}
                data-testid="login-username-input"
                type="text"
                required
                disabled={isSubmitting}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={isLogin ? 'Nhập tên đăng nhập hoặc email' : 'tentaikhoan'}
                autoComplete={isLogin ? 'username' : 'new-username'}
                className="w-full bg-transparent text-base sm:text-sm text-ink placeholder:text-muted focus:outline-none focus-visible:shadow-none disabled:opacity-50"
              />
            </div>
          </div>

          {!isLogin && (
            <div>
              <label htmlFor="auth-email" className="block text-xs font-medium text-muted mb-1.5">
                Email
              </label>
              <div className="relative flex items-center rounded-lg border border-surface-border bg-surface-muted px-3 py-2.5 focus-within:border-brand focus-within:ring-1 focus-within:ring-brand">

                <input
                  id="auth-email"
                  type="email"
                  required
                  disabled={isSubmitting}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="email@vidu.com"
                  autoComplete="email"
                  className="w-full bg-transparent text-base sm:text-sm text-ink placeholder:text-muted focus:outline-none focus-visible:shadow-none disabled:opacity-50"
                />
              </div>
            </div>
          )}

          <div>
            <label htmlFor="auth-password" className="block text-xs font-medium text-muted mb-1.5">
              Mật khẩu
            </label>
            <div className="relative flex items-center rounded-lg border border-surface-border bg-surface-muted px-3 py-2.5 focus-within:border-brand focus-within:ring-1 focus-within:ring-brand">

              <input
                id="auth-password"
                data-testid="login-password-input"
                type="password"
                required
                disabled={isSubmitting}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete={isLogin ? 'current-password' : 'new-password'}
                className="w-full bg-transparent text-base sm:text-sm text-ink placeholder:text-muted focus:outline-none focus-visible:shadow-none disabled:opacity-50"
              />
            </div>
          </div>

          <button
            data-testid="login-submit-button"
            type="submit"
            disabled={isSubmitting}
            className="btn-primary w-full justify-center py-2.5 text-xs sm:text-sm font-bold shadow-brand-sm disabled:opacity-50 cursor-pointer"
          >

            {isSubmitting ? (
              <span className="flex items-center gap-2">
                Đang xử lý…
              </span>
            ) : isLogin ? (
              <span className="flex items-center gap-1.5">
                Đăng nhập
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                Tạo tài khoản
              </span>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
