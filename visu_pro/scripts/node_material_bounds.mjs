// Prints, per node and material, the bounds of the geometry in the normalized vehicle frame
// (x: right -1..left +1, y: 0..1, z: rear -1..front +1). Used to define interior component regions.
// Usage: node scripts/node_material_bounds.mjs scene.gltf Dashboard seats ...
import fs from "node:fs";

const [file, ...wanted] = process.argv.slice(2);
const g = JSON.parse(fs.readFileSync(file, "utf8"));
const mul = (a, b) => { const r = new Array(16).fill(0); for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) for (let k = 0; k < 4; k++) r[j * 4 + i] += a[k * 4 + i] * b[j * 4 + k]; return r; };
const compose = (n) => {
  if (n.matrix) return n.matrix;
  const [x, y, z, w] = n.rotation || [0, 0, 0, 1]; const [sx, sy, sz] = n.scale || [1, 1, 1]; const [tx, ty, tz] = n.translation || [0, 0, 0];
  return [(1 - 2 * (y * y + z * z)) * sx, 2 * (x * y + z * w) * sx, 2 * (x * z - y * w) * sx, 0, 2 * (x * y - z * w) * sy, (1 - 2 * (x * x + z * z)) * sy, 2 * (y * z + x * w) * sy, 0, 2 * (x * z + y * w) * sz, 2 * (y * z - x * w) * sz, (1 - 2 * (x * x + y * y)) * sz, 0, tx, ty, tz, 1];
};
const xf = (m, p) => [0, 1, 2].map(i => m[i] * p[0] + m[4 + i] * p[1] + m[8 + i] * p[2] + m[12 + i]);
const C = [-0.02, 0.97, 0.02], H = [1.47, 1.94, 3.30];
const norm = (p) => [(p[0] - C[0]) / H[0], p[1] / H[1], (p[2] - C[2]) / H[2]];
const walk = (idx, parent, owner) => {
  const n = g.nodes[idx], m = mul(parent, compose(n));
  const own = owner ?? (wanted.includes(n.name) ? n.name : undefined);
  if (own && n.mesh !== undefined) for (const p of g.meshes[n.mesh].primitives) {
    const a = g.accessors[p.attributes.POSITION];
    const lo = [9, 9, 9], hi = [-9, -9, -9];
    for (const cx of [a.min[0], a.max[0]]) for (const cy of [a.min[1], a.max[1]]) for (const cz of [a.min[2], a.max[2]]) {
      const v = norm(xf(m, [cx, cy, cz]));
      for (let i = 0; i < 3; i++) { lo[i] = Math.min(lo[i], v[i]); hi[i] = Math.max(hi[i], v[i]); }
    }
    const f = (i) => `${lo[i].toFixed(2)}..${hi[i].toFixed(2)}`;
    console.log(own.padEnd(18), (g.materials[p.material]?.name ?? "").padEnd(14), "x", f(0).padEnd(12), "y", f(1).padEnd(11), "z", f(2));
  }
  for (const c of n.children || []) walk(c, m, own);
};
const I = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
for (const r of g.scenes[g.scene ?? 0].nodes) walk(r, I, undefined);
