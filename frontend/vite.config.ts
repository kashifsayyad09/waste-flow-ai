import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Nginx (port 80) is the front door and proxies "/" to this dev server.
// If you open http://localhost:5173 directly, API calls are forwarded to
// Nginx — never straight to FastAPI — so the architecture stays the same.
const NGINX = "http://127.0.0.1";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": NGINX,
      "/health": NGINX,
    },
  },
});
