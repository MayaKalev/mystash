import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Inside Docker, the computer's file changes don't always reach the container, so
    // docker-compose.yml turns on checking the files regularly instead.
    watch: { usePolling: process.env.VITE_POLLING === "true" },
  },
});
