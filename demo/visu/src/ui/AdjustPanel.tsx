import type { ScoredComponent } from "../models/types";
import {
  FINISH_PARAMS, PROPORTION_LIMITS, type ColorSpec, type Finish, type Proportions, type Vec3, type WebDesign,
} from "../lib/design";

const FINISHES = Object.keys(FINISH_PARAMS) as Finish[];

function Slider({ label, value, min, max, step, unit, onChange }: {
  label: string; value: number; min: number; max: number; step: number; unit: string; onChange: (v: number) => void;
}) {
  return (
    <label className="slider">
      <span className="slider-label">{label}</span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <span className="slider-value">{value > 0 && unit !== "×" ? "+" : ""}{unit === "×" ? `×${value.toFixed(2)}` : `${value}${unit}`}</span>
    </label>
  );
}

function ColorRow({ label, spec, onChange }: { label: string; spec: ColorSpec | null; onChange: (s: ColorSpec | null) => void }) {
  const cur = spec ?? { hex: "#808080", finish: "gloss" as Finish };
  return (
    <div className="color-row">
      <span className="slider-label">{label}</span>
      <input type="color" value={cur.hex} onChange={(e) => onChange({ ...cur, hex: e.target.value })} />
      <select value={cur.finish} onChange={(e) => onChange({ ...cur, finish: e.target.value as Finish })}>
        {FINISHES.map((f) => <option key={f}>{f}</option>)}
      </select>
      <button className="link" disabled={!spec} onClick={() => onChange(null)}>original</button>
    </div>
  );
}

/** Manual Level 1 / Level 2 controls; edits the same design state the AI prompt produces. */
export function AdjustPanel({ design, selected, onChange }: {
  design: WebDesign;
  selected: ScoredComponent | null;
  onChange: (d: WebDesign) => void;
}) {
  const set = (patch: Partial<WebDesign>) => onChange({ ...design, ...patch });
  const setProp = (k: keyof Proportions, v: number) => set({ proportions: { ...design.proportions, [k]: v } });
  const id = selected?.id;
  const scale: Vec3 = (id && design.scale[id]) || [1, 1, 1];
  const move: Vec3 = (id && design.move[id]) || [0, 0, 0];
  const setVec = (key: "scale" | "move", i: number, v: number) => {
    if (!id) return;
    const cur = [...(key === "scale" ? scale : move)] as Vec3;
    cur[i] = v;
    set({ [key]: { ...design[key], [id]: cur } } as Partial<WebDesign>);
  };
  const resetPart = () => {
    if (!id) return;
    const strip = <T,>(r: Record<string, T>) => Object.fromEntries(Object.entries(r).filter(([k]) => k !== id));
    set({ scale: strip(design.scale), move: strip(design.move), hidden: strip(design.hidden), componentColors: strip(design.componentColors) });
  };

  return (
    <section className="panel adjust">
      <div className="panel-head"><h2>Adjust</h2><span className="muted small">changes show in both views</span></div>

      {selected ? (
        <div className="adjust-group">
          <div className="adjust-title">
            <strong>{selected.name}</strong>
            <button className="link" onClick={resetPart}>reset part</button>
          </div>
          <ColorRow label="Color (L1)" spec={design.componentColors[selected.id] ?? null}
            onChange={(s) => {
              const cc = { ...design.componentColors };
              if (s) cc[selected.id] = s; else delete cc[selected.id];
              set({ componentColors: cc });
            }} />
          {selected.category !== "Wheels" && <p className="muted small">Shape edits blend smoothly into the neighbouring panels.</p>}
          {(["Width", "Height", "Length"] as const).map((l, i) => (
            <Slider key={l} label={`${l} (L2)`} value={scale[i]} min={0.7} max={1.5} step={0.01} unit="×" onChange={(v) => setVec("scale", i, v)} />
          ))}
          {(["Left/right", "Up/down", "Fwd/back"] as const).map((l, i) => (
            <Slider key={l} label={`${l} (L2)`} value={move[i]} min={-15} max={15} step={0.5} unit=" cm" onChange={(v) => setVec("move", i, v)} />
          ))}
          <label className="check">
            <input type="checkbox" checked={!!design.hidden[selected.id]}
              onChange={(e) => set({ hidden: { ...design.hidden, [selected.id]: e.target.checked } })} /> Remove part (L2)
          </label>
        </div>
      ) : <p className="muted small">Select a part to color, scale, move or remove it.</p>}

      <div className="adjust-group">
        <div className="adjust-title"><strong>Whole car</strong></div>
        <ColorRow label="Body paint (L1)" spec={design.bodyColor} onChange={(s) => set({ bodyColor: s })} />
        <ColorRow label="Wheels (L1)" spec={design.wheelColor} onChange={(s) => set({ wheelColor: s })} />
        {(Object.keys(PROPORTION_LIMITS) as (keyof Proportions)[]).map((k) => (
          <Slider key={k} label={PROPORTION_LIMITS[k][2]} value={design.proportions[k]} min={PROPORTION_LIMITS[k][0]}
            max={PROPORTION_LIMITS[k][1]} step={0.5} unit=" cm" onChange={(v) => setProp(k, v)} />
        ))}
        <Slider label="Ride height" value={design.rideHeightCm} min={-6} max={6} step={0.5} unit=" cm" onChange={(v) => set({ rideHeightCm: v })} />
        <Slider label="Wheel size" value={design.wheelDeltaInches} min={-1} max={3} step={0.5} unit={'"'} onChange={(v) => set({ wheelDeltaInches: v })} />
        <Slider label="Track width (per side)" value={design.trackWidthCm} min={0} max={8} step={0.5} unit=" cm" onChange={(v) => set({ trackWidthCm: v })} />
      </div>
    </section>
  );
}
