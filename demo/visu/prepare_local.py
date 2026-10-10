"""Prepare the local, never-committed parts of the Torque 3D view (demo/torque/dist/visu/).

    python demo/visu/prepare_local.py --cars "<folder with the car zips>"

1. data/feedback-<series>[-<market>].json: heat map scores per series (ALL, F70, G60, G70) and
   Torque market (EU, CN, US, RoW) from Dataset/*_feedback_hackathon.xlsx
   (they contain customer comment quotes, so like Torque's quotes.json they stay local).
   data/options-<series>.json: option list features linked to car parts (outputs/markdown/options).
2. models/<car>/: the three glTF cars, one per model family of the Dataset (Sketchfab, Ddiaz Design,
   CC-BY-NC-SA-4.0, not redistributed via git): X1 for the 1 Series, X5 for the 5 Series, X7 for the 7 Series.
   Without --cars only the data is refreshed.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import zipfile
from pathlib import Path

import feedback
import options

log = logging.getLogger("visu.prepare")
OUT = Path(__file__).resolve().parents[1] / "torque" / "dist" / "visu"
OPTIONS_MD = Path(__file__).resolve().parents[2] / "outputs" / "markdown" / "options" / "processed"
# car id (src/models/cars.ts) -> zip file name in the cars folder
CARS = {"bmw-x1-2020": "2020_bmw_x1_xdrive_18d.zip", "bmw-x5-2019": "2019_bmw_x5_xdrive30d.zip",
        "bmw-x7-2019": "2019_bmw_x7_xdrive40i.zip"}


def write_data(out: Path) -> None:
    ds = feedback.get_dataset()
    if ds.error:
        raise SystemExit(f"feedback data: {ds.error}")
    (out / "data").mkdir(parents=True, exist_ok=True)
    for series in [None, *feedback.SERIES]:
        for market in [None, *feedback.MARKETS]:
            name = f"feedback-{series or 'ALL'}{'-' + market if market else ''}.json"
            scores = ds.scores(series, market)
            (out / "data" / name).write_text(json.dumps(scores, ensure_ascii=False), encoding="utf-8")
            log.info("wrote %s (%d comments, %d classified mentions)", name, scores["comments"], scores["rows_used"])
    options.write_all(OPTIONS_MD, out / "data", list(feedback.SERIES))


def install_cars(folder: Path, out: Path) -> None:
    for car, zip_name in CARS.items():
        src, dest = folder / zip_name, out / "models" / car
        if not src.is_file():
            log.warning("missing %s: %s is not installed", src, car)
            continue
        if dest.exists():
            shutil.rmtree(dest)
        with zipfile.ZipFile(src) as z:
            z.extractall(dest)
        if not (dest / "scene.gltf").is_file():
            raise SystemExit(f"no scene.gltf at the top of {src}")
        log.info("installed %s into %s", car, dest)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cars", type=Path, help="folder with the car zips (see CARS)")
    parser.add_argument("--out", type=Path, default=OUT, help=f"default: {OUT}")
    args = parser.parse_args()
    write_data(args.out)
    if args.cars:
        install_cars(args.cars.expanduser().resolve(), args.out)
    missing = [c for c in CARS if not (args.out / "models" / c / "scene.gltf").is_file()]
    if missing:
        log.warning("cars not installed yet: %s (re-run with --cars <folder>)", ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
