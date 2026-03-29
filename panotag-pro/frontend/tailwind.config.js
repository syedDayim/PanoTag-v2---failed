/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        pano: {
          bg: "#0d0f14",
          panel: "#151820",
          accent: "#00e5ff",
          muted: "#6b7590",
        },
      },
    },
  },
  plugins: [],
};
