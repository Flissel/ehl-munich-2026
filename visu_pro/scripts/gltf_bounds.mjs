// Prints world-space bounds of each named part in a glTF (read-only asset inspection).
// Usage: node scripts/gltf_bounds.mjs path/to/scene.gltf
import fs from "node:fs";

const g = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const mul = (a, b) => { const r = new Array(16).fill(0); for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) for (let k = 0; k < 4; k++) r[j * 4 + i] += a[k * 4 + i] * b[j * 4 + k]; return r; };
const compose = (n) => {
  if (n.matrix) return n.matrix;
  const [x, y, z, w] = n.rotation || [0, 0, 0, 1]; const [sx, sy, sz] = n.scale || [1, 1, 1]; const [tx, ty, tz] = n.translation || [0, 0, 0];
  return [(1 - 2 * (y * y + z * z)) * sx, 2 * (x * y + z * w) * sx, 2 * (x * z - y * w) * sx, 0,
          2 * (x * y - z * w) * sy, (1 - 2 * (x * x + z * z)) * sy, 2 * (y * z + x * w) * sy, 0,
          2 * (x * z + y * w) * sz, 2 * (y * z - x * w) * sz, (1 - 2 * (x * x + y * y)) * sz, 0, tx, ty, tz, 1];
};
const xf = (m, p) => [0, 1, 2].map(i => m[i] * p[0] + m[4 + i] * p[1] + m[8 + i] * p[2] + m[12 + i]);
const parts = {};
const walk = (idx, parent, part, parentName) => {
  const n = g.nodes[idx]; const m = mul(parent, compose(n));
  const depthPart = part ?? (parentName === "RootNode" ? n.name : undefined);
  if (n.mesh !== undefined) {
    for (const p of g.meshes[n.mesh].primitives) {
      const a = g.accessors[p.attributes.POSITION];
      for (const cx of [a.min[0], a.max[0]]) for (const cy of [a.min[1], a.max[1]]) for (const cz of [a.min[2], a.max[2]]) {
        const w = xf(m, [cx, cy, cz]); const b = (parts[depthPart] ??= { min: [1e9, 1e9, 1e9], max: [-1e9, -1e9, -1e9] });
        for (let i = 0; i < 3; i++) { b.min[i] = Math.min(b.min[i], w[i]); b.max[i] = Math.max(b.max[i], w[i]); }
      }
    }
  }
  const child = Object.assign(m, { __depth: (parent.__depth ?? 0) + 1 });
  for (const c of n.children || []) walk(c, child, depthPart, n.name);
};
const I = Object.assign([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], { __depth: 0 });
for (const r of g.scenes[g.scene ?? 0].nodes) walk(r, I, undefined);
const f = v => v.map(x => x.toFixed(2).padStart(7)).join(" ");
for (const [k, b] of Object.entries(parts)) console.log(k.padEnd(20), "center", f(b.min.map((v, i) => (v + b.max[i]) / 2)), " size", f(b.max.map((v, i) => v - b.min[i])));
