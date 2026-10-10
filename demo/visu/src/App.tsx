import { useCallback, useEffect, useMemo, useState } from "react";
import { CarViewer, LoadingOverlay, type CameraView, type ViewMode } from "./viewer/CarViewer";
import { MODELS, DEFAULT_MODEL_ID } from "./models/registry";
import type { ScoredComponent } from "./models/types";
import { getScores } from "./data/syntheticScores";
import { clampScore, LEGEND_GRADIENT } from "./lib/heatmap";
import type { SegmentationReport } from "./lib/segmentation";
import { applyWebActions, EMPTY_DESIGN, isEmptyDesign, type WebAction, type WebDesign } from "./lib/design";
import { ComponentPanel, SelectionCard } from "./ui/ComponentPanel";
import { PromptPanel } from "./ui/PromptPanel";
import { AdjustPanel } from "./ui/AdjustPanel";
import { api, type FeedbackScores } from "./api";

type LoadState = { kind: "loading" } | { kind: "ready"; report: SegmentationReport } | { kind: "error"; message: string };
type Source = "ALL" | "F70" | "G60" | "G70" | "synthetic";
const SOURCES: [Source, string][] = [
  ["ALL", "Customer feedback · all series"], ["F70", "Customer feedback · 1 Series F70"],
  ["G60", "Customer feedback · 5 Series G60"], ["G70", "Customer feedback · 7 Series G70"],
  ["synthetic", "Synthetic demo scores"],
];

// Torque embeds this app and passes the model it shows: ?series=F70|G60|G70 (G68 and others -> ALL),
// later changes arrive as postMessage {type: "visu:series", series}.
const toSource = (s: string | null): Source => (["F70", "G60", "G70", "synthetic"].includes(s ?? "") ? s as Source : "ALL");
const EMBED = new URLSearchParams(location.search).has("embed");

