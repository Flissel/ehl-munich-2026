import type { CarComponent, CarModel, ComponentCategory, ComponentPart, Region } from "./types";

/*
 * Shared component template for the Sketchfab BMW models by Ddiaz Design (X1, X5, X7; 2026-10-10, PR #7).
 * Their meshes are merged differently per car (the X1 body is one paint mesh, the X7 has 166 pieces), so the
 * 56 components are defined by MATERIAL ROLES (paint, trim, glass, lights, tyres, seats, ...) per car plus
 * REGIONS in the normalized vehicle frame (x: right -1 .. left +1, y: 0 ground .. 1 top, z: rear -1 .. front +1;
 * all three: +Y up, +Z forward, +X = car's left, left-hand drive). Regions come from per-material bounds
 * (scratch analysis of scene.gltf). Spatial carving is approximate, like the M4 mapping it replaces.
 * The ids, names and categories below are the shared catalogue (demo/visu/vault.py reads them).
 */

export const CATALOGUE: { id: string; name: string; category: ComponentCategory }[] = [
  { id: "hood", name: "Hood", category: "Body panels" },
  { id: "roof", name: "Roof", category: "Body panels" },
  { id: "trunk-lid", name: "Trunk lid", category: "Body panels" },
  { id: "fender-front-left", name: "Front-left fender", category: "Body panels" },
  { id: "fender-front-right", name: "Front-right fender", category: "Body panels" },
  { id: "quarter-rear-left", name: "Rear-left quarter panel", category: "Body panels" },
  { id: "quarter-rear-right", name: "Rear-right quarter panel", category: "Body panels" },
  { id: "pillars-sills", name: "Pillars & body sides", category: "Body panels" },
  { id: "underbody", name: "Underbody", category: "Body panels" },
  { id: "front-splitter", name: "Front splitter", category: "Bumpers & aero" },
  { id: "front-bumper", name: "Front bumper", category: "Bumpers & aero" },
  { id: "rear-diffuser", name: "Rear diffuser", category: "Bumpers & aero" },
  { id: "rear-bumper", name: "Rear bumper", category: "Bumpers & aero" },
  { id: "side-skirt-left", name: "Left side skirt", category: "Bumpers & aero" },
  { id: "side-skirt-right", name: "Right side skirt", category: "Bumpers & aero" },
  { id: "rear-spoiler", name: "Rear spoiler", category: "Bumpers & aero" },
  { id: "kidney-grille", name: "Kidney grille", category: "Bumpers & aero" },
  { id: "lower-intake", name: "Lower front intake", category: "Bumpers & aero" },
  { id: "mirror-left", name: "Left side mirror", category: "Doors" },
  { id: "mirror-right", name: "Right side mirror", category: "Doors" },
  { id: "door-left", name: "Left door", category: "Doors" },
  { id: "door-right", name: "Right door", category: "Doors" },
  { id: "windshield", name: "Windshield", category: "Glass" },
  { id: "rear-window", name: "Rear window", category: "Glass" },
  { id: "window-left", name: "Left side window", category: "Glass" },
  { id: "window-right", name: "Right side window", category: "Glass" },
  { id: "headlight-left", name: "Left headlight", category: "Lighting" },
  { id: "headlight-right", name: "Right headlight", category: "Lighting" },
  { id: "taillight-left", name: "Left taillight", category: "Lighting" },
  { id: "taillight-right", name: "Right taillight", category: "Lighting" },
  { id: "wheel-front-left", name: "Front-left wheel", category: "Wheels" },
  { id: "wheel-front-right", name: "Front-right wheel", category: "Wheels" },
  { id: "wheel-rear-left", name: "Rear-left wheel", category: "Wheels" },
  { id: "wheel-rear-right", name: "Rear-right wheel", category: "Wheels" },
  { id: "exhaust", name: "Exhaust system", category: "Trim & details" },
  { id: "roof-fin", name: "Shark-fin antenna", category: "Trim & details" },
  { id: "badges", name: "Badges & logos", category: "Trim & details" },
  { id: "license-plate", name: "License plate", category: "Trim & details" },
  { id: "seat-driver", name: "Driver seat", category: "Interior" },
  { id: "seat-passenger", name: "Passenger seat", category: "Interior" },
  { id: "rear-seats", name: "Rear seats", category: "Interior" },
  { id: "instrument-cluster", name: "Instrument cluster display", category: "Interior" },
  { id: "central-display", name: "Central touch display", category: "Interior" },
  { id: "climate-controls", name: "Climate control panel", category: "Interior" },
  { id: "center-console", name: "Center console & armrest", category: "Interior" },
  { id: "dashboard", name: "Dashboard", category: "Interior" },
  { id: "steering-wheel", name: "Steering wheel", category: "Interior" },
  { id: "pedals", name: "Pedals", category: "Interior" },
  { id: "door-trim-left", name: "Left door trim & speaker", category: "Interior" },
  { id: "door-trim-right", name: "Right door trim & speaker", category: "Interior" },
  { id: "overhead-console", name: "Overhead console (SOS, lights)", category: "Interior" },
  { id: "headliner", name: "Headliner & pillar trim", category: "Interior" },
  { id: "interior-side-panels", name: "Sills & side panels", category: "Interior" },
  { id: "seat-belts", name: "Seat belts", category: "Interior" },
  { id: "interior-mirror", name: "Interior mirror", category: "Interior" },
  { id: "sun-visors", name: "Sun visors", category: "Interior" },
];

