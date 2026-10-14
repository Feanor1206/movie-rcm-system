import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './features/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#090d0b',
        foreground: '#f3f4f6',
        surface: {
          DEFAULT: '#111714',
          elevated: '#16201b',
          hover: '#1d2a23',
          border: '#23332a',
        },
        brand: {
          DEFAULT: '#10b981',
          foreground: '#09090b',
          hover: '#34d399',
          active: '#059669',
          dark: '#047857',
          light: '#34d399',
          muted: '#064e3b',
          subtle: 'rgba(16, 185, 129, 0.12)',
        },
        danger: {
          DEFAULT: '#ef4444',
          hover: '#dc2626',
          muted: '#7f1d1d',
        },
        cinema: {
          red: '#10b981',
          'red-hover': '#059669',
          'red-muted': '#064e3b',
        },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
      boxShadow: {
        'brand-sm': '0 0 15px -3px rgba(16, 185, 129, 0.35)',
        'brand-lg': '0 0 30px -5px rgba(16, 185, 129, 0.4)',
        'red-sm': '0 0 15px -3px rgba(16, 185, 129, 0.35)',
        'red-lg': '0 0 30px -5px rgba(16, 185, 129, 0.4)',
        'card-hover': '0 10px 25px -5px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(16, 185, 129, 0.25)',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out forwards',
        'slide-up': 'slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
