/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'media',
  theme: {
    extend: {
      colors: {
        bg: '#0A0A0B',
        panel: '#131316',
        panelAlt: '#1C1E21',
        borderc: 'rgba(255,255,255,0.08)',
        textsub: '#9C9CA0',
        textmute: '#6A6A6E',
        orange: '#FF6B35',
        teal: '#8AD3D8',
        tealdark: '#33474A',
        redc: '#EF5A5A',
      },
    },
  },
  plugins: [],
}
