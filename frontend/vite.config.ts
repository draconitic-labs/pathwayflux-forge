import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // No CORS: other local pages must not reach /api through the dev or preview server.
  server: {
    port: 5173,
    cors: false,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8741",
        changeOrigin: true,
      },
    },
  },
  preview: {
    cors: false,
  },
});