/** Material roles of one car (glTF material names). Empty lists are fine: the component is then absent. */
export type MaterialRoles = {
  paint: string[];
  /** black / plastic exterior trim: bumper lower parts, grille surround, skirts, window frames */
  trim: string[];
  chrome: string[];
  chassis: string[];
  glass: string[];
  roofGlass: string[];
  /** separate mirror materials; without them the mirror head is carved out of the paint */
  mirrors: string[];
  headlights: string[];
  taillights: string[];
  /** light materials used front and rear (split by z) */
  lightsBoth: string[];
  tyres: string[];
  rims: string[];
  brakes: string[];
  badges: string[];
  plate: string[];
  frontSeats: string[];
  rearSeats: string[];
  steering: string[];
  /** steering wheel and centre tunnel in one material (split by x) */
  steeringAndConsole: string[];
  console: string[];
  dashboard: string[];
  doorTrims: string[];
  headliner: string[];
  sidePanels: string[];
};

export type CarSpec = {
  id: string;
  displayName: string;
  url: string;
  lengthMeters: number;
  credit: string;
  /** glTF root node (contains all meshes) */
  root: string;
  roles: MaterialRoles;
};

const LEFT: Region = { x: [0, 1] };
const RIGHT: Region = { x: [-1, 0] };
const FRONT: Region = { z: [0, 1] };
const REAR: Region = { z: [-1, 0] };
const both = (r: Region, side: Region): Region => ({ ...r, ...side });

/** Wheels: tyre, rim and brake meshes hold all four corners; split by quadrant below the belt line. */
const WHEEL = { y: [0, 0.46] as [number, number], absX: [0.45, 1] as [number, number] };
const CORNERS: Record<string, Region> = {
  "wheel-front-left": { ...WHEEL, x: [0, 1], z: [0.2, 1] },
  "wheel-front-right": { ...WHEEL, x: [-1, 0], z: [0.2, 1] },
  "wheel-rear-left": { ...WHEEL, x: [0, 1], z: [-1, -0.2] },
  "wheel-rear-right": { ...WHEEL, x: [-1, 0], z: [-1, -0.2] },
};

