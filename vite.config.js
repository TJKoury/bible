import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { studyAssets } from "./scripts/vite-assets.js";

export default defineConfig({
  base: process.env.BASE_PATH || '/',
  plugins: [svelte(), studyAssets()],
  server: { strictPort: true },
  worker: { format: "es" },
});
