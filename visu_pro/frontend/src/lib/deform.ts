import { Box3, BufferAttribute, InterleavedBufferAttribute, Matrix4, Vector3 } from "three";
import type { CarModel } from "../models/types";
import type { SegmentedMesh } from "./segmentation";
import type { WebDesign } from "./design";

/*
 * Level 2 shape engine: a continuous space deformation applied to every body/interior vertex in
 * world space, so neighbouring panels stay connected (no gaps). Wheels stay rigid and follow the
 * axles. Two kinds of edits:
 *   - body proportions (overhangs, wheelbase, width, fender flares, roof height, ride height)
 *   - soft per-component edits (scale / move): full effect on the component, smoothly fading out
 *     over a falloff distance into the neighbouring panels (like proportional editing in Blender).
 * Geometry topology, UVs and materials are untouched; only vertex positions move.
 */

type PosAttr = BufferAttribute | InterleavedBufferAttribute;

type AttrEntry = {
  attr: PosAttr;
  meshes: SegmentedMesh[];
  baseLocal: Float32Array;
  baseWorld: Float32Array; // in vehicle frame (x left, y up, z forward)
  toLocal: Matrix4; // world -> local
  masks: Map<string, Uint8Array>; // component id -> vertex membership
};

export type DeformEngine = {
  apply: (design: WebDesign) => void;
  wheelPlacement: (design: WebDesign) => Map<string, Matrix4>;
};

/** Original local positions per attribute (survives engine re-creation, e.g. hot reload). */
const BASE = new WeakMap<PosAttr, Float32Array>();

/** World matrix of a mesh at its original pose (wheel matrices are modified later). */
const baseWorldMatrix = (m: SegmentedMesh) => {
  const pw = m.userData.parentWorld as Matrix4 | undefined, bm = m.userData.baseMatrix as Matrix4 | undefined;
  return pw && bm ? pw.clone().multiply(bm) : m.matrixWorld.clone();
};

const smooth = (t: number) => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));
const clamp01 = (t: number) => Math.max(0, Math.min(1, t));

