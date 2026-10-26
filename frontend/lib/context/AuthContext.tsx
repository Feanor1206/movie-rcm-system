'use client';

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
  ReactNode,
} from 'react';

export type AuthUser = {
  id: number;
  username: string;
  email: string;
  fullName?: string;
  role: string;
};

export type AuthStatus = 'guest' | 'checking' | 'authenticated' | 'unavailable';

type AuthContextType = {
  user: AuthUser | null;
  token: string | null;
  status: AuthStatus;
  isAuthenticated: boolean;
  isLoading: boolean;
  isUnavailable: boolean;
  errorMessage: string | null;
  isAuthModalOpen: boolean;
  authModalMode: 'login' | 'register';
  openAuthModal: (mode?: 'login' | 'register') => void;
  closeAuthModal: () => void;
  login: (usernameOrEmail: string, password: string) => Promise<{ success: boolean; message?: string }>;
  register: (username: string, email: string, password: string, fullName?: string) => Promise<{ success: boolean; message?: string }>;
  logout: () => void;
  retryVerify: () => Promise<void>;
  handleSessionExpired: () => void;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const SPRINGBOOT_API = process.env.NEXT_PUBLIC_SPRINGBOOT_API_URL || '/api';
const REQUEST_TIMEOUT_MS = 8000;

function validateAuthPayload(data: any, fallbackToken?: string): { user: AuthUser; token: string } | null {
  if (!data || typeof data !== 'object') return null;

  const rawToken = typeof data.token === 'string' && data.token.trim().length > 0 ? data.token.trim() : fallbackToken;
  if (!rawToken || typeof rawToken !== 'string' || rawToken.trim().length === 0) {
    return null;
  }

  // ID must be a valid positive integer number
  let numericId: number | null = null;
  if (typeof data.id === 'number' && Number.isFinite(data.id) && data.id > 0) {
    numericId = data.id;
  } else if (typeof data.id === 'string' && /^\d+$/.test(data.id.trim())) {
    const parsed = parseInt(data.id.trim(), 10);
    if (parsed > 0) numericId = parsed;
  }
  if (numericId === null) {
    return null;
  }

  if (typeof data.username !== 'string' || data.username.trim().length === 0) {
    return null;
  }

  if (typeof data.email !== 'string' || !data.email.includes('@')) {
    return null;
  }

  const user: AuthUser = {
    id: numericId,
    username: data.username.trim(),
    email: data.email.trim(),
    fullName: typeof data.fullName === 'string' && data.fullName.trim().length > 0 ? data.fullName.trim() : undefined,
    role: typeof data.role === 'string' && data.role.trim().length > 0 ? data.role.trim() : 'ROLE_USER',
  };

  return { user, token: rawToken };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<AuthStatus>('checking');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState<'login' | 'register'>('login');

  // Generation counter to invalidate stale asynchronous responses across async boundaries
  const generationRef = useRef<number>(0);
  const activeAbortCtrlRef = useRef<AbortController | null>(null);

  const abortActiveRequest = useCallback(() => {
    if (activeAbortCtrlRef.current) {
      activeAbortCtrlRef.current.abort();
      activeAbortCtrlRef.current = null;
    }
  }, []);

  const clearSessionStorage = useCallback(() => {
    try {
      localStorage.removeItem('dippie_auth_token');
      localStorage.removeItem('dippie_auth_user');
    } catch {}
  }, []);

  const saveSessionStorage = useCallback((authToken: string, authUser: AuthUser) => {
    try {
      localStorage.setItem('dippie_auth_token', authToken);
      localStorage.setItem('dippie_auth_user', JSON.stringify(authUser));
    } catch {}
  }, []);

  // Verify stored session with backend /api/auth/me
  const verifySession = useCallback(
    async (authToken: string, generation: number) => {
      abortActiveRequest();
      const abortCtrl = new AbortController();
      activeAbortCtrlRef.current = abortCtrl;
      let timeoutId: any = null;

      try {
        timeoutId = setTimeout(() => abortCtrl.abort(), REQUEST_TIMEOUT_MS);

        const res = await fetch(`${SPRINGBOOT_API}/auth/me`, {
          headers: {
            Authorization: `Bearer ${authToken}`,
            Accept: 'application/json',
          },
          signal: abortCtrl.signal,
        });

        // 1. Guard check immediately after fetch
        if (generation !== generationRef.current) {
          return;
        }

        if (res.ok) {
          let json: any = null;
          try {
            json = await res.json();
          } catch {
            if (generation !== generationRef.current) return;
            setStatus('unavailable');
            setErrorMessage('Phản hồi từ máy chủ không hợp lệ.');
            return;
          }

          // 2. Guard check after reading json body
          if (generation !== generationRef.current) {
            return;
          }

          const validated = validateAuthPayload(json?.data, authToken);
          if (json?.success && validated) {
            // 3. Guard check immediately before commit
            if (generation !== generationRef.current) {
              return;
            }
            setUser(validated.user);
            setToken(validated.token);
            setStatus('authenticated');
            setErrorMessage(null);
            saveSessionStorage(validated.token, validated.user);
            return;
          } else {
            // Malformed data
            if (generation !== generationRef.current) return;
            setUser(null);
            setToken(null);
            setStatus('guest');
            setErrorMessage(null);
            clearSessionStorage();
            return;
          }
        }

        if (res.status === 401 || res.status === 403) {
          if (generation !== generationRef.current) return;
          setUser(null);
          setToken(null);
          setStatus('guest');
          setErrorMessage(null);
          clearSessionStorage();
        } else {
          if (generation !== generationRef.current) return;
          setStatus('unavailable');
          setErrorMessage('Máy chủ xác thực tạm thời không phản hồi. Vui lòng thử lại.');
        }
      } catch (err: unknown) {
        if (generation !== generationRef.current) {
          return;
        }

        if (err instanceof DOMException && err.name === 'AbortError') {
          setStatus('unavailable');
          setErrorMessage('Kết nối tới máy chủ quá thời gian chờ (timeout).');
        } else {
          setStatus('unavailable');
          setErrorMessage('Không thể kết nối đến máy chủ xác thực.');
        }
      } finally {
        if (timeoutId) {
          clearTimeout(timeoutId);
        }
        if (activeAbortCtrlRef.current === abortCtrl) {
          activeAbortCtrlRef.current = null;
        }
      }
    },
    [abortActiveRequest, clearSessionStorage, saveSessionStorage]
  );

  // Boot check
  useEffect(() => {
    let savedToken: string | null = null;
    try {
      savedToken = localStorage.getItem('dippie_auth_token');
    } catch {}

    if (savedToken && typeof savedToken === 'string' && savedToken.trim().length > 0) {
      generationRef.current += 1;
      const gen = generationRef.current;
      setStatus('checking');
      verifySession(savedToken.trim(), gen);
    } else {
      setStatus('guest');
    }

    return () => {
      generationRef.current += 1;
      abortActiveRequest();
    };
  }, [abortActiveRequest, verifySession]);

  const retryVerify = async () => {
    let savedToken: string | null = token;
    if (!savedToken) {
      try {
        savedToken = localStorage.getItem('dippie_auth_token');
      } catch {}
    }

    if (!savedToken) {
      setStatus('guest');
      return;
    }

    generationRef.current += 1;
    const gen = generationRef.current;
    setStatus('checking');
    setErrorMessage(null);
    await verifySession(savedToken, gen);
  };

  const handleSessionExpired = useCallback(() => {
    abortActiveRequest();
    generationRef.current += 1;
    setUser(null);
    setToken(null);
    setStatus('guest');
    setErrorMessage('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
    clearSessionStorage();
  }, [abortActiveRequest, clearSessionStorage]);

  const openAuthModal = (mode: 'login' | 'register' = 'login') => {
    setAuthModalMode(mode);
    setIsAuthModalOpen(true);
  };

  const closeAuthModal = () => {
    setIsAuthModalOpen(false);
  };

  const login = async (
    usernameOrEmail: string,
    password: string
  ): Promise<{ success: boolean; message?: string }> => {
    const cleanUsername = usernameOrEmail.trim();
    // Raw password verbatim - NEVER trimmed or lowercased
    const rawPassword = password;

    if (!cleanUsername) {
      return { success: false, message: 'Vui lòng nhập tên đăng nhập hoặc email' };
    }
    if (!rawPassword) {
      return { success: false, message: 'Vui lòng nhập mật khẩu' };
    }

    abortActiveRequest();
    generationRef.current += 1;
    const currentGen = generationRef.current;

    const abortCtrl = new AbortController();
    activeAbortCtrlRef.current = abortCtrl;
    let timeoutId: any = null;

    try {
      timeoutId = setTimeout(() => abortCtrl.abort(), REQUEST_TIMEOUT_MS);

      const res = await fetch(`${SPRINGBOOT_API}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          usernameOrEmail: cleanUsername,
          password: rawPassword,
        }),
        signal: abortCtrl.signal,
      });

      // 1. Guard check after fetch
      if (currentGen !== generationRef.current) {
        return { success: false, message: 'Thao tác đã bị hủy.' };
      }

      let json: any = null;
      try {
        json = await res.json();
      } catch {
        if (currentGen !== generationRef.current) {
          return { success: false, message: 'Thao tác đã bị hủy.' };
        }
        return { success: false, message: 'Phản hồi từ máy chủ không hợp lệ.' };
      }

      // 2. Guard check after reading json body
      if (currentGen !== generationRef.current) {
        return { success: false, message: 'Thao tác đã bị hủy.' };
      }

      const validated = validateAuthPayload(json?.data);
      if (res.ok && json?.success && validated) {
        // 3. Guard check immediately before commit
        if (currentGen !== generationRef.current) {
          return { success: false, message: 'Thao tác đã bị hủy.' };
        }

        setToken(validated.token);
        setUser(validated.user);
        setStatus('authenticated');
        setErrorMessage(null);
        saveSessionStorage(validated.token, validated.user);
        closeAuthModal();
        return { success: true };
      } else {
        const errorMsg =
          json?.message ||
          (res.status === 401
            ? 'Tên đăng nhập hoặc mật khẩu không chính xác.'
            : 'Đăng nhập thất bại.');
        return { success: false, message: errorMsg };
      }
    } catch (err: unknown) {
      if (currentGen !== generationRef.current) {
        return { success: false, message: 'Thao tác đã bị hủy.' };
      }

      if (err instanceof DOMException && err.name === 'AbortError') {
        return { success: false, message: 'Kết nối máy chủ quá thời gian chờ (timeout).' };
      }
      return {
        success: false,
        message: 'Không thể kết nối đến máy chủ xác thực. Vui lòng kiểm tra lại mạng hoặc dịch vụ.',
      };
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      if (activeAbortCtrlRef.current === abortCtrl) {
        activeAbortCtrlRef.current = null;
      }
    }
  };

  const register = async (
    username: string,
    email: string,
    password: string,
    fullName?: string
  ): Promise<{ success: boolean; message?: string }> => {
    const cleanUsername = username.trim();
    const cleanEmail = email.trim();
    const rawPassword = password; // Verbatim raw password

    if (!cleanUsername || cleanUsername.length < 3) {
      return { success: false, message: 'Tên đăng nhập phải có ít nhất 3 ký tự.' };
    }
    if (!cleanEmail || !cleanEmail.includes('@')) {
      return { success: false, message: 'Email không đúng định dạng.' };
    }
    if (!rawPassword || rawPassword.length < 6) {
      return { success: false, message: 'Mật khẩu phải có ít nhất 6 ký tự.' };
    }

    abortActiveRequest();
    generationRef.current += 1;
    const currentGen = generationRef.current;

    const abortCtrl = new AbortController();
    activeAbortCtrlRef.current = abortCtrl;
    let timeoutId: any = null;

    try {
      timeoutId = setTimeout(() => abortCtrl.abort(), REQUEST_TIMEOUT_MS);

      const res = await fetch(`${SPRINGBOOT_API}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          username: cleanUsername,
          email: cleanEmail,
          password: rawPassword,
          fullName: fullName?.trim() || undefined,
        }),
        signal: abortCtrl.signal,
      });

      // 1. Guard check after fetch
      if (currentGen !== generationRef.current) {
        return { success: false, message: 'Thao tác đã bị hủy.' };
      }

      let json: any = null;
      try {
        json = await res.json();
      } catch {
        if (currentGen !== generationRef.current) {
          return { success: false, message: 'Thao tác đã bị hủy.' };
        }
        return { success: false, message: 'Phản hồi từ máy chủ không hợp lệ.' };
      }

      // 2. Guard check after reading json body
      if (currentGen !== generationRef.current) {
        return { success: false, message: 'Thao tác đã bị hủy.' };
      }

      const validated = validateAuthPayload(json?.data);
      if (res.ok && json?.success && validated) {
        // 3. Guard check immediately before commit
        if (currentGen !== generationRef.current) {
          return { success: false, message: 'Thao tác đã bị hủy.' };
        }

        setToken(validated.token);
        setUser(validated.user);
        setStatus('authenticated');
        setErrorMessage(null);
        saveSessionStorage(validated.token, validated.user);
        closeAuthModal();
        return { success: true };
      } else {
        const errorMsg = json?.message || 'Đăng ký thất bại. Vui lòng thử lại.';
        return { success: false, message: errorMsg };
      }
    } catch (err: unknown) {
      if (currentGen !== generationRef.current) {
        return { success: false, message: 'Thao tác đã bị hủy.' };
      }

      if (err instanceof DOMException && err.name === 'AbortError') {
        return { success: false, message: 'Kết nối máy chủ quá thời gian chờ (timeout).' };
      }
      return {
        success: false,
        message: 'Không thể kết nối đến máy chủ xác thực. Vui lòng kiểm tra kết nối mạng.',
      };
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      if (activeAbortCtrlRef.current === abortCtrl) {
        activeAbortCtrlRef.current = null;
      }
    }
  };

  const logout = useCallback(() => {
    abortActiveRequest();
    generationRef.current += 1; // Invalidate any incoming response across all boundaries
    setUser(null);
    setToken(null);
    setStatus('guest');
    setErrorMessage(null);
    clearSessionStorage();
  }, [abortActiveRequest, clearSessionStorage]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        status,
        isAuthenticated: status === 'authenticated',
        isLoading: status === 'checking',
        isUnavailable: status === 'unavailable',
        errorMessage,
        isAuthModalOpen,
        authModalMode,
        openAuthModal,
        closeAuthModal,
        login,
        register,
        logout,
        retryVerify,
        handleSessionExpired,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
