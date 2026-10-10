"""Torque's purchase driver texts, written by the agent from the data (RAG + findings + Dataset aggregates).

    python demo/visu/generate_texts.py [--only R-04,R-14] [--vault ~/.rowboat/knowledge] [--model gpt-4.1]
    python demo/visu/generate_texts.py --read [--vault ...]      # Requirements/*.md -> JSON on stdout

For every purchase driver the agent gets: Torque's counts for the driver (dist/bmw.json: comments by feedback
type, market, model), the customer study items, the option per model, the research findings
(research/findings/findings.csv) and the best Dataset passages from the RAG backend (src/rag_backend, :8100).
It writes the texts Torque shows (title, motive, attribute, target, acceptance, assumptions, customer evidence,
conflict) following research/AGENT.md: customer-facing, every claim backed by cited IDs, counts only from the
data, gaps stated. The id, short name and category stay fixed (Torque's assumptions and the 3D view key on
them). Output: one editable note per driver in <vault>/Requirements/ and dist/texts.seed.json (the copy for
PCs without the vault). `vault.py sync` hands edited notes to Torque (visu/data/texts.json).
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

log = logging.getLogger("visu.texts")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DIST = HERE.parent / "torque" / "dist"
SEED = DIST / "texts.seed.json"
FOLDER = "Requirements"
MARKER = "managed_by: ehl-visu"
RAG_URL = os.environ.get("RAG_URL", "http://127.0.0.1:8100")
FIELDS = ["title", "motive", "attr", "target", "accept", "assume", "cs", "conflict", "feature_on", "feature_off"]
LABELS = {"title": "Title", "motive": "Why customers buy it", "attr": "Customer attribute", "target": "Target",
          "accept": "Acceptance", "assume": "Assumptions", "cs": "Customer evidence", "conflict": "Conflicting evidence",
          "feature_on": "Successor feature", "feature_off": "Today (baseline)"}
MODELS = {"1": "F70 (1 Series)", "5": "G60 (5 Series) / G68 (5 Series LWB, China)", "7": "G70 (7 Series)"}
TYPES = {"L": "likes", "W": "wants", "D": "difficult to use", "F": "defects", "P": "purchase reasons",
         "C": "switching threats", "R": "rival comparisons", "K": "conquest"}

SYSTEM = """You are the Customer Requirements Research Agent for BMW product management (rules: research/AGENT.md).
Write the texts of ONE purchase driver of the decision cockpit Torque from the evidence given, nothing else.
The driver's topic is fixed by EVIDENCE.topic (short name, category and definition). Stay strictly on that topic:
ignore RAG passages and findings about other topics, and say in conflict when the on-topic evidence is thin.
Rules (non-negotiable):
- Customer-facing: what the customer experiences, not engineering. No pricing claims beyond the option prices given.
- No evidence, no claim. Counts only from EVIDENCE (never estimate). Cite comment IDs (e.g. G60-1288), finding IDs
  (e.g. F-001), study items or option codes in cs and conflict.
- Quote at most 12 words verbatim, only from the RAG passages, and only when it adds meaning.
- State gaps honestly (thin evidence, China has no owner comments and is modelled from the study, German option lists).
- No personal data. No em dashes. Plain sentences.
Return JSON only with these keys:
title: 3 to 7 words, a customer benefit (e.g. "Fast charging that fits a coffee stop")
motive: 1 sentence, why customers buy it (the emotional or practical reason)
attr: 1 short phrase, the measurable customer attribute
target: 1 sentence, a concrete testable target for the successor
accept: 1 sentence, how a product manager verifies the target
assume: list of 1 to 3 short assumptions the target rests on
cs: 1 sentence, what the BMW customer comments show, with counts and IDs
conflict: 1 to 3 sentences, where the evidence disagrees or is thin, with counts and IDs
feature_on: at most 10 words, the visible feature of the successor that meets the target, as shown on a concept car
  (for a driver with no visible part say so, e.g. "Privacy controls, no visible change"; for range you may use the
  placeholders {kwh} and {rangeKm})
feature_off: at most 8 words, today's baseline from option_today (or "Standard ..." if none)"""


