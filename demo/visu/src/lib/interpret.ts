// Design prompt -> validated web actions, in the browser (port of visu_pro/backend/web_design.py).
// Inside Rowboat the prompt goes to the model configured in Rowboat (/_rowboat/llm/generate, app
// capability "llm"); without it (plain browser, LLM not configured) the keyword matcher answers.
import type { WebAction } from "./design";

export type Unsupported = { request: string; category: string; reason: string };
export type Proposal = { summary: string; actions: unknown[]; unsupported: Unsupported[] };
type Comp = { id: string; name: string };

const LIMITS: Record<string, [number, number]> = {
  factor: [0.7, 1.5], move: [-15, 15], ride: [-6, 6], wheel: [-1, 3], track: [0, 8],
  front_overhang_cm: [-10, 30], rear_overhang_cm: [-10, 30], wheelbase_cm: [-10, 30],
  body_width_cm: [0, 10], fender_flare_cm: [0, 10], roof_height_cm: [-8, 6],
};
const FINISHES = ["gloss", "metallic", "matte", "satin", "chrome", "carbon"];
const TYPES = ["set_body_color", "set_wheel_color", "set_component_color", "scale_component", "move_component",
  "hide_component", "set_ride_height", "set_wheel_size", "set_track_width", "set_body_proportions", "reset_design"];
const PROPORTIONS = ["front_overhang_cm", "rear_overhang_cm", "wheelbase_cm", "body_width_cm", "fender_flare_cm",
  "roof_height_cm"];

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

export function validateActions(actions: unknown[], components: Comp[]) {
  const lookup = new Map<string, string>();
  for (const c of components) { lookup.set(norm(c.id), c.id); lookup.set(norm(c.name), c.id); }
  const valid: WebAction[] = [], rejected: { action: unknown; error: string }[] = [];
  for (const raw of actions.slice(0, 16)) {
    if (!raw || typeof raw !== "object") { rejected.push({ action: raw, error: "not an action" }); continue; }
    const d: Record<string, unknown> = { ...(raw as Record<string, unknown>) };
    if (!TYPES.includes(String(d.type))) { rejected.push({ action: d, error: `unknown action '${d.type}'` }); continue; }
    const notes: string[] = [];
    const clamp = (k: string, limit: string, label: string) => {
      const [lo, hi] = LIMITS[limit], v = Number(d[k] ?? 0), c = Math.max(lo, Math.min(hi, Number.isFinite(v) ? v : 0));
      if (c !== v) notes.push(`${label} limited to ${c} (allowed ${lo}..${hi})`);
      d[k] = c;
    };
    if (d.component_id !== undefined) {
      const id = lookup.get(norm(String(d.component_id)));
      if (!id) { rejected.push({ action: d, error: `unknown component '${d.component_id}'` }); continue; }
      d.component_id = id;
    }
    if (d.color_hex !== undefined && !/^#[0-9a-fA-F]{6}$/.test(String(d.color_hex))) {
      rejected.push({ action: d, error: `invalid color '${d.color_hex}'` }); continue;
    }
    if (d.finish !== undefined && !FINISHES.includes(String(d.finish))) d.finish = "gloss";
    switch (d.type) {
      case "scale_component": ["factor_x", "factor_y", "factor_z"].forEach((k) => clamp(k, "factor", k)); break;
      case "move_component": ["dx_cm", "dy_cm", "dz_cm"].forEach((k) => clamp(k, "move", k)); break;
      case "set_ride_height": clamp("offset_cm", "ride", "ride height"); break;
      case "set_wheel_size": clamp("delta_inches", "wheel", "wheel size"); break;
      case "set_track_width": clamp("offset_cm", "track", "track width"); break;
      case "set_body_proportions": PROPORTIONS.forEach((k) => clamp(k, k, k.replace(/_/g, " "))); break;
      case "hide_component": d.hidden = d.hidden !== false; break;
    }
    if (notes.length) d.notes = notes;
    valid.push(d as unknown as WebAction);
  }
  return { valid, rejected };
}

function instructions(modelName: string, components: Comp[], selected: string | null) {
  const list = components.map((c) => `  - ${c.id}: ${c.name}`).join("\n");
  const sel = selected ? `\nThe user currently has '${selected}' selected; 'this part' refers to it.` : "";
  return `You are the design assistant of a web 3D car configurator showing a ${modelName}.
Translate the user's request into actions and answer with ONE JSON object only (no prose, no code fence):
{"summary": "1-3 sentences describing exactly what will change", "actions": [...], "unsupported": [{"request": "...", "category": "geometry_modification", "reason": "..."}]}

Actions (finish is one of gloss|metallic|matte|satin|chrome|carbon, colors as #RRGGBB):
LEVEL 1 - appearance:
- {"type":"set_body_color","color_hex","finish"}: the main body paint.
- {"type":"set_wheel_color","color_hex","finish"}: all four rims.
- {"type":"set_component_color","component_id","color_hex","finish"}: one component.
LEVEL 2 - shape (the car deforms as ONE connected shell):
- {"type":"set_body_proportions","front_overhang_cm","rear_overhang_cm","wheelbase_cm","body_width_cm","fender_flare_cm","roof_height_cm"}:
  overhangs and wheelbase -10..30, body width and flares 0..10 per side, roof -8..6; 0 = unchanged.
  Use THIS for longer/wider/lower-roof body or wide-body kits, never many scaled panels.
- {"type":"scale_component","component_id","factor_x","factor_y","factor_z"}: width/height/length factors 0.7-1.5.
- {"type":"move_component","component_id","dx_cm","dy_cm","dz_cm"}: left+/up+/forward+, each -15..15.
- {"type":"hide_component","component_id","hidden":true}
- {"type":"set_ride_height","offset_cm"}: -6..6, negative lowers.
- {"type":"set_wheel_size","delta_inches"}: -1..3.
- {"type":"set_track_width","offset_cm"}: 0..8 per side.
- {"type":"reset_design"}

Component ids (use exactly these):
${list}${sel}

Rules: translate words into concrete values ("a bit lower" -> -3 cm, "British racing green" -> #004225 metallic).
Never invent component ids or action types. Prefer few, coherent actions; keep scale factors within 0.85-1.25
and moves within 8 cm unless the user asks for extremes. New detailed geometry cannot be generated:
approximate the intent with moderate edits, say so in the summary and list the detail under "unsupported".`;
}

