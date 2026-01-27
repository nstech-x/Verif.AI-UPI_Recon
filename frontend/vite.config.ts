import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(), // standard React plugin for TS + JSX/TSX
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"), // REQUIRED for shadcn imports
    },
  },
  server: {
    port: 5173,
  },
});
