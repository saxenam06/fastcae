import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // 5173 is taken by the previous project's dev server on this machine.
    port: 5183,
    strictPort: true,
    // The API is a separate process on 8000. Proxying rather than calling it cross-origin keeps
    // the browser on one origin, which matters for the binary mesh fetch.
    proxy: { "/api": { target: "http://127.0.0.1:8021", changeOrigin: true } },
  },
});
