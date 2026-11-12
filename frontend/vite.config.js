import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development (npm run dev) /api is forwarded to the backend: no CORS and no absolute URLs.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": process.env.VITE_PROXY_TARGET || "http://localhost:8000" },
  },
});
