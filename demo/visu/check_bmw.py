"""Checks Torque's data file (demo/torque/dist/bmw.json) against Dataset/.

    python demo/visu/check_bmw.py      # exit 1 on any mismatch

bmw.json holds the Dataset aggregates Torque ranks with (produced by the prototype's bmw_pipeline.py, moved out
of the page code on 2026-10-10). This recomputes its countable facts from the raw workbooks: rows, unique
comments, comments per market, country, drivetrain, source and feedback type, and the sales plan.
"""
from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from pathlib import Path

from openpyxl import load_workbook

log = logging.getLogger("check_bmw")
REPO = Path(__file__).resolve().parents[2]
BMW = REPO / "demo" / "torque" / "dist" / "bmw.json"
EUROPE = {"GB", "DE", "FR", "IT", "ES", "SE", "DK", "FI", "NO", "NL", "BE", "AT", "CH", "PL", "IE", "PT", "LV"}
TYPE = {"Likes": "L", "Wants": "W", "Difficult to Use": "D", "Defect": "F"}
ENGINE = {"BEVE": "BEV"}


def market(country: str) -> str:
    return country if country in ("US", "CN") else "EU" if country in EUROPE else "RoW"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    data, bad = json.loads(BMW.read_text(encoding="utf-8")), 0

    def check(what: str, ours, theirs) -> None:
        nonlocal bad
        if ours != theirs:
            bad += 1
            log.error("MISMATCH %s: Dataset %s, bmw.json %s", what, ours, theirs)

    for code, meta in data["meta"].items():
        ws = load_workbook(REPO / "Dataset" / f"{code}_feedback_hackathon.xlsx", read_only=True, data_only=True).worksheets[0]
        it = ws.iter_rows(values_only=True)
        h = list(next(it))
        rows = [dict(zip(h, r)) for r in it]
        first = {}
        for r in rows:
            first.setdefault(r["ID"], r)
        check(f"{code} rows", len(rows), meta["rows"])
        check(f"{code} unique comments", len(first), meta["unique"])
        check(f"{code} comments per market", {k: v for k, v in Counter(market(r["Country"]) for r in first.values()).items()},
              {k: v for k, v in meta["mk"].items() if v})
        check(f"{code} top countries", dict(Counter(r["Country"] for r in first.values()).most_common(8)), meta["countries"])
        check(f"{code} drivetrains", {k: v for k, v in Counter(ENGINE.get(r["Engine Type"], r["Engine Type"]) for r in first.values()).items()},
              {k: v for k, v in meta["eng"].items() if v})
        check(f"{code} sources", {k: v for k, v in Counter(r["Source"][-1] for r in first.values()).items()},
              {k: v for k, v in meta["src"].items() if v})
    wb = load_workbook(REPO / "Dataset" / "sales_volumes.xlsx", read_only=True, data_only=True)
    keys = {"F70": "1", "G60_G68": "5", "G70": "7"}
    for ws in wb.worksheets:
        for r in list(ws.iter_rows(values_only=True))[1:]:
            if r and r[1]:
                check(f"sales {ws.title} {r[1]}", [v or 0 for v in r[2:5]], [v or 0 for v in data["sales"][keys[ws.title]][r[1]]])
    log.info("%s: %d mismatch(es)", BMW.name, bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
