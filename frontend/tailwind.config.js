/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        nordic: {
          fjord: '#0B1528',         // Deep Arctic Fjord midnight
          fjordSurface: '#132238',  // Fjord surface card/border
          frost: '#F0F4F8',         // Crisp Arctic Snow / Frost base background
          card: '#FFFFFF',
          border: '#E2E8F0',
          dark: '#0F172A',
          slate: '#334155',
          muted: '#64748B',
          glacier: '#0284C7',       // Arctic Glacier Blue
          glacierHover: '#0369A1',
          glacierLight: '#E0F2FE',
          ice: '#BAE6FD',
          pine: '#0D9488',          // Boreal Pine Teal
          pineLight: '#CCFBF1',
          lingonberry: '#BE123C',    // Nordic Lingonberry Crimson
          lingonberryLight: '#FFE4E6',
          cloudberry: '#D97706',     // Nordic Cloudberry Amber
          cloudberryLight: '#FEF3C7',
          aurora: '#4F46E5',         // Northern Aurora Indigo
          auroraLight: '#EEF2FF',
        }
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
