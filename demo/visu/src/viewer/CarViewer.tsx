import { Component, Suspense, useEffect, useLayoutEffect, useMemo, useRef, type ReactNode } from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { ContactShadows, Environment, Lightformer, OrbitControls, useGLTF, useProgress } from "@react-three/drei";
import {
  Box3, Color, DoubleSide, Material, Matrix4, Mesh, MeshBasicMaterial, MeshPhysicalMaterial, MeshStandardMaterial,
  Object3D, PerspectiveCamera, Sphere, Vector3,
} from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { CarModel } from "../models/types";
import { scoreToColor } from "../lib/heatmap";
import { FINISH_PARAMS, type ColorSpec, type WebDesign } from "../lib/design";
import { segmentModel, type SegmentationReport, type SegmentationResult, type SegmentedMesh } from "../lib/segmentation";
import { createDeformEngine } from "../lib/deform";

export type ViewMode = "heatmap" | "design";
export type CameraView = "exterior" | "interior" | "cutaway";

type Props = {
  model: CarModel;
  scores: Record<string, number>;
  mode: ViewMode;
  design: WebDesign;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onLoaded: (report: SegmentationReport) => void;
  onError: (message: string) => void;
  resetSignal: number;
  view: CameraView;
  /** Frames this component (e.g. a purchase driver picked in Torque); re-applied when focusSignal changes. */
  focusId?: string | null;
  focusSignal?: number;
};

export function CarViewer(props: Props) {
  return (
    <Canvas shadows="percentage" dpr={[1, 1.75]} camera={{ fov: 35, near: 0.1, far: 200, position: [6, 2.2, 7] }}
      gl={{ antialias: true }}>
      <color attach="background" args={["#0d0f13"]} />
      <fog attach="fog" args={["#0d0f13", 18, 40]} />
      <hemisphereLight args={["#dfe6ff", "#1a1c22", 0.6]} />
      <directionalLight position={[5, 8, 4]} intensity={1.6} castShadow shadow-mapSize={[1024, 1024]} />
      <directionalLight position={[-6, 4, -5]} intensity={0.6} />
      <Environment resolution={256} frames={1}>
        {/* Procedural studio light panels: no network download needed */}
        <Lightformer form="rect" intensity={3} position={[0, 6, 0]} rotation-x={Math.PI / 2} scale={[12, 4, 1]} />
        <Lightformer form="rect" intensity={1.5} position={[-6, 2, 0]} rotation-y={Math.PI / 2} scale={[10, 2, 1]} />
        <Lightformer form="rect" intensity={1.5} position={[6, 2, 0]} rotation-y={-Math.PI / 2} scale={[10, 2, 1]} />
        <Lightformer form="ring" intensity={1} position={[0, 3, 8]} scale={4} />
      </Environment>
      <mesh rotation-x={-Math.PI / 2} position={[0, -0.002, 0]} receiveShadow>
        <circleGeometry args={[9, 64]} />
        <meshStandardMaterial color="#15181e" roughness={0.85} />
      </mesh>
      <ContactShadows position={[0, 0, 0]} opacity={0.65} scale={12} blur={2.4} far={2} resolution={512} />
      <LoadErrorBoundary onError={props.onError}>
        <Suspense fallback={null}>
          <Car {...props} />
        </Suspense>
      </LoadErrorBoundary>
    </Canvas>
  );
}

/** DOM overlay (outside the canvas) showing glTF download progress. */
export function LoadingOverlay() {
  const { progress, active } = useProgress();
  if (!active && progress >= 100) return null;
  return <div className="viewer-loading overlay"><div className="spinner" />Loading BMW model… {progress.toFixed(0)}%</div>;
}

class LoadErrorBoundary extends Component<{ onError: (m: string) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    this.props.onError(`The 3D model could not be loaded: ${msg}. Run "npm run prepare-assets" in frontend/ ` +
      `to copy the glTF from assets/extracted/ into public/models/.`);
  }
  render() { return this.state.failed ? null : this.props.children; }
}

const NEUTRAL = new MeshStandardMaterial({ color: "#3a3f48", roughness: 0.8, metalness: 0.05 });
const HIGHLIGHT = new MeshBasicMaterial({ color: "#ffffff", transparent: true, opacity: 0.32, depthWrite: false,
  polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2, side: DoubleSide });