// Exterior body regions (SUV proportions; first matching component wins, so order matters).
const R = {
  mirror: { absX: [0.86, 1], y: [0.6, 0.88], z: [0.12, 0.36] } as Region,
  hood: { z: [0.42, 1], y: [0.6, 1], absX: [0, 0.74] } as Region,
  frontBumper: { z: [0.84, 1], y: [0, 0.5] } as Region,
  rearBumper: { z: [-1, -0.86], y: [0, 0.47] } as Region,
  spoiler: { z: [-1, -0.8], y: [0.86, 1] } as Region,
  tailgate: { z: [-1, -0.74], y: [0.4, 1], absX: [0, 0.78] } as Region,
  roof: { y: [0.88, 1], z: [-0.82, 0.28] } as Region,
  door: { absX: [0.55, 1], z: [-0.5, 0.26], y: [0.22, 0.78] } as Region,
  skirt: { absX: [0.7, 1], y: [0, 0.3], z: [-0.55, 0.55] } as Region,
  grille: { z: [0.86, 1], absX: [0, 0.32], y: [0.38, 0.66] } as Region,
  intake: { z: [0.86, 1], y: [0.12, 0.38], absX: [0, 0.78] } as Region,
  splitter: { z: [0.88, 1], y: [0, 0.13] } as Region,
  diffuser: { z: [-1, -0.86], y: [0, 0.3] } as Region,
  exhaust: { z: [-1, -0.84], y: [0, 0.28], absX: [0.2, 0.9] } as Region,
  roofFin: { y: [0.94, 1], z: [-0.72, -0.4], absX: [0, 0.12] } as Region,
  windshield: { z: [0.08, 1] } as Region,
  rearWindow: { z: [-1, -0.6] } as Region,
};
// Interior regions (driver on the left = +x).
const I = {
  cluster: { x: [0.12, 0.62], y: [0.58, 0.82] } as Region,
  display: { absX: [0, 0.2], y: [0.6, 0.82] } as Region,
  climate: { absX: [0, 0.2], y: [0.4, 0.6] } as Region,
  steering: { x: [0.12, 0.62], y: [0.4, 0.82] } as Region,
  pedals: { x: [0.08, 0.62], y: [0.12, 0.38], z: [0.3, 0.62] } as Region,
  overhead: { absX: [0, 0.2], z: [0.15, 0.45] } as Region,
  visors: { absX: [0.2, 0.75], z: [0.22, 0.45], y: [0.8, 1] } as Region,
};

