import { useEffect, useMemo, useState } from "react";
import type { ComponentCategory, ScoredComponent } from "../models/types";
import type { FeedbackDetail } from "../api";
import { scoreToHex } from "../lib/heatmap";

/** Parts the design prompt can change visibly (colour, finish, shape); underbody and glass are left out. */
const DESIGN_CATEGORIES: ComponentCategory[] = ["Body panels", "Bumpers & aero", "Doors", "Lighting", "Wheels",
  "Trim & details", "Interior"];
const SKIP = new Set(["underbody", "pillars-sills"]);
const MIN_COMMENTS = 5;
const DEFAULT_PICK = 3;

const dominant = (d: FeedbackDetail) => {
  const neg: [string, number][] = [["difficult to use", d.counts["Difficult to Use"] ?? 0], ["defects", d.counts["Defect"] ?? 0],
    ["wants", d.counts["Wants"] ?? 0]];
  const [label, n] = neg.sort((a, b) => b[1] - a[1])[0];
  return n ? `mostly ${label} (${n})` : "few complaints";
};

/**
 * Design from customer feedback: the most criticised visible parts of the selected model and market (scores and
 * counts from the same data as the heat map), the top 3 ticked by default, turned into a design prompt that also
 * carries the agent's target for the purchase driver a part belongs to (Rowboat notes Requirements/).
 */
export function FeedbackDesign({ components, details, scope, targets, onPrompt }: {
  components: ScoredComponent[];
  details: (id: string) => FeedbackDetail | null;
  scope: string;
  targets: Record<string, string>;
  onPrompt: (text: string) => void;
}) {
  const items = useMemo(() => components
    .filter((c) => DESIGN_CATEGORIES.includes(c.category) && !SKIP.has(c.id))
    .map((c) => ({ c, d: details(c.id) }))
    .filter((x): x is { c: ScoredComponent; d: FeedbackDetail } =>
      !!x.d && x.d.basis === "specific" && (x.d.comments ?? x.d.n) >= MIN_COMMENTS)
    // left/right twins share their feedback: keep one entry per feedback signature
    .filter((x, i, all) => all.findIndex((y) => y.d.score === x.d.score && y.d.n === x.d.n
      && y.c.name.replace(/^(Left|Right|Front-left|Front-right|Rear-left|Rear-right) /i, "") === x.c.name.replace(/^(Left|Right|Front-left|Front-right|Rear-left|Rear-right) /i, "")) === i)
    .sort((a, b) => a.c.score - b.c.score)
    .slice(0, 8), [components, details]);

  const [picked, setPicked] = useState<string[]>([]);
  useEffect(() => { setPicked(items.slice(0, DEFAULT_PICK).map((x) => x.c.id)); }, [scope, items.map((x) => x.c.id).join()]); // eslint-disable-line react-hooks/exhaustive-deps

  const prompt = useMemo(() => {
    const sel = items.filter((x) => picked.includes(x.c.id));
    if (!sel.length) return "";
    const lines = sel.map((x, i) => {
      const name = x.c.name.replace(/^(Left|Right|Front-left|Front-right|Rear-left|Rear-right) /i, (m) => /wheel/i.test(x.c.name) ? "" : m);
      const t = targets[x.c.id];
      return `${i + 1}. ${name} (component ${x.c.id}): customer score ${x.c.score}/100, ${x.d.comments ?? x.d.n} comments, ${dominant(x.d)}`
        + `${x.d.classes.length ? `, about ${x.d.classes.slice(0, 3).join(", ")}` : ""}.${t ? ` Target: ${t}` : ""}`;
    });
    return `Redesign the ${scope} to answer the ${sel.length === 1 ? "most criticised design point" : `${sel.length} most criticised design points`} in the customer feedback:\n`
      + `${lines.join("\n")}\nMake clear, visible changes to these parts only (colour, finish, size, position, proportions); keep the rest of the car unchanged.`;
  }, [items, picked, scope, targets]);

  useEffect(() => { onPrompt(prompt); }, [prompt]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="panel feedback-design">
      <div className="panel-head"><h2>Design from customer feedback</h2><span className="tag">{scope}</span></div>
      {items.length ? (
        <ul className="fd-list">
          {items.map(({ c, d }) => (
            <li key={c.id}>
              <label>
                <input type="checkbox" checked={picked.includes(c.id)}
                  onChange={(e) => setPicked((p) => e.target.checked ? [...p, c.id] : p.filter((x) => x !== c.id))} />
                <span className="dot" style={{ background: scoreToHex(c.score) }} />
                <b>{c.name}</b>
                <span className="muted small">{c.score}/100 · {d.comments ?? d.n} comments · {dominant(d)}</span>
              </label>
            </li>
          ))}
        </ul>
      ) : <p className="muted small">Not enough feedback on visible parts for this model and market.</p>}
      <p className="muted small">The top {DEFAULT_PICK} are selected; the prompt below is written from your selection. Press Visualize to apply it.</p>
    </section>
  );
}
