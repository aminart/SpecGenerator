import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8010", "/health": "http://127.0.0.1:8010" },
    // src/lib/version.ts lit le fichier VERSION de specGen-main, un niveau au-dessus du frontend.
    fs: { allow: [".."] },
  },
});