export default function App() {
  const model = MODELS[DEFAULT_MODEL_ID];
  const [source, setSource] = useState<Source>(() => toSource(new URLSearchParams(location.search).get("series")));
  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      if (e.origin === location.origin && e.data?.type === "visu:series") setSource(toSource(e.data.series));
    };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, []);
  const [feedback, setFeedback] = useState<FeedbackScores | null>(null);
  const [synthetic, setSynthetic] = useState<Record<string, number>>({});
  const [scoreError, setScoreError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setMode] = useState<ViewMode>("heatmap");
  const [design, setDesign] = useState<WebDesign>(EMPTY_DESIGN);
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });
  const [resetSignal, setResetSignal] = useState(0);
  const [view, setView] = useState<CameraView>("exterior");

  useEffect(() => { getScores(model.id).then(setSynthetic); }, [model.id]);
  useEffect(() => {
    if (source === "synthetic") { setScoreError(null); return; }
    let cancelled = false, timer: number | undefined;
    setFeedback(null);
    const load = () => api.feedbackScores(source === "ALL" ? null : source)
      .then((f) => { if (!cancelled) { setFeedback(f); setScoreError(null); } })
      .catch((e) => {
        if (cancelled) return;
        setScoreError(`${e instanceof Error ? e.message : e} — showing synthetic demo scores (retrying).`);
        timer = window.setTimeout(load, 4000);
      });
    load();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [source]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setSelectedId(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const usingFeedback = source !== "synthetic" && feedback !== null && !scoreError;
  const scores = useMemo(() => {
    if (!usingFeedback) return synthetic;
    return Object.fromEntries(Object.entries(feedback!.components).map(([k, v]) => [k, v.score]));
  }, [usingFeedback, feedback, synthetic]);
  const sourceLabel = usingFeedback ? `customer feedback (${feedback!.series_label})` : "synthetic demo score";

  // Only components that were actually found in the model are listed/scored.
  const components: ScoredComponent[] = useMemo(() => {
    const mapped = load.kind === "ready" ? load.report.components : null;
    return model.components
      .filter((c) => !mapped || mapped[c.id])
      .map((c) => ({ ...c, score: clampScore(scores[c.id] ?? 50) }));
  }, [model, scores, load]);
  const selected = components.find((c) => c.id === selectedId) ?? null;

  const onLoaded = useCallback((report: SegmentationReport) => setLoad({ kind: "ready", report }), []);
  const onError = useCallback((message: string) => setLoad({ kind: "error", message }), []);

  const applyActions = (actions: WebAction[]) => {
    const { design: next, results } = applyWebActions(model, design, actions);
    setDesign(next);
    if (results.some((r) => r.applied && r.level === 1)) setMode("design");
    return results;
  };

  const report = load.kind === "ready" ? load.report : null;
  return (
    <div className={EMBED ? "app embed" : "app"}>
      <header className="topbar">
        <div className="brand"><span className="logo">◐</span> BMW Design Studio</div>
        <div className="model-label">{model.displayName}</div>
        <div className={`load-status ${load.kind}`}>
          <span className="dot" />
          {load.kind === "loading" ? "Loading model…" : load.kind === "ready" ? "Model loaded" : "Model failed to load"}
        </div>
      </header>

      <main className="layout">
        <section className="viewer-wrap">
          <div className="viewer">
            <CarViewer model={model} scores={scores} mode={mode} design={design} selectedId={selectedId}
              onSelect={setSelectedId} onLoaded={onLoaded} onError={onError} resetSignal={resetSignal} view={view} />
            {load.kind === "loading" && <LoadingOverlay />}
            {load.kind === "error" && <div className="viewer-error">{load.message}</div>}
            <div className="viewer-toolbar">
              <div className="segmented">
                <button className={mode === "heatmap" ? "on" : ""} onClick={() => setMode("heatmap")}>Heat map</button>
                <button className={mode === "design" ? "on" : ""} onClick={() => setMode("design")}>Design</button>
              </div>
              <div className="segmented">
                {([["exterior", "Exterior"], ["interior", "Interior"], ["cutaway", "Cutaway"]] as [CameraView, string][]).map(([v, l]) => (
                  <button key={v} className={view === v ? "on" : ""} onClick={() => { setView(v); setResetSignal((n) => n + 1); }}>{l}</button>
                ))}
              </div>
              <button className="ghost" onClick={() => setResetSignal((n) => n + 1)}>Reset camera</button>
            </div>
            {mode === "heatmap" && (
              <div className="legend">
                <div className="legend-title">{usingFeedback ? "Customer sentiment (relative)" : "Demo scores (synthetic)"}</div>
                <div className="legend-bar" style={{ background: LEGEND_GRADIENT }} />
                <div className="legend-labels">
                  <span>{usingFeedback ? "0 — Most criticised" : "0 — Low"}</span><span>50</span>
                  <span>{usingFeedback ? "100 — Best rated" : "100 — High"}</span>
                </div>
              </div>
            )}
            {mode === "design" && (
              <div className="legend design-legend">
                Design view{isEmptyDesign(design) ? " · original car" : " · modified (Level 1/2 changes applied)"}
              </div>
            )}
          </div>
          <SelectionCard component={selected} sourceLabel={sourceLabel} onClear={() => setSelectedId(null)}
            detail={usingFeedback && selected ? feedback!.components[selected.id] : undefined} />
          <PromptPanel model={model} selected={selected} components={components.map((c) => ({ id: c.id, name: c.name }))}
            onApply={applyActions} onReset={() => setDesign(EMPTY_DESIGN)} />
          <AdjustPanel design={design} selected={selected} onChange={setDesign} />
        </section>

        <aside className="side">
          <div className="panel source">
            <label className="small muted" htmlFor="source">Heat map data</label>
            <select id="source" value={source} onChange={(e) => setSource(e.target.value as Source)}>
              {SOURCES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            {scoreError && <p className="err small">{scoreError}</p>}
            {usingFeedback && (
              <p className="muted small">
                {feedback!.rows_used.toLocaleString()} classified comments from the EHL dataset. The 1/5/7 Series
                feedback is mapped onto this M4 model as a stand-in. Score = rank of positive share among parts.
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
