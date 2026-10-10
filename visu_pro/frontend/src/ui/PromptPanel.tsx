import { useState } from "react";
import { api, type PromptResponse } from "../api";
import type { CarModel, ScoredComponent } from "../models/types";
import type { ActionResult, WebAction } from "../lib/design";

const EXAMPLES = [
  ["Level 1", "Matte British racing green body, gloss black wheels and carbon mirrors"],
  ["Level 2", "Lower it 3 cm, 1 inch bigger wheels, wider stance and a 30% bigger rear spoiler"],
  ["Geometry", "Change the front bumper to a more aggressive design"],
];

export function PromptPanel({ model, selected, components, onApply, onReset }: {
  model: CarModel;
  selected: ScoredComponent | null;
  components: { id: string; name: string }[];
  onApply: (actions: WebAction[]) => ActionResult[];
  onReset: () => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ res: PromptResponse; applied: ActionResult[] } | null>(null);

  const submit = async () => {
    const text = prompt.trim();
    if (text.length < 3) { setError("Please describe a design change."); return; }
    setBusy(true); setError(null); setResult(null);
    try {
      const res = await api.prompt(model.id, text, selected ? { id: selected.id, name: selected.name } : null, components);
      setResult({ res, applied: onApply(res.actions) });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel prompt">
      <div className="panel-head"><h2>Design prompt</h2>
        {selected && <span className="tag">Context: {selected.name}</span>}</div>
      <textarea value={prompt} placeholder="Describe a design change..." rows={3}
        onChange={(e) => setPrompt(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit(); }} />
      <div className="prompt-actions">
        {EXAMPLES.map(([label, text]) => (
          <button key={label} className="link" onClick={() => setPrompt(text)}>Example: {label}</button>
        ))}
        <button className="ghost small-btn" onClick={() => { onReset(); setResult(null); }}>Reset design</button>
        <button className="primary" disabled={busy} onClick={submit}>{busy ? "Thinking…" : "Submit"}</button>
      </div>
      <div className="prompt-status" aria-live="polite">
        {error && <p className="err">{error}</p>}
        {!error && !result && !busy && <p className="muted small">
          Level 1: any color/finish on the body, wheels or a single part. Level 2: scale, move or remove parts,
          ride height, wheel size, track width. Brand-new geometry (sculpted bumpers etc.) is not generated.</p>}
        {result && (
          <>
            <p>{result.res.summary}</p>
            <ul className="status-list">
              {result.applied.map((a, i) => (
                <li key={i} className={a.applied ? "ok" : "err"}>
                  {a.applied ? "Applied in web viewer" : "Not applied"}
                  {a.level > 0 && <span className="lvl">L{a.level}</span>} {a.label}{a.note ? ` — ${a.note}` : ""}
                </li>
              ))}
              {result.res.rejected.map((r, i) => <li key={`r${i}`} className="err">Rejected · {r.error}</li>)}
              {result.res.unsupported.map((u, i) => (
                <li key={`u${i}`} className="warn">Proposed only · {u.request} — {u.reason}</li>
              ))}
              {!result.applied.length && !result.res.unsupported.length &&
                <li className="muted">No supported change found.</li>}
            </ul>
            <p className="muted small">Interpreter: {result.res.engine}</p>
          </>
        )}
      </div>
    </section>
  );
}
