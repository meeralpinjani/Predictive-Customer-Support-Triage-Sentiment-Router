import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API is proxied under /api so the session cookie is same-origin (no CORS, HttpOnly cookie works).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: process.env.VITE_API_PROXY || "http://localhost:8000", changeOrigin: true },
    },
  },
  preview: {
    port: 5173,
    proxy: {
      "/api": { target: process.env.VITE_API_PROXY || "http://localhost:8000", changeOrigin: true },
    },
  },
});