type Prepared = SegmentationResult & {
  root: Object3D;
  sphere: Sphere;
  all: SegmentedMesh[];
  /** world-space pivot (bbox center at the original pose) and size per component */
  pivots: Map<string, { center: Vector3; size: Vector3 }>;
};

function paramsFor(spec: ColorSpec, transparent: boolean) {
  const f = FINISH_PARAMS[spec.finish];
  return { color: new Color(spec.hex), metalness: f.metalness, roughness: f.roughness, clearcoat: f.clearcoat,
    transparent, opacity: transparent ? 0.5 : 1, depthWrite: !transparent, ...(transparent ? { side: DoubleSide } : {}) };
}

function Car({ model, scores, mode, design, selectedId, onSelect, onLoaded, resetSignal, view, focusId, focusSignal }: Props) {
  const gltf = useGLTF(model.url);

  // Normalize scale/position once, segment into per-component meshes and record the base pose.
  const prep: Prepared = useMemo(() => {
    const root = gltf.scene;
    if (!root.userData.__segmented) {
      const box = new Box3().setFromObject(root);
      const size = box.getSize(new Vector3());
      const lengthAxis = model.frame.forward.endsWith("z") ? size.z : size.x;
      root.scale.multiplyScalar(model.lengthMeters / lengthAxis);
      root.updateMatrixWorld(true);
      const b2 = new Box3().setFromObject(root);
      const c = b2.getCenter(new Vector3());
      root.position.sub(new Vector3(c.x, b2.min.y, c.z));
      root.updateMatrixWorld(true);
      const seg = segmentModel(root, model);
      root.updateMatrixWorld(true);
      const all = [...seg.others, ...[...seg.byComponent.values()].flat()];
      for (const m of all) {
        m.userData.baseMatrix = m.matrix.clone();
        m.userData.parentWorld = m.parent!.matrixWorld.clone();
        m.matrixAutoUpdate = false;
      }
      const pivots = new Map<string, { center: Vector3; size: Vector3 }>();
      for (const [id, meshes] of seg.byComponent) {
        const bb = new Box3();
        for (const m of meshes) bb.union(m.geometry.boundingBox!.clone().applyMatrix4(m.matrixWorld));
        pivots.set(id, { center: bb.getCenter(new Vector3()), size: bb.getSize(new Vector3()) });
      }
      root.userData.__segmented = { ...seg, all, pivots };
    }
    const sphere = new Box3().setFromObject(root).getBoundingSphere(new Sphere());
    return { ...(root.userData.__segmented as Omit<Prepared, "root" | "sphere">), root, sphere };
  }, [gltf, model]);

  useEffect(() => { onLoaded(prep.report); }, [prep, onLoaded]);

  const compById = useMemo(() => new Map(model.components.map((c) => [c.id, c])), [model]);

  // One heat map material per component (never shared across components).
  const heatMaterials = useMemo(() => {
    const map = new Map<string, Material>();
    for (const comp of model.components) {
      const color = scoreToColor(scores[comp.id] ?? 0);
      map.set(comp.id, comp.transparent
        ? new MeshPhysicalMaterial({ color, roughness: 0.1, metalness: 0, transparent: true, opacity: 0.5,
                                     depthWrite: false, side: DoubleSide })
        : new MeshStandardMaterial({ color, roughness: 0.45, metalness: 0.1, envMapIntensity: 0.6 }));
    }
    return map;
  }, [model, scores]);

  // Level 1 per-component color overrides (design view only).
  const overrideMaterials = useMemo(() => {
    const map = new Map<string, Material>();
    for (const [id, spec] of Object.entries(design.componentColors)) {
      map.set(id, new MeshPhysicalMaterial(paramsFor(spec, !!compById.get(id)?.transparent)));
    }
    return map;
  }, [design.componentColors, compById]);

  // Choose materials per mesh for the current mode.
  useLayoutEffect(() => {
    for (const [id, meshes] of prep.byComponent) {
      for (const m of meshes) {
        m.material = mode === "heatmap" ? heatMaterials.get(id)! : overrideMaterials.get(id) ?? m.userData.originalMaterial;
      }
    }
    for (const m of prep.others) m.material = mode === "heatmap" ? NEUTRAL : m.userData.originalMaterial;
  }, [prep, mode, heatMaterials, overrideMaterials]);

  // Level 1 body paint / wheel color: modify the asset's own paint & rim materials (restorable).
  useLayoutEffect(() => {
    const apply = (names: string[], spec: ColorSpec | null) => {
      const seen = new Set<Material>();
      for (const m of prep.all) {
        const mat = m.userData.originalMaterial as MeshPhysicalMaterial;
        if (!names.includes(m.userData.gltfMaterialName) || seen.has(mat)) continue;
        seen.add(mat);
        mat.userData.base ??= { color: mat.color.clone(), metalness: mat.metalness, roughness: mat.roughness,
                                clearcoat: mat.clearcoat ?? 0 };
        const base = mat.userData.base as { color: Color; metalness: number; roughness: number; clearcoat: number };
        const p = spec ? paramsFor(spec, false) : null;
        mat.color.copy(p ? p.color : base.color);
        mat.metalness = p ? p.metalness : base.metalness;
        mat.roughness = p ? p.roughness : base.roughness;
        if ("clearcoat" in mat) mat.clearcoat = p ? p.clearcoat : base.clearcoat;
        mat.needsUpdate = true;
      }
    };
    apply(model.design.paintMaterials, design.bodyColor);
    apply(model.design.rimMaterials, design.wheelColor);
  }, [prep, model, design.bodyColor, design.wheelColor]);

  // Level 2: body/interior vertices are deformed continuously (panels stay connected); wheels are
  // placed rigidly so they follow the axles, track width and wheel size.
  const engine = useMemo(() => createDeformEngine(model, prep.all, prep.byComponent), [model, prep]);
  useLayoutEffect(() => {
    engine.apply(design);
    const wheels = engine.wheelPlacement(design);
    const inv = new Matrix4();
    for (const m of prep.all) {
      const id = m.userData.componentId;
      const delta = id ? wheels.get(id) : undefined;
      if (delta) {
        inv.copy(m.userData.parentWorld as Matrix4).invert();
        m.matrix.copy(inv).multiply(delta).multiply(m.userData.parentWorld as Matrix4).multiply(m.userData.baseMatrix as Matrix4);
        m.matrixWorldNeedsUpdate = true;
      }
    }
  }, [engine, prep, design]);

  // Cutaway: hide roof/glass/headliner so the cabin is visible (independent of the design state).
  useLayoutEffect(() => {
    const hide = new Set(view === "cutaway" ? model.cutawayHide ?? [] : []);
    for (const m of prep.all) {
      const id = m.userData.componentId;
      m.visible = !(id && (design.hidden[id] || hide.has(id)));
    }
  }, [prep, model, view, design.hidden]);

  // Interior camera: driver eye position from the driver seat, looking forward.
  const interiorCam = useMemo(() => {
    const seat = model.driverSeat ? prep.byComponent.get(model.driverSeat) : undefined;
    if (!seat?.length) return null;
    const bb = new Box3();
    for (const m of seat) bb.union(m.geometry.boundingBox!.clone().applyMatrix4(m.matrixWorld));
    const c = bb.getCenter(new Vector3());
    const fwd = new Vector3(model.frame.forward.endsWith("x") ? 1 : 0, 0, model.frame.forward.endsWith("z") ? 1 : 0)
      .multiplyScalar(model.frame.forward.startsWith("-") ? -1 : 1);
    const eye = new Vector3(c.x, bb.max.y - 0.04, c.z).addScaledVector(fwd, 0.05);
    return { eye, target: eye.clone().addScaledVector(fwd, 0.35).add(new Vector3(0, -0.06, 0)) };
  }, [prep, model]);

  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    if (e.delta > 4) return; // it was a drag (orbit), not a click
    e.stopPropagation();
    // Prefer opaque parts behind glass (e.g. the dashboard seen through the windshield).
    const hits = e.intersections.filter((i) => (i.object as SegmentedMesh).userData?.componentId && i.object.visible);
    const isGlass = (id: string) => !!compById.get(id)?.transparent;
    const hit = hits.find((i) => !isGlass((i.object as SegmentedMesh).userData.componentId!)) ?? hits[0];
    onSelect(hit ? (hit.object as SegmentedMesh).userData.componentId : null);
  };

  const selectedMeshes = selectedId ? prep.byComponent.get(selectedId) ?? [] : [];
  return (
    <>
      <primitive object={prep.root} onClick={handleClick}
        onPointerOver={(e: ThreeEvent<PointerEvent>) => {
          if ((e.object as SegmentedMesh).userData?.componentId) document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => { document.body.style.cursor = ""; }} />
      {selectedMeshes.map((m, i) => <Highlight key={`${selectedId}-${i}`} source={m} />)}
      <CameraRig sphere={prep.sphere} resetSignal={resetSignal} view={view} interior={interiorCam}
        focus={focusId && prep.pivots.get(focusId) ? { ...prep.pivots.get(focusId)!, signal: focusSignal ?? 0,
          inside: compById.get(focusId)?.category === "Interior" } : null} />
    </>
  );
}

