"""Fill the real-data block of demo/showcase/index.html from Dataset/ and demo/link-targets.json.

Usage (from the repo root):
    pip install pandas openpyxl
    python demo/showcase/fill_data.py

Only the <script id="data-real"> block is rewritten. The hand-edited <script id="data-team"> block
(placeholders, requirement texts, audit events, screenshots) is never touched.
Only aggregates leave this script: counts, means, volumes. No customer text (spec D8).
"""
import argparse
import json
import logging
import re
from datetime import date
from pathlib import Path

import pandas as pd

log = logging.getLogger("showcase.fill")
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

MODELS = {"F70": "BMW 1 Series", "G60": "BMW 5 Series", "G68": "BMW 5 Series LWB", "G70": "BMW 7 Series"}
SALES_SHEET = {"F70": "F70", "G60": "G60_G68", "G68": "G60_G68", "G70": "G70"}
TYPES = {"Likes": "likes", "Wants": "wants", "Difficult to Use": "difficult", "Defect": "defect"}
EU = {"GB", "SE", "FR", "DK", "FI", "NO", "ES", "LV", "DE", "IT", "NL", "BE", "AT", "CH", "PL", "IE", "PT"}
YEARS = ["volume_2024", "volume_2025", "volume_2030"]
BLOCK = re.compile(r'(<script id="data-real" type="application/json">)(.*?)(</script>)', re.S)


def market(country: str) -> str:
    if country in ("US", "CN"):
        return country
    return "EU" if country in EU else "RoW"


def counts(series: pd.Series) -> dict:
    return {str(k): int(v) for k, v in series.value_counts().items()}


def feedback(path: Path) -> dict:
    fb = pd.read_excel(path)
    fb["market"] = fb["Country"].map(market)
    fb["type"] = fb["Feedback Type"].map(TYPES).fillna("untyped")
    unique = fb.drop_duplicates("Customer Feedback")
    signals = []
    for kind, types, top in (("pain", ["difficult", "defect"], 6), ("want", ["wants"], 3)):
        sub = fb[fb["type"].isin(types)].dropna(subset=["Vfc level2 Name"])
        sub = sub.drop_duplicates(["Customer Feedback", "Vfc level2 Name"])
        found = [{"kind": kind, "category": cat, "count": len(grp), "market": grp["market"].mode().iat[0],
                  "defects": int((grp["type"] == "defect").sum())}
                 for cat, grp in sub.groupby("Vfc level2 Name")]
        signals += sorted(found, key=lambda s: -s["count"])[:top]
    return {"rows": len(fb), "unique": len(unique), "types": counts(unique["type"]),
            "markets": counts(unique["market"]), "engines": counts(unique["Engine Type"]), "signals": signals}


def study_cn_eu(path: Path) -> dict:
    raw = pd.read_excel(path, sheet_name="CN_EU_2025", header=None)
    markets = raw.iloc[1, 1:].ffill()
    cols = [{"market": "CN" if m == "China" else m, "product": str(p).split()[-1]}
            for m, p in zip(markets, raw.iloc[2, 1:]) if pd.notna(p)]
    items = []
    for i in range(2, len(raw) - 1):
        if pd.notna(raw.iat[i, 0]) and raw.iat[i + 1, 0] == "Mean":
            values = [round(float(v), 2) for v in raw.iloc[i + 1, 1:len(cols) + 1]]
            items.append({"name": str(raw.iat[i, 0]).strip(), "values": values})
    return {"scale": "Mean satisfaction, 1 to 10", "columns": cols, "items": items}


def us_items(path: Path) -> int:
    raw = pd.read_excel(path, sheet_name="US_2025", header=None)
    return int((raw[1].isna() & raw[0].notna()).sum())


def volumes(path: Path) -> dict:
    out = {}
    for sheet in ("F70", "G60_G68", "G70"):
        df = pd.read_excel(path, sheet_name=sheet)
        out[sheet] = {r.market_code: [int(getattr(r, y)) for y in YEARS] for r in df.itertuples()}
    return out


def candidates(study: dict, n: int = 10) -> list:
    rows = []
    for item in study["items"]:
        if item["name"].startswith("Overall product"):
            continue
        vals = item["values"]
        worst = min(range(len(vals)), key=vals.__getitem__)
        rows.append({"attribute": item["name"], "mean": round(sum(vals) / len(vals), 2),
                     "worst": vals[worst], "worst_in": study["columns"][worst]})
    return sorted(rows, key=lambda r: r["mean"])[:n]


def graph_base(path: Path) -> dict:
    lt = json.loads(path.read_text(encoding="utf-8"))
    products = [{"id": k, "roadmap": v["roadmap"], "model": v["model"]} for k, v in lt["products"].items()]
    return {"products": products, "roadmaps": lt["roadmaps"], "channels": lt["channels"],
            "research": lt["research"], "team": lt["team"], "frozen": lt["frozen"]}


def build(dataset: Path) -> dict:
    studies = dataset / "F70_G60_G68_G70_customer_studies.xlsx"
    study = study_cn_eu(studies)
    vol = volumes(dataset / "sales_volumes.xlsx")
    products = []
    for code, model in MODELS.items():
        fb_path = dataset / f"{code}_feedback_hackathon.xlsx"
        overall = next(i for i in study["items"] if i["name"].startswith("Overall product"))
        products.append({
            "code": code, "model": model, "sales_sheet": SALES_SHEET[code],
            "feedback": feedback(fb_path) if fb_path.exists() else None,
            "option_list": (dataset / f"{code}_OptionList.PDF").exists(),
            "satisfaction": [{"market": c["market"], "value": v}
                             for c, v in zip(study["columns"], overall["values"]) if c["product"] == code],
        })
        log.info("%s: %s feedback rows", code, products[-1]["feedback"]["rows"] if products[-1]["feedback"] else "no")
    fb = [p["feedback"] for p in products if p["feedback"]]
    return {
        "generated": date.today().isoformat(),
        "source": "Dataset/ (BMW hackathon files) and demo/link-targets.json",
        "kpis": {
            "feedback_rows": sum(f["rows"] for f in fb),
            "unique_comments": sum(f["unique"] for f in fb),
            "derivatives": len(MODELS),
            "study_cells": len(study["items"]) * len(study["columns"]),
            "us_study_items": us_items(studies),
            "volume_2030": sum(v[2] for sheet in vol.values() for v in sheet.values()),
        },
        "products": products,
        "volumes": {"years": [2024, 2025, 2030], "sheets": vol},
        "study": study,
        "candidates": candidates(study),
        "graph": graph_base(HERE.parent / "link-targets.json"),
    }


def inject(html: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, indent=1).replace("</", "<\\/")
    new, n = BLOCK.subn(lambda m: f"{m.group(1)}\n{payload}\n{m.group(3)}", html, count=1)
    if n != 1:
        raise ValueError('index.html has no <script id="data-real" type="application/json"> block')
    return new


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dataset", type=Path, default=ROOT / "Dataset")
    ap.add_argument("--html", type=Path, default=HERE / "index.html")
    args = ap.parse_args()
    data = build(args.dataset)
    args.html.write_text(inject(args.html.read_text(encoding="utf-8"), data), encoding="utf-8")
    log.info("wrote real data into %s (%d feedback rows, %d study cells)",
             args.html, data["kpis"]["feedback_rows"], data["kpis"]["study_cells"])


if __name__ == "__main__":
    main()
