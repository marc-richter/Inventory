/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        drk: {
          red: "#e2001a",
          dark: "#a50014",
        },
      },
    },
  },
  plugins: [],
}
