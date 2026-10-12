/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"Noto Sans JP"',
          '"Hiragino Kaku Gothic ProN"',
          '"Meiryo"',
          "sans-serif",
        ],
      },
      colors: {
        manga: {
          50: "#f0f4ff",
          100: "#dce6ff",
          500: "#4f6ef7",
          600: "#3b5bf5",
          700: "#2a47e8",
          900: "#1a2a8a",
        },
      },
    },
  },
  plugins: [],
};
