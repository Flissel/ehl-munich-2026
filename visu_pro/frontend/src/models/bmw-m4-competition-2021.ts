import type { CarComponent, CarModel, ComponentPart, Region } from "./types";

/*
 * Component mapping for 2021_bmw_m4_competitionglTF.zip (scene.gltf).
 * Evidence: node names under "RootNode" (see scripts/gltf_bounds.mjs). Asset frame: +Y up,
 * +Z forward, +X = car's left (Driver_Door and Steering Wheel are at +X, left-hand drive).
 *
 * The asset merges several panels into one mesh, so some components are carved out spatially
 * (segmentation: "spatial"), which is approximate:
 *   - "Body" = hood + roof + fenders + rear quarters + trunk lid + pillars/sills
 *   - "bumpers" = front + rear bumper (+ splitter / diffuser lips)
 *   - "headlight", "glsslight*", "headglass" = both headlights; "tail*" = both taillights
 *   - "skirt" = both side skirts; "glass" = windshield + rear window
 * Side mirrors are not identifiable as separate geometry; an approximate region of the doors is used.
 * Interior: seats split left/right; the Dashboard mesh is split by material (displays, climate panel)
 * and position (centre console); InteriorAlcntr = headliner + overhead console (SOS panel texture).
 */

const PAINT = "Material_692";
const DOOR_OUTER = [PAINT, "Material_694", "Material_695", "Material_697", "Material_698"];
const DOOR_GLASS = ["Material_699", "Material_932"];
const DOOR_TRIM = ["Material_706", "Material_849", "Material_847", "Material_1824"];
const LEFT: Region = { x: [0, 1] };
const RIGHT: Region = { x: [-1, 0] };

const wheel = (id: string, name: string, rim: string, tyre: string, cap: string, disc: string, caliper: string): CarComponent => ({
  id, name, category: "Wheels", segmentation: "node",
  nodeNames: [rim, tyre, cap, disc, caliper],
  parts: [rim, tyre, cap, disc, caliper].map((node) => ({ node })),
});

const split = (nodes: string[], region: Region): ComponentPart[] => nodes.map((node) => ({ node, region }));

const HEADLIGHT_NODES = ["headlight", "glsslight", "glsslight001", "headglass", "laseralumobj"];
const TAILLIGHT_NODES = ["tail", "tailpiece", "tailglass"];
// Mirror head = cluster of outer door triangles above the door skin (scripts/region_probe.mjs).
const MIRROR: Region = { absX: [0.84, 1], y: [0.63, 0.82], z: [0.13, 0.27] };

