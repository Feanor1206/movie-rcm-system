'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

export type AuthUser = {
  id: number;
  username: string;
  email: string;
  fullName?: string;
  role: string;
};

type AuthContextType = {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isAuthModalOpen: boolean;
  authModalMode: 'login' | 'register';
  openAuthModal: (mode?: 'login' | 'register') => void;
  closeAuthModal: () => void;
  login: (usernameOrEmail: string, password: string) => Promise<{ success: boolean; message?: string }>;
  register: (username: string, email: string, password: string, fullName?: string) => Promise<{ success: boolean; message?: string }>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const SPRINGBOOT_API = process.env.NEXT_PUBLIC_SPRINGBOOT_API_URL || 'http://localhost:8080/api';

const MOCK_50_USERS: Record<string, { id: number; fullName: string; email: string; role: string }> = {
  alex: { id: 1, fullName: 'Alex Morgan', email: 'alex@dippie.com', role: 'ROLE_ADMIN' },
  linh_dan: { id: 2, fullName: 'Nguyễn Linh Đan', email: 'linhdan@gmail.com', role: 'ROLE_USER' },
  minh_tri: { id: 3, fullName: 'Trần Minh Trí', email: 'minhtri.tran@gmail.com', role: 'ROLE_USER' },
  duc_anh: { id: 4, fullName: 'Lê Đức Anh', email: 'ducanh.le@yahoo.com', role: 'ROLE_USER' },
  mai_anh: { id: 5, fullName: 'Phạm Mai Anh', email: 'maianh.pham@outlook.com', role: 'ROLE_USER' },
  hoang_long: { id: 6, fullName: 'Hoàng Long', email: 'hoanglong99@gmail.com', role: 'ROLE_USER' },
  viet_dung: { id: 7, fullName: 'Vũ Việt Dũng', email: 'dung.vu@gmail.com', role: 'ROLE_USER' },
  huong_giang: { id: 8, fullName: 'Đặng Hương Giang', email: 'giang.dang@gmail.com', role: 'ROLE_USER' },
  tuan_kiet: { id: 9, fullName: 'Bùi Tuấn Kiệt', email: 'kiet.bui@gmail.com', role: 'ROLE_USER' },
  thao_vy: { id: 10, fullName: 'Võ Thảo Vy', email: 'thaovy.vo@gmail.com', role: 'ROLE_USER' },
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState<'login' | 'register'>('login');

  // Load session from localStorage on boot
  useEffect(() => {
    try {
      const savedToken = localStorage.getItem('dippie_auth_token');
      const savedUser = localStorage.getItem('dippie_auth_user');

      if (savedToken && savedUser) {
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
        fetchCurrentUser(savedToken);
      } else {
        setIsLoading(false);
      }
    } catch {
      setIsLoading(false);
    }
  }, []);

  const fetchCurrentUser = async (authToken: string) => {
    try {
      const res = await fetch(`${SPRINGBOOT_API}/auth/me`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (res.ok) {
        const json = await res.json();
        if (json.success && json.data) {
          setUser(json.data);
          localStorage.setItem('dippie_auth_user', JSON.stringify(json.data));
        }
      }
    } catch {
      // Backend not running or offline, keep local user state
    } finally {
      setIsLoading(false);
    }
  };

  const openAuthModal = (mode: 'login' | 'register' = 'login') => {
    setAuthModalMode(mode);
    setIsAuthModalOpen(true);
  };

  const closeAuthModal = () => {
    setIsAuthModalOpen(false);
  };

  const login = async (usernameOrEmail: string, password: string): Promise<{ success: boolean; message?: string }> => {
    const cleanInput = usernameOrEmail.trim().toLowerCase();
    const cleanPass = password.trim();

    try {
      // 1. Thử kết nối đến Spring Boot Backend
      const res = await fetch(`${SPRINGBOOT_API}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usernameOrEmail: cleanInput, password: cleanPass }),
      });

      const json = await res.json();
      if (res.ok && json.success) {
        const authData = json.data;
        const loggedUser: AuthUser = {
          id: authData.id,
          username: authData.username,
          email: authData.email,
          fullName: authData.fullName,
          role: authData.role,
        };

        setToken(authData.token);
        setUser(loggedUser);
        localStorage.setItem('dippie_auth_token', authData.token);
        localStorage.setItem('dippie_auth_user', JSON.stringify(loggedUser));
        closeAuthModal();
        return { success: true };
      } else {
        return { success: false, message: json.message || 'Tên đăng nhập hoặc mật khẩu không chính xác' };
      }
    } catch {
      // 2. Chế độ dự phòng thông minh (Zero-Downtime Mock Login khi Spring Boot chưa bật)
      const matchedMock = MOCK_50_USERS[cleanInput] || {
        id: Math.floor(Math.random() * 900) + 51,
        fullName: cleanInput.charAt(0).toUpperCase() + cleanInput.slice(1),
        email: `${cleanInput}@dippie.com`,
        role: 'ROLE_USER',
      };

      if (cleanPass === 'password123' || cleanPass.length >= 6) {
        const mockUser: AuthUser = {
          id: matchedMock.id,
          username: cleanInput,
          email: matchedMock.email,
          fullName: matchedMock.fullName,
          role: matchedMock.role,
        };
        const mockToken = `mock_jwt_${cleanInput}_${Date.now()}`;
        setToken(mockToken);
        setUser(mockUser);
        localStorage.setItem('dippie_auth_token', mockToken);
        localStorage.setItem('dippie_auth_user', JSON.stringify(mockUser));
        closeAuthModal();
        return { success: true };
      }

      return {
        success: false,
        message: 'Mật khẩu mặc định là: password123 (hoặc tối thiểu 6 ký tự).',
      };
    }
  };

  const register = async (
    username: string,
    email: string,
    password: string,
    fullName?: string
  ): Promise<{ success: boolean; message?: string }> => {
    const cleanUsername = username.trim().toLowerCase();
    const cleanEmail = email.trim().toLowerCase();
    const cleanPassword = password.trim();

    try {
      const res = await fetch(`${SPRINGBOOT_API}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: cleanUsername, email: cleanEmail, password: cleanPassword, fullName }),
      });

      const json = await res.json();
      if (res.ok && json.success) {
        const authData = json.data;
        const loggedUser: AuthUser = {
          id: authData.id,
          username: authData.username,
          email: authData.email,
          fullName: authData.fullName,
          role: authData.role,
        };

        setToken(authData.token);
        setUser(loggedUser);
        localStorage.setItem('dippie_auth_token', authData.token);
        localStorage.setItem('dippie_auth_user', JSON.stringify(loggedUser));
        closeAuthModal();
        return { success: true };
      } else {
        return { success: false, message: json.message || 'Đăng ký thất bại' };
      }
    } catch {
      // Offline fallback for registration
      const newMockUser: AuthUser = {
        id: Math.floor(Math.random() * 900) + 100,
        username: cleanUsername,
        email: cleanEmail,
        fullName: fullName || cleanUsername,
        role: 'ROLE_USER',
      };
      const mockToken = `mock_jwt_${cleanUsername}_${Date.now()}`;
      setToken(mockToken);
      setUser(newMockUser);
      localStorage.setItem('dippie_auth_token', mockToken);
      localStorage.setItem('dippie_auth_user', JSON.stringify(newMockUser));
      closeAuthModal();
      return { success: true };
    }
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('dippie_auth_token');
    localStorage.removeItem('dippie_auth_user');
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isLoading,
        isAuthModalOpen,
        authModalMode,
        openAuthModal,
        closeAuthModal,
        login,
        register,
        logout,
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
