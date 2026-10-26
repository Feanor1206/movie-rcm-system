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
        ink: '#18241e',
        paper: '#f4f0e5',
        'paper-white': '#fbf9f2',
        muted: '#59665a',
        sage: '#8dad86',
        mint: '#c9ddbd',
        background: '#f4f0e5',
        foreground: '#18241e',
        surface: {
          DEFAULT: '#fbf9f2',
          elevated: '#e7e1d2',
          muted: '#f1eddf',
          hover: '#dce8d4',
          border: '#18241e',
        },
        brand: {
          DEFAULT: '#8dad86',
          foreground: '#18241e',
          hover: '#a9c5a0',
          active: '#718d6b',
          dark: '#536c50',
          light: '#c9ddbd',
          muted: '#dce8d4',
          subtle: 'rgba(141, 173, 134, 0.18)',
        },
        danger: {
          DEFAULT: '#ef4444',
          hover: '#dc2626',
          muted: '#7f1d1d',
        },
        cinema: { red: '#8dad86', 'red-hover': '#718d6b', 'red-muted': '#dce8d4' },
      },
      fontFamily: {
        sans: ['ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        display: ['Georgia', 'Cambria', '"Times New Roman"', 'serif'],
      },
      boxShadow: {
        'brand-sm': '3px 3px 0 #18241e',
        'brand-lg': '5px 5px 0 #18241e',
        'red-sm': '3px 3px 0 #18241e',
        'red-lg': '5px 5px 0 #18241e',
        'card-hover': '4px 4px 0 #18241e',
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
