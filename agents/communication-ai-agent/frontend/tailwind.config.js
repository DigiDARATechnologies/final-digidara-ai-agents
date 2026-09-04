/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f5ff",
          100: "#e0ebff",
          200: "#c2d6ff",
          300: "#94b8ff",
          400: "#5f8fff",
          500: "#6879f4",
          600: "#536dfe",
          700: "#4355d8",
          800: "#1f318a",
          900: "#1e2c6e",
        },
        coach: {
          bg: "#f7f8fc",
          surface: "#ffffff",
          soft: "#f8fafc",
          border: "#e4e8f2",
          text: "#172033",
          muted: "#667085",
          info: "#0284c7",
          success: "#059669",
          warning: "#b45309",
          error: "#dc2626",
        },
      },
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
      },
      boxShadow: {
        soft: "0 2px 5px rgba(30,41,59,.035), 0 18px 45px rgba(30,41,59,.075)",
        lift: "0 18px 42px rgba(79,70,229,.11)",
      },
    },
  },
  plugins: [],
};