// Order matters for spatial components: the first component whose region claims a triangle wins.
const components: CarComponent[] = [
  // --- Body panels carved out of "Body"
  { id: "hood", name: "Hood", category: "Body panels", segmentation: "spatial", nodeNames: ["Body"],
    parts: [{ node: "Body", region: { z: [0.33, 1], y: [0.5, 1], absX: [0, 0.6] } }] },
  { id: "roof", name: "Roof", category: "Body panels", segmentation: "spatial", nodeNames: ["Body"],
    parts: [{ node: "Body", region: { z: [-0.45, 0.12], y: [0.86, 1] } }] },
  { id: "trunk-lid", name: "Trunk lid", category: "Body panels", segmentation: "spatial", nodeNames: ["Body"],
    parts: [{ node: "Body", region: { z: [-1, -0.6], y: [0.58, 1], absX: [0, 0.6] } }] },
  { id: "fender-front-left", name: "Front-left fender", category: "Body panels", segmentation: "spatial", nodeNames: ["Body"],
    parts: [{ node: "Body", region: { z: [0.25, 1], x: [0, 1] } }] },
  { id: "fender-front-right", name: "Front-right fender", category: "Body panels", segmentation: "spatial", nodeNames: ["Body"],
    parts: [{ node: "Body", region: { z: [0.25, 1], x: [-1, 0] } }] },
  { id: "quarter-rear-left", name: "Rear-left quarter panel", category: "Body panels", segmentation: "spatial", nodeNames: ["Body"],
    parts: [{ node: "Body", region: { z: [-1, -0.25], x: [0, 1] } }] },
  { id: "quarter-rear-right", name: "Rear-right quarter panel", category: "Body panels", segmentation: "spatial", nodeNames: ["Body"],
    parts: [{ node: "Body", region: { z: [-1, -0.25], x: [-1, 0] } }] },
  { id: "pillars-sills", name: "Pillars & body sides", category: "Body panels", segmentation: "spatial", nodeNames: ["Body"],
    parts: [{ node: "Body" }] },
  { id: "underbody", name: "Underbody", category: "Body panels", segmentation: "node", nodeNames: ["bottom"],
    parts: [{ node: "bottom" }] },

  // --- Bumpers & aero
  { id: "front-splitter", name: "Front splitter", category: "Bumpers & aero", segmentation: "spatial", nodeNames: ["bumpers"],
    parts: [{ node: "bumpers", region: { z: [0.85, 1], y: [0, 0.22] } }] },
  { id: "front-bumper", name: "Front bumper", category: "Bumpers & aero", segmentation: "spatial", nodeNames: ["bumpers"],
    parts: [{ node: "bumpers", region: { z: [0, 1] } }] },
  { id: "rear-diffuser", name: "Rear diffuser", category: "Bumpers & aero", segmentation: "spatial", nodeNames: ["diffuser details", "bumpers"],
    parts: [{ node: "diffuser details" }, { node: "bumpers", region: { z: [-1, -0.85], y: [0, 0.3] } }] },
  { id: "rear-bumper", name: "Rear bumper", category: "Bumpers & aero", segmentation: "spatial", nodeNames: ["bumpers"],
    parts: [{ node: "bumpers", region: { z: [-1, 0] } }] },
  { id: "side-skirt-left", name: "Left side skirt", category: "Bumpers & aero", segmentation: "spatial", nodeNames: ["skirt"],
    parts: [{ node: "skirt", region: LEFT }] },
  { id: "side-skirt-right", name: "Right side skirt", category: "Bumpers & aero", segmentation: "spatial", nodeNames: ["skirt"],
    parts: [{ node: "skirt", region: RIGHT }] },
  { id: "rear-spoiler", name: "Rear spoiler", category: "Bumpers & aero", segmentation: "node", nodeNames: ["spoiler"],
    parts: [{ node: "spoiler" }] },
  { id: "kidney-grille", name: "Kidney grille", category: "Bumpers & aero", segmentation: "node", nodeNames: ["grilles"],
    parts: [{ node: "grilles" }] },
  { id: "lower-intake", name: "Lower front intake", category: "Bumpers & aero", segmentation: "node", nodeNames: ["fgrllpiece"],
    parts: [{ node: "fgrllpiece" }] },

  // --- Doors & mirrors (mirror regions first so they are carved out of the doors)
  { id: "mirror-left", name: "Left side mirror", category: "Doors", segmentation: "spatial", nodeNames: ["Driver_Door"],
    parts: [{ node: "Driver_Door", materials: DOOR_OUTER, region: { ...MIRROR, x: [0, 1] } }] },
  { id: "mirror-right", name: "Right side mirror", category: "Doors", segmentation: "spatial", nodeNames: ["Passenger_Door"],
    parts: [{ node: "Passenger_Door", materials: DOOR_OUTER, region: { ...MIRROR, x: [-1, 0] } }] },
  { id: "door-left", name: "Left door", category: "Doors", segmentation: "node", nodeNames: ["Driver_Door"],
    parts: [{ node: "Driver_Door", materials: DOOR_OUTER }] },
  { id: "door-right", name: "Right door", category: "Doors", segmentation: "node", nodeNames: ["Passenger_Door"],
    parts: [{ node: "Passenger_Door", materials: DOOR_OUTER }] },

  // --- Glass
  { id: "windshield", name: "Windshield", category: "Glass", segmentation: "spatial", nodeNames: ["glass"], transparent: true,
    parts: [{ node: "glass", region: { z: [-0.05, 1] } }] },
  { id: "rear-window", name: "Rear window", category: "Glass", segmentation: "spatial", nodeNames: ["glass"], transparent: true,
    parts: [{ node: "glass" }] },
  { id: "window-left", name: "Left side window", category: "Glass", segmentation: "node", nodeNames: ["Driver_Door"], transparent: true,
    parts: [{ node: "Driver_Door", materials: DOOR_GLASS }] },
  { id: "window-right", name: "Right side window", category: "Glass", segmentation: "node", nodeNames: ["Passenger_Door"], transparent: true,
    parts: [{ node: "Passenger_Door", materials: DOOR_GLASS }] },

  // --- Lighting (both sides live in the same meshes -> split left/right)
  { id: "headlight-left", name: "Left headlight", category: "Lighting", segmentation: "spatial", nodeNames: HEADLIGHT_NODES,
    parts: split(HEADLIGHT_NODES, LEFT) },
  { id: "headlight-right", name: "Right headlight", category: "Lighting", segmentation: "spatial", nodeNames: HEADLIGHT_NODES,
    parts: split(HEADLIGHT_NODES, RIGHT) },
  { id: "taillight-left", name: "Left taillight", category: "Lighting", segmentation: "spatial", nodeNames: TAILLIGHT_NODES,
    parts: split(TAILLIGHT_NODES, LEFT) },
  { id: "taillight-right", name: "Right taillight", category: "Lighting", segmentation: "spatial", nodeNames: TAILLIGHT_NODES,
    parts: split(TAILLIGHT_NODES, RIGHT) },

  // --- Wheels (rim + tyre + centre cap + brake disc + caliper per corner)
  wheel("wheel-front-left", "Front-left wheel", "Rim", "tire07", "tire06", "brake disc", "Brake"),
  wheel("wheel-front-right", "Front-right wheel", "Rim002", "tire013", "tire012", "brake disc002", "Brake002"),
  wheel("wheel-rear-left", "Rear-left wheel", "Rim001", "tire009", "tire008", "brake disc001", "Brake001"),
  wheel("wheel-rear-right", "Rear-right wheel", "Rim003", "tire011", "tire010", "brake disc003", "Brake003"),

  // --- Trim & details
  { id: "exhaust", name: "Exhaust system", category: "Trim & details", segmentation: "node", nodeNames: ["exhausts", "exhaust muffler"],
    parts: [{ node: "exhausts" }, { node: "exhaust muffler" }] },
  { id: "roof-fin", name: "Shark-fin antenna", category: "Trim & details", segmentation: "node", nodeNames: ["rooffin"],
    parts: [{ node: "rooffin" }] },
  { id: "badges", name: "Badges & logos", category: "Trim & details", segmentation: "node",
    nodeNames: ["Frontlogo", "rear_logo", "sidelogos", "Cylinder001", "Cylinder002"],
    parts: ["Frontlogo", "rear_logo", "sidelogos", "Cylinder001", "Cylinder002"].map((node) => ({ node })) },
  { id: "license-plate", name: "License plate", category: "Trim & details", segmentation: "node", nodeNames: ["Plate", "platebolts"],
    parts: [{ node: "Plate" }, { node: "platebolts" }] },

  // --- Interior (bounds from scripts/node_material_bounds.mjs; driver = left = +X)
  { id: "seat-driver", name: "Driver seat", category: "Interior", segmentation: "spatial", nodeNames: ["seats"],
    parts: [{ node: "seats", region: LEFT }] },
  { id: "seat-passenger", name: "Passenger seat", category: "Interior", segmentation: "spatial", nodeNames: ["seats"],
    parts: [{ node: "seats", region: RIGHT }] },
  { id: "rear-seats", name: "Rear seats", category: "Interior", segmentation: "node",
    nodeNames: ["rearseats", "rear_seatbackrest", "Plane003"],
    parts: [{ node: "rearseats" }, { node: "rear_seatbackrest" }, { node: "Plane003" }] },
  { id: "instrument-cluster", name: "Instrument cluster display", category: "Interior", segmentation: "node", nodeNames: ["Dashboard"],
    parts: [{ node: "Dashboard", materials: ["Material_1548", "Material_775"] }] },
  { id: "central-display", name: "Central touch display", category: "Interior", segmentation: "node", nodeNames: ["Dashboard"],
    parts: [{ node: "Dashboard", materials: ["Material_1522", "Material_699"] }] },
  { id: "climate-controls", name: "Climate control panel", category: "Interior", segmentation: "node", nodeNames: ["Dashboard"],
    parts: [{ node: "Dashboard", materials: ["Material_1001"] }] },
  { id: "center-console", name: "Center console & armrest", category: "Interior", segmentation: "spatial", nodeNames: ["Dashboard"],
    parts: [{ node: "Dashboard", region: { absX: [0, 0.17], y: [0.15, 0.55], z: [-0.25, 0.3] } }] },
  { id: "dashboard", name: "Dashboard", category: "Interior", segmentation: "spatial", nodeNames: ["Dashboard"],
    parts: [{ node: "Dashboard" }] },
  { id: "steering-wheel", name: "Steering wheel", category: "Interior", segmentation: "node", nodeNames: ["Steering Wheel", "Box003"],
    parts: [{ node: "Steering Wheel" }, { node: "Box003" }] },
  { id: "pedals", name: "Pedals", category: "Interior", segmentation: "node", nodeNames: ["plds"], parts: [{ node: "plds" }] },
  { id: "door-trim-left", name: "Left door trim & speaker", category: "Interior", segmentation: "node", nodeNames: ["Driver_Door"],
    parts: [{ node: "Driver_Door", materials: DOOR_TRIM }] },
  { id: "door-trim-right", name: "Right door trim & speaker", category: "Interior", segmentation: "node", nodeNames: ["Passenger_Door"],
    parts: [{ node: "Passenger_Door", materials: DOOR_TRIM }] },
  { id: "overhead-console", name: "Overhead console (SOS, lights)", category: "Interior", segmentation: "node", nodeNames: ["InteriorAlcntr"],
    parts: [{ node: "InteriorAlcntr", materials: ["Material_706", "Material_694", "Material_1860", "Material_697"] }] },
  { id: "headliner", name: "Headliner & pillar trim", category: "Interior", segmentation: "node", nodeNames: ["InteriorAlcntr"],
    parts: [{ node: "InteriorAlcntr", materials: ["Material_850"] }] },
  { id: "interior-side-panels", name: "Sills & side panels", category: "Interior", segmentation: "node", nodeNames: ["Object002"],
    parts: [{ node: "Object002" }] },
  { id: "seat-belts", name: "Seat belts", category: "Interior", segmentation: "node", nodeNames: ["seatbelt"], parts: [{ node: "seatbelt" }] },
  { id: "interior-mirror", name: "Interior mirror", category: "Interior", segmentation: "node", nodeNames: ["interior_mirror"],
    parts: [{ node: "interior_mirror" }] },
  { id: "sun-visors", name: "Sun visors", category: "Interior", segmentation: "node", nodeNames: ["sunvisors"], parts: [{ node: "sunvisors" }] },
];

/** Parts hidden in the cutaway view so the cabin is visible from above. */
export const CUTAWAY_HIDE = ["roof", "windshield", "rear-window", "window-left", "window-right", "headliner",
  "overhead-console", "sun-visors", "interior-mirror", "roof-fin"];

export const bmwM4Competition2021: CarModel = {
  id: "bmw-m4-competition-2021",
  displayName: "BMW M4 Competition · 2021",
  url: "/models/bmw-m4-competition-2021/scene.gltf",
  lengthMeters: 4.794,
  frame: { up: "+y", forward: "+z", left: "+x" },
  components,
  design: {
    paintMaterials: [PAINT],
    rimMaterials: ["Material_753"],
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
  credit: '"2021 BMW M4 Competition" by Ricy (sketchfab.com/ngon_3d), CC-BY-NC-4.0',
  cutawayHide: CUTAWAY_HIDE,
  driverSeat: "seat-driver",
};
