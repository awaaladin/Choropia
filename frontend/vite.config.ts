import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In dev the SPA runs on :5173 and proxies the API (and WebSockets) to the Django server on
// :8000, so the browser still sees one origin — same as production, where Django/Vercel serves both.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8010",
      "/media": "http://localhost:8010",
      "/ws": { target: "ws://localhost:8010", ws: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
