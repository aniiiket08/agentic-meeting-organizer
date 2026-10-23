import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Local dev proxies to the backend on the same host. In Docker Compose the
// backend is a separate service, so VITE_PROXY_TARGET is set to its hostname.
const apiProxyTarget = process.env.VITE_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  envDir: path.resolve(__dirname, ".."),
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
