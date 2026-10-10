import { useEffect, useMemo, useState } from "react";
import type { ScoredComponent } from "../models/types";
import { scoreToHex } from "../lib/heatmap";
import type { FeedbackDetail } from "../api";

type Sort = "score-asc" | "score-desc" | "name";

export function ComponentPanel({ components, selectedId, onSelect, tag, preferredCategory }: {
  components: ScoredComponent[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  tag: string;
  preferredCategory?: string;
}) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [sort, setSort] = useState<Sort>("score-asc");
  useEffect(() => { if (preferredCategory) setCategory(preferredCategory); }, [preferredCategory]);
  const categories = useMemo(() => ["All", ...new Set(components.map((c) => c.category))], [components]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = components.filter((c) => (category === "All" || c.category === category) &&
      (!q || c.name.toLowerCase().includes(q) || c.nodeNames.some((n) => n.toLowerCase().includes(q))));
    return list.sort((a, b) => sort === "name" ? a.name.localeCompare(b.name)
      : sort === "score-asc" ? a.score - b.score : b.score - a.score);
  }, [components, query, category, sort]);

  return (
    <section className="panel components">
      <div className="panel-head">
        <h2>Components <span className="muted">({components.length})</span></h2>
        <span className="tag">{tag}</span>
      </div>
      <div className="filters">
        <input type="search" placeholder="Search components…" value={query} onChange={(e) => setQuery(e.target.value)} />
        <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category">
          {categories.map((c) => <option key={c}>{c}</option>)}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort">
          <option value="score-asc">Score ↑</option>
          <option value="score-desc">Score ↓</option>
          <option value="name">Name</option>
        </select>
      </div>
      <ul className="component-list">
        {rows.map((c) => (
          <li key={c.id}>
            <button className={c.id === selectedId ? "row selected" : "row"}
              onClick={() => onSelect(c.id === selectedId ? null : c.id)}>
              <span className="swatch" style={{ background: scoreToHex(c.score) }} />
              <span className="row-name">{c.name}{c.segmentation === "spatial" && <span className="approx" title="Carved out of a larger mesh by position (approximate)">≈</span>}</span>
              <span className="row-score">{c.score}</span>
            </button>
          </li>
        ))}
        {!rows.length && <li className="muted empty">No matching components.</li>}
      </ul>
    </section>
  );
}

export function SelectionCard({ component, detail, sourceLabel, onClear }: {
  component: ScoredComponent | null;
  detail?: FeedbackDetail;
  sourceLabel: string;
  onClear: () => void;
}) {
  if (!component) return <div className="selection-card muted">Click a part of the car or a list entry to inspect it.</div>;
  return (
    <div className="selection-card column">
      <div className="selection-row">
        <span className="badge" style={{ background: scoreToHex(component.score) }}>{component.score}</span>
        <div className="selection-text">
          <strong>{component.name}</strong>
          <span className="muted small">
            {component.category} · {sourceLabel} · nodes: {component.nodeNames.join(", ")}
            {component.segmentation === "spatial" && " · approximate region"}
          </span>
        </div>
        <button className="ghost" onClick={onClear} title="Deselect (Esc)">✕</button>
      </div>
      {detail && (
        <div className="feedback-detail small">
          {detail.basis === "specific" ? (
            <span>{detail.n} customer comments · {Object.entries(detail.counts).map(([k, v]) => `${v} ${k}`).join(" · ")} ·
              {" "}{detail.positive_share}% positive (weighted)</span>
          ) : (
            <span className="warn">No part-specific feedback in the dataset — neutral score. General exterior
              feedback shown for context ({detail.n} comments, {detail.positive_share}% positive).</span>
          )}
          {detail.classes.length > 0 && <span className="muted">Feature classes: {detail.classes.join(", ")}</span>}
          {detail.quotes.map((q, i) => (
            <blockquote key={i}><b className={q.type === "Likes" ? "ok" : "err"}>{q.type}</b>
              <span className="muted"> · {q.series} · {q.country}</span> — “{q.text}”</blockquote>
          ))}
        </div>
      )}
    </div>
  );
}