/** Overlay following its source mesh every frame (so it also follows Level 2 transforms). */
function Highlight({ source }: { source: Mesh }) {
  const ref = useRef<Mesh>(null);
  useFrame(() => {
    if (!ref.current) return;
    ref.current.matrix.copy(source.matrixWorld);
    ref.current.visible = source.visible;
  });
  return <mesh ref={ref} geometry={source.geometry} material={HIGHLIGHT} matrixAutoUpdate={false} renderOrder={10} />;
}

/** Frames the whole car from a 3/4 front view; re-applied on reset. */
type Focus = { center: Vector3; size: Vector3; signal: number; inside: boolean };

function CameraRig({ sphere, resetSignal, view, interior, focus }: {
  sphere: Sphere; resetSignal: number; view: CameraView; interior: { eye: Vector3; target: Vector3 } | null;
  focus: Focus | null;
}) {
  const camera = useThree((s) => s.camera) as PerspectiveCamera;
  const controls = useRef<OrbitControlsImpl>(null);
  const goal = useRef<{ pos: Vector3; target: Vector3 } | null>(null);
  // Glide towards a focused component: from outside along its direction from the car's centre,
  // interior parts from above (the cutaway hides the roof).
  useEffect(() => {
    if (!focus || view === "interior") return;
    const out = focus.center.clone().sub(sphere.center).setY(0);
    const dir = focus.inside || out.lengthSq() < 1e-4 ? new Vector3(0.3, 1.2, 0.4) : out.normalize().setY(0.45);
    const reach = Math.max(focus.size.length() * 2.6, sphere.radius * 1.25);
    goal.current = { target: focus.center.clone(), pos: focus.center.clone().addScaledVector(dir.normalize(), reach) };
    if (controls.current) controls.current.minDistance = 0.3;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.signal]);
  useFrame(() => {
    const g = goal.current, c = controls.current;
    if (!g || !c) return;
    camera.position.lerp(g.pos, 0.08);
    c.target.lerp(g.target, 0.08);
    c.update();
    if (camera.position.distanceTo(g.pos) < 0.01) goal.current = null;
  });
  useEffect(() => {
    // Any drag ends the glide.
    const c = controls.current;
    if (!c) return;
    const stop = () => { goal.current = null; };
    c.addEventListener("start", stop);
    return () => c.removeEventListener("start", stop);
  }, []);
  useEffect(() => {
    if (view === "interior" && interior) {
      // Driver eye: orbit around a point just ahead, so dragging looks around the cabin.
      camera.position.copy(interior.eye);
      camera.near = 0.01;
      camera.far = 100;
      camera.fov = 60;
      camera.updateProjectionMatrix();
      if (controls.current) {
        controls.current.target.copy(interior.target);
        controls.current.minDistance = 0.05;
        controls.current.maxDistance = 1.2;
        controls.current.maxPolarAngle = Math.PI - 0.1;
        controls.current.update();
      }
      return;
    }
    camera.fov = 35;
    if (controls.current) controls.current.maxPolarAngle = Math.PI / 2 - 0.04;
    const fov = (camera.fov * Math.PI) / 180;
    const aspect = Math.max(camera.aspect, 0.6);
    const fit = sphere.radius / Math.sin(Math.min(fov, fov * aspect) / 2);
    const dist = fit * (view === "cutaway" ? 1.0 : 0.72);
    const target = new Vector3(sphere.center.x, sphere.center.y * 0.7, sphere.center.z);
    const dir = (view === "cutaway" ? new Vector3(0.35, 1.1, 0.45) : new Vector3(0.62, 0.32, 0.72)).normalize();
    camera.position.copy(target).addScaledVector(dir, dist);
    camera.near = dist / 100;
    camera.far = dist * 10;
    camera.updateProjectionMatrix();
    if (controls.current) {
      controls.current.target.copy(target);
      controls.current.minDistance = sphere.radius * 0.9;
      controls.current.maxDistance = dist * 2.5;
      controls.current.update();
    }
    goal.current = null;
  }, [camera, sphere, resetSignal, view, interior]);
  return <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={0.08} maxPolarAngle={Math.PI / 2 - 0.04} />;
}
