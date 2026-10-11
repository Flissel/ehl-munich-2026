import { Box3, BufferAttribute, BufferGeometry, Material, Mesh, Object3D, Vector3 } from "three";
import type { CarComponent, CarModel, ComponentPart, Region } from "../models/types";

export type SegmentedMesh = Mesh & {
  userData: { componentId: string | null; originalMaterial: Material; gltfMaterialName: string };
};

export type SegmentationReport = {
  /** component id -> number of meshes/triangles assigned */
  components: Record<string, { meshes: number; triangles: number }>;
  /** components whose node names were not found or got no triangles */
  unmapped: string[];
  missingNodes: string[];
  unscoredMeshes: number;
};

export type SegmentationResult = {
  byComponent: Map<string, SegmentedMesh[]>;
  others: SegmentedMesh[];
  report: SegmentationReport;
};

/** GLTFLoader keeps the original glTF name in userData.name and sanitizes object.name. */
const gltfName = (o: Object3D): string => (o.userData?.name as string | undefined) ?? o.name;
const sanitize = (s: string) => s.replace(/\s/g, "_").replace(/[[\].:/]/g, "");

function inRange(v: number, r?: [number, number]) {
  return !r || (v >= r[0] && v <= r[1]);
}

function inRegion(n: Vector3, r?: Region) {
  return !r || (inRange(n.x, r.x) && inRange(Math.abs(n.x), r.absX) && inRange(n.y, r.y) && inRange(n.z, r.z));
}

/** Maps a world-space point to the normalized vehicle frame (x: right -1..left +1, y: 0..1, z: rear -1..front +1). */
function makeNormalizer(model: CarModel, box: Box3) {
  const c = box.getCenter(new Vector3());
  const size = box.getSize(new Vector3());
  const axis = (spec: string, p: Vector3) => {
    const sign = spec[0] === "-" ? -1 : 1;
    const key = spec[1] as "x" | "z";
    return (sign * (p[key] - c[key])) / (size[key] / 2);
  };
  return (p: Vector3, out: Vector3) =>
    out.set(axis(model.frame.left, p), (p.y - box.min.y) / size.y, axis(model.frame.forward, p));
}

/**
 * Splits the loaded glTF scene into per-component meshes. Must run once, after the scene has been
 * scaled/positioned. Geometry attributes (positions, normals, UVs) are shared, only new index
 * buffers are created, so the original geometry is preserved.
 */
export function segmentModel(root: Object3D, model: CarModel): SegmentationResult {
  root.updateMatrixWorld(true);
  const box = new Box3().setFromObject(root);
  const normalize = makeNormalizer(model, box);

  // node name -> objects (exact glTF name, with sanitized fallback)
  const byName = new Map<string, Object3D[]>();
  root.traverse((o) => {
    for (const key of new Set([gltfName(o), o.name])) {
      if (!byName.has(key)) byName.set(key, []);
      byName.get(key)!.push(o);
    }
  });
  const findNodes = (name: string) => byName.get(name) ?? byName.get(sanitize(name)) ?? [];

  const missingNodes = new Set<string>();
  // mesh -> ordered candidate (component, part) pairs
  const candidates = new Map<Mesh, { comp: CarComponent; part: ComponentPart }[]>();
  for (const comp of model.components) {
    for (const part of comp.parts) {
      const nodes = findNodes(part.node);
      if (!nodes.length) missingNodes.add(part.node);
      for (const node of nodes) {
        node.traverse((o) => {
          const mesh = o as Mesh;
          if (!mesh.isMesh) return;
          const matName = (mesh.material as Material).name;
          if (part.materials && !part.materials.includes(matName)) return;
          if (!candidates.has(mesh)) candidates.set(mesh, []);
          candidates.get(mesh)!.push({ comp, part });
        });
      }
    }
  }

  const meshes: Mesh[] = [];
  root.traverse((o) => { if ((o as Mesh).isMesh) meshes.push(o as Mesh); });

  const byComponent = new Map<string, SegmentedMesh[]>();
  const others: SegmentedMesh[] = [];
  const stats: Record<string, { meshes: number; triangles: number }> = {};
  const tag = (m: Mesh, componentId: string | null, original: Material) => {
    const sm = m as SegmentedMesh;
    sm.userData.componentId = componentId;
    sm.userData.originalMaterial = original;
    sm.userData.gltfMaterialName = original.name;
    sm.castShadow = true;
    if (componentId) {
      if (!byComponent.has(componentId)) byComponent.set(componentId, []);
      byComponent.get(componentId)!.push(sm);
    } else {
      others.push(sm);
    }
    return sm;
  };

  const a = new Vector3(), b = new Vector3(), c = new Vector3(), n = new Vector3();
  for (const mesh of meshes) {
    const original = mesh.material as Material;
    const cands = candidates.get(mesh) ?? [];
    if (!cands.length) { tag(mesh, null, original); continue; }
    if (!cands[0].part.region) {
      tag(mesh, cands[0].comp.id, original);
      const t = triangleCount(mesh.geometry);
      stats[cands[0].comp.id] = add(stats[cands[0].comp.id], 1, t);
      continue;
    }

    // Per-triangle assignment by region (first matching candidate wins).
    const geo = mesh.geometry;
    const pos = geo.getAttribute("position");
    const index = geo.index;
    const triCount = triangleCount(geo);
    const buckets = new Map<string | null, number[]>();
    const vi = (k: number) => (index ? index.getX(k) : k);
    for (let t = 0; t < triCount; t++) {
      const i0 = vi(3 * t), i1 = vi(3 * t + 1), i2 = vi(3 * t + 2);
      a.fromBufferAttribute(pos, i0); b.fromBufferAttribute(pos, i1); c.fromBufferAttribute(pos, i2);
      a.add(b).add(c).divideScalar(3).applyMatrix4(mesh.matrixWorld);
      normalize(a, n);
      const hit = cands.find((cand) => inRegion(n, cand.part.region));
      const id = hit ? hit.comp.id : null;
      if (!buckets.has(id)) buckets.set(id, []);
      buckets.get(id)!.push(i0, i1, i2);
    }

    const parent = mesh.parent!;
    for (const [id, idx] of buckets) {
      const g = new BufferGeometry();
      for (const [name, attr] of Object.entries(geo.attributes)) g.setAttribute(name, attr);
      g.setIndex(new BufferAttribute(pos.count > 65535 ? new Uint32Array(idx) : new Uint16Array(idx), 1));
      g.computeBoundingBox();
      g.computeBoundingSphere();
      const piece = new Mesh(g, original);
      piece.name = `${mesh.name}__${id ?? "unassigned"}`;
      piece.position.copy(mesh.position);
      piece.quaternion.copy(mesh.quaternion);
      piece.scale.copy(mesh.scale);
      parent.add(piece);
      tag(piece, id, original);
      if (id) stats[id] = add(stats[id], 1, idx.length / 3);
    }
    parent.remove(mesh);
  }

  const unmapped = model.components.filter((cmp) => !stats[cmp.id]).map((cmp) => cmp.id);
  return {
    byComponent,
    others,
    report: { components: stats, unmapped, missingNodes: [...missingNodes], unscoredMeshes: others.length },
  };
}

function triangleCount(g: BufferGeometry) {
  return (g.index ? g.index.count : g.getAttribute("position").count) / 3;
}

function add(s: { meshes: number; triangles: number } | undefined, meshes: number, triangles: number) {
  return { meshes: (s?.meshes ?? 0) + meshes, triangles: (s?.triangles ?? 0) + triangles };
}
