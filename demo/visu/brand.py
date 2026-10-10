"""The Dataset in Rowboat's knowledge, in Rowboat's own schema: one top-level folder per note type.

    python demo/visu/brand.py [--vault ~/.rowboat/knowledge] [--refresh] [--register]

    Brands/           BMW                         -> Models
    Models/           1er F70, 5er G60, ...       -> Brand, Components, Feature Classes, Data workbook
    Components/       the 56 parts of the 3D car  -> Models, Feature Classes; editable heat + option tables
    Feature Classes/  VFC level 2 classes that colour a component -> Components, Models
    Data/BMW Dataset.xlsx   one workbook for analysis (Feedback, Heat, Sales, Studies, Options)

Rowboat colours its graph by top-level folder and its note agents know types from config/notes.json, so the
hierarchy lives in the links, not in nested folders (--register adds the four types to notes.json). Details
that are columns rather than things (country, market, engine, source, feedback type, VFC level 3) live in the
workbook. Every value comes from Dataset/ and outputs/markdown/options; comment texts never go into the vault
(spec D8). Notes are created only when missing; --refresh rewrites notes that still carry managed_by: ehl-visu.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook

import feedback
import options

log = logging.getLogger("visu.brand")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DATASET = REPO / "Dataset"
OPTIONS_MD = REPO / "outputs" / "markdown" / "options" / "processed"
GRAPH = HERE.parent / "torque" / "dist" / "visu" / "graph.json"
MARKER = "managed_by: ehl-visu"
BRAND = "BMW"
FOLDERS = {"brand": "Brands", "model": "Models", "part": "Components", "class": "Feature Classes", "data": "Data"}
WORKBOOK = f"{FOLDERS['data']}/BMW Dataset.xlsx"
# The 3D car is a placeholder that stands for every model with feedback.
MODELS = {
    "F70": {"folder": "1er F70", "name": "BMW 1 Series", "series": "1 Series", "sheet": "F70", "feedback": True,
            "studies": {"Europe": ("CN_EU_2025", 3)}},
    "G60": {"folder": "5er G60", "name": "BMW 5 Series", "series": "5 Series", "sheet": "G60_G68", "feedback": True,
            "studies": {"Europe": ("CN_EU_2025", 4), "USA": ("US_2025", 2)}},
    "G68": {"folder": "5er G68", "name": "BMW 5 Series long wheelbase", "series": "5 Series", "sheet": "G60_G68",
            "feedback": False, "studies": {"China": ("CN_EU_2025", 1)}},
    "G70": {"folder": "7er G70", "name": "BMW 7 Series", "series": "7 Series", "sheet": "G70", "feedback": True,
            "studies": {"Europe": ("CN_EU_2025", 5), "USA": ("US_2025", 3), "China": ("CN_EU_2025", 2)}},
}
TYPES = ["Likes", "Difficult to Use", "Defect", "Wants"]
COUNT_COLS = ["Comments", "Mentions", "Likes", "Difficult to use", "Defects", "Wants", "Untyped"]
HEAT_COLS = ["Model", "Market", "Heat", "Comments", "Mentions", "Likes", "Difficult to use", "Defects", "Wants", "Positive %"]
OPT_COLS = ["Model", "Option", "Code", "Price EUR", "Availability"]
MARKET_LABEL = {"EU": "Europe", "CN": "China", "US": "USA", "RoW": "Rest of World"}
SOURCE_HINT = {"Source A": "owner reviews", "Source B": "customer care logs", "Source C": "quality survey",
               "Source D": "appeal survey"}
NO_CLASS = "no_class_found"

# Rowboat note types (config/notes.json) for the four folders, so Rowboat's agents write them the same way.
NOTE_TYPES = [
    {"type": "Brands", "folder": FOLDERS["brand"],
     "template": "# {Brand}\n\n## Info\n**Type:** Brand\n\n## Connected to\n- [[Models/{Model}]]\n\n## Key facts\n{Models, comments, sales.}",
     "extractionGuide": "Look for: car brand (e.g. BMW, Audi) and its models"},
    {"type": "Models", "folder": FOLDERS["model"],
     "template": "# {Model folder name, e.g. 5er G60}\n\n## Info\n**Type:** Model\n**Brand:** [[Brands/{Brand}]]\n"
                 "**Derivate (e-code):** {code}\n\n## Connected to\n- [[Components/{Part}]]\n- [[Feature Classes/{Class}]]\n\n"
                 "## Key facts\n{Comments, markets, engines, sources, sales, studies, options as tables.}",
     "extractionGuide": "Look for: car model, e-code, sales, customer studies, option list facts"},
    {"type": "Components", "folder": FOLDERS["part"],
     "template": "# {Part name}\n\n## Info\n**Type:** Component\n**Part ID:** {part_id of the 3D car}\n\n## Connected to\n"
                 "- [[Models/{Model}]]\n- [[Feature Classes/{Class}]]\n\n## Key facts\n### Customer feedback heat map\n"
                 "| Model | Market | Heat | Comments | Mentions | Likes | Difficult to use | Defects | Wants | Positive % |\n\n"
                 "### Options today\n| Model | Option | Code | Price EUR | Availability |",
     "extractionGuide": "Look for: car part, its customer feedback per model and market, options with prices. Keep part_id "
                        "in the front matter and the table columns unchanged (Torque Concept 3D reads them)"},
    {"type": "Assumptions", "folder": "Assumptions",
     "template": "# {Assumption group}\n\n## Info\n**Type:** Assumption\n**Status:** {hand-set|researched}\n\n## About\n"
                 "{What the values mean}\n\n## Values\n```json\n{values, keep the keys}\n```\n\n## Sources\n- {source of a researched value}",
     "extractionGuide": "Look for: values Torque needs that the Dataset does not contain (competitor prices, costs, segment "
                        "shares, weights, dimensions); keep the JSON keys and name a source for every changed value"},
    {"type": "Feature Classes", "folder": FOLDERS["class"],
     "template": "# {VFC level 2 name}\n\n## Info\n**Type:** Feature class (VFC level 2)\n\n## Connected to\n"
                 "- [[Components/{Part}]]\n- [[Models/{Model}]]\n\n## Key facts\n{Comments per model, VFC level 3 aspects.}",
     "extractionGuide": "Look for: vehicle feature class from customer feedback classification, the parts it concerns"},
]


def safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "-", name).strip(" .")


def model_note(code: str) -> str:
    return f"{FOLDERS['model']}/{MODELS[code]['folder']}"


def part_note(part: dict) -> str:
    return f"{FOLDERS['part']}/{safe(part['name'])}"


def class_note(cls: str) -> str:
    return f"{FOLDERS['class']}/{safe(cls)}"


def models_with_feedback() -> list[str]:
    return [c for c, m in MODELS.items() if m["feedback"]]


# --------------------------------------------------------------------------- data
def load_rows() -> dict[str, list[dict]]:
    out = {}
    for code in models_with_feedback():
        ws = load_workbook(DATASET / f"{code}_feedback_hackathon.xlsx", read_only=True, data_only=True).worksheets[0]
        it = ws.iter_rows(values_only=True)
        head = [str(h) for h in next(it)]
        out[code] = [{k: ("" if v is None else str(v).strip()) for k, v in zip(head, r)} for r in it]
    return out


def load_sheets(name: str) -> dict[str, list[list]]:
    wb = load_workbook(DATASET / name, read_only=True, data_only=True)
    return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}


def study_rows(sheets: dict, sheet: str, col: int) -> list[list]:
    """[topic or question, value]: CN_EU = mean 0-10 per topic; US = answer distribution per question."""
    rows, out = sheets[sheet], []
    if sheet == "CN_EU_2025":
        topic = None
        for r in rows[3:]:
            if r[0] and r[0] != "Mean":
                topic = str(r[0]).strip()
            elif r[0] == "Mean" and topic and r[col] is not None:
                out.append([topic, round(float(r[col]), 2)])
        return out
    q, dist = None, []
    for r in rows + [[None, None]]:
        if r[0] and not r[1]:
            if q and dist:
                out.append([q, " · ".join(dist)])
            q, dist = str(r[0]).strip(), []
        elif r[0] and r[1] and str(r[0]) != "Sample total" and len(r) > col and r[col] not in (None, ""):
            dist.append(f"{str(r[0]).strip()} {round(100 * float(r[col]))} %")
    if q and dist:
        out.append([q, " · ".join(dist)])
    return out


def counts(rows: list[dict], key: str) -> list[list]:
    ids, n, t = defaultdict(set), Counter(), defaultdict(Counter)
    for r in rows:
        v = r.get(key) or "(empty)"
        ids[v].add(r["ID"])
        n[v] += 1
        t[v][r["Feedback Type"] if r["Feedback Type"] in TYPES else ""] += 1
    return [[v, len(ids[v]), n[v], *[t[v][x] for x in TYPES], t[v][""]] for v in sorted(ids, key=lambda v: (-len(ids[v]), v))]


# --------------------------------------------------------------------------- markdown
def link(note: str, label: str | None = None) -> str:
    return f"[[{note}|{label}]]" if label else f"[[{note}]]"


def table(cols: list[str], rows: list[list]) -> list[str]:
    # "|" separates table cells, so links inside a table carry no label ([[note|label]] -> [[note]]).
    unlabel = lambda t: re.sub(r"\[\[([^\]|]+)\|[^\]]*\]\]", r"[[\1]]", t)
    cell = lambda v: "" if v is None else unlabel(str(v)).replace("|", "/").replace("\n", " ")
    return ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]


def render(title: str, kind: str, info: list[str], connected: list[str], facts: list[str], front: list[str], today: str) -> str:
    return "\n".join(["---", "source: dataset", MARKER, f"node: {kind}", *front, f"updated: {today}", "---", f"# {title}", "",
                      "## Info", f"**Type:** {kind}", *info, "", "## Connected to", *[f"- {c}" for c in dict.fromkeys(connected)],
                      "", "## Key facts", *facts, ""])


def build(graph: dict, today: str) -> tuple[dict[str, str], dict[str, list[list]]]:
    rows, sales, studies = load_rows(), load_sheets("sales_volumes.xlsx"), load_sheets("F70_G60_G68_G70_customer_studies.xlsx")
    ds = feedback.get_dataset()
    if ds.error:
        raise SystemExit(ds.error)
    parts = graph["parts"]
    opts = {c: options.parse(OPTIONS_MD / f"{c.lower()}_options_features.md", linked_only=False)
            for c in MODELS if (OPTIONS_MD / f"{c.lower()}_options_features.md").is_file()}
    scores = {(c, mk): ds.scores(c, None if mk == "ALL" else mk) for c in rows for mk in ["ALL", "EU", "US", "RoW"]}
    part_of = defaultdict(list)
    for pid, p in parts.items():
        for c in p["feature_classes"]:
            part_of[c].append(pid)
    present = {c: {r["Vfc level2 Name"] for r in rs} for c, rs in rows.items()}
    graph_classes = sorted(c for c in part_of if any(c in v for v in present.values()))
    has_data = {pid: [c for c in rows if scores[(c, "ALL")]["components"].get(pid, {}).get("comments")] for pid in parts}
    notes, sheets = {}, {"Feedback": [], "Heat": [], "Sales": [], "Studies": [], "Options": []}
    wb_link = link(WORKBOOK, "BMW Dataset workbook")

    # Brand
    brand_rows = []
    for code, m in MODELS.items():
        r = rows.get(code, [])
        total = sum(x[3] or 0 for x in sales[m["sheet"]][1:] if x and x[1])
        brand_rows.append([link(model_note(code), m["folder"]), len({x["ID"] for x in r}) or "", len(r) or "", total])
    notes[f"{FOLDERS['brand']}/{BRAND}"] = render(BRAND, "Brand", ["**Brand:** BMW (column Brand)"],
                                                  [link(model_note(c)) for c in MODELS] + [wb_link],
                                                  ["", *table(["Model", "Comments", "Mentions", "Sales 2025 (sheet)"], brand_rows),
                                                   "", "- G60 and G68 share the sales sheet G60_G68."], [], today)
    # Models
    for code, m in MODELS.items():
        r = rows.get(code, [])
        info = [f"**Brand:** {link(FOLDERS['brand'] + '/' + BRAND, BRAND)}", f"**Derivate (e-code):** {code}",
                f"**Sales description:** {m['name']}",
                f"**Comments:** {len({x['ID'] for x in r}):,} unique IDs, {len(r):,} rows" if r else
                "**Comments:** none in the Dataset (study and sales only)", f"**Data:** {wb_link}"]
        facts = ["", "### Sales", *table(["Market", "2024", "2025", "2030 plan"],
                                         [[x[0], *x[2:5]] for x in sales[m["sheet"]][1:] if x and x[0]])]
        for region, (sheet, col) in m["studies"].items():
            facts += ["", f"### Customer study {region} 2025 ({sheet})", "Full answers: workbook sheet Studies."]
            st = study_rows(studies, sheet, col)
            if sheet == "CN_EU_2025":
                st = sorted(st, key=lambda x: x[1])
                facts += table(["Weakest topics", "Mean 0-10"], st[:5]) + [""] + table(["Strongest topics", "Mean 0-10"], st[-5:][::-1])
            else:
                facts.append(f"- {len(st)} questions with answer distributions.")
        if r:
            for title, col, label in [("Markets", None, "Market"), ("Engines", "Engine Type", "Engine"),
                                      ("Sources", "Source", "Source"), ("Feedback types", "Feedback Type", "Type")]:
                data = counts([{**x, "M": MARKET_LABEL[feedback.market_of(x["Country"])]} for x in r], "M") if col is None else counts(r, col)
                if col == "Source":
                    data = [[f"{v} ({SOURCE_HINT.get(v, '')})" if v in SOURCE_HINT else v, *x] for v, *x in data]
                facts += ["", f"### {title}", *table([label, *COUNT_COLS], data)]
            top = [x for x in counts(r, "Vfc level2 Name") if x[0] != NO_CLASS][:15]
            facts += ["", "### Top feature classes (VFC level 2)", *table(["Feature class", *COUNT_COLS],
                      [[link(class_note(v), v) if v in graph_classes else v, *x] for v, *x in top])]
        notes[model_note(code)] = render(m["folder"], "Model", info,
                                         [link(FOLDERS['brand'] + '/' + BRAND)]
                                         + [link(part_note(parts[p])) for p in parts if code in has_data[p]]
                                         + [link(class_note(c)) for c in graph_classes if c in present.get(code, set())] + [wb_link],
                                         facts, [f"model: {code}"], today)
    # Components (editable tables feed Torque Concept 3D)
    for pid, p in parts.items():
        heat, orow = [], []
        for code in rows:
            for mk in ["ALL", "EU", "US", "RoW"]:
                c = scores[(code, mk)]["components"].get(pid)
                if c and c.get("comments"):
                    k = c["counts"]
                    heat.append([code, mk, c["score"], c["comments"], c["n"], k.get("Likes", 0), k.get("Difficult to Use", 0),
                                 k.get("Defect", 0), k.get("Wants", 0), c["positive_share"]])
        for code, lst in opts.items():
            orow += [[code, o["name"], o["package"] if o["package"] not in ("", "unclear") else "", o["price_eur"] or "",
                      o["availability"]] for o in lst if pid in o["parts"]]
        drivers = ", ".join(f"{d} {graph['drivers'][d]['short']}" for d in p["drivers"]) or "none"
        notes[part_note(p)] = render(p["name"], "Component",
                                     [f"**Part ID:** {pid}", f"**Area:** {p['side']} / {p['area']}",
                                      f"**Feature classes:** {', '.join(p['feature_classes']) or 'none of its own, uses ' + p['fallback'] + ' feedback'}",
                                      f"**Purchase drivers (Torque):** {drivers}"],
                                     [link(model_note(c)) for c in has_data[pid]] + [link(class_note(c)) for c in p["feature_classes"] if c in graph_classes],
                                     ["", "### Customer feedback heat map",
                                      "Heat 0 = most criticised part, 100 = best rated part of that model and market. Comments = unique comment IDs,",
                                      "mentions = classified rows. Edit values here; Torque's Concept 3D shows them.", "",
                                      *table(HEAT_COLS, heat), "", "### Options today", "From the German price lists.", "", *table(OPT_COLS, orow)],
                                     [f"part_id: {pid}"], today)
        sheets["Heat"] += [[pid, p["name"], *h] for h in heat]
    # Feature classes that colour a component
    for cls in graph_classes:
        per_model, aspects = [], []
        for code, r in rows.items():
            sub = [x for x in r if x["Vfc level2 Name"] == cls]
            if sub:
                per_model.append([link(model_note(code), MODELS[code]["folder"]), *counts(sub, "Vfc level2 Name")[0][1:]])
                aspects += [[MODELS[code]["folder"], *a] for a in counts(sub, "Vfc level3 Name")]
        notes[class_note(cls)] = render(cls, "Feature class (VFC level 2)", ["**Column:** Vfc level2 Name"],
                                        [link(part_note(parts[p])) for p in part_of[cls]]
                                        + [link(model_note(c)) for c in rows if cls in present[c]],
                                        ["", *table(["Model", *COUNT_COLS], per_model), "", "### VFC level 3 (aspects)",
                                         *table(["Model", "Aspect", *COUNT_COLS], aspects)], [], today)
    # Workbook sheets
    for code, r in rows.items():
        for x in r:
            v2 = x["Vfc level2 Name"]
            sheets["Feedback"].append([x["ID"], code, MODELS[code]["folder"], x["Country"], MARKET_LABEL[feedback.market_of(x["Country"])],
                                       x["Engine Type"], x["Source"], x["Feedback Type"] or "(untyped)", v2, x["Vfc level3 Name"],
                                       x["Vfc level2 3 Name"], ", ".join(parts[p]["name"] for p in part_of.get(v2, []))])
    for code, m in MODELS.items():
        for x in sales[m["sheet"]][1:]:
            if x and x[0]:
                sheets["Sales"] += [[code, m["folder"], m["sheet"], x[0], x[1], year, v] for year, v in zip((2024, 2025, 2030), x[2:5])]
        for region, (sheet, col) in m["studies"].items():
            sheets["Studies"] += [[code, m["folder"], region, sheet, *s] for s in study_rows(studies, sheet, col)]
        for o in opts.get(code, []):
            sheets["Options"].append([code, m["folder"], o["category"], o["name"], o["availability"], o["package"], o["price_eur"],
                                      ", ".join(parts[p]["name"] for p in o["parts"] if p in parts)])
    return notes, sheets


SHEET_HEADS = {
    "Feedback": ["ID", "Model code", "Model", "Country", "Market", "Engine", "Source", "Feedback type", "VFC level 2",
                 "VFC level 3", "VFC level 2 3", "Components"],
    "Heat": ["Part ID", "Component", *HEAT_COLS],
    "Sales": ["Model code", "Model", "Sheet", "Market", "Market code", "Year", "Volume"],
    "Studies": ["Model code", "Model", "Study", "Sheet", "Topic or question", "Mean (0-10) or answers"],
    "Options": ["Model code", "Model", "Category", "Option", "Availability", "Package or code", "Price EUR", "Components"],
}


def write_workbook(path: Path, sheets: dict[str, list[list]]) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        ws.append(SHEET_HEADS[name])
        for r in rows:
            ws.append(r)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    log.info("wrote %s (%s)", path, ", ".join(f"{k} {len(v)}" for k, v in sheets.items()))


def register_types(config: Path) -> None:
    """Adds the four note types to Rowboat's config/notes.json (existing types are kept)."""
    defs = json.loads(config.read_text(encoding="utf-8"))
    known = {d["type"] for d in defs}
    added = [t for t in NOTE_TYPES if t["type"] not in known]
    if added:
        config.write_text(json.dumps(defs + added, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log.info("notes.json: %s", f"added {', '.join(t['type'] for t in added)}" if added else "types already registered")


def write(vault: Path, refresh: bool, graph: dict) -> int:
    notes, sheets = build(graph, datetime.now().strftime("%Y-%m-%d"))
    written = 0
    for rel, text in notes.items():
        path = vault / f"{rel}.md"
        if path.exists() and (not refresh or MARKER not in path.read_text(encoding="utf-8")[:300]):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written += 1
    write_workbook(vault / WORKBOOK, sheets)
    log.info("%d of %d note(s) written to %s", written, len(notes), vault)
    return written


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vault", type=Path, default=Path("~/.rowboat/knowledge"))
    ap.add_argument("--refresh", action="store_true", help="rewrite notes that still carry managed_by: ehl-visu")
    ap.add_argument("--register", action="store_true", help="add the note types to <vault>/../config/notes.json")
    args = ap.parse_args()
    vault = args.vault.expanduser()
    write(vault, args.refresh, json.loads(GRAPH.read_text(encoding="utf-8")))
    if args.register:
        register_types(vault.parent / "config" / "notes.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
