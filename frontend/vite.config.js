import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // host:true lets you open the dev site from your phone on the same Wi-Fi
    // (e.g. http://192.168.x.x:5173). Without it Vite only listens on
    // 127.0.0.1 / ::1 and the phone can't connect.
    host: true,
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
