/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        arena: {
          50: '#f0fdf4',
          100: '#dcfce7',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          900: '#14532d',
        },
        // 手绘手账风色板
        paper: {
          50: '#fdfbf7',
          100: '#faf6f0', // 主背景：米白纸色
          200: '#f5efe4', // 侧边栏背景
          300: '#f0ebe3', // 系统消息背景
        },
        ink: {
          50: '#8b8b7b',
          100: '#6b6b6b',
          200: '#4a4a4a',
          300: '#2b2b2b', // 主文字：墨水黑
        },
        divider: {
          DEFAULT: '#d4cfc7',
          light: '#e8e4dc',
        },
        marker: {
          red: '#e85d5d',
          blue: '#5b8def',
          green: '#6bc47a',
          yellow: '#f2c94c',
          purple: '#9b7bf2',
          gold: '#d4a843', // 皇冠金
        },
        washi: {
          pink: '#ffb6c1',
          blue: '#a8d4f0',
          yellow: '#ffe4a0',
          green: '#b8e0c0',
        },
        sticky: {
          white: '#ffffff', // Agent 气泡
          cream: '#fff8e1', // 用户气泡（淡黄便利贴）
          blue: '#e8f0ff',
          pink: '#fff0f5',
          green: '#f0fff0',
        },
      },
      fontFamily: {
        hand: ['"Ma Shan Zheng"', '"Caveat"', 'cursive'],
        sans: ['-apple-system', 'BlinkMacSystemFont', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
      },
      borderRadius: {
        'hd-sm': '4px',
        'hd-md': '8px',
        'hd-lg': '12px',
        'hd-xl': '16px',
      },
      borderWidth: {
        'hd-thin': '1px',
        'hd': '2px',
        'hd-thick': '3px',
      },
      boxShadow: {
        'hd-sm': '2px 2px 0 rgba(0,0,0,0.1)',
        'hd': '3px 3px 0 rgba(0,0,0,0.12)',
        'hd-lg': '4px 6px 12px rgba(0,0,0,0.08)',
        'sticky': '2px 3px 8px rgba(0,0,0,0.08)',
        'sticky-hover': '4px 6px 16px rgba(0,0,0,0.12)',
      },
      keyframes: {
        'hand-drawn-in': {
          '0%': { strokeDashoffset: '100%' },
          '100%': { strokeDashoffset: '0' },
        },
        'sticky-bounce': {
          '0%': { transform: 'scale(0.9) rotate(-2deg)', opacity: '0' },
          '60%': { transform: 'scale(1.03) rotate(1deg)', opacity: '1' },
          '100%': { transform: 'scale(1) rotate(-0.5deg)', opacity: '1' },
        },
        'ripple': {
          '0%': { transform: 'scale(0)', opacity: '0.6' },
          '100%': { transform: 'scale(4)', opacity: '0' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-4px)' },
        },
      },
      animation: {
        'sticky-bounce': 'sticky-bounce 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both',
        'ripple': 'ripple 1.2s ease-out infinite',
        'float': 'float 3s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
