import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// LOCAL DEVELOPMENT ONLY. `npm run dev` forwards /api and /health to FastAPI.
// Production never uses this proxy: `npm run build` emits static files and the
// frontend Nginx forwards /api/ and /health to the backend EC2 (see deploy/).
// Override the target for one shell session if needed, e.g.
//   DEV_API_TARGET=http://127.0.0.1:9000 npm run dev
const target = process.env.DEV_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": target,
      "/health": target,
    },
  },
  test: { environment: "jsdom", include: ["src/**/*.test.{ts,tsx}"], setupFiles: ["src/__tests__/setup.ts"] },
});
