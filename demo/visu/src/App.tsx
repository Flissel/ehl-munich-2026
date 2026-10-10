import { useCallback, useEffect, useMemo, useState } from "react";
import { CarViewer, LoadingOverlay, type CameraView, type ViewMode } from "./viewer/CarViewer";
import { MODELS, DEFAULT_MODEL_ID, SERIES_MODEL } from "./models/registry";
import type { ScoredComponent } from "./models/types";
import { getScores } from "./data/syntheticScores";
import { clampScore, LEGEND_GRADIENT } from "./lib/heatmap";
import type { SegmentationReport } from "./lib/segmentation";
import { applyWebActions, EMPTY_DESIGN, isEmptyDesign, type WebAction, type WebDesign } from "./lib/design";
import { ComponentPanel, SelectionCard } from "./ui/ComponentPanel";
import { PromptPanel } from "./ui/PromptPanel";
import { AdjustPanel } from "./ui/AdjustPanel";
import { FeedbackDesign } from "./ui/FeedbackDesign";
import { UnrealButton } from "./ui/UnrealButton";
import { api, type FeedbackScores, type UnrealDesign } from "./api";

type LoadState = { kind: "loading" } | { kind: "ready"; report: SegmentationReport } | { kind: "error"; message: string };
type Source = "ALL" | "F70" | "G60" | "G70" | "synthetic";
const SOURCES: [Source, string][] = [
  ["ALL", "Customer feedback · all series"], ["F70", "Customer feedback · 1 Series F70"],
  ["G60", "Customer feedback · 5 Series G60"], ["G70", "Customer feedback · 7 Series G70"],
  ["synthetic", "Synthetic demo scores"],
];
const MARKETS: [string, string][] = [["", "All markets"], ["EU", "Europe"], ["CN", "China"], ["US", "USA"], ["RoW", "Rest of world"]];
/** Below this many comments a market's heat map is not meaningful; the series' all-market data is shown instead. */
const MIN_ROWS = 20;

const toSource = (s: string | null | undefined): Source =>
  (["F70", "G60", "G70", "synthetic"].includes(s ?? "") ? s as Source : "ALL");

// Embedded in Torque's Concept 3D (?embed=1): Torque owns model, market, the purchase driver list and the
// info card. Torque -> app: {type: "visu:context", series, market, title, focus, focusSignal}.
// App -> Torque: {type: "visu:ready"} and {type: "visu:select", ...} whenever a part is selected.
// Cars imported into the Unreal project (visu_pro/unreal); the X1/X5/X7 are not yet.
const UNREAL_MODELS: string[] = [];
const PARAMS = new URLSearchParams(location.search);
const EMBED = PARAMS.has("embed");
/** Scores Torque computes itself where no comments exist (China: its customer study per purchase driver). */
type Override = { label: string; note?: string; scores: Record<string, number> };
type Context = { series: string | null; market: string; title: string; focus: string | null; focusSignal: number;
  override?: Override | null };
/** Part data from Rowboat's vault (demo/visu/vault.py sync -> data/visu.json): heat rows keyed "MODEL|MARKET". */
type VaultRow = { score: number | null; comments: number | null; n: number | null; counts: Record<string, number>; positive_share: number | null };
type Vault = { generated?: string; parts: Record<string, { note: string; heat: Record<string, VaultRow> }> };
const post = (msg: unknown) => { if (EMBED) window.parent.postMessage(msg, location.origin); };

