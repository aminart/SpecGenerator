import typography from "@tailwindcss/typography";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Roboto", "Arial", "sans-serif"],
      },
      colors: {
        navy: { DEFAULT: "#0F1D96", dark: "#0A1470", soft: "#EEF0FB", softer: "#F7F8FE", muted: "#5C66B8" },
        ink: { DEFAULT: "#1B1D2A", body: "#2B2E3E", muted: "#4A4E61", subtle: "#5A5F73" },
        line: { DEFAULT: "#E2E4EC", strong: "#D5D8E3", dashed: "#A9AFC4" },
        ground: "#F5F6F9",
        success: { DEFAULT: "#1E8A52", text: "#17663F", soft: "#E9F6EF" },
      },
    },
  },
  plugins: [typography],
};