export function createDeformEngine(model: CarModel, all: SegmentedMesh[], byComponent: Map<string, SegmentedMesh[]>): DeformEngine {
  // Vehicle frame <-> world (the asset can be authored along any horizontal axis).
  const fwd = model.frame.forward, left = model.frame.left;
  const axis = (s: string) => (s[1] === "x" ? 0 : 2), sgn = (s: string) => (s[0] === "-" ? -1 : 1);
  const toV = (w: number[], out: number[]) => {
    out[0] = sgn(left) * w[axis(left)]; out[1] = w[1]; out[2] = sgn(fwd) * w[axis(fwd)];
  };
  const fromV = (v: number[], out: number[]) => {
    out[1] = v[1]; out[axis(left)] = sgn(left) * v[0]; out[axis(fwd)] = sgn(fwd) * v[2];
  };

  const wheelIds = new Set(model.components.filter((c) => c.category === "Wheels").map((c) => c.id));
  const isWheelMesh = (m: SegmentedMesh) => !!m.userData.componentId && wheelIds.has(m.userData.componentId);

  // Group deformable meshes by their (shared) position attribute.
  const entries = new Map<PosAttr, AttrEntry>();
  const tmp = new Vector3(), w = [0, 0, 0], v = [0, 0, 0];
  for (const m of all) {
    if (isWheelMesh(m)) continue;
    const attr = m.geometry.getAttribute("position") as PosAttr;
    let e = entries.get(attr);
    if (!e) {
      const n = attr.count;
      let baseLocal = BASE.get(attr);
      if (!baseLocal) {
        baseLocal = new Float32Array(n * 3);
        for (let i = 0; i < n; i++) {
          tmp.fromBufferAttribute(attr, i);
          baseLocal[3 * i] = tmp.x; baseLocal[3 * i + 1] = tmp.y; baseLocal[3 * i + 2] = tmp.z;
        }
        BASE.set(attr, baseLocal);
      }
      const baseWorld = new Float32Array(n * 3), mw = baseWorldMatrix(m);
      for (let i = 0; i < n; i++) {
        tmp.set(baseLocal[3 * i], baseLocal[3 * i + 1], baseLocal[3 * i + 2]).applyMatrix4(mw);
        w[0] = tmp.x; w[1] = tmp.y; w[2] = tmp.z; toV(w, v);
        baseWorld[3 * i] = v[0]; baseWorld[3 * i + 1] = v[1]; baseWorld[3 * i + 2] = v[2];
      }
      e = { attr, meshes: [], baseLocal, baseWorld, toLocal: mw.clone().invert(), masks: new Map() };
      entries.set(attr, e);
    }
    e.meshes.push(m);
    const id = m.userData.componentId;
    if (id) {
      let mask = e.masks.get(id);
      if (!mask) { mask = new Uint8Array(attr.count); e.masks.set(id, mask); }
      const index = m.geometry.index;
      if (index) for (let k = 0; k < index.count; k++) mask[index.getX(k)] = 1;
      else mask.fill(1);
    }
  }

  // Car extents and axle positions in the vehicle frame.
  const ext = { minZ: Infinity, maxZ: -Infinity, maxX: 0, maxY: 0 };
  for (const e of entries.values()) {
    const b = e.baseWorld;
    for (let i = 0; i < b.length; i += 3) {
      ext.minZ = Math.min(ext.minZ, b[i + 2]); ext.maxZ = Math.max(ext.maxZ, b[i + 2]);
      ext.maxX = Math.max(ext.maxX, Math.abs(b[i])); ext.maxY = Math.max(ext.maxY, b[i + 1]);
    }
  }
  const wheelCenters = new Map<string, number[]>();
  const wheelBoxes = new Map<string, Box3>();
  for (const id of wheelIds) {
    const bb = new Box3();
    for (const m of byComponent.get(id) ?? []) bb.union(m.geometry.boundingBox!.clone().applyMatrix4(baseWorldMatrix(m)));
    if (bb.isEmpty()) continue;
    const c = bb.getCenter(new Vector3());
    w[0] = c.x; w[1] = c.y; w[2] = c.z; const cv = [0, 0, 0]; toV(w, cv);
    wheelCenters.set(id, cv);
    wheelBoxes.set(id, bb);
  }
  const zs = [...wheelCenters.values()].map((c) => c[2]);
  const frontAxle = zs.length ? Math.max(...zs) : ext.maxZ * 0.6;
  const rearAxle = zs.length ? Math.min(...zs) : ext.minZ * 0.6;
  const wheelDia = Math.max(...[...wheelBoxes.values()].map((b) => b.getSize(tmp).y), 0.01);
  const beltY = ext.maxY * 0.52;

  // Component boxes (vehicle frame) for soft edits.
  const compBox = new Map<string, { min: number[]; max: number[]; c: number[]; r: number }>();
  for (const [id] of byComponent) {
    if (wheelIds.has(id)) continue;
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    for (const e of entries.values()) {
      const mask = e.masks.get(id); if (!mask) continue;
      const b = e.baseWorld;
      for (let i = 0; i < mask.length; i++) if (mask[i]) for (let a = 0; a < 3; a++) {
        min[a] = Math.min(min[a], b[3 * i + a]); max[a] = Math.max(max[a], b[3 * i + a]);
      }
    }
    if (min[0] === Infinity) continue;
    const size = Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2]);
    compBox.set(id, { min, max, c: min.map((m, a) => (m + max[a]) / 2), r: Math.min(0.45, Math.max(0.15, size * 0.35)) });
  }

  const wheelFactor = (d: WebDesign) => (wheelDia + 0.0254 * d.wheelDeltaInches) / wheelDia;

  /** Global proportion deformation in the vehicle frame (in place). */
  const global = (p: number[], d: WebDesign, lift: number) => {
    const P = d.proportions;
    const x = p[0], y = p[1], z = p[2];
    let nz = z, nx = x, ny = y;
    // wheelbase: stretch between the axles, rigid shift outside
    if (P.wheelbaseCm) nz += (P.wheelbaseCm / 100) * (clamp01((z - rearAxle) / (frontAxle - rearAxle)) - 0.5);
    // overhangs: stretch beyond the axles
    if (P.frontOverhangCm && z > frontAxle) nz += (P.frontOverhangCm / 100) * clamp01((z - frontAxle) / (ext.maxZ - frontAxle));
    if (P.rearOverhangCm && z < rearAxle) nz -= (P.rearOverhangCm / 100) * clamp01((rearAxle - z) / (rearAxle - ext.minZ));
    // body width: outer surfaces move out, centre stays
    const ax = Math.abs(x), side = Math.sign(x) || 1;
    if (P.bodyWidthCm) nx += side * (P.bodyWidthCm / 100) * smooth((ax / ext.maxX - 0.35) / 0.5);
    // fender flares: wide-body arches around each axle, lower body only
    if (P.fenderFlareCm) {
      const arch = Math.max(Math.exp(-(((z - frontAxle) / 0.5) ** 2)), Math.exp(-(((z - rearAxle) / 0.5) ** 2)));
      nx += side * (P.fenderFlareCm / 100) * arch * smooth((ax / ext.maxX - 0.55) / 0.3) * (1 - smooth((y - beltY) / 0.25));
    }
    // roof height: everything above the belt line
    if (P.roofHeightCm) ny += (P.roofHeightCm / 100) * clamp01((y - beltY) / (ext.maxY - beltY));
    ny += d.rideHeightCm / 100 + lift;
    p[0] = nx; p[1] = ny; p[2] = nz;
  };

  /** Soft component edit (in place, before the global deformation). */
  const soft = (p: number[], inside: boolean, box: { min: number[]; max: number[]; c: number[]; r: number },
                s: number[], t: number[]) => {
    let wgt = 1;
    if (!inside) {
      let d2 = 0;
      for (let a = 0; a < 3; a++) {
        const o = p[a] < box.min[a] ? box.min[a] - p[a] : p[a] > box.max[a] ? p[a] - box.max[a] : 0;
        d2 += o * o;
      }
      const dist = Math.sqrt(d2);
      if (dist >= box.r) return;
      wgt = smooth(1 - dist / box.r);
    }
    for (let a = 0; a < 3; a++) p[a] += wgt * ((s[a] - 1) * (p[a] - box.c[a]) + t[a]);
  };

  const apply = (d: WebDesign) => {
    const lift = ((wheelFactor(d) - 1) * wheelDia) / 2;
    const edits: { id: string; box: { min: number[]; max: number[]; c: number[]; r: number }; s: number[]; t: number[] }[] = [];
    for (const [id, box] of compBox) {
      const sc = d.scale[id], mv = d.move[id];
      if (!sc && !mv) continue;
      edits.push({ id, box, s: sc ?? [1, 1, 1], t: mv ? mv.map((c) => c / 100) : [0, 0, 0] });
    }
    const p = [0, 0, 0], out = [0, 0, 0], loc = new Vector3();
    for (const e of entries.values()) {
      const b = e.baseWorld, n = e.attr.count;
      const editMasks = edits.map((ed) => e.masks.get(ed.id));
      const m = e.toLocal.elements;
      for (let i = 0; i < n; i++) {
        p[0] = b[3 * i]; p[1] = b[3 * i + 1]; p[2] = b[3 * i + 2];
        for (let k = 0; k < edits.length; k++) soft(p, !!editMasks[k]?.[i], edits[k].box, edits[k].s, edits[k].t);
        global(p, d, lift);
        fromV(p, out);
        loc.set(
          m[0] * out[0] + m[4] * out[1] + m[8] * out[2] + m[12],
          m[1] * out[0] + m[5] * out[1] + m[9] * out[2] + m[13],
          m[2] * out[0] + m[6] * out[1] + m[10] * out[2] + m[14]);
        e.attr.setXYZ(i, loc.x, loc.y, loc.z);
      }
      if ("needsUpdate" in e.attr) (e.attr as BufferAttribute).needsUpdate = true;
      else (e.attr as InterleavedBufferAttribute).data.needsUpdate = true;
      for (const mesh of e.meshes) { mesh.geometry.computeBoundingBox(); mesh.geometry.computeBoundingSphere(); }
    }
  };

  /** Rigid world-space delta for each wheel: follows the axles, track/width, wheel size, own edits. */
  const wheelPlacement = (d: WebDesign) => {
    const out = new Map<string, Matrix4>();
    const f = wheelFactor(d), lift = ((f - 1) * wheelDia) / 2;
    const P = d.proportions;
    for (const [id, c] of wheelCenters) {
      const front = c[2] > 0, side = Math.sign(c[0]) || 1;
      const dz = (P.wheelbaseCm / 100) * (front ? 0.5 : -0.5);
      const dx = side * (d.trackWidthCm + P.bodyWidthCm + 0.8 * P.fenderFlareCm) / 100;
      const mv = d.move[id] ?? [0, 0, 0], sc = d.scale[id] ?? [1, 1, 1];
      const tv = [dx + mv[0] / 100, lift + mv[1] / 100, dz + mv[2] / 100], tw = [0, 0, 0];
      fromV(tv, tw);
      const cw = [0, 0, 0]; fromV(c, cw);
      const sv = [sc[0] * f, sc[1] * f, sc[2] * f], sw = [0, 0, 0];
      sw[1] = sv[1]; sw[axis(left)] = sv[0]; sw[axis(fwd)] = sv[2];
      const mtx = new Matrix4().makeTranslation(tw[0], tw[1], tw[2])
        .multiply(new Matrix4().makeTranslation(cw[0], cw[1], cw[2]))
        .multiply(new Matrix4().makeScale(sw[0], sw[1], sw[2]))
        .multiply(new Matrix4().makeTranslation(-cw[0], -cw[1], -cw[2]));
      out.set(id, mtx);
    }
    return out;
  };

  return { apply, wheelPlacement };
}
