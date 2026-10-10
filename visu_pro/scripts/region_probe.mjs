// Prints a histogram of a node's triangle centroids in the normalized vehicle frame, to tune
// spatial component regions. Usage: node scripts/region_probe.mjs scene.gltf Driver_Door Material_692
import fs from "node:fs";
import path from "node:path";

const [file, nodeName, matName] = process.argv.slice(2);
const g = JSON.parse(fs.readFileSync(file, "utf8"));
const bin = fs.readFileSync(path.join(path.dirname(file), g.buffers[0].uri));
const read = (acc) => {
  const a = g.accessors[acc], v = g.bufferViews[a.bufferView];
  const comps = { SCALAR: 1, VEC3: 3 }[a.type], off = (v.byteOffset || 0) + (a.byteOffset || 0);
  const T = { 5126: Float32Array, 5125: Uint32Array, 5123: Uint16Array }[a.componentType];
  const stride = v.byteStride ? v.byteStride / T.BYTES_PER_ELEMENT : comps;
  const arr = new T(bin.buffer, bin.byteOffset + off, (a.count - 1) * stride + comps);
  return { get: (i, c = 0) => arr[i * stride + c], count: a.count };
};
const mul = (a, b) => { const r = new Array(16).fill(0); for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) for (let k = 0; k < 4; k++) r[j * 4 + i] += a[k * 4 + i] * b[j * 4 + k]; return r; };
const compose = (n) => {
  if (n.matrix) return n.matrix;
  const [x, y, z, w] = n.rotation || [0, 0, 0, 1]; const [sx, sy, sz] = n.scale || [1, 1, 1]; const [tx, ty, tz] = n.translation || [0, 0, 0];
  return [(1 - 2 * (y * y + z * z)) * sx, 2 * (x * y + z * w) * sx, 2 * (x * z - y * w) * sx, 0, 2 * (x * y - z * w) * sy, (1 - 2 * (x * x + z * z)) * sy, 2 * (y * z + x * w) * sy, 0, 2 * (x * z + y * w) * sz, 2 * (y * z - x * w) * sz, (1 - 2 * (x * x + y * y)) * sz, 0, tx, ty, tz, 1];
};
const xf = (m, p) => [0, 1, 2].map(i => m[i] * p[0] + m[4 + i] * p[1] + m[8 + i] * p[2] + m[12 + i]);
// car bounds (from scripts/gltf_bounds.mjs RootNode): center (-0.02, 0.97, 0.02) size (2.94, 1.94, 6.60)
const C = [-0.02, 0.97, 0.02], H = [1.47, 1.94, 3.30], minY = 0;
const tris = [];
const walk = (idx, parent, inside) => {
  const n = g.nodes[idx], m = mul(parent, compose(n)), here = inside || n.name === nodeName;
  if (here && n.mesh !== undefined) for (const p of g.meshes[n.mesh].primitives) {
    if (matName && g.materials[p.material]?.name !== matName) continue;
    const pos = read(p.attributes.POSITION), ind = read(p.indices);
    for (let t = 0; t < ind.count; t += 3) {
      const c = [0, 0, 0];
      for (let k = 0; k < 3; k++) { const v = xf(m, [0, 1, 2].map(j => pos.get(ind.get(t + k), j))); c[0] += v[0] / 3; c[1] += v[1] / 3; c[2] += v[2] / 3; }
      tris.push([(c[0] - C[0]) / H[0], (c[1] - minY) / H[1], (c[2] - C[2]) / H[2]]);
    }
  }
  for (const ch of n.children || []) walk(ch, m, here);
};
const I = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
for (const r of g.scenes[g.scene ?? 0].nodes) walk(r, I, false);
console.log(`${tris.length} triangles`);
const outer = tris.filter(t => Math.abs(t[0]) > 0.86);
const b = (v) => (Math.floor(v * 20) / 20).toFixed(2);
const hist = {};
for (const t of outer) { const k = `absX>=${b(Math.abs(t[0]))} y=${b(t[1])} z=${b(t[2])}`; hist[k] = (hist[k] || 0) + 1; }
for (const [k, v] of Object.entries(hist).sort()) console.log(k, v);
