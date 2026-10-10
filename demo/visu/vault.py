"""The 3D car in Rowboat's knowledge graph: fixed links, editable data.

    python demo/visu/vault.py graph                  # rebuild the link map demo/torque/dist/visu/graph.json
    python demo/visu/vault.py notes [--vault V]      # write missing notes: Brands, Models, Components, Feature Classes + Data workbook (brand.py)
    python demo/visu/vault.py notes --refresh        # also rewrite existing managed notes (overwrites edits)
    python demo/visu/vault.py sync [--watch]         # vault -> demo/torque/dist/visu/data/visu.json

Links (which part belongs to which area, purchase driver, theme, model and market) come from graph.json,
generated here from fixed tables and committed: editing a note never changes what the UI links. The data
attached to a part (heat map rows per model and market, option rows) lives in the note's tables; Rowboat's AI
may edit them and `sync --watch` hands every change to Torque's Concept 3D within seconds. Notes are only
created when missing, so edits survive a re-run. Customer quotes never go into the vault (spec D8).

Schema (brand.py, Rowboat style: one top-level folder per note type, hierarchy in the links): Brands -> Models ->
Components -> Feature Classes, plus Data/BMW Dataset.xlsx for analysis.
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

import brand
import feedback

log = logging.getLogger("visu.vault")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DIST = HERE.parent / "torque" / "dist"
GRAPH = DIST / "visu" / "graph.json"
OUT_DATA = DIST / "visu" / "data"
MODEL_TS = HERE / "src" / "models" / "template.ts"  # shared component catalogue

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


def safe_name(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', " ", title).strip()


def torque_drivers() -> dict[str, dict]:
    """Driver ids, titles and short names from Torque's texts (dist/texts.seed.json, the agent output; REQS no
    longer lives in the page code). Note names follow the Requirements notes (generate_texts.py)."""
    sys.path.insert(0, str(HERE.parent / "torque"))
    import sync  # Torque's sync: theme topics per driver
    reqs = json.loads((DIST / "texts.seed.json").read_text(encoding="utf-8"))["requirements"]
    return {rid: {"title": r["title"], "short": r["short"], "note": f"Requirements/{rid} {safe_name(r['short'])}",
                  "topics": [f"Topics/{t}" for t in sync.TOPICS.get(rid, [])], "parts": DRIVER_PARTS.get(rid, [])}
            for rid, r in reqs.items()}


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
        parts[pid] = {"name": name, "side": side, "area": area,
                      "feature_classes": classes.get(pid, []),
                      "fallback": "general interior" if side == "Interior" else "general exterior",
                      "drivers": drv, "topics": topics}
        parts[pid]["note"] = brand.part_note(parts[pid])
        parts[pid]["notes"] = {code: parts[pid]["note"] for code in brand.models_with_feedback()}
        a = areas.setdefault(area, {"side": side, "parts": []})
        a["parts"].append(pid)
    return {"version": 3, "folders": brand.FOLDERS, "brand": brand.BRAND,
            "models": {c: {"folder": m["folder"], "note": brand.model_note(c)} for c, m in brand.MODELS.items()},
            "areas": areas, "parts": parts, "drivers": drivers}


def write_graph() -> dict:
    g = build_graph()
    GRAPH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH.write_text(json.dumps(g, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log.info("wrote %s (%d parts, %d areas, %d drivers)", GRAPH, len(g["parts"]), len(g["areas"]), len(g["drivers"]))
    return g


# --------------------------------------------------------------------------- notes
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
    """Component data from the notes, keyed by the fixed part_id (+ model) in their front matter, so a renamed
    or moved note still feeds the same 3D part. Links in the notes are never read."""
    parts = {pid: {"notes": {}, "heat": {}, "options": {}} for pid in g["parts"]}
    for f in sorted((vault / brand.FOLDERS["part"]).rglob("*.md")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        head = re.match(r"---\n(.*?)\n---", text, flags=re.S)
        meta = dict(re.findall(r"^(\w+):\s*(.+?)\s*$", head[1], flags=re.M)) if head else {}
        pid, code = meta.get("part_id"), meta.get("model", "")
        if pid not in parts:
            continue
        p = parts[pid]
        note = f.relative_to(vault).with_suffix("").as_posix()
        p["notes"].update({c: note for c in brand.models_with_feedback()} if not code else {code: note})
        for r in read_table(text, "Customer feedback heat map"):
            p["heat"][f"{r.get('Model') or code}|{r.get('Market', 'ALL')}"] = {
                "score": num(r.get("Heat", "")), "comments": num(r.get("Comments", "")), "n": num(r.get("Mentions", "")),
                "counts": {"Likes": num(r.get("Likes", "0")) or 0, "Difficult to Use": num(r.get("Difficult to use", "0")) or 0,
                           "Defect": num(r.get("Defects", "0")) or 0, "Wants": num(r.get("Wants", "0")) or 0},
                "positive_share": num(r.get("Positive %", ""))}
        for r in read_table(text, "Options today"):
            p["options"].setdefault(r.get("Model") or code, []).append(
                {"name": r.get("Option", ""), "package": r.get("Code", ""), "price_eur": num(r.get("Price EUR", "")),
                 "availability": r.get("Availability", "")})
    return {pid: p for pid, p in parts.items() if p["notes"]}


def sync_once(vault: Path, out: Path) -> bool:
    import assumptions  # Assumptions/*.md -> assumptions.json (Torque reads it before its seed copy)
    write_json(out / "assumptions.json", assumptions.read(vault))
    import generate_texts  # Requirements/*.md (agent output, editable) -> texts.json, on top of the seed
    seed = json.loads(generate_texts.SEED.read_text(encoding="utf-8"))
    for rid, t in generate_texts.read_notes(vault).items():
        seed["requirements"][rid] = {**seed["requirements"].get(rid, {}), **{k: v for k, v in t.items() if v}}
    write_json(out / "texts.json", {**seed, "source": "Rowboat notes Requirements/ (agent output, editable)"})
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
    for attempt in range(10):  # Windows: the app server may hold the file open for a moment
        try:
            tmp.replace(dst)
            break
        except PermissionError:
            time.sleep(0.2)
    else:
        log.warning("could not replace %s (locked); next change retries", dst)
        return False
    log.info("synced %d part notes -> %s", len(data["parts"]), dst)
    return True


def write_json(dst: Path, data: dict) -> bool:
    """Writes only on change; retries while the app server holds the file (Windows)."""
    text = json.dumps(data, ensure_ascii=False)
    if dst.exists() and dst.read_text(encoding="utf-8") == text:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    for _ in range(10):
        try:
            tmp.replace(dst)
            log.info("wrote %s", dst.name)
            return True
        except PermissionError:
            time.sleep(0.2)
    return False


def signature(vault: Path) -> tuple:
    files = (list((vault / brand.FOLDERS["part"]).rglob("*.md")) + list((vault / "Assumptions").glob("*.md"))
             + list((vault / "Requirements").glob("*.md")) + [GRAPH])
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
        brand.write(vault, args.refresh, json.loads(GRAPH.read_text(encoding="utf-8")) if GRAPH.exists() else write_graph())
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
