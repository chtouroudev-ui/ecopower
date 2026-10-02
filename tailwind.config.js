/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#edfcf8',
          100: '#d2f6ec',
          200: '#a8ecd9',
          300: '#71dcbf',
          400: '#3ac2a0',
          500: '#1ea586',
          600: '#14846c',
          700: '#0a6e5c', // Main brand primary
          800: '#0c584b',
          900: '#064d40', // Deep brand dark
          950: '#032a24',
        },
        skywater: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#1ca7ec', // Accent cyan water
          600: '#0284c7',
          700: '#0369a1',
        },
        energy: {
          500: '#ff6b35', // Warm orange for CTA / energy
          600: '#e85a28',
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        arabic: ['Tajawal', 'Inter', 'sans-serif'],
      }
    },
  },
  plugins: [
    require('tailwindcss-animate'),
  ],
}

