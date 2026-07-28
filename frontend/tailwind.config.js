/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        drk: {
          red: "#e2001a",
          dark: "#a50014",
        },
        // Semantische, theme-abhaengige Farben (Werte kommen aus CSS-Variablen in
        // index.css und wechseln zwischen Light- und Dark-Mode).
        surface: "rgb(var(--surface) / <alpha-value>)",
        base: "rgb(var(--base) / <alpha-value>)",
        ink: "rgb(var(--ink) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",
      },
    },
  },
  plugins: [],
}
