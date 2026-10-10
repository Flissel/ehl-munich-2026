import type { CarModel } from "../models/types";

export type Finish = "gloss" | "metallic" | "matte" | "satin" | "chrome" | "carbon";
export type ColorSpec = { hex: string; finish: Finish };
export type Vec3 = [number, number, number];

/** Everything the web viewer can change. Level 1 = colors, Level 2 = shape adjustments. */
export type WebDesign = {
  bodyColor: ColorSpec | null;
  wheelColor: ColorSpec | null;
  componentColors: Record<string, ColorSpec>;
  scale: Record<string, Vec3>;
  move: Record<string, Vec3>; // cm: [left+, up+, forward+]
  hidden: Record<string, boolean>;
  rideHeightCm: number;
  wheelDeltaInches: number;
  trackWidthCm: number;
  proportions: Proportions;
};

/** Whole-body shape (Level 2), applied as a continuous deformation so panels stay connected. */
export type Proportions = {
  frontOverhangCm: number; // longer nose (-10..30)
  rearOverhangCm: number; // longer tail (-10..30)
  wheelbaseCm: number; // longer cabin / wheelbase (-10..30)
  bodyWidthCm: number; // wider body per side (0..10)
  fenderFlareCm: number; // wide-body arches per side (0..10)
  roofHeightCm: number; // chop (-) or raise (+) the roof (-8..6)
};

export const NEUTRAL_PROPORTIONS: Proportions = {
  frontOverhangCm: 0, rearOverhangCm: 0, wheelbaseCm: 0, bodyWidthCm: 0, fenderFlareCm: 0, roofHeightCm: 0,
};

export const PROPORTION_LIMITS: Record<keyof Proportions, [number, number, string]> = {
  frontOverhangCm: [-10, 30, "Front overhang (longer nose)"],
  rearOverhangCm: [-10, 30, "Rear overhang (longer tail)"],
  wheelbaseCm: [-10, 30, "Wheelbase"],
  bodyWidthCm: [0, 10, "Body width (per side)"],
  fenderFlareCm: [0, 10, "Fender flares (per side)"],
  roofHeightCm: [-8, 6, "Roof height"],
};

export const EMPTY_DESIGN: WebDesign = {
  bodyColor: null, wheelColor: null, componentColors: {}, scale: {}, move: {}, hidden: {},
  rideHeightCm: 0, wheelDeltaInches: 0, trackWidthCm: 0, proportions: NEUTRAL_PROPORTIONS,
};

export const FINISH_PARAMS: Record<Finish, { metalness: number; roughness: number; clearcoat: number }> = {
  gloss: { metalness: 0.1, roughness: 0.18, clearcoat: 1 },
  metallic: { metalness: 0.7, roughness: 0.3, clearcoat: 1 },
  matte: { metalness: 0.05, roughness: 0.78, clearcoat: 0 },
  satin: { metalness: 0.35, roughness: 0.45, clearcoat: 0.3 },
  chrome: { metalness: 1, roughness: 0.05, clearcoat: 0 },
  carbon: { metalness: 0.25, roughness: 0.32, clearcoat: 1 },
};

/** Validated action as returned by /api/web/design. */
export type WebAction =
  | { type: "set_body_color"; color_hex: string; finish: Finish; notes?: string[] }
  | { type: "set_wheel_color"; color_hex: string; finish: Finish; notes?: string[] }
  | { type: "set_component_color"; component_id: string; color_hex: string; finish: Finish; notes?: string[] }
  | { type: "scale_component"; component_id: string; factor_x: number; factor_y: number; factor_z: number; notes?: string[] }
  | { type: "move_component"; component_id: string; dx_cm: number; dy_cm: number; dz_cm: number; notes?: string[] }
  | { type: "hide_component"; component_id: string; hidden: boolean; notes?: string[] }
  | { type: "set_ride_height"; offset_cm: number; notes?: string[] }
  | { type: "set_wheel_size"; delta_inches: number; notes?: string[] }
  | { type: "set_track_width"; offset_cm: number; notes?: string[] }
  | { type: "set_body_proportions"; front_overhang_cm: number; rear_overhang_cm: number; wheelbase_cm: number;
      body_width_cm: number; fender_flare_cm: number; roof_height_cm: number; notes?: string[] }
  | { type: "reset_design"; notes?: string[] };

