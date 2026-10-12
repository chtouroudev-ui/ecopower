/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./resources/views/**/*.blade.php",
    "./resources/js/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb', // Pure Modern Blue
          700: '#1d4ed8', // Rich Royal Blue
          800: '#1e40af', // Deep Navy Blue
          900: '#1e3a8a',
          950: '#0f172a',
        },
        skywater: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0284c7', // Azure Water Blue
          600: '#0369a1',
          700: '#075985',
          800: '#0c4a6e',
          900: '#082f49',
        },
        energy: {
          500: '#0284c7', // Clean Blue accent
          600: '#0369a1',
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