export function buildModel(spec: CarSpec): CarModel {
  const r = spec.roles, root = spec.root;
  const part = (materials: string[], region?: Region): ComponentPart[] =>
    materials.length ? [{ node: root, materials, ...(region ? { region } : {}) }] : [];
  const parts: Record<string, ComponentPart[]> = {};
  const add = (id: string, p: ComponentPart[]) => { if (p.length) (parts[id] ??= []).push(...p); };
  const body = [...r.paint], outer = [...r.paint, ...r.trim];

  // Order = priority for the shared meshes.
  add("mirror-left", r.mirrors.length ? part(r.mirrors, LEFT) : part(r.paint, both(R.mirror, LEFT)));
  add("mirror-right", r.mirrors.length ? part(r.mirrors, RIGHT) : part(r.paint, both(R.mirror, RIGHT)));
  add("roof-fin", part(outer, R.roofFin));
  add("kidney-grille", part([...r.trim, ...r.chrome], R.grille));
  add("lower-intake", part(r.trim, R.intake));
  add("front-splitter", part(r.trim, R.splitter));
  add("exhaust", part([...r.chrome, ...r.trim, ...r.chassis], R.exhaust));
  add("rear-diffuser", part(r.trim, R.diffuser));
  add("hood", part(body, R.hood));
  add("front-bumper", part(outer, R.frontBumper));
  add("rear-bumper", part(outer, R.rearBumper));
  add("rear-spoiler", part(outer, R.spoiler));
  add("trunk-lid", part(body, R.tailgate));
  add("roof", [...part(body, R.roof), ...part(r.roofGlass)]);
  add("door-left", part(body, both(R.door, LEFT)));
  add("door-right", part(body, both(R.door, RIGHT)));
  add("side-skirt-left", part(outer, both(R.skirt, LEFT)));
  add("side-skirt-right", part(outer, both(R.skirt, RIGHT)));
  add("fender-front-left", part(body, both({ z: [0.2, 1] }, LEFT)));
  add("fender-front-right", part(body, both({ z: [0.2, 1] }, RIGHT)));
  add("quarter-rear-left", part(body, both({ z: [-1, -0.2] }, LEFT)));
  add("quarter-rear-right", part(body, both({ z: [-1, -0.2] }, RIGHT)));
  add("underbody", [...part(r.chassis), ...part(r.trim, { y: [0, 0.1] })]);
  add("pillars-sills", part(outer));

  add("windshield", part(r.glass, R.windshield));
  add("rear-window", part(r.glass, R.rearWindow));
  add("window-left", part(r.glass, LEFT));
  add("window-right", part(r.glass, RIGHT));

  add("headlight-left", [...part(r.headlights, LEFT), ...part(r.lightsBoth, both(FRONT, LEFT))]);
  add("headlight-right", [...part(r.headlights, RIGHT), ...part(r.lightsBoth, both(FRONT, RIGHT))]);
  add("taillight-left", [...part(r.taillights, LEFT), ...part(r.lightsBoth, both(REAR, LEFT))]);
  add("taillight-right", [...part(r.taillights, RIGHT), ...part(r.lightsBoth, both(REAR, RIGHT))]);

  for (const [id, region] of Object.entries(CORNERS)) add(id, part([...r.tyres, ...r.rims, ...r.brakes], region));

  add("badges", part(r.badges));
  add("license-plate", part(r.plate));

  add("seat-driver", part(r.frontSeats, LEFT));
  add("seat-passenger", part(r.frontSeats, RIGHT));
  add("rear-seats", part(r.rearSeats));
  add("instrument-cluster", part(r.dashboard, I.cluster));
  add("central-display", part(r.dashboard, I.display));
  add("climate-controls", part(r.dashboard, I.climate));
  add("dashboard", part(r.dashboard));
  add("steering-wheel", [...part(r.steering), ...part(r.steeringAndConsole, I.steering)]);
  add("center-console", [...part(r.console), ...part(r.steeringAndConsole)]);
  add("pedals", part(r.sidePanels, I.pedals));
  add("door-trim-left", part(r.doorTrims, LEFT));
  add("door-trim-right", part(r.doorTrims, RIGHT));
  add("overhead-console", part(r.headliner, I.overhead));
  add("sun-visors", part(r.headliner, I.visors));
  add("headliner", part(r.headliner));
  add("interior-side-panels", part(r.sidePanels));

  // Priority order (insertion order of `parts`), not catalogue order: segmentation lets the first match win.
  const byId = new Map(CATALOGUE.map((c) => [c.id, c]));
  const components: CarComponent[] = Object.keys(parts).map((id) => byId.get(id)!).map((c) => ({
    ...c, parts: parts[c.id], nodeNames: [root],
    segmentation: parts[c.id].some((p) => p.region) ? "spatial" : "node",
    ...(c.category === "Glass" ? { transparent: true } : {}),
  }));
  return {
    id: spec.id, displayName: spec.displayName, url: spec.url, lengthMeters: spec.lengthMeters,
    frame: { up: "+y", forward: "+z", left: "+x" },
    components,
    design: {
      paintMaterials: r.paint, rimMaterials: r.rims,
      paints: [
        { id: "black", label: "Sapphire Black metallic", hex: "#0b0c10", metalness: 0.6, roughness: 0.3 },
        { id: "white", label: "Alpine White", hex: "#e8e8e4", metalness: 0.0, roughness: 0.3 },
        { id: "silver", label: "Brooklyn Silver metallic", hex: "#a9acb2", metalness: 0.9, roughness: 0.3 },
        { id: "racing_red", label: "Racing Red", hex: "#b3060c", metalness: 0.15, roughness: 0.3 },
        { id: "midnight_blue", label: "Midnight Blue metallic", hex: "#0c1d4f", metalness: 0.75, roughness: 0.3 },
      ],
      wheels: [
        { id: "standard", label: "Standard - Orbit Grey alloy", hex: "#4a4c52", metalness: 1, roughness: 0.35 },
        { id: "sport", label: "Sport - Gold Bronze M finish", hex: "#a47a3a", metalness: 1, roughness: 0.28 },
      ],
    },
    credit: spec.credit,
    cutawayHide: ["roof", "windshield", "rear-window", "window-left", "window-right", "headliner", "overhead-console",
      "sun-visors", "interior-mirror", "roof-fin"],
    driverSeat: "seat-driver",
  };
}
