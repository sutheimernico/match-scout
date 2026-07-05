import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Production build uses the GitHub Pages sub-path; the dev/preview server serves at root so
// local viewing is just http://localhost:5173/ (no sub-path footgun).
export default defineConfig(({ command }) => ({
  base: command === "build" ? "/match-scout/" : "/",
  plugins: [react()],
  server: { host: true },
  preview: { host: true },
}));
