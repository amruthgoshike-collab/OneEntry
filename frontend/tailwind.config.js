/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#1E2A2E',
        'ink-muted': '#6B7A80',
        paper: '#FCFBF8',
        rule: '#E5E2DA',
        carbon: '#DCE8F0',
        ledger: '#DEE9DF',
        duplicate: '#F5DFE1',
        manila: '#F1E5CE',
        action: '#2C6E68',
        'action-hover': '#245854',
      },
      fontFamily: {
        sans: ['Hanken Grotesk', 'system-ui', 'sans-serif'],
        raw: ['IBM Plex Sans', 'sans-serif'],
        num: ['IBM Plex Mono', 'monospace'],
      },
      borderRadius: { DEFAULT: '4px' },
    },
  },
}
