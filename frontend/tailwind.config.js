/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      // Semantic Nordic tokens; values live in src/index.css (light + dark).
      colors: {
        canvas: v("canvas"),
        card: v("card"),
        sunken: v("sunken"),
        line: v("line"),
        ink: { DEFAULT: v("ink"), 2: v("ink-2"), 3: v("ink-3") },
        fjord: { DEFAULT: "#0B1528", surface: "#132238" },
        glacier: { DEFAULT: v("glacier"), soft: v("glacier-soft"), text: v("glacier-text") },
        senior: { DEFAULT: v("senior"), soft: v("senior-soft"), text: v("senior-text") },
        tier2: { DEFAULT: v("tier2"), soft: v("tier2-soft"), text: v("tier2-text") },
        tier1: { DEFAULT: v("tier1"), soft: v("tier1-soft"), text: v("tier1-text") },
        auto: { DEFAULT: v("auto"), soft: v("auto-soft"), text: v("auto-text") },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        "toast-in": { from: { opacity: 0, transform: "translateY(-6px)" }, to: { opacity: 1, transform: "none" } },
      },
      animation: {
        shimmer: "shimmer 1.4s infinite",
        "toast-in": "toast-in .18s ease-out",
      },
    },
  },
  plugins: [],
};
