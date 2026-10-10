"""Prepare the local, never-committed parts of the Torque 3D view (demo/torque/dist/visu/).

    python demo/visu/prepare_local.py --model <2021_bmw_m4_competitionglTF.zip or its extracted folder>

1. data/feedback-{ALL,F70,G60,G70}.json: heat map scores from Dataset/*_feedback_hackathon.xlsx
   (they contain customer comment quotes, so like Torque's quotes.json they stay local).
2. models/bmw-m4-competition-2021/: the glTF car (CC-BY-NC-4.0, not redistributed via git).
   Without --model only the data is refreshed.
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

log = logging.getLogger("visu.prepare")
OUT = Path(__file__).resolve().parents[1] / "torque" / "dist" / "visu"
MODEL_ID = "bmw-m4-competition-2021"


def write_data(out: Path) -> None:
    ds = feedback.get_dataset()
    if ds.error:
        raise SystemExit(f"feedback data: {ds.error}")
    (out / "data").mkdir(parents=True, exist_ok=True)
    for series in [None, *feedback.SERIES]:
        path = out / "data" / f"feedback-{series or 'ALL'}.json"
        path.write_text(json.dumps(ds.scores(series), ensure_ascii=False), encoding="utf-8")
        log.info("wrote %s", path)


def install_model(src: Path, out: Path) -> None:
    dest = out / "models" / MODEL_ID
    if dest.exists():
        shutil.rmtree(dest)
    if src.is_file() and src.suffix.lower() == ".zip":
        with zipfile.ZipFile(src) as z:
            z.extractall(dest)
    elif (src / "scene.gltf").is_file():
        shutil.copytree(src, dest)
    else:
        raise SystemExit(f"--model must be the glTF zip or a folder with scene.gltf: {src}")
    if not (dest / "scene.gltf").is_file():
        raise SystemExit(f"no scene.gltf at the top of {src}")
    log.info("installed model into %s", dest)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", type=Path, help="glTF zip or extracted folder of the car model")
    parser.add_argument("--out", type=Path, default=OUT, help=f"default: {OUT}")
    args = parser.parse_args()
    write_data(args.out)
    if args.model:
        install_model(args.model.expanduser().resolve(), args.out)
    elif not (args.out / "models" / MODEL_ID / "scene.gltf").is_file():
        log.warning("car model not installed yet: re-run with --model <glTF zip>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