def load_env() -> None:
    for path in (REPO / "search" / ".env", REPO / ".env"):
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                k, _, v = line.partition("=")
                if k.strip() and v.strip() and k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip().strip('"')


def rag(question: str, top_k: int = 8) -> list[dict]:
    req = urllib.request.Request(RAG_URL + "/search", json.dumps({"question": question, "top_k": top_k}).encode(),
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)["results"]
    except OSError as err:
        log.warning("RAG not reachable (%s): texts rest on the aggregates only", err)
        return []


def findings_for(words: list[str]) -> list[dict]:
    rows = list(csv.DictReader(open(REPO / "research" / "findings" / "findings.csv", encoding="utf-8")))
    hit = lambda r: any(w.lower() in (r["keywords"] + " " + r["statement"]).lower() for w in words)
    return [{k: r[k] for k in ("finding_id", "statement", "n", "scope", "confidence", "caveat")} for r in rows if hit(r)][:5]


def evidence(rid: str, cur: dict, bmw: dict) -> tuple[dict, list[dict]]:
    t = bmw["themes"].get(rid, {})
    words = [w for w in re.split(r"[^A-Za-z]+", f"{cur['short']} {cur['cat']}") if len(w) > 3]
    topic = f"{cur['short']} ({cur['cat']}): {cur.get('attr', '')}"
    hits = rag(f"{topic}. What do BMW customers say about {cur['short'].lower()}: praise, wants, difficulties, defects?")
    ev = {
        "id": rid, "topic": {"short": cur["short"], "category": cur["cat"], "definition": cur.get("attr", ""),
                             "prototype_title": cur.get("title", "")},
        "comments_all_models": {"total": t.get("n"), **{TYPES[k]: t.get(k) for k in TYPES if k in t}},
        "comments_by_market": {m: v.get("n") for m, v in (t.get("mk") or {}).items()},
        "comments_by_model": {MODELS.get(k, k): (v.get("n") if isinstance(v, dict) else v) for k, v in (t.get("dv") or {}).items()},
        "evidence_level": bmw["evidence"].get(rid),
        "customer_study": bmw["study"].get(rid),
        "option_today": bmw["options"].get(rid),
        "research_findings": findings_for(words),
        "rag_passages": [{"source": ", ".join(str(h.get(k)) for k in ("source_type", "vehicle_model", "market", "section") if h.get(k)),
                          "text": re.sub(r"^---[\s\S]*?---\s*", "", h.get("text", ""))[:1800]} for h in hits],
    }
    return ev, hits


def known_ids() -> set[str]:
    """Every comment ID in the Dataset (research/data/processed/comments.csv, built by prepare_data.py)."""
    rows = csv.DictReader(open(REPO / "research" / "data" / "processed" / "comments.csv", encoding="utf-8"))
    return {r["comment_id"] for r in rows}


def drop_unknown_ids(t: dict, ids: set[str]) -> list[str]:
    """No evidence, no claim: comment IDs the model cites that are not in the Dataset are removed."""
    bad = []
    for k in ("cs", "conflict"):
        for cid in re.findall(r"(?<![\w-])[FG]\d{2}-\d{4}(?!\d)", t[k]):
            if cid not in ids:
                bad.append(cid)
                t[k] = re.sub(rf"\s*,?\s*{cid}", "", t[k]).replace("(, ", "(").replace("()", "").replace(" e.g. )", ")")
    return bad


def generate(client, model: str, ev: dict) -> dict:
    import time
    for attempt in range(5):  # the API drops connections now and then: retry with backoff
        try:
            res = client.chat.completions.create(model=model, temperature=0.2, response_format={"type": "json_object"},
                                                 messages=[{"role": "system", "content": SYSTEM},
                                                           {"role": "user", "content": "EVIDENCE:\n" + json.dumps(ev, ensure_ascii=False)}])
            break
        except Exception as err:  # openai.APIConnectionError, RateLimitError, APITimeoutError
            if attempt == 4:
                raise
            log.warning("API error (%s), retry %d in %ds", type(err).__name__, attempt + 1, 2 ** (attempt + 1))
            time.sleep(2 ** (attempt + 1))
    out = json.loads(res.choices[0].message.content)
    out["assume"] = [str(a) for a in (out.get("assume") or [])][:3]
    return {k: out.get(k, "") for k in FIELDS}


