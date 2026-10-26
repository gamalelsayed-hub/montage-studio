import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// وقت التطوير: الواجهة على 5173 وبتكلم السيرفر على 8765
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/files": "http://127.0.0.1:8765",
      "/fonts": "http://127.0.0.1:8765",
    },
  },
});
