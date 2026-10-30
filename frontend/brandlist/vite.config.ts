import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Built assets are served by Django from STATIC_URL + "brandlist/" (services/main/pages/vite.py).
// `base` must match, so URLs Vite writes into JS/CSS (chunk imports, url()) resolve.
const STATIC_BASE = "/static/brandlist/";

export default defineConfig(({ command }) => ({
  plugins: [react()],
  // The dev server serves from its own root; only the production build uses the static prefix.
  base: command === "build" ? STATIC_BASE : "/",
  build: {
    // Mirrors the image's /opt/frontend-dist layout (design §7): ../build/brandlist/.
    outDir: "../build/brandlist",
    emptyOutDir: true,
    manifest: true, // → ../build/brandlist/.vite/manifest.json, read by the vite_asset tag
    rollupOptions: {
      // No index.html: Django renders the page and the vite_asset tag injects this entry.
      input: "src/main.tsx",
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    // Same-origin API in dev, no CORS (Req 9.4).
    proxy: { "/api": "http://localhost:8000" },
  },
}));
