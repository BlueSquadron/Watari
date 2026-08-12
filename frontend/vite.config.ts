import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// Inside Docker Compose the API is reachable as `api`; when running Vite on the
// host directly it's on `localhost`. Allow either by honouring VITE_API_TARGET.
const apiTarget = process.env.VITE_API_TARGET ?? "http://localhost:8000";
const wsTarget = apiTarget.replace(/^http/, "ws");

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
      "/ws": {
        target: wsTarget,
        ws: true,
      },
    },
  },
});
