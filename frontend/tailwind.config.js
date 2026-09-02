/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Outfit', 'Inter', 'ui-sans-serif', 'system-ui'],
      },
      colors: {
        upsc: {
          navy: '#2B3990',
          gold: '#B89456',
          maroon: '#8B0000',
          dark: '#F1F5F9',
          card: '#FFFFFF',
          main: '#FFFFFF',
        },
        text: {
          main: '#0F172A',
          muted: '#64748B',
        }
      }
    },
  },
  plugins: [],
}

