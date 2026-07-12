/** Tailwind build config — compiles web/templates classes to static CSS. */
module.exports = {
  content: ["./web/templates/**/*.html"],
  theme: {
    extend: {
      colors: {
        primary: "#1f2937", primaryDark: "#111827", secondary: "#112231",
        gradient: "#112231", accent: "#10b981",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        heading: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
