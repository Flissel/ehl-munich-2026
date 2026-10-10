"""Keeps Torque and the Rowboat knowledge graph in sync.

    python3 sync.py --watch      # keep running next to Rowboat; checks every 2 seconds
    python3 sync.py              # sync once

Lives in the Torque app folder (demo/torque, symlinked to ~/.rowboat/apps/torque). Both directions:
  Torque -> vault   data/torque.json (rankings of every model and market plus the review decisions, written by
                    Torque inside Rowboat on every change) becomes one note per purchase driver and one top 10
                    note per model in <vault>/Purchase Drivers, linked to the product, theme and market notes.
  vault -> Torque   the product and topic notes go into data/rowboat.json, which Torque shows in Data and
                    workflow, in the "In Rowboat" links and in the copilot's context.
Only notes with "managed_by: torque" in their front matter are ever rewritten; delete that line to keep a note
as you edited it. A file is only written when its content changes. Standard library only (Python 3.9+).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger("torque-sync")

APP = Path(__file__).resolve().parent
FOLDER = "Purchase Drivers"
DASH = re.compile(r"\s[–—]\s")
# Topic notes each purchase driver belongs to: the WP1 customer themes and trends (demo/dataset_to_notes.py,
# grouped like demo/data/themes.csv) and the older research themes; a link is only written when the note exists
TOPICS = {"R-01": ["Range and charging", "Trend Electrification"], "R-02": ["Range and charging", "Trend Electrification"],
          "R-03": ["Comfort and seats", "Space and storage"], "R-04": ["Infotainment and operation", "Infotainment Usability"],
          "R-05": ["Infotainment and operation", "Climate Control Usability"],
          "R-06": ["Connectivity and digital services", "Trend Software and connected car"], "R-07": ["Assistance and parking"],
          "R-08": ["Connectivity and digital services", "Trend Software and connected car"], "R-09": ["Interior design and quality"],
          "R-10": ["Exterior design", "Trend Neue Klasse"], "R-11": ["Driving experience"], "R-12": ["Connectivity and digital services"],
          "R-13": ["Access and convenience"], "R-14": ["Comfort and seats"], "R-15": ["Connectivity and digital services", "Phone Charging"],
          "R-16": ["Space and storage"], "R-17": ["Driving experience"], "R-18": ["Infotainment and operation"],
          "R-19": ["Assistance and parking"], "R-20": ["Comfort and seats", "Climate Control Usability"], "R-21": ["Value and overall impression"]}
MARKET_NOTES = {"EU": "Market Europe", "CN": "Market China", "US": "Market USA", "RoW": "Market Rest of World"}
STATUS = {"approved": "Approved", "modified": "Edited", "challenged": "Challenged", "rejected": "Rejected"}


def parse_note(path: Path, rel: str) -> dict:
    text = path.read_text(encoding="utf-8")
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    title = next((l[2:].strip() for l in body.splitlines() if l.startswith("# ")), path.stem)
    field = lambda k: (re.search(rf"\*\*{k}:\*\*\s*(.+)", body) or [None, ""])[1].strip()
    section = re.search(r"^## Key facts\n(.*?)(?=^## |\Z)", body, flags=re.S | re.M)
    facts = [DASH.sub(", ", l[2:].replace("`", "").strip()) for l in (section[1].splitlines() if section else []) if l.startswith("- ")]
    m = re.search(r"([\d,]+) distinct comment IDs", section[1] if section else "")
    return {"title": DASH.sub(", ", title), "group": rel.split("/")[1], "type": field("Type"), "model": field("Model"),
            "links": sorted(set(re.findall(r"\[\[([^\]|#]+)", body))), "facts": facts,
            "comments": int(m[1].replace(",", "")) if m else None}


def read_vault(vault: Path) -> dict:
    return {f"knowledge/{g}/{f.name}": parse_note(f, f"knowledge/{g}/{f.name}")
            for g in ("Projects", "Topics") for f in sorted((vault / g).glob("*.md"))}


def link(rel: str) -> str:
    return "[[" + rel[len("knowledge/"):-len(".md")] + "]]"


def safe_name(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', " ", title).strip()


def write_if_changed(path: Path, text: str, managed_only: bool = True) -> bool:
    if path.exists():
        old = path.read_text(encoding="utf-8")
        if old == text or (managed_only and "managed_by: torque" not in old[:300]):
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return True


def decision_line(name: str, d: dict) -> str:
    when = str(d.get("at", ""))[:10]
    s = f"{name} successor: {STATUS.get(d.get('status'), d.get('status'))} by {d.get('by') or 'unknown'}" + (f" on {when}" if when else "")
    s += f", round {d.get('round', 1)}."
    if d.get("reason"):
        s += f" Reason: {DASH.sub(', ', str(d['reason']).strip())}"
    if d.get("target"):
        s += f" New target: {DASH.sub(', ', str(d['target']).strip())}"
    if d.get("ask"):
        s += f" Evidence asked from {d['ask']}."
    return s


def run(app: Path, vault: Path, out: Path | None = None) -> int:
    """One sync pass. Returns the number of files written."""
    out = out or vault
    at = lambda rel: out / rel[len("knowledge/"):]   # note keys are "knowledge/<folder>/<name>.md", like Rowboat's own paths
    src = app / "data" / "torque.json"
    if not src.exists():
        log.warning("no %s yet: open Torque in Rowboat once (or run deploy.py)", src)
        return 0
    T = json.loads(src.read_text(encoding="utf-8"))
    notes = read_vault(vault)
    today = datetime.now().strftime("%Y-%m-%d")
    top, mk, dec = T["top"], T["markets"], T.get("decisions", {})
    mk_label = lambda k: mk[k] + (" (modelled)" if k == "CN" else "")
    driver_rel = {rid: f"knowledge/{FOLDER}/{safe_name(r['title'])}.md" for rid, r in T["reqs"].items()}
    top_rel = {m: f"knowledge/{FOLDER}/{v['name']} top {top}.md" for m, v in T["models"].items()}
    model_notes = {m: [rel for rel, n in notes.items() if n["group"] == "Projects"
                       and (Path(rel).stem.startswith(v["code"]) or v["name"] in n["model"])] for m, v in T["models"].items()}
    topic_rel = {t: f"knowledge/Topics/{t}.md" for ts in TOPICS.values() for t in ts}
    market_rel = {k: f"knowledge/Topics/{t}.md" for k, t in MARKET_NOTES.items() if f"knowledge/Topics/{t}.md" in notes}
    head = f"---\nsource: torque\nmanaged_by: torque\nreviewed_on: {today}\n"
    status_of = lambda m, rid: STATUS.get((dec.get(m, {}).get(rid) or {}).get("status"))
    written = 0

    for m, v in T["models"].items():
        lines = [head + f"torque_model: {v['code']}\n---", f"# {v['name']} top {top}", "", "## Info",
                 f"**Model:** BMW {v['name']} successor ({v['code']})", "**Type:** Purchase driver ranking",
                 "**Ranked by:** Torque Decision Cockpit, purchase signal over stated wish", "", "## Connected to"]
        lines += [f"- {link(n)}" for n in model_notes[m]]
        lines += [f"- {link(market_rel[k])}" for k in v["markets"] if k in market_rel]
        lines += [f"- {link(t)}" for t in ("knowledge/Topics/Market Research.md", "knowledge/Topics/EHL Data Quality.md") if t in notes]
        lines += ["", "## Key facts"]
        for k, cell in v["markets"].items():
            lines += ["", f"### {mk_label(k)}", f"Basis: {cell['basis']}."]
            lines += [f"{x['rank']}. {link(driver_rel[x['id']])} ({x['id']}, purchase signal {x['buy']}, asked for {x['wish']})"
                      + (f", {status_of(m, x['id']).lower()}" if status_of(m, x['id']) else ", proposed") for x in cell["rows"][:top]]
        done = sum(1 for x in dec.get(m, {}).values() if x.get("status") in STATUS)
        lines += ["", "## Open items", f"- {done} decisions recorded in Torque for the {v['name']} successor; every driver needs one with a reason.",
                  "- China has no comments; its ranking rests on the China study and research factors."]
        written += write_if_changed(at(top_rel[m]), "\n".join(lines) + "\n")

    for rid, r in T["reqs"].items():
        ins, outs, models_in, markets_in = [], [], [], []
        for m, v in T["models"].items():
            for k, cell in v["markets"].items():
                x = next(y for y in cell["rows"] if y["id"] == rid)
                (ins if x["rank"] <= top else outs).append(f"{v['name']} {mk_label(k)} #{x['rank']}")
                if x["rank"] <= top:
                    models_in += [m] if m not in models_in else []
                    markets_in += [k] if k not in markets_in else []
        best = min(((x, v, k) for v in T["models"].values() for k, c in v["markets"].items() for x in c["rows"] if x["id"] == rid),
                   key=lambda t: t[0]["rank"])
        decided = [(T["models"][m]["name"], dec[m][rid]) for m in T["models"] if dec.get(m, {}).get(rid, {}).get("status") in STATUS]
        lines = [head + f"torque_id: {rid}\n---", f"# {r['title']}", "", "## Info", f"**ID:** {rid}",
                 "**Type:** Purchase driver candidate", f"**Category:** {r['cat']}", f"**Evidence level:** {r['level']}",
                 "**Status:** " + ("; ".join(f"{n} {STATUS[d['status']].lower()}" for n, d in decided) if decided else "proposed"),
                 "", "## Connected to"]
        lines += [f"- {link(top_rel[m])}" for m in models_in]
        lines += [f"- {link(n)}" for m in models_in for n in model_notes[m] if not Path(n).stem.endswith("Roadmap")]
        lines += [f"- {link(topic_rel[t])}" for t in TOPICS.get(rid, []) if topic_rel[t] in notes]
        lines += [f"- {link(market_rel[k])}" for k in markets_in if k in market_rel]
        lines += ["", "## Key facts", f"- Why customers buy it: {r['motive']}",
                  f"- In the top {top}: {', '.join(ins) if ins else 'in no model and market'}.",
                  f"- Below the top {top}: {', '.join(outs) if outs else 'nowhere'}.",
                  f"- Best rank {best[0]['rank']} ({best[1]['name']}, {mk_label(best[2])}): purchase signal {best[0]['buy']}, "
                  f"asked for {best[0]['wish']}, in the top {top} under {best[0]['robust']} of {T['presets']} weightings.",
                  "- Ranks come from Torque's scoring of the BMW hackathon comments, customer studies, sales plan and option prices."]
        lines += ["", "## Decisions"] + ([f"- {decision_line(n, d)}" for n, d in decided] or ["- No decision yet in Torque."])
        lines += ["", "## Open items", "- Product manager decision in Torque: approve, edit, challenge or reject with a reason."]
        written += write_if_changed(at(driver_rel[rid]), "\n".join(lines) + "\n")

    for rel in list(driver_rel.values()) + list(top_rel.values()):
        if at(rel).exists():
            notes[rel] = parse_note(at(rel), rel)
    snap = {"notes": notes, "models": model_notes, "tops": top_rel,
            "drivers": {rid: {"note": driver_rel[rid], "topics": [topic_rel[t] for t in TOPICS.get(rid, []) if topic_rel[t] in notes]}
                        for rid in T["reqs"]},
            "count": {"notes": len(notes), "drivers": len(driver_rel) + len(top_rel)}}
    dst = app / "data" / "rowboat.json"
    try:
        old = json.loads(dst.read_text(encoding="utf-8"))
        old.pop("generated", None)
    except (OSError, ValueError):
        old = None
    if old != json.loads(json.dumps(snap)):
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
        written += write_if_changed(dst, json.dumps({"generated": stamp, **snap}, indent=1, ensure_ascii=False) + "\n", managed_only=False)
    return written


def signature(app: Path, vault: Path) -> tuple:
    files = [app / "data" / "torque.json"] + [f for g in ("Projects", "Topics") for f in (vault / g).glob("*.md")]
    return tuple(sorted((str(f), f.stat().st_mtime_ns, f.stat().st_size) for f in files if f.exists()))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vault", default="~/.rowboat/knowledge", help="Rowboat vault (default ~/.rowboat/knowledge)")
    ap.add_argument("--app", default=str(APP), help="Torque app folder (default: the folder of this script)")
    ap.add_argument("--watch", action="store_true", help="keep running and sync on every change")
    ap.add_argument("--interval", type=float, default=2.0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    app, vault = Path(args.app).expanduser().resolve(), Path(args.vault).expanduser()
    if not (vault / "Projects").is_dir():
        raise SystemExit(f"no vault at {vault}")
    last = None
    while True:
        sig = signature(app, vault)
        if sig != last:
            n = run(app, vault)
            if n or last is None:
                log.info("synced: %d file(s) updated", n)
            last = signature(app, vault)
        if not args.watch:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
