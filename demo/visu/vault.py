"""The 3D car in Rowboat's knowledge graph: fixed links, editable data.

    python demo/visu/vault.py graph                  # rebuild the link map demo/torque/dist/visu/graph.json
    python demo/visu/vault.py notes [--vault V]      # write missing part notes into <vault>/Vehicle Parts
    python demo/visu/vault.py notes --refresh        # also rewrite existing notes (overwrites edits)
    python demo/visu/vault.py sync [--watch]         # vault -> demo/torque/dist/visu/data/visu.json

Links (which part belongs to which area, purchase driver, theme, model and market) come from graph.json,
generated here from fixed tables and committed: editing a note never changes what the UI links. The data
attached to a part (heat map rows per model and market, option rows) lives in the note's tables; Rowboat's AI
may edit them and `sync --watch` hands every change to Torque's Concept 3D within seconds. Notes are only
created when missing, so edits survive a re-run. Customer quotes never go into the vault (spec D8).

Graph: Vehicle -> Exterior / Interior -> area -> part; parts also link to Purchase Drivers (Torque),
Topics (WP1 themes and markets) and Projects (models).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import feedback
import options

log = logging.getLogger("visu.vault")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DIST = HERE.parent / "torque" / "dist"
GRAPH = DIST / "visu" / "graph.json"
OUT_DATA = DIST / "visu" / "data"
MODEL_TS = HERE / "src" / "models" / "bmw-m4-competition-2021.ts"
OPTIONS_MD = REPO / "outputs" / "markdown" / "options" / "processed"
FOLDER = "Vehicle Parts"
MARKER = "managed_by: ehl-visu"

# Purchase driver -> parts of the car (first = where the camera flies). Same reasoning as Torque's drivers.
DRIVER_PARTS = {
    "R-01": ["quarter-rear-left"], "R-02": ["underbody"], "R-03": ["rear-seats"], "R-04": ["central-display"],
    "R-05": ["center-console", "steering-wheel"], "R-06": ["instrument-cluster", "central-display"],
    "R-07": ["windshield", "interior-mirror"], "R-08": ["dashboard", "overhead-console"],
    "R-09": ["door-trim-left", "door-trim-right", "dashboard", "interior-side-panels"],
    "R-10": ["kidney-grille", "headlight-left", "headlight-right", "taillight-left", "taillight-right"],
    "R-11": ["wheel-front-left", "wheel-front-right", "wheel-rear-left", "wheel-rear-right"], "R-12": ["central-display"],
    "R-13": ["door-left", "door-right"], "R-14": ["seat-driver", "seat-passenger"], "R-15": ["center-console"],
    "R-16": ["trunk-lid"], "R-17": ["instrument-cluster"], "R-18": ["door-trim-left", "door-trim-right"],
    "R-19": ["rear-bumper", "front-bumper"], "R-20": ["climate-controls"],
}
# Model category -> (side, area). Interior is split into areas so the graph has more, smaller clusters.
INTERIOR_AREAS = {
    "Seats": ["seat-driver", "seat-passenger", "rear-seats", "seat-belts"],
    "Cockpit and displays": ["instrument-cluster", "central-display", "climate-controls", "steering-wheel", "pedals", "dashboard"],
    "Console and storage": ["center-console"],
    "Cabin trim": ["door-trim-left", "door-trim-right", "overhead-console", "headliner", "interior-side-panels",
                   "interior-mirror", "sun-visors"],
}
AREA_NAMES = {"Body panels": "Body panels", "Bumpers & aero": "Bumpers and aero", "Doors": "Doors and mirrors",
              "Glass": "Glass", "Lighting": "Lighting", "Wheels": "Wheels and brakes", "Trim & details": "Exterior details"}
MODELS = {"F70": "Projects/F70", "G60": "Projects/G60", "G68": "Projects/G68", "G70": "Projects/G70"}
MARKETS = {"EU": "Topics/Market Europe", "CN": "Topics/Market China", "US": "Topics/Market USA", "RoW": "Topics/Market Rest of World"}
HEAT_COLS = ["Model", "Market", "Heat", "Comments", "Mentions", "Likes", "Difficult to use", "Defects", "Wants", "Positive %"]
OPT_COLS = ["Model", "Option", "Code", "Price EUR", "Availability"]
MIN_COMMENTS = 1


def safe_name(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', " ", title).strip()


def torque_drivers() -> dict[str, dict]:
    """Driver ids and titles from Torque's REQS (the note names Torque's sync.py writes)."""
    html = (DIST / "index.html").read_text(encoding="utf-8")
    sys.path.insert(0, str(HERE.parent / "torque"))
    import sync  # Torque's sync: same note names and theme topics
    out = {}
    for rid, title, short in re.findall(r'\{id:"(R-\d+)", title:"([^"]+)", short:"([^"]+)"', html):
        out[rid] = {"title": title, "short": short, "note": f"{sync.FOLDER}/{safe_name(title)}",
                    "topics": [f"Topics/{t}" for t in sync.TOPICS.get(rid, [])], "parts": DRIVER_PARTS.get(rid, [])}
    return out


def build_graph() -> dict:
    ts = MODEL_TS.read_text(encoding="utf-8")
    comps = re.findall(r'id: "([a-z-]+)", name: "([^"]+)", category: "([^"]+)"', ts)
    comps += [(i, n, "Wheels") for i, n in re.findall(r'wheel\("([a-z-]+)", "([^"]+)"', ts)]
    drivers = torque_drivers()
    classes: dict[str, list[str]] = {}
    for vfc, ids in feedback.SPECIFIC.items():
        for i in ids:
            classes.setdefault(i, []).append(vfc)
    interior_area = {p: a for a, ps in INTERIOR_AREAS.items() for p in ps}
    parts, areas = {}, {}
    for pid, name, cat in comps:
        side = "Interior" if cat == "Interior" else "Exterior"
        area = interior_area.get(pid, "Cabin trim") if side == "Interior" else AREA_NAMES[cat]
        drv = [rid for rid, d in drivers.items() if pid in d["parts"]]
        topics = sorted({t for rid in drv for t in drivers[rid]["topics"]})
        parts[pid] = {"name": name, "side": side, "area": area, "note": f"{FOLDER}/{safe_name(name)}",
                      "feature_classes": classes.get(pid, []),
                      "fallback": "general interior" if side == "Interior" else "general exterior",
                      "drivers": drv, "topics": topics}
        a = areas.setdefault(area, {"side": side, "note": f"{FOLDER}/{area}", "parts": []})
        a["parts"].append(pid)
    return {"version": 1, "folder": FOLDER,
            "hub": {"note": f"{FOLDER}/Vehicle", "sides": {s: f"{FOLDER}/{s}" for s in ("Exterior", "Interior")}},
            "areas": areas, "parts": parts, "drivers": drivers, "models": MODELS, "markets": MARKETS}


def write_graph() -> dict:
    g = build_graph()
    GRAPH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH.write_text(json.dumps(g, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log.info("wrote %s (%d parts, %d areas, %d drivers)", GRAPH, len(g["parts"]), len(g["areas"]), len(g["drivers"]))
    return g


# --------------------------------------------------------------------------- notes
def link(note: str) -> str:
    return f"[[{note}]]"


def table(cols: list[str], rows: list[list]) -> list[str]:
    return ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + \
           ["| " + " | ".join("" if v is None else str(v) for v in r) + " |" for r in rows]


def heat_rows(pid: str, scores: dict) -> list[list]:
    rows = []
    for (series, market), s in scores.items():
        c = s["components"].get(pid)
        if not c or not c.get("comments"):
            continue
        k = c["counts"]
        rows.append([series, market, c["score"], c["comments"], c["n"], k.get("Likes", 0), k.get("Difficult to Use", 0),
                     k.get("Defect", 0), k.get("Wants", 0), c["positive_share"]])
    return rows


def option_rows(pid: str, opts: dict) -> list[list]:
    return [[code, o["name"].replace("|", "/"), o["package"] if o["package"] not in ("", "unclear") else "",
             o["price_eur"] or "", o["availability"]]
            for code, lst in opts.items() for o in lst if pid in o["parts"]]


def part_note(pid: str, p: dict, g: dict, scores: dict, opts: dict, today: str) -> str:
    d = g["drivers"]
    lines = ["---", "source: dataset", MARKER, f"part_id: {pid}", f"updated: {today}", "---", f"# {p['name']}", "",
             "## Info", f"**Type:** Car part (3D model)", f"**Part ID:** {pid}", f"**Area:** {link(g['areas'][p['area']]['note'])}",
             f"**Feature classes:** {', '.join(p['feature_classes']) or 'none of its own, uses ' + p['fallback'] + ' feedback'}",
             "", "## Connected to", f"- {link(g['areas'][p['area']]['note'])}"]
    lines += [f"- {link(d[r]['note'])}: {r} {d[r]['short']}" for r in p["drivers"]]
    lines += [f"- {link(t)}" for t in p["topics"]]
    lines += [f"- {link(n)}" for n in MODELS.values()]
    lines += ["", "## Activity", f"- {today}: created from Dataset/ (feedback) and outputs/markdown/options",
              "", "## Key facts", "",
              "### Customer feedback heat map",
              "Heat 0 = most criticised part, 100 = best rated part of this model and market. Comments = unique comment IDs,",
              "mentions = classified rows. Edit values here; Torque's Concept 3D shows them.", ""]
    lines += table(HEAT_COLS, heat_rows(pid, scores)) or []
    lines += ["", "### Options today", "From the German price lists (Dataset/*_OptionList.PDF).", ""]
    lines += table(OPT_COLS, option_rows(pid, opts))
    lines += ["", "## Open items", "- Check the heat map values against the latest feedback export."]
    return "\n".join(lines) + "\n"


def hub_notes(g: dict, today: str) -> dict[str, str]:
    head = "\n".join(["---", "source: dataset", MARKER, f"updated: {today}", "---"])
    out = {g["hub"]["note"]: "\n".join([head, "# Vehicle", "", "## Info", "**Type:** 3D car (stand-in: BMW M4 Competition 2021)",
                                         "", "## Connected to"] + [f"- {link(n)}" for n in g["hub"]["sides"].values()]
                                        + [f"- {link(n)}" for n in MODELS.values()]
                                        + ["", "## Key facts", f"- {len(g['parts'])} parts in {len(g['areas'])} areas, linked to "
                                           f"{len(g['drivers'])} purchase drivers.", ""])}
    for side, note in g["hub"]["sides"].items():
        areas = [a for a, v in g["areas"].items() if v["side"] == side]
        out[note] = "\n".join([head, f"# {side}", "", "## Info", "**Type:** Vehicle side", "", "## Connected to",
                               f"- {link(g['hub']['note'])}"] + [f"- {link(g['areas'][a]['note'])}" for a in areas] + [""])
    for area, a in g["areas"].items():
        out[a["note"]] = "\n".join([head, f"# {area}", "", "## Info", "**Type:** Vehicle area", "", "## Connected to",
                                    f"- {link(g['hub']['sides'][a['side']])}"]
                                   + [f"- {link(g['parts'][p]['note'])}" for p in a["parts"]] + [""])
    return out


def write_notes(vault: Path, refresh: bool) -> int:
    g = json.loads(GRAPH.read_text(encoding="utf-8")) if GRAPH.exists() else write_graph()
    ds = feedback.get_dataset()
    if ds.error:
        raise SystemExit(ds.error)
    scores = {(s or "ALL", m or "ALL"): ds.scores(s, m) for s in [None, *feedback.SERIES] for m in [None, *feedback.MARKETS]}
    opts = {code: options.parse(OPTIONS_MD / f"{code.lower()}_options_features.md")
            for code in feedback.SERIES if (OPTIONS_MD / f"{code.lower()}_options_features.md").is_file()}
    today = datetime.now().strftime("%Y-%m-%d")
    texts = hub_notes(g, today)
    for pid, p in g["parts"].items():
        texts[p["note"]] = part_note(pid, p, g, scores, opts, today)
    written = 0
    for note, text in texts.items():
        path = vault / f"{note}.md"
        if path.exists() and not refresh:
            continue
        if path.exists() and MARKER not in path.read_text(encoding="utf-8")[:300]:
            continue  # someone took the note over (removed managed_by): never touch it
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written += 1
    log.info("%d note(s) written to %s/%s (%d in the graph)", written, vault, FOLDER, len(texts))
    return written


# --------------------------------------------------------------------------- vault -> UI
def num(v: str):
    v = v.strip().replace(",", "")
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return v or None


def read_table(body: str, heading: str) -> list[dict]:
    m = re.search(rf"^### {re.escape(heading)}\n(.*?)(?=^#{{2,3}} |\Z)", body, flags=re.S | re.M)
    if not m:
        return []
    lines = [l for l in m[1].splitlines() if l.strip().startswith("|")]
    if len(lines) < 2:
        return []
    cols = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    return [dict(zip(cols, [c.strip() for c in l.strip().strip("|").split("|")])) for l in lines[2:]]


def read_vault(vault: Path, g: dict) -> dict:
    """Part data from the notes, keyed by the fixed part ids of graph.json (links in the notes are ignored)."""
    # Found by the fixed part_id in the front matter, so a renamed or moved note still feeds the same 3D part.
    by_id = {}
    for f in vault.rglob("*.md"):
        m = re.match(r"---\n.*?^part_id:\s*([a-z-]+)\s*$.*?\n---", f.read_text(encoding="utf-8", errors="ignore")[:600],
                     flags=re.S | re.M)
        if m and m[1] in g["parts"]:
            by_id.setdefault(m[1], f)
    parts = {}
    for pid, p in g["parts"].items():
        path = by_id.get(pid) or vault / f"{p['note']}.md"
        if not path.exists():
            continue
        body = path.read_text(encoding="utf-8")
        heat = {}
        for r in read_table(body, "Customer feedback heat map"):
            key = f"{r.get('Model', 'ALL')}|{r.get('Market', 'ALL')}"
            heat[key] = {"score": num(r.get("Heat", "")), "comments": num(r.get("Comments", "")), "n": num(r.get("Mentions", "")),
                         "counts": {"Likes": num(r.get("Likes", "0")) or 0, "Difficult to Use": num(r.get("Difficult to use", "0")) or 0,
                                    "Defect": num(r.get("Defects", "0")) or 0, "Wants": num(r.get("Wants", "0")) or 0},
                         "positive_share": num(r.get("Positive %", ""))}
        opts = {}
        for r in read_table(body, "Options today"):
            opts.setdefault(r.get("Model", ""), []).append({"name": r.get("Option", ""), "package": r.get("Code", ""),
                                                            "price_eur": num(r.get("Price EUR", "")), "availability": r.get("Availability", "")})
        parts[pid] = {"note": path.relative_to(vault).with_suffix("").as_posix(), "heat": heat, "options": opts}
    return parts


def sync_once(vault: Path, out: Path) -> bool:
    g = json.loads(GRAPH.read_text(encoding="utf-8"))
    data = {"source": str(vault), "parts": read_vault(vault, g)}
    dst = out / "visu.json"
    old = None
    try:
        old = json.loads(dst.read_text(encoding="utf-8"))
        old.pop("generated", None)
    except (OSError, ValueError):
        pass
    if old == json.loads(json.dumps(data)):
        return False
    out.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name("visu.json.tmp")
    tmp.write_text(json.dumps({"generated": datetime.now().astimezone().isoformat(timespec="seconds"), **data},
                              ensure_ascii=False), encoding="utf-8")
    tmp.replace(dst)
    log.info("synced %d part notes -> %s", len(data["parts"]), dst)
    return True


def signature(vault: Path) -> tuple:
    files = list(vault.rglob("*.md")) + [GRAPH]
    return tuple(sorted((str(f), f.stat().st_mtime_ns, f.stat().st_size) for f in files if f.exists()))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["graph", "notes", "sync"])
    ap.add_argument("--vault", type=Path, default=Path("~/.rowboat/knowledge"))
    ap.add_argument("--refresh", action="store_true", help="notes: also rewrite existing managed notes")
    ap.add_argument("--watch", action="store_true", help="sync: keep running")
    ap.add_argument("--interval", type=float, default=2.0)
    args = ap.parse_args()
    vault = args.vault.expanduser()
    if args.command == "graph":
        write_graph()
    elif args.command == "notes":
        write_notes(vault, args.refresh)
    else:
        last = None
        while True:
            sig = signature(vault)
            if sig != last:
                sync_once(vault, OUT_DATA)
                last = sig
            if not args.watch:
                break
            time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