export type ActionResult = { label: string; level: 1 | 2 | 0; applied: boolean; note?: string };

const sign = (v: number) => (v > 0 ? `+${v}` : `${v}`);

/** Applies actions to a design; component ids are checked against the model. */
export function applyWebActions(model: CarModel, design: WebDesign, actions: WebAction[]): { design: WebDesign; results: ActionResult[] } {
  let d: WebDesign = structuredClone(design);
  const names = new Map(model.components.map((c) => [c.id, c.name]));
  const results: ActionResult[] = [];
  const note = (a: WebAction) => a.notes?.join("; ");
  for (const a of actions) {
    if ("component_id" in a && !names.has(a.component_id)) {
      results.push({ label: `${a.type} ${a.component_id}`, level: 0, applied: false, note: "unknown component" });
      continue;
    }
    const n = "component_id" in a ? names.get(a.component_id)! : "";
    switch (a.type) {
      case "reset_design":
        d = structuredClone(EMPTY_DESIGN); results.push({ label: "Reset to original design", level: 0, applied: true }); break;
      case "set_body_color":
        d.bodyColor = { hex: a.color_hex, finish: a.finish };
        results.push({ label: `Body paint ${a.color_hex} (${a.finish})`, level: 1, applied: true, note: note(a) }); break;
      case "set_wheel_color":
        d.wheelColor = { hex: a.color_hex, finish: a.finish };
        results.push({ label: `Wheels ${a.color_hex} (${a.finish})`, level: 1, applied: true, note: note(a) }); break;
      case "set_component_color":
        d.componentColors[a.component_id] = { hex: a.color_hex, finish: a.finish };
        results.push({ label: `${n} ${a.color_hex} (${a.finish})`, level: 1, applied: true, note: note(a) }); break;
      case "scale_component":
        d.scale[a.component_id] = [a.factor_x, a.factor_y, a.factor_z];
        results.push({ label: `${n} scaled ×${a.factor_x}/${a.factor_y}/${a.factor_z} (w/h/l)`, level: 2, applied: true, note: note(a) }); break;
      case "move_component":
        d.move[a.component_id] = [a.dx_cm, a.dy_cm, a.dz_cm];
        results.push({ label: `${n} moved ${sign(a.dx_cm)}/${sign(a.dy_cm)}/${sign(a.dz_cm)} cm (left/up/fwd)`, level: 2, applied: true, note: note(a) }); break;
      case "hide_component":
        d.hidden[a.component_id] = a.hidden;
        results.push({ label: `${n} ${a.hidden ? "removed" : "restored"}`, level: 2, applied: true, note: note(a) }); break;
      case "set_ride_height":
        d.rideHeightCm = a.offset_cm;
        results.push({ label: `Ride height ${sign(a.offset_cm)} cm`, level: 2, applied: true, note: note(a) }); break;
      case "set_wheel_size":
        d.wheelDeltaInches = a.delta_inches;
        results.push({ label: `Wheel size ${sign(a.delta_inches)}"`, level: 2, applied: true, note: note(a) }); break;
      case "set_body_proportions": {
        d.proportions = {
          frontOverhangCm: a.front_overhang_cm, rearOverhangCm: a.rear_overhang_cm, wheelbaseCm: a.wheelbase_cm,
          bodyWidthCm: a.body_width_cm, fenderFlareCm: a.fender_flare_cm, roofHeightCm: a.roof_height_cm,
        };
        const parts = (Object.keys(PROPORTION_LIMITS) as (keyof Proportions)[])
          .filter((k) => d.proportions[k]).map((k) => `${PROPORTION_LIMITS[k][2]} ${sign(d.proportions[k])} cm`);
        results.push({ label: `Body proportions: ${parts.join(", ") || "unchanged"}`, level: 2, applied: true, note: note(a) }); break;
      }
      case "set_track_width":
        d.trackWidthCm = a.offset_cm;
        results.push({ label: `Track width +${a.offset_cm} cm per side`, level: 2, applied: true, note: note(a) }); break;
    }
  }
  return { design: d, results };
}

export function isEmptyDesign(d: WebDesign) {
  return JSON.stringify(d) === JSON.stringify(EMPTY_DESIGN);
}