# --------------------------------------------------------------------------- notes
def note_text(rid: str, short: str, cat: str, t: dict, sources: list[str], model: str, today: str) -> str:
    lines = ["---", "source: agent", MARKER, f"req_id: {rid}", f"generated_by: {model} + RAG", f"updated: {today}", "---",
             f"# {t['title']}", "", "## Info", "**Type:** Requirement (purchase driver)", f"**ID:** {rid}", f"**Short:** {short}",
             f"**Category:** {cat}", ""]
    for k in FIELDS[1:]:
        lines += [f"## {LABELS[k]}"] + ([f"- {a}" for a in t[k]] if k == "assume" else [t[k]]) + [""]
    lines += ["## Sources", *[f"- {s}" for s in sources], ""]
    return "\n".join(lines)


def read_notes(vault: Path) -> dict:
    out = {}
    for f in sorted((vault / FOLDER).glob("*.md")):
        text = f.read_text(encoding="utf-8")
        rid = re.search(r"^req_id:\s*(R-\d+)", text, flags=re.M)
        if not rid:
            continue
        sec = lambda label: (re.search(rf"^## {re.escape(label)}\n(.*?)(?=^## |\Z)", text, flags=re.S | re.M) or [None, ""])[1].strip()
        info = lambda k: (re.search(rf"^\*\*{k}:\*\*\s*(.+)$", text, flags=re.M) or [None, ""])[1].strip()
        t = {"title": (re.search(r"^# (.+)$", text, flags=re.M) or [None, ""])[1].strip(), "short": info("Short"), "cat": info("Category")}
        for k in FIELDS[1:]:
            v = sec(LABELS[k])
            t[k] = [l[2:].strip() for l in v.splitlines() if l.startswith("- ")] if k == "assume" else " ".join(v.split())
        out[rid[1]] = t
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vault", type=Path, default=Path("~/.rowboat/knowledge"))
    ap.add_argument("--model", default="gpt-4.1")
    ap.add_argument("--only", help="comma separated driver ids")
    ap.add_argument("--read", action="store_true")
    args = ap.parse_args()
    vault = args.vault.expanduser()
    if args.read:
        json.dump(read_notes(vault), sys.stdout, ensure_ascii=False)
        return 0
    load_env()
    from openai import OpenAI
    client = OpenAI()
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    bmw = json.loads((DIST / "bmw.json").read_text(encoding="utf-8"))
    only = set(args.only.split(",")) if args.only else None
    today = datetime.now().strftime("%Y-%m-%d")
    ids = known_ids()
    for rid, cur in seed["requirements"].items():
        if only and rid not in only:
            continue
        ev, hits = evidence(rid, cur, bmw)
        t = generate(client, args.model, ev)
        bad = drop_unknown_ids(t, ids)
        if bad:
            log.warning("%s: removed comment IDs not in the Dataset: %s", rid, ", ".join(bad))
        seed["requirements"][rid] = {**cur, **t}
        sources = [f"RAG: {h.get('source_file')} ({h.get('section') or h.get('vehicle_model')})" for h in hits[:8]]
        sources += [f"Finding {f['finding_id']}: {f['statement']}" for f in ev["research_findings"]]
        sources += ["Torque data (dist/bmw.json): comment counts, study items, options"]
        path = vault / FOLDER / f"{rid} {re.sub(r'[\\/:*?\"<>|]', ' ', cur['short'])}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or MARKER in path.read_text(encoding="utf-8")[:300]:
            path.write_text(note_text(rid, cur["short"], cur["cat"], t, sources, args.model, today), encoding="utf-8")
        log.info("%s %s: %s", rid, cur["short"], t["title"])
    seed["source"] = f"agent output ({args.model} + RAG, demo/visu/generate_texts.py, {today})"
    SEED.write_text(json.dumps(seed, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