export default function App() {
  const [ctx, setCtx] = useState<Context>({ series: PARAMS.get("series"), market: PARAMS.get("market") ?? "",
    title: "", focus: null, focusSignal: 0 });
  const [source, setSource] = useState<Source>(() => toSource(PARAMS.get("series")));
  // The car of the selected model family (X1 / X5 / X7); switching series loads that car.
  const model = MODELS[SERIES_MODEL[source === "synthetic" ? "ALL" : source] ?? DEFAULT_MODEL_ID];
  const [feedback, setFeedback] = useState<FeedbackScores | null>(null);
  const [fallback, setFallback] = useState<string | null>(null);
  const [synthetic, setSynthetic] = useState<Record<string, number>>({});
  const [scoreError, setScoreError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setMode] = useState<ViewMode>("heatmap");
  const [design, setDesign] = useState<WebDesign>(EMPTY_DESIGN);
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });
  const [resetSignal, setResetSignal] = useState(0);
  const [view, setView] = useState<CameraView>("exterior");
  const [panel, setPanel] = useState(false);
  const [vault, setVault] = useState<Vault | null>(null);
  const [preset, setPreset] = useState({ text: "", key: 0 });
  const [showOriginal, setShowOriginal] = useState(false);
  const [targets, setTargets] = useState<Record<string, string>>({});

  // Agent targets per part: graph.json links parts to purchase drivers, texts carry the agent's target per driver.
  useEffect(() => {
    const get = (u: string) => fetch(u, { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    Promise.all([get("graph.json"), get("data/texts.json").then((t) => t ?? get("../texts.seed.json"))]).then(([g, t]) => {
      if (!g || !t) return;
      const out: Record<string, string> = {};
      for (const [pid, p] of Object.entries(g.parts as Record<string, { drivers: string[] }>)) {
        const target = p.drivers.map((d) => t.requirements?.[d]?.target).find(Boolean);
        if (target) out[pid] = target;
      }
      setTargets(out);
    });
  }, []);

  // Rowboat is the source of the part data: re-read the synced vault every few seconds.
  useEffect(() => {
    let last = "";
    const read = () => fetch("data/visu.json", { cache: "no-store" }).then((r) => (r.ok ? r.json() : null))
      .then((v: Vault | null) => { if (v && v.generated !== last) { last = v.generated ?? ""; setVault(v); } }).catch(() => {});
    read();
    const t = window.setInterval(read, 3000);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      if (e.origin !== location.origin || e.data?.type !== "visu:context") return;
      const d = e.data as Partial<Context> & { type: string };
      setCtx((c) => ({ ...c, ...d }));
      if (d.series !== undefined) setSource(toSource(d.series));
    };
    window.addEventListener("message", onMsg);
    post({ type: "visu:ready" });
    return () => window.removeEventListener("message", onMsg);
  }, []);

  // A purchase driver picked in Torque: select its part and fly to it (interior parts in the cutaway).
  useEffect(() => {
    if (!ctx.focusSignal) return;
    setSelectedId(ctx.focus);
    const comp = model.components.find((c) => c.id === ctx.focus);
    if (comp?.category === "Interior" && view === "exterior") setView("cutaway");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.focusSignal]);

  useEffect(() => { getScores(model.id).then(setSynthetic); }, [model.id]);
  useEffect(() => { setLoad({ kind: "loading" }); setSelectedId(null); }, [model.id]);
  useEffect(() => {
    if (source === "synthetic") { setScoreError(null); setFallback(null); return; }
    let cancelled = false, timer: number | undefined;
    const series = source === "ALL" ? null : source, market = ctx.market || null;
    const load = async () => {
      try {
        let f = await api.feedbackScores(series, market), note: string | null = null;
        if (market && f.rows_used < MIN_ROWS) {
          note = `${f.rows_used} owner comments for ${f.market_label} in the Dataset: showing all markets of this series`;
          f = await api.feedbackScores(series, null);
        }
        if (!cancelled) { setFeedback(f); setFallback(note); setScoreError(null); }
      } catch (e) {
        if (cancelled) return;
        setScoreError(`${e instanceof Error ? e.message : e} — showing synthetic demo scores (retrying).`);
        timer = window.setTimeout(load, 4000);
      }
    };
    load();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [source, ctx.market]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setSelectedId(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const override = EMBED ? ctx.override ?? null : null;
  const usingFeedback = !override && source !== "synthetic" && feedback !== null && !scoreError;
  const vaultKey = `${source === "ALL" ? "ALL" : source}|${fallback || !ctx.market ? "ALL" : ctx.market}`;
  const vaultRows = useMemo(() => {
    if (!vault || override || source === "synthetic") return null;
    const rows = Object.fromEntries(Object.entries(vault.parts).map(([id, p]) => [id, p.heat[vaultKey]]).filter(([, r]) => r));
    return Object.keys(rows).length ? rows as Record<string, VaultRow> : null;
  }, [vault, vaultKey, override, source]);
  const scores = useMemo(() => {
    if (override) return override.scores;
    if (vaultRows) return Object.fromEntries(Object.entries(vaultRows).map(([k, r]) => [k, r.score ?? 50]));
    if (!usingFeedback) return synthetic;
    return Object.fromEntries(Object.entries(feedback!.components).map(([k, v]) => [k, v.score]));
  }, [override, vaultRows, usingFeedback, feedback, synthetic]);
  const dataLabel = override ? override.label : usingFeedback
    ? `${feedback!.series_label} · ${fallback ? "all markets" : feedback!.market_label ?? "all markets"} · ` +
      `${(feedback!.comments ?? feedback!.rows_used).toLocaleString()} comments`
    : "synthetic demo scores";
  const note = override ? override.note ?? null : fallback;
  const fromVault = vaultRows ? " · data from Rowboat" : "";
  const sourceLabel = usingFeedback ? `customer feedback (${dataLabel})` : "synthetic demo score";

  // Only components that were actually found in the model are listed/scored.
  const components: ScoredComponent[] = useMemo(() => {
    const mapped = load.kind === "ready" ? load.report.components : null;
    return model.components
      .filter((c) => !mapped || mapped[c.id])
      .map((c) => ({ ...c, score: clampScore(scores[c.id] ?? 50) }));
  }, [model, scores, load]);
  const selected = components.find((c) => c.id === selectedId) ?? null;

  // Tell Torque what is selected, with the part's feedback, so its info card shows the same data.
  useEffect(() => {
    if (load.kind !== "ready") return;
    post({ type: "visu:select", id: selected?.id ?? null, name: selected?.name ?? null,
      category: selected?.category ?? null, score: selected?.score ?? null, data: dataLabel + fromVault, fallback: note,
      detail: selected && (usingFeedback || vaultRows) ? partDetail(selected.id) : null });
  }, [selected?.id, selected?.score, dataLabel, note, load.kind, vaultRows]); // eslint-disable-line react-hooks/exhaustive-deps

  // Counts from the vault (edited in Rowboat), quotes only from the local feedback file (never in the vault).
  function partDetail(id: string) {
    const fb = feedback?.components[id], v = vaultRows?.[id];
    if (!v) return fb ?? null;
    return { ...(fb ?? { basis: "specific", classes: [], quotes: [] }), score: v.score ?? 50, comments: v.comments ?? undefined,
      n: v.n ?? 0, counts: v.counts, positive_share: v.positive_share ?? 0 };
  }

  const onLoaded = useCallback((report: SegmentationReport) => setLoad({ kind: "ready", report }), []);
  const onError = useCallback((message: string) => setLoad({ kind: "error", message }), []);

  const applyActions = (actions: WebAction[]) => {
    const { design: next, results } = applyWebActions(model, design, actions);
    setDesign(next);
    setShowOriginal(false);
    if (results.some((r) => r.applied && r.level === 1)) setMode("design");
    return results;
  };

  // The Unreal viewer only knows paint / wheel presets: send them when the web design matches one.
  const unrealDesign: UnrealDesign = {
    paint: model.design.paints.find((p) => p.hex.toLowerCase() === design.bodyColor?.hex.toLowerCase())?.id ?? null,
    wheel_style: model.design.wheels.find((w) => w.hex.toLowerCase() === design.wheelColor?.hex.toLowerCase())?.id ?? null,
  };

  const report = load.kind === "ready" ? load.report : null;
  const viewer = (
    <div className="viewer">
      <CarViewer key={model.id} model={model} scores={scores} mode={mode} design={showOriginal ? EMPTY_DESIGN : design} selectedId={selectedId}
        onSelect={setSelectedId} onLoaded={onLoaded} onError={onError} resetSignal={resetSignal} view={view}
        focusId={ctx.focus} focusSignal={ctx.focusSignal} />
      {load.kind === "loading" && <LoadingOverlay />}
      {load.kind === "error" && <div className="viewer-error">{load.message}</div>}
      {EMBED && (
        <div className="embed-head">
          <b>{ctx.title || model.displayName}</b>
          <span>{dataLabel}{fromVault}</span>
          {note && <span className="warn">{note}</span>}
          <span className="muted">3D car: {model.displayName} (stand-in)</span>
        </div>
      )}
      <div className="viewer-toolbar">
        <div className="segmented">
          <button className={mode === "heatmap" ? "on" : ""} onClick={() => setMode("heatmap")}>Heat map</button>
          <button className={mode === "design" ? "on" : ""} onClick={() => { setMode("design"); if (EMBED) setPanel(true); }}>Design</button>
        </div>
        <div className="segmented">
          {([["exterior", "Exterior"], ["interior", "Interior"], ["cutaway", "Cutaway"]] as [CameraView, string][]).map(([v, l]) => (
            <button key={v} className={view === v ? "on" : ""} onClick={() => { setView(v); setResetSignal((n) => n + 1); }}>{l}</button>
          ))}
        </div>
        <button className="ghost" onClick={() => setResetSignal((n) => n + 1)}>Reset camera</button>
        {EMBED && <button className={panel ? "ghost on" : "ghost"} onClick={() => setPanel((p) => !p)}>Design prompt</button>}
      </div>
      {mode === "heatmap" && (
        <div className="legend">
          <div className="legend-title">{override ? "Customer study (relative)" : usingFeedback ? "Customer sentiment (relative)" : "Demo scores (synthetic)"}</div>
          <div className="legend-bar" style={{ background: LEGEND_GRADIENT }} />
          <div className="legend-labels">
            <span>{usingFeedback || override ? "0 — Most criticised" : "0 — Low"}</span><span>50</span>
            <span>{usingFeedback || override ? "100 — Best rated" : "100 — High"}</span>
          </div>
        </div>
      )}
      {mode === "design" && (
        <div className="legend design-legend">
          Design view{isEmptyDesign(design) ? " · original car" : showOriginal ? " · original (compare)" : " · adjusted (Level 1/2 changes applied)"}
        </div>
      )}
      {!isEmptyDesign(design) && (
        <div className="compare segmented" role="group" aria-label="Compare">
          <button className={showOriginal ? "on" : ""} onClick={() => setShowOriginal(true)}>Original</button>
          <button className={showOriginal ? "" : "on"} onClick={() => setShowOriginal(false)}>Adjusted</button>
        </div>
      )}
      {EMBED && <div className="embed-unreal"><UnrealButton modelId={model.id} design={unrealDesign} unavailable={UNREAL_MODELS.includes(model.id) ? undefined : "Not imported in Unreal yet"} /></div>}
      {EMBED && panel && (
        <div className="embed-panel">
          <button className="ghost close" onClick={() => setPanel(false)} aria-label="Close">✕</button>
          <FeedbackDesign components={components} details={partDetail} targets={targets}
            scope={EMBED && ctx.title ? ctx.title.replace(" · ", " successor, ").replace(" successor successor", " successor") : (feedback ? `${feedback.series_label} · ${fallback ? "all markets" : feedback.market_label ?? "all markets"}` : model.displayName)}
            onPrompt={(text) => setPreset((p) => ({ text, key: p.key + 1 }))} />
          <PromptPanel model={model} selected={selected} components={components.map((c) => ({ id: c.id, name: c.name }))}
            onApply={applyActions} onReset={() => { setDesign(EMPTY_DESIGN); setShowOriginal(false); }} preset={preset} />
          <AdjustPanel design={design} selected={selected} onChange={setDesign} />
        </div>
      )}
    </div>
  );

  if (EMBED) return <div className="app embed">{viewer}</div>;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand"><span className="logo">◐</span> BMW Design Studio</div>
        <div className="model-label">{model.displayName}</div>
        <div className={`load-status ${load.kind}`}>
          <span className="dot" />
          {load.kind === "loading" ? "Loading model…" : load.kind === "ready" ? "Model loaded" : "Model failed to load"}
        </div>
        <UnrealButton modelId={model.id} design={unrealDesign} unavailable={UNREAL_MODELS.includes(model.id) ? undefined : "Not imported in Unreal yet"} />
      </header>

      <main className="layout">
        <section className="viewer-wrap">
          {viewer}
          <SelectionCard component={selected} sourceLabel={sourceLabel} onClear={() => setSelectedId(null)}
            detail={usingFeedback && selected ? feedback!.components[selected.id] : undefined} />
          <FeedbackDesign components={components} details={partDetail} targets={targets}
            scope={EMBED && ctx.title ? ctx.title.replace(" · ", " successor, ").replace(" successor successor", " successor") : (feedback ? `${feedback.series_label} · ${fallback ? "all markets" : feedback.market_label ?? "all markets"}` : model.displayName)}
            onPrompt={(text) => setPreset((p) => ({ text, key: p.key + 1 }))} />
          <PromptPanel model={model} selected={selected} components={components.map((c) => ({ id: c.id, name: c.name }))}
            onApply={applyActions} onReset={() => { setDesign(EMPTY_DESIGN); setShowOriginal(false); }} preset={preset} />
          <AdjustPanel design={design} selected={selected} onChange={setDesign} />
        </section>

        <aside className="side">
          <div className="panel source">
            <label className="small muted" htmlFor="source">Heat map data</label>
            <select id="source" value={source} onChange={(e) => setSource(e.target.value as Source)}>
              {SOURCES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <select aria-label="Market" value={ctx.market} onChange={(e) => setCtx((c) => ({ ...c, market: e.target.value }))}>
              {MARKETS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            {scoreError && <p className="err small">{scoreError}</p>}
            {fallback && <p className="small warn">{fallback}</p>}
            {usingFeedback && (
              <p className="muted small">
                {feedback!.rows_used.toLocaleString()} classified comments from the EHL dataset. The 1/5/7 Series
                feedback is shown on {model.displayName} as the stand-in for this model family. Score = rank of positive share among parts.
              </p>
            )}
          </div>
          <ComponentPanel components={components} selectedId={selectedId} onSelect={setSelectedId}
            preferredCategory={view === "exterior" ? "All" : "Interior"}
            tag={usingFeedback ? `Feedback · ${feedback!.series}` : "Synthetic scores"} />
          {usingFeedback && feedback!.no_geometry.length > 0 && (
            <div className="panel note small">
              Feedback without a 3D part in this model:{" "}
              {feedback!.no_geometry.map((g) => `${g.feature} (${g.n} comments, ${g.positive_share}% positive; ${g.reason})`).join(" · ")}
            </div>
          )}
          {report && (report.unmapped.length > 0 || report.missingNodes.length > 0) && (
            <div className="panel note small">
              Not found in this model: {[...report.unmapped, ...report.missingNodes].join(", ")}
            </div>
          )}
          <p className="credit small muted">
            Model: {model.credit}. Non-commercial use only.
          </p>
        </aside>
      </main>
    </div>
  );
}