const COLORS: Record<string, string> = {
  "midnight blue": "#0c1d4f", navy: "#0c1d4f", "dark blue": "#0c1d4f", blue: "#1c4fb8",
  "racing red": "#b3060c", red: "#b3060c", white: "#e8e8e4", black: "#0b0c10",
  silver: "#a9acb2", grey: "#5a5d63", gray: "#5a5d63", green: "#0f5a2e",
  "british racing green": "#004225", yellow: "#e8c400", orange: "#e05a00", gold: "#b08a3a",
  bronze: "#8c6239", purple: "#4b2a7a",
};
const PARTS: Record<string, string[]> = {
  mirror: ["mirror-left", "mirror-right"], roof: ["roof"], spoiler: ["rear-spoiler"], grille: ["kidney-grille"],
  hood: ["hood"], splitter: ["front-splitter"], diffuser: ["rear-diffuser"], "front bumper": ["front-bumper"],
  "rear bumper": ["rear-bumper"],
};

export function keywordProposal(prompt: string): Proposal {
  const t = prompt.toLowerCase();
  let acts: Record<string, unknown>[] = [];
  const color = Object.entries(COLORS).sort((a, b) => b[0].length - a[0].length).find(([n]) => t.includes(n))?.[1];
  const finish = ["matte", "chrome", "carbon", "satin", "metallic"].find((f) => t.includes(f)) ?? "gloss";
  const part = Object.entries(PARTS).find(([n]) => t.includes(n))?.[1];
  const bodyWord = /\b(paint|car|body)\b/.test(t);
  if (color && part && !bodyWord) {
    acts.push(...part.map((c) => ({ type: "set_component_color", component_id: c, color_hex: color, finish })));
  } else if (color && /\b(wheel|wheels|rims?)\b/.test(t) && !bodyWord) {
    acts.push({ type: "set_wheel_color", color_hex: color, finish });
  } else if (color) {
    acts.push({ type: "set_body_color", color_hex: color, finish });
  }
  if (/\b(lower|lowered|slammed)\b/.test(t)) acts.push({ type: "set_ride_height", offset_cm: -3 });
  if (/\b(bigger|larger)\s+(wheel|wheels|rims?)\b/.test(t)) acts.push({ type: "set_wheel_size", delta_inches: 1 });
  if (/\b(wider|wide)\s+(stance|track)\b/.test(t)) acts.push({ type: "set_track_width", offset_cm: 3 });
  if (/\b(bigger|larger)\s+spoiler\b/.test(t))
    acts.push({ type: "scale_component", component_id: "rear-spoiler", factor_x: 1.1, factor_y: 1.4, factor_z: 1.3 });
  if (/\b(remove|delete|no)\s+(the\s+)?spoiler\b/.test(t))
    acts.push({ type: "hide_component", component_id: "rear-spoiler", hidden: true });
  const longer = /\b(longer|stretch|stretched|extended)\b/.test(t), wider = /\b(wide-?body|wider body|flares?)\b/.test(t);
  if (longer || wider) acts.push({ type: "set_body_proportions", front_overhang_cm: longer ? 10 : 0,
    rear_overhang_cm: longer ? 8 : 0, wheelbase_cm: longer ? 10 : 0, body_width_cm: 0,
    fender_flare_cm: wider ? 5 : 0, roof_height_cm: 0 });
  if (/\breset\b/.test(t)) acts = [{ type: "reset_design" }];
  const unsupported: Unsupported[] = /\b(redesign|sculpt|new shape|aggressive)\b/.test(t)
    ? [{ request: "freeform reshaping", category: "geometry_modification",
        reason: "New geometry cannot be generated; only scale/move/hide of existing parts." }] : [];
  return { summary: acts.length ? `Keyword matcher recognised ${acts.length} change(s).` : "No supported change recognised.",
    actions: acts, unsupported };
}

function parseJson(text: string): Proposal {
  const body = text.slice(text.indexOf("{"), text.lastIndexOf("}") + 1);
  const p = JSON.parse(body) as Partial<Proposal>;
  return { summary: String(p.summary ?? ""), actions: Array.isArray(p.actions) ? p.actions : [],
    unsupported: Array.isArray(p.unsupported) ? p.unsupported : [] };
}

/** Asks Rowboat's model; returns null if no LLM is reachable or its answer is unusable. */
export async function llmProposal(modelName: string, prompt: string, components: Comp[], selected: string | null) {
  try {
    const r = await fetch("/_rowboat/llm/generate", {
      method: "POST", headers: { "Content-Type": "application/json", "X-Rowboat-App": "1" },
      body: JSON.stringify({ system: instructions(modelName, components, selected), prompt, maxOutputTokens: 1500 }),
    });
    if (!r.ok) return null;
    const j = (await r.json()) as { text?: string; model?: string };
    return { proposal: parseJson(String(j.text ?? "")), engine: `Rowboat model${j.model ? ` (${j.model})` : ""}` };
  } catch {
    return null;
  }
}
