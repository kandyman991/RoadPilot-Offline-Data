import { defineConfig } from "vite";

export default defineConfig({
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
  },
  envPrefix: ["VITE_", "TAURI_"],
  build: {
    target: ["es2022", "chrome120", "safari14"],
    minify: process.env.TAURI_DEBUG ? false : "esbuild",
    sourcemap: !!process.env.TAURI_DEBUG,
  },
});
