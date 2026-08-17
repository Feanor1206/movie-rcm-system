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
        background: '#09090d',
        foreground: '#f8fafc',
        cinema: {
          950: '#09090d',
          900: '#0f0f18',
          850: '#131322',
          800: '#1a1a2e',
          700: '#262642',
          600: '#3c3a63',
          500: '#5a578c',
          400: '#8c89b8',
          300: '#bcbae0',
          200: '#deddf2',
          100: '#f0f0fa',
        },
        accent: {
          rose: '#e11d48',
          'rose-hover': '#f43f5e',
          gold: '#f59e0b',
          'gold-light': '#fbbf24',
        },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', 'sans-serif'],
        editorial: ['var(--font-editorial)', 'Didot', 'Bodoni MT', 'serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        'glow-rose': '0 0 25px -5px rgba(225, 29, 72, 0.35)',
        'glow-gold': '0 0 25px -5px rgba(245, 158, 11, 0.35)',
        'card-hover': '0 12px 30px -8px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(225, 29, 72, 0.25)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out forwards',
        'slide-up': 'slideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'pulse-subtle': 'pulseSubtle 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSubtle: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.75' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
