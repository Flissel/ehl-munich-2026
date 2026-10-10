"""The Dataset as a folder tree and graph in Rowboat's knowledge.

    python demo/visu/brand.py [--vault ~/.rowboat/knowledge] [--refresh]

    Brands/ -> <Brand>/ -> Models/ -> <model>/ -> Components, VFC, ID, Country, Engine, Source, Feedback,
                                                  Sales, Studies, Options

Every folder has a hub note with the folder's name, so the graph mirrors the folders. Every value comes from
Dataset/ (feedback, sales and study workbooks) and outputs/markdown/options (price lists); comment texts never
go into the vault (spec D8). Component notes carry the part_id of the 3D car and editable tables (heat map,
options) that `vault.py sync --watch` hands to Torque's Concept 3D. Notes are created only when missing;
--refresh rewrites notes that still carry managed_by: ehl-visu. A second brand gets its own Brands/<Brand>/.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

import feedback
import options

log = logging.getLogger("visu.brand")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DATASET = REPO / "Dataset"
OPTIONS_MD = REPO / "outputs" / "markdown" / "options" / "processed"
ROOT = "Brands"
BRAND = "BMW"
MARKER = "managed_by: ehl-visu"
# Model folders. The 3D car stands for every model with feedback (for now it is shown as the 1er).
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
SOURCE_HINT = {"Source A": "owner reviews, many countries", "Source B": "customer care logs, US",
               "Source C": "quality survey, US", "Source D": "appeal survey, US"}
NO_CLASS = "no_class_found"


# --------------------------------------------------------------------------- paths
def safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "-", name).strip(" .")


def model_dir(code: str) -> str:
    return f"{ROOT}/{BRAND}/Models/{MODELS[code]['folder']}"


def hub(path: str) -> str:
    """The hub note of a folder: <folder>/<folder name>."""
    return f"{path}/{path.rsplit('/', 1)[-1]}"


def model_note(code: str) -> str:
    return hub(model_dir(code))


def part_note(code: str, part: dict) -> str:
    return f"{model_dir(code)}/Components/{part['side']}/{part['area']}/{safe(part['name'])}"


def vfc_note(code: str, cls: str) -> str:
    return f"{model_dir(code)}/VFC/{safe(cls)}"


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
        log.info("%s: %d rows", code, len(out[code]))
    return out


def load_sales() -> dict[str, list[list]]:
    wb = load_workbook(DATASET / "sales_volumes.xlsx", read_only=True, data_only=True)
    return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}


def load_studies() -> dict[str, list[list]]:
    wb = load_workbook(DATASET / "F70_G60_G68_G70_customer_studies.xlsx", read_only=True, data_only=True)
    return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}


def study_rows(sheets: dict, sheet: str, col: int) -> tuple[list[str], list[list]]:
    rows = sheets[sheet]
    if sheet == "CN_EU_2025":  # topic row, then "Mean" row with one column per market and model
        out, topic = [], None
        for r in rows[3:]:
            if r[0] and r[0] != "Mean":
                topic = str(r[0]).strip()
            elif r[0] == "Mean" and topic and r[col] is not None:
                out.append([topic, round(float(r[col]), 2)])
        return ["Topic", "Mean (0 to 10)"], out
    out, q, dist = [], None, []
    for r in rows + [[None, None]]:  # US: question row, then answers with % of column
        if r[0] and not r[1]:
            if q and dist:
                out.append([q, " · ".join(dist)])
            q, dist = str(r[0]).strip(), []
        elif r[0] and r[1] and str(r[0]) != "Sample total" and len(r) > col and r[col] not in (None, ""):
            dist.append(f"{str(r[0]).strip()} {round(100 * float(r[col]))} %")
    if q and dist:
        out.append([q, " · ".join(dist)])
    return ["Question", "Answers (% of owners)"], out


def counts(rows: list[dict], key: str) -> list[list]:
    """Per value: unique comments, rows (mentions) and rows per feedback type, most comments first."""
    ids, n, t = defaultdict(set), Counter(), defaultdict(Counter)
    for r in rows:
        v = r.get(key) or "(empty)"
        ids[v].add(r["ID"])
        n[v] += 1
        t[v][r["Feedback Type"] if r["Feedback Type"] in TYPES else ""] += 1
    order = sorted(ids, key=lambda v: (-len(ids[v]), v))
    return [[v, len(ids[v]), n[v], *[t[v][x] for x in TYPES], t[v][""]] for v in order]


# --------------------------------------------------------------------------- markdown
def link(note: str, label: str | None = None) -> str:
    return f"[[{note}|{label}]]" if label else f"[[{note}]]"


def table(cols: list[str], rows: list[list]) -> list[str]:
    cell = lambda v: "" if v is None else str(v).replace("|", "/").replace("\n", " ")
    return ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]


class Notes(dict):
    def __init__(self, today: str):
        super().__init__()
        self.today = today

    def add(self, rel: str, title: str, kind: str, info: list[str], connected: list[str], facts: list[str],
            front: list[str] = ()) -> None:
        self[rel] = "\n".join(["---", "source: dataset", MARKER, f"node: {kind}", *front, f"updated: {self.today}", "---",
                               f"# {title}", "", "## Info", f"**Type:** {kind}", *info, "", "## Connected to",
                               *[f"- {c}" for c in dict.fromkeys(connected)], "", "## Key facts", *facts, ""])


# --------------------------------------------------------------------------- tree
def build(graph: dict, today: str) -> Notes:
    rows, sales, studies = load_rows(), load_sales(), load_studies()
    ds = feedback.get_dataset()
    if ds.error:
        raise SystemExit(ds.error)
    notes = Notes(today)
    brand_dir, models_dir = f"{ROOT}/{BRAND}", f"{ROOT}/{BRAND}/Models"
    notes.add(hub(ROOT), ROOT, "Brands", [], [link(hub(brand_dir))], ["", f"- {BRAND}"])
    notes.add(hub(brand_dir), BRAND, "Brand", ["**Brand:** BMW (column Brand)"], [link(hub(ROOT)), link(hub(models_dir))],
              ["", f"- {len(MODELS)} models: {', '.join(m['folder'] for m in MODELS.values())}"])
    model_rows = []
    for code, m in MODELS.items():
        r = rows.get(code, [])
        total = sum(x[3] or 0 for x in sales.get(m["sheet"], [])[1:] if x and x[1])
        model_rows.append([link(model_note(code), m["folder"]), len({x["ID"] for x in r}) or "", len(r) or "", total])
    notes.add(hub(models_dir), "Models", "Models", [f"**Brand:** {link(hub(brand_dir), BRAND)}"],
              [link(hub(brand_dir))] + [link(model_note(c)) for c in MODELS],
              ["", *table(["Model", "Comments", "Mentions", "Sales 2025 (sheet)"], model_rows),
               "", "- G60 and G68 share the sales sheet G60_G68 (the same numbers appear in both)."])
    opts_all = {c: options.parse(OPTIONS_MD / f"{c.lower()}_options_features.md", linked_only=False)
                for c in MODELS if (OPTIONS_MD / f"{c.lower()}_options_features.md").is_file()}
    for code, m in MODELS.items():
        build_model(notes, code, m, rows.get(code, []), sales, studies, ds, graph, opts_all.get(code, []))
    return notes


def build_model(notes: Notes, code: str, m: dict, r: list[dict], sales: dict, studies: dict, ds, graph: dict,
                opts: list[dict]) -> None:
    base, mnote = model_dir(code), model_note(code)
    front = [f"model: {code}"]
    subs = (["Components", "VFC", "ID", "Country", "Engine", "Source", "Feedback"] if r else []) + \
           ["Sales", "Studies"] + (["Options"] if opts else [])
    info = [f"**Brand:** {link(hub(f'{ROOT}/{BRAND}'), BRAND)}", f"**Derivate (e-code):** {code}",
            f"**Sales description:** {m['name']}", f"**Sales sheet:** {m['sheet']}"]
    info.append(f"**Comments:** {len({x['ID'] for x in r}):,} unique IDs, {len(r):,} rows" if r
                else "**Comments:** none in the Dataset (study and sales only)")
    if r:
        info.append("**3D car:** shown as this model in Torque's Concept 3D (placeholder model for now)")
    notes.add(mnote, m["folder"], "Model", info, [link(hub(f"{ROOT}/{BRAND}/Models"))] + [link(hub(f"{base}/{s}")) for s in subs],
              ["", f"- Sub nodes: {', '.join(subs)}."], front)
    sub_hub = lambda s, info_, conn, facts: notes.add(hub(f"{base}/{s}"), s, s, [f"**Model:** {link(mnote, m['folder'])}", *info_],
                                                      [link(mnote), *conn], facts, front)
    # Sales
    srows = [[x[0], x[1], *x[2:5]] for x in sales.get(m["sheet"], [])[1:] if x and x[0]]
    sub_hub("Sales", ["Sales volumes per market (Dataset/sales_volumes.xlsx)."], [],
            ["", *table(["Market", "Code", "2024", "2025", "2030 plan"], srows)]
            + (["", "- Sheet G60_G68 reports G60 and G68 together."] if m["sheet"] == "G60_G68" else []))
    # Studies
    study_notes = []
    for region, (sheet, col) in m["studies"].items():
        rel = f"{base}/Studies/Study {region} 2025"
        cols, data = study_rows(studies, sheet, col)
        notes.add(rel, f"Study {region} 2025", "Study", [f"**Model:** {link(mnote, m['folder'])}",
                  f"**Source:** Dataset/F70_G60_G68_G70_customer_studies.xlsx, sheet {sheet}"],
                  [link(hub(f"{base}/Studies"))], ["", *table(cols, data)], front)
        study_notes.append(rel)
    sub_hub("Studies", ["Customer studies 2025 for this model."], [link(n) for n in study_notes], [""])
    # Options
    if opts:
        parts_by_id = graph["parts"]
        orows = [[o["category"], o["name"], o["availability"], o["package"] if o["package"] != "unclear" else "",
                  o["price_eur"] or "", ", ".join(link(part_note(code, parts_by_id[p]), parts_by_id[p]["name"])
                                                  for p in o["parts"] if r and p in parts_by_id)] for o in opts]
        sub_hub("Options", [f"Price list (Dataset/{code}_OptionList.PDF via outputs/markdown/options)."], [],
                ["", *table(["Category", "Option", "Availability", "Code", "Price EUR", "Components"], orows)])
    if not r:
        return
    scores = {mk: ds.scores(code, None if mk == "ALL" else mk) for mk in ["ALL", "EU", "US", "RoW"]}
    classes = {v for v, *_ in counts(r, "Vfc level2 Name")} - {NO_CLASS}
    # Components: Components -> Exterior / Interior -> area -> part
    parts = graph["parts"]
    sides = defaultdict(lambda: defaultdict(list))
    for pid, p in parts.items():
        sides[p["side"]][p["area"]].append(pid)
    comp_dir = f"{base}/Components"
    sub_hub("Components", ["The parts of the 3D car with this model's customer feedback and options."],
            [link(hub(f"{comp_dir}/{s}")) for s in sides], ["", f"- {len(parts)} parts in {sum(len(a) for a in sides.values())} areas."])
    for side, areas in sides.items():
        notes.add(hub(f"{comp_dir}/{side}"), side, "Vehicle side", [f"**Model:** {link(mnote, m['folder'])}"],
                  [link(hub(comp_dir))] + [link(hub(f"{comp_dir}/{side}/{a}")) for a in areas], [""], front)
        for area, pids in areas.items():
            notes.add(hub(f"{comp_dir}/{side}/{area}"), area, "Vehicle area", [f"**Model:** {link(mnote, m['folder'])}"],
                      [link(hub(f"{comp_dir}/{side}"))] + [link(part_note(code, parts[p])) for p in pids], [""], front)
            for pid in pids:
                p = parts[pid]
                heat = []
                for mk, s in scores.items():
                    c = s["components"].get(pid)
                    if c and c.get("comments"):
                        k = c["counts"]
                        heat.append([code, mk, c["score"], c["comments"], c["n"], k.get("Likes", 0), k.get("Difficult to Use", 0),
                                     k.get("Defect", 0), k.get("Wants", 0), c["positive_share"]])
                orow = [[code, o["name"], o["package"] if o["package"] not in ("", "unclear") else "", o["price_eur"] or "",
                         o["availability"]] for o in opts if pid in o["parts"]]
                drivers = ", ".join(f"{d} {graph['drivers'][d]['short']}" for d in p["drivers"]) or "none"
                notes.add(part_note(code, p), p["name"], "Component",
                          [f"**Model:** {link(mnote, m['folder'])}", f"**Part ID:** {pid}",
                           f"**Feature classes:** {', '.join(p['feature_classes']) or 'none of its own, uses ' + p['fallback'] + ' feedback'}",
                           f"**Purchase drivers (Torque):** {drivers}"],
                          [link(hub(f"{comp_dir}/{side}/{area}"))] + [link(vfc_note(code, c)) for c in p["feature_classes"] if c in classes],
                          ["", "### Customer feedback heat map",
                           "Heat 0 = most criticised part, 100 = best rated part of this model and market. Comments = unique comment IDs,",
                           "mentions = classified rows. Edit values here; Torque's Concept 3D shows them.", "",
                           *table(HEAT_COLS, heat), "", "### Options today", "From the German price list.", "", *table(OPT_COLS, orow)],
                          [f"part_id: {pid}", *front])
    # VFC: overview + one note per feature class (level 2) with its level 3 and level 2+3 tables
    part_of = defaultdict(list)
    for pid, p in parts.items():
        for c in p["feature_classes"]:
            part_of[c].append(pid)
    lvl2 = counts(r, "Vfc level2 Name")
    sub_hub("VFC", ["Vehicle feature classes: level 2 (feature), level 3 (aspect), level 2 3 (combined)."],
            [link(vfc_note(code, v)) for v, *_ in lvl2 if v != NO_CLASS],
            ["", "### VFC level 2", *table(["Feature class", *COUNT_COLS],
                                           [[link(vfc_note(code, v), v) if v != NO_CLASS else v, *x] for v, *x in lvl2]),
             "", "### VFC level 3", *table(["Aspect", *COUNT_COLS], counts(r, "Vfc level3 Name"))])
    for v, *x in lvl2:
        if v == NO_CLASS:
            continue
        sub_rows = [y for y in r if y["Vfc level2 Name"] == v]
        notes.add(vfc_note(code, v), v, "Feature class (VFC level 2)",
                  [f"**Model:** {link(mnote, m['folder'])}", f"**Comments:** {x[0]:,} unique IDs, {x[1]:,} rows"],
                  [link(hub(f"{base}/VFC"))] + [link(part_note(code, parts[p])) for p in part_of.get(v, [])],
                  ["", *table(["Feature class", *COUNT_COLS], [[v, *x]]),
                   "", "### VFC level 3", *table(["Aspect", *COUNT_COLS], counts(sub_rows, "Vfc level3 Name")),
                   "", "### VFC level 2 3", *table(["Class and aspect", *COUNT_COLS], counts(sub_rows, "Vfc level2 3 Name")),
                   "", "### By market (mentions)", *table(["Market", "Mentions"],
                                                          sorted(Counter(MARKET_LABEL[feedback.market_of(y["Country"])] for y in sub_rows).items()))],
                  front)
    # ID: one table, no texts
    by_id = {}
    for y in r:
        e = by_id.setdefault(y["ID"], {"src": y["Source"], "c": y["Country"], "e": y["Engine Type"], "t": [], "v": []})
        if y["Feedback Type"] and y["Feedback Type"] not in e["t"]:
            e["t"].append(y["Feedback Type"])
        if y["Vfc level2 Name"] not in ("", NO_CLASS) and y["Vfc level2 Name"] not in e["v"]:
            e["v"].append(y["Vfc level2 Name"])
    sub_hub("ID", ["Every comment ID with source, country, engine, feedback types and feature classes. Comment texts stay out of the vault (spec D8)."],
            [], ["", f"- {len(by_id):,} comment IDs, {len(r):,} rows.", "",
                 *table(["ID", "Source", "Country", "Engine", "Feedback types", "VFC level 2"],
                        [[i, e["src"], e["c"], e["e"], ", ".join(e["t"]), ", ".join(e["v"])] for i, e in by_id.items()])])
    # Country, Engine, Source, Feedback: hub table + one note per value
    dims = {"Country": ("Country", "Comments per country, with the Torque market."),
            "Engine": ("Engine Type", "Comments per drivetrain (BEVE = battery electric)."),
            "Source": ("Source", "Comments per source."),
            "Feedback": ("Feedback Type", "Feedback types; empty = untyped.")}
    for dim, (col, text) in dims.items():
        data = counts(r, col)
        label = lambda v: (f"{v} ({MARKET_LABEL[feedback.market_of(v)]})" if dim == "Country" else
                           f"{v} ({SOURCE_HINT[v]})" if dim == "Source" and v in SOURCE_HINT else v)
        value_note = lambda v: f"{base}/{dim}/{safe(v)}"
        values = [v for v, *_ in data if v != "(empty)"]
        sub_hub(dim, [text], [link(value_note(v)) for v in values],
                ["", *table([dim, *COUNT_COLS], [[link(value_note(v), label(v)) if v != "(empty)" else v, *x] for v, *x in data])])
        for v, *x in data:
            if v == "(empty)":
                continue
            sub_rows = [y for y in r if y[col] == v]
            top = counts([y for y in sub_rows if y["Vfc level2 Name"] not in ("", NO_CLASS)], "Vfc level2 Name")[:15]
            notes.add(value_note(v), v, dim, [f"**Model:** {link(mnote, m['folder'])}", f"**{dim}:** {label(v)}"],
                      [link(hub(f"{base}/{dim}"))] + [link(vfc_note(code, c)) for c, *_ in top],
                      ["", *table([dim, *COUNT_COLS], [[label(v), *x]]),
                       "", "### Top feature classes", *table(["Feature class", *COUNT_COLS],
                                                             [[link(vfc_note(code, c), c), *y] for c, *y in top])],
                      front)


def write(vault: Path, refresh: bool, graph: dict) -> int:
    notes = build(graph, datetime.now().strftime("%Y-%m-%d"))
    written = 0
    for rel, text in notes.items():
        path = vault / f"{rel}.md"
        if path.exists() and (not refresh or MARKER not in path.read_text(encoding="utf-8")[:300]):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written += 1
    log.info("%d of %d note(s) written to %s/%s", written, len(notes), vault, ROOT)
    return written


def main() -> int:
    import json
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vault", type=Path, default=Path("~/.rowboat/knowledge"))
    ap.add_argument("--refresh", action="store_true", help="rewrite notes that still carry managed_by: ehl-visu")
    args = ap.parse_args()
    graph = json.loads((HERE.parent / "torque" / "dist" / "visu" / "graph.json").read_text(encoding="utf-8"))
    write(args.vault.expanduser(), args.refresh, graph)
    return 0


if __name__ == "__main__":
    sys.exit(main())
