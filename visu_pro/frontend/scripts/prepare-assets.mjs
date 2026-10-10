// Copies the extracted glTF (scene.gltf + scene.bin + textures/) into public/models/<modelId>/
// so Vite can serve it with its relative paths intact. Extracts from assets/source/*.zip if needed.
// The original ZIP files are only read, never modified.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const MODELS = [
  { id: "bmw-m4-competition-2021", zip: "2021_bmw_m4_competitionglTF.zip", extracted: "bmw-m4-competition-2021-gltf" },
];

for (const m of MODELS) {
  const extracted = path.join(root, "assets", "extracted", m.extracted);
  if (!fs.existsSync(path.join(extracted, "scene.gltf"))) {
    const zip = [path.join(root, "assets", "source", m.zip), path.join(root, m.zip)].find(fs.existsSync);
    if (!zip) { console.error(`[assets] ${m.zip} not found; cannot prepare ${m.id}`); process.exit(1); }
    fs.mkdirSync(extracted, { recursive: true });
    execFileSync("powershell", ["-NoProfile", "-Command",
      `Expand-Archive -LiteralPath '${zip}' -DestinationPath '${extracted}' -Force`], { stdio: "inherit" });
  }
  const dest = path.join(root, "frontend", "public", "models", m.id);
  const marker = path.join(dest, "scene.gltf");
  if (fs.existsSync(marker) && fs.statSync(marker).mtimeMs >= fs.statSync(path.join(extracted, "scene.gltf")).mtimeMs) {
    console.log(`[assets] ${m.id} up to date`);
    continue;
  }
  fs.mkdirSync(dest, { recursive: true });
  fs.cpSync(extracted, dest, { recursive: true });
  console.log(`[assets] copied ${m.id} -> ${path.relative(root, dest)}`);
}
