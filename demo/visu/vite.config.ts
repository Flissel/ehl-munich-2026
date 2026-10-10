import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built into Torque's dist so Rowboat serves it next to Torque (torque.apps.localhost:3210/visu/).
// data/ and models/ in that folder are written by prepare_local.py and are never committed,
// so the build must not wipe the folder; it only replaces assets/.
const OUT = "../torque/dist/visu";

export default defineConfig(({ command }) => ({
  base: "./",
  plugins: [react()],
  // In dev, serve the locally prepared data/ and models/ straight from the build folder.
  publicDir: command === "serve" ? OUT : false,
  build: { outDir: OUT, emptyOutDir: false, chunkSizeWarningLimit: 2000 },
  server: { host: "127.0.0.1", port: 5174 },
}));
