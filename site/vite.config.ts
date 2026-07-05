import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// base must match the GitHub Pages sub-path (sutheimernico.github.io/match-scout/).
export default defineConfig({
  base: "/match-scout/",
  plugins: [react()],
});
