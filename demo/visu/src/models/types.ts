/**
 * Normalized box in the vehicle frame, evaluated per triangle centroid:
 *   x: -1 (car's right) .. +1 (car's left)
 *   y:  0 (ground)      ..  1 (highest point)
 *   z: -1 (rear)        .. +1 (front)
 * absX: like x but on |x| (symmetric left/right regions).
 */
export type Region = {
  x?: [number, number];
  absX?: [number, number];
  y?: [number, number];
  z?: [number, number];
};

/** One source of geometry for a component: a glTF node (and its descendants), optionally filtered. */
export type ComponentPart = {
  node: string;
  /** Only meshes using one of these glTF material names. */
  materials?: string[];
  /** Only triangles whose centroid falls inside this region ("spatial segmentation"). */
  region?: Region;
};

export type ComponentCategory =
  | "Body panels" | "Bumpers & aero" | "Doors" | "Glass" | "Lighting" | "Wheels" | "Trim & details" | "Interior";

export type CarComponent = {
  id: string;
  name: string;
  category: ComponentCategory;
  /** glTF node names this component is built from (evidence from the model). */
  nodeNames: string[];
  parts: ComponentPart[];
  /** "node" = whole meshes; "spatial" = carved out of a larger mesh by region (approximate). */
  segmentation: "node" | "spatial";
  /** Kept transparent/tinted instead of opaque in the heat map. */
  transparent?: boolean;
};

/** A component plus its (synthetic or real) score. */
export type ScoredComponent = CarComponent & { score: number };

export type PaintOption = { id: string; label: string; hex: string; metalness: number; roughness: number };
export type WheelOption = { id: string; label: string; hex: string; metalness: number; roughness: number };

export type CarModel = {
  id: string;
  displayName: string;
  url: string;
  /** Real-world length in meters used to scale the model. */
  lengthMeters: number;
  /** Axis conventions of the asset after loading. */
  frame: { up: "+y"; forward: "+z" | "-z" | "+x" | "-x"; left: "+x" | "-x" | "+z" | "-z" };
  components: CarComponent[];
  /** glTF material names that design actions may modify. */
  design: { paintMaterials: string[]; rimMaterials: string[]; paints: PaintOption[]; wheels: WheelOption[] };
  credit: string;
  /** Component ids hidden in the cutaway view (roof, glass, headliner ...). */
  cutawayHide?: string[];
  /** Component id whose position defines the interior (driver eye) camera. */
  driverSeat?: string;
};
