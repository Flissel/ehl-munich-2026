"""The Dataset as a graph in Rowboat: Brand -> Model -> Country, ID, Engine, VFC 1-3, Source, Sales, Feedback.

    python demo/visu/brand.py [--vault ~/.rowboat/knowledge] [--refresh]

Every value comes from Dataset/ (the three *_feedback_hackathon.xlsx files and sales_volumes.xlsx); comment
texts never go into the vault (spec D8), the ID node lists IDs with their attributes only. Notes go to
<vault>/BMW/, are created only when missing (--refresh rewrites notes that still carry managed_by: ehl-visu)
and are attached to the app: models link to the Vehicle hub, Torque's top 10 and WP1's project note; VFC 1
classes link to the car parts they colour in Concept 3D (demo/torque/dist/visu/graph.json).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

import feedback

log = logging.getLogger("visu.brand")

HERE = Path(__file__).resolve().parent
DATASET = HERE.parents[1] / "Dataset"
GRAPH = HERE.parent / "torque" / "dist" / "visu" / "graph.json"
FOLDER = "BMW"
MARKER = "managed_by: ehl-visu"
BRAND = "BMW"
MODELS = {"F70": {"name": "BMW 1 Series", "series": "1 Series", "sheet": "F70", "feedback": True},
          "G60": {"name": "BMW 5 Series", "series": "5 Series", "sheet": "G60_G68", "feedback": True},
          "G68": {"name": "BMW 5 Series long wheelbase", "series": "5 Series", "sheet": "G60_G68", "feedback": False},
          "G70": {"name": "BMW 7 Series", "series": "7 Series", "sheet": "G70", "feedback": True}}
DIMENSIONS = ["Country", "ID", "Engine", "VFC 1", "VFC 2", "VFC 3", "Source", "Sales", "Feedback"]
# Dataset columns behind the dimensions (VFC 1 = feature class, VFC 2 = aspect, VFC 3 = both combined)
COLUMNS = {"Country": "Country", "Engine": "Engine Type", "Source": "Source", "Feedback": "Feedback Type",
           "VFC 1": "Vfc level2 Name", "VFC 2": "Vfc level3 Name", "VFC 3": "Vfc level2 3 Name"}
DIM_INFO = {"Country": "Comments per country (column Country), with the Torque market it belongs to.",
            "ID": "Every comment ID (column ID) with source, country, engine, feedback types and feature classes. "
                  "Comment texts stay out of the vault (spec D8).",
            "Engine": "Comments per drivetrain (column Engine Type; BEVE = battery electric).",
            "VFC 1": "Vehicle feature classes, level 2 (column Vfc level2 Name), linked to the car part they colour in Concept 3D.",
            "VFC 2": "Feedback aspect, level 3 (column Vfc level3 Name), e.g. Like: function, Not user-friendly.",
            "VFC 3": "Feature class and aspect combined (column Vfc level2 3 Name).",
            "Source": "Comments per source (column Source).",
            "Sales": "Sales volumes per market (Dataset/sales_volumes.xlsx).",
            "Feedback": "Feedback types (column Feedback Type) overall and per market; empty type = untyped."}
SOURCE_HINT = {"Source A": "owner reviews, many countries", "Source B": "customer care logs, US",
               "Source C": "quality survey, US", "Source D": "appeal survey, US"}
TYPES = ["Likes", "Difficult to Use", "Defect", "Wants"]
COUNT_COLS = ["Comments", "Mentions", "Likes", "Difficult to use", "Defects", "Wants", "Untyped"]
MARKET_LABEL = {"EU": "Europe", "CN": "China", "US": "USA", "RoW": "Rest of World"}


def load_rows() -> dict[str, list[dict]]:
    out = {}
    for code, m in MODELS.items():
        path = DATASET / f"{code}_feedback_hackathon.xlsx"
        if not m["feedback"] or not path.is_file():
            continue
        ws = load_workbook(path, read_only=True, data_only=True).worksheets[0]
        it = ws.iter_rows(values_only=True)
        head = [str(h) for h in next(it)]
        out[code] = [{k: ("" if v is None else str(v).strip()) for k, v in zip(head, r)} for r in it]
        log.info("%s: %d rows", code, len(out[code]))
    return out


def load_sales() -> dict[str, list[list]]:
    wb = load_workbook(DATASET / "sales_volumes.xlsx", read_only=True, data_only=True)
    return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}


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


def link(note: str, label: str | None = None) -> str:
    return f"[[{note}|{label}]]" if label else f"[[{note}]]"


def table(cols: list[str], rows: list[list]) -> list[str]:
    cell = lambda v: "" if v is None else str(v).replace("|", "/").replace("\n", " ")
    return ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]


def note(title: str, kind: str, info: list[str], connected: list[str], facts: list[str], today: str, extra: str = "") -> str:
    return "\n".join(["---", "source: dataset", MARKER, f"node: {kind}", *([extra] if extra else []), f"updated: {today}", "---",
                      f"# {title}", "", "## Info", f"**Type:** {kind}", *info, "", "## Connected to",
                      *[f"- {c}" for c in connected], "", "## Key facts", *facts, ""])


def build(rows: dict[str, list[dict]], sales: dict, graph: dict, today: str) -> dict[str, str]:
    part_of = defaultdict(list)  # feature class -> part notes
    for p in graph.get("parts", {}).values():
        for c in p["feature_classes"]:
            part_of[c].append(p["note"])
    nn = lambda code, dim=None: f"{FOLDER}/{code} {dim}" if dim else f"{FOLDER}/{MODELS[code]['name']} ({code})"
    brand_note = f"{FOLDER}/{BRAND}"
    texts = {}

    model_lines = []
    for code, m in MODELS.items():
        r = rows.get(code, [])
        model_lines.append([link(nn(code)), len({x["ID"] for x in r}) or "", len(r) or "",
                            sum(row[3] or 0 for row in sales.get(m["sheet"], [])[1:] if row and row[1])])
    texts[brand_note] = note(BRAND, "Brand", ["**Brand:** BMW (column Brand)", f"**Models:** {', '.join(MODELS)}"],
                             [link(nn(c)) for c in MODELS] + [link("Vehicle Parts/Vehicle"), link("Topics/Market Research")],
                             ["", *table(["Model", "Comments", "Mentions", "Sales 2025, all markets"], model_lines),
                              "", "- G60 and G68 share the sales sheet G60_G68; G68 (long wheelbase, China) has no feedback file."],
                             today)

    for code, m in MODELS.items():
        r = rows.get(code, [])
        dims = DIMENSIONS if r else ["Sales"]
        torque_top = f"Purchase Drivers/{m['series']} top 10"
        texts[nn(code)] = note(f"{m['name']} ({code})", "Model",
                               [f"**Brand:** {link(brand_note, BRAND)}", f"**Derivate (e-code):** {code}",
                                f"**Sales description:** {m['name']}", f"**Sales sheet:** {m['sheet']}"]
                               + ([f"**Comments:** {len({x['ID'] for x in r}):,} (unique IDs), {len(r):,} rows"] if r else
                                  ["**Comments:** none in the Dataset (China long wheelbase model, study and sales only)"]),
                               [link(brand_note)] + [link(nn(code, d)) for d in dims]
                               + [link(f"Projects/{code}"), link(torque_top), link("Vehicle Parts/Vehicle")],
                               ["", f"- Sub nodes: {', '.join(dims)}."], today, f"model: {code}")
        sub = lambda d, info, facts, more=(): note(f"{code} {d}", d, [f"**Model:** {link(nn(code))}", info],
                                                   [link(nn(code)), *more], facts, today, f"model: {code}")
        # Sales
        sheet = sales.get(m["sheet"], [])
        srows = [[x[0], x[1], *x[2:5]] for x in sheet[1:] if x and x[0]]
        texts[nn(code, "Sales")] = sub("Sales", DIM_INFO["Sales"],
                                       ["", *table(["Market", "Code", "2024", "2025", "2030 plan"], srows)]
                                       + (["", f"- Sheet {m['sheet']} reports G60 and G68 together."] if m["sheet"] == "G60_G68" else []))
        if not r:
            continue
        for d in ("Engine", "Source", "VFC 2", "VFC 3"):
            data = counts(r, COLUMNS[d])
            first = {"Engine": "Engine", "Source": "Source", "VFC 2": "VFC level 3", "VFC 3": "VFC level 2 3"}[d]
            if d == "Source":
                data = [[f"{v} ({SOURCE_HINT.get(v, '')})" if v in SOURCE_HINT else v, *rest] for v, *rest in data]
            texts[nn(code, d)] = sub(d, DIM_INFO[d], ["", *table([first, *COUNT_COLS], data)])
        data = counts(r, "Country")
        data = [[v, MARKET_LABEL.get(feedback.market_of(v), ""), *rest] for v, *rest in data]
        texts[nn(code, "Country")] = sub("Country", DIM_INFO["Country"], ["", *table(["Country", "Market", *COUNT_COLS], data)])
        data = counts(r, COLUMNS["VFC 1"])
        data = [[v, ", ".join(link(p) for p in part_of.get(v, [])), *rest] for v, *rest in data]
        linked = sorted({p for v, *_ in counts(r, COLUMNS["VFC 1"]) for p in part_of.get(v, [])})
        texts[nn(code, "VFC 1")] = sub("VFC 1", DIM_INFO["VFC 1"],
                                       ["", *table(["VFC level 2", "Car part (Concept 3D)", *COUNT_COLS], data)],
                                       [link(p) for p in linked])
        # Feedback: types overall and per market
        types = counts([{**x, "T": x["Feedback Type"] or "(untyped)"} for x in r], "T")
        per_mk = defaultdict(Counter)
        for x in r:
            per_mk[feedback.market_of(x["Country"])][x["Feedback Type"] or "(untyped)"] += 1
        mk_rows = [[MARKET_LABEL[k], *[per_mk[k][t] for t in TYPES], per_mk[k]["(untyped)"]] for k in MARKET_LABEL if per_mk[k]]
        texts[nn(code, "Feedback")] = sub("Feedback", DIM_INFO["Feedback"],
                                          ["", "### By type", *table(["Feedback type", *COUNT_COLS], types),
                                           "", "### By market (mentions)", *table(["Market", "Likes", "Difficult to use", "Defects", "Wants", "Untyped"], mk_rows)])
        # ID: one row per comment ID, no text
        by_id = {}
        for x in r:
            e = by_id.setdefault(x["ID"], {"src": x["Source"], "c": x["Country"], "e": x["Engine Type"], "t": [], "v": []})
            if x["Feedback Type"] and x["Feedback Type"] not in e["t"]:
                e["t"].append(x["Feedback Type"])
            if x["Vfc level2 Name"] and x["Vfc level2 Name"] != "no_class_found" and x["Vfc level2 Name"] not in e["v"]:
                e["v"].append(x["Vfc level2 Name"])
        id_rows = [[i, e["src"], e["c"], e["e"], ", ".join(e["t"]), ", ".join(e["v"])] for i, e in by_id.items()]
        texts[nn(code, "ID")] = sub("ID", DIM_INFO["ID"],
                                    ["", f"- {len(id_rows):,} comment IDs, {len(r):,} rows.", "",
                                     *table(["ID", "Source", "Country", "Engine", "Feedback types", "VFC level 2"], id_rows)])
    return texts


def write(vault: Path, refresh: bool) -> int:
    graph = json.loads(GRAPH.read_text(encoding="utf-8")) if GRAPH.exists() else {}
    texts = build(load_rows(), load_sales(), graph, datetime.now().strftime("%Y-%m-%d"))
    written = 0
    for rel, text in texts.items():
        path = vault / f"{rel}.md"
        if path.exists() and (not refresh or MARKER not in path.read_text(encoding="utf-8")[:300]):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written += 1
    log.info("%d of %d note(s) written to %s/%s", written, len(texts), vault, FOLDER)
    return written


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vault", type=Path, default=Path("~/.rowboat/knowledge"))
    ap.add_argument("--refresh", action="store_true", help="rewrite notes that still carry managed_by: ehl-visu")
    args = ap.parse_args()
    write(args.vault.expanduser(), args.refresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
