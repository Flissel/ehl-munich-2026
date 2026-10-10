"""Torque's numbers without a Dataset source, as PM-editable assumption notes in Rowboat.

    python demo/visu/assumptions.py notes [--vault ~/.rowboat/knowledge] [--refresh]   # seed -> Assumptions/*.md
    python demo/visu/assumptions.py read  [--vault ...]                               # Assumptions/*.md -> JSON (stdout)

Competitor benchmarks and prices, feature prices and price response, customer segments and the choice model,
ranking weights, car dimensions and per-driver feasibility were hand-set in the Torque prototype. They are
kept, but as assumptions: one note per group with the values in a ```json block that the PM (or Rowboat's
AI) edits. `vault.py sync` writes them to dist/visu/data/assumptions.json, which Torque reads before its own
seed copy (dist/assumptions.seed.json). Replace a value with a researched one by editing the block and
naming the source under "Sources".
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

log = logging.getLogger("visu.assumptions")

HERE = Path(__file__).resolve().parent
SEED = HERE.parent / "torque" / "dist" / "assumptions.seed.json"
FOLDER = "Assumptions"
MARKER = "managed_by: ehl-visu"
# note title -> (keys of the seed in this note, what the values mean)
GROUPS = {
    "Competitors": (["modelExtra", "rivals"],
                    "modelExtra per model ('1', '5', '7'): segment, competitor scores per attribute (0-100, attribute order as "
                    "Torque's ATTRS) and today's car. rivals per model: name, markets, price EUR, purchase drivers they offer, "
                    "range km, complexity, segment bias."),
    "Feature prices and price response": (["features"],
                                          "Per purchase driver: feature name, price willingness per segment (pw), market "
                                          "adjustments (mk), cost in EUR (number or per model), complexity (cx), only (markets)."),
    "Standard equipment": (["baseOn"], "Purchase drivers already standard today per model (read from the option lists by hand)."),
    "Customer segments and choice model": (["segments"],
                                           "Segments, segment shares per market (SEG_MK) and per model (SEG_ADJ), price and "
                                           "complexity sensitivities (BETA, BETA_M, GAMMA, PW_SCALE, CX_SCALE), today's market share (SHARE0)."),
    "Ranking weights": (["weights"], "Weights of the ranking factors: the default ('Learned from data') and the presets."),
    "Car dimensions": (["carDims"], "Front overhang, wheelbase, rear overhang, width, height in metres per model."),
    "Requirement parameters": (["requirements"],
                               "Per purchase driver: feasibility 0-100 (feas), China weights (cn) and the attribute index (pa)."),
}


def note_text(title: str, keys: list[str], what: str, seed: dict, today: str) -> str:
    block = json.dumps({k: seed[k] for k in keys}, indent=1, ensure_ascii=False)
    return "\n".join(["---", "source: assumption", MARKER, f"updated: {today}", "---", f"# {title}", "", "## Info",
                      "**Type:** Assumption", "**Status:** hand-set in the Torque prototype, no Dataset source",
                      f"**Used by:** Torque (dist/visu/data/assumptions.json)", "", "## About", what, "",
                      "## Values", "Edit the JSON below (keep the keys); Torque uses it from its next reload.", "",
                      "```json", block, "```", "", "## Sources",
                      "- None yet. When a value is replaced by researched data, name the source here.", ""])


def write_notes(vault: Path, refresh: bool) -> int:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    today, written = datetime.now().strftime("%Y-%m-%d"), 0
    for title, (keys, what) in GROUPS.items():
        path = vault / FOLDER / f"{title}.md"
        if path.exists() and (not refresh or MARKER not in path.read_text(encoding="utf-8")[:300]):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(note_text(title, keys, what, seed, today), encoding="utf-8")
        written += 1
    log.info("%d of %d assumption note(s) written to %s", written, len(GROUPS), vault / FOLDER)
    return written


def read(vault: Path) -> dict:
    """Seed values overlaid with every valid ```json block of the Assumptions notes (a broken block keeps the seed)."""
    out = json.loads(SEED.read_text(encoding="utf-8"))
    out["_notes"] = {}
    for title, (keys, _) in GROUPS.items():
        path = vault / FOLDER / f"{title}.md"
        if not path.exists():
            continue
        m = re.search(r"```json\s*\n(.*?)\n```", path.read_text(encoding="utf-8"), flags=re.S)
        try:
            block = json.loads(m[1]) if m else {}
        except ValueError as err:
            log.warning("%s: invalid JSON (%s), using the seed values", path.name, err)
            continue
        for k in keys:
            if k in block:
                out[k] = block[k]
        out["_notes"][title] = f"{FOLDER}/{title}"
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["notes", "read"])
    ap.add_argument("--vault", type=Path, default=Path("~/.rowboat/knowledge"))
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    vault = args.vault.expanduser()
    if args.command == "notes":
        write_notes(vault, args.refresh)
    else:
        json.dump(read(vault), sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
