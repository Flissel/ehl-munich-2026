"""Option list features per model, linked to the parts of the 3D car.

Source: outputs/markdown/options/processed/<model>_options_features.md (from feat/ehl-search:
scripts/preprocess_options.py, an LLM extract of Dataset/<model>_OptionList.PDF, German price lists).
Each "#### name" block has Availability, Package (option code or package name), Price and Source pages.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger("visu.options")

# Part ids of the 3D car -> keywords in option names (German and English, lower case).
PART_KEYWORDS: dict[str, list[str]] = {
    "wheels": ["räder", "reifen", "wheel", "tire", "tyre", "brems", "brake", "fahrwerk", "suspension"],
    "seats": ["sitz", "seat", "massage", "lordose", "lumbar"],
    "rear-seats": ["fond", "rear seat", "rear-seat", "executive lounge", "theatre", "theater"],
    "central-display": ["display", "navigation", "curved", "operating system", "idrive", "live cockpit", "head-up"],
    "instrument-cluster": ["head-up", "instrument", "live cockpit"],
    "door-trims": ["sound", "harman", "bowers", "audio", "lautsprecher", "speaker", "ambient", "interieurleiste", "trim"],
    "climate-controls": ["klima", "climate", "standheiz", "standlüft", "ventilation", "air conditioning"],
    "steering-wheel": ["lenkrad", "steering"],
    "lights": ["licht", "light", "glow", "scheinwerfer", "laser", "\bled\b"],
    "kidney-grille": ["niere", "grille", "iconic glow"],
    "roof": ["dach", "roof", "panorama", "sky lounge"],
    "trunk-lid": ["heckklappe", "tailgate", "trunk", "gepäck", "kofferraum", "anhänger", "trailer", "durchlade"],
    "doors": ["tür", "door", "komfortzugang", "comfort access", "soft close", "soft-close", "schlüssel", "\bkey\b"],
    "windshield": ["driving assistant", "fahrassistent", "assist", "frontkamera", "camera"],
    "bumpers": ["parking", "park", "parkassistent", "rückfahr", "surround view"],
    "body": ["lackierung", "paint", "carbon exterior", "carbon exterieur", "shadow line"],
    "dashboard": ["leder", "leather", "merino", "alcantara", "veganza", "glass application", "interieur", "craftedclarity"],
    "center-console": ["phone", "telefon", "wireless", "ablage", "smartphone", "ladeschale"],
    "charging": ["laden", "charging", "ladekabel", "wallbox", "\bkw\b"],
}
GROUPS: dict[str, list[str]] = {
    "wheels": ["wheel-front-left", "wheel-front-right", "wheel-rear-left", "wheel-rear-right"],
    "seats": ["seat-driver", "seat-passenger"],
    "door-trims": ["door-trim-left", "door-trim-right"],
    "lights": ["headlight-left", "headlight-right", "taillight-left", "taillight-right"],
    "doors": ["door-left", "door-right"],
    "bumpers": ["front-bumper", "rear-bumper"],
    "body": ["hood", "fender-front-left", "fender-front-right", "quarter-rear-left", "quarter-rear-right"],
    "charging": ["quarter-rear-left", "underbody"],
}
SKIP_SECTIONS = {"technical specifications", "technical values", "dimensions and weights", "environmental impact",
                 "recycling information", "delivery options", "additional information", "vehicle models",
                 "vehicle prices & models"}


def parts_for(name: str) -> list[str]:
    n = name.lower()
    out: list[str] = []
    hits = {key for key, words in PART_KEYWORDS.items() if any(re.search(w, n) for w in words)}
    # The more specific match wins: a heated steering wheel is no road wheel, park assist no front camera.
    if "steering-wheel" in hits:
        hits.discard("wheels")
    if "bumpers" in hits:
        hits.discard("windshield")
    for key in PART_KEYWORDS:
        if key in hits:
            for p in GROUPS.get(key, [key]):
                if p not in out:
                    out.append(p)
    return out


def price_eur(text: str) -> int | None:
    """'1.220,–', '2,400 EUR', '70.900,– €' -> euros; None for 'unclear' or 'standard'."""
    m = re.search(r"\d[\d.,]*", text or "")
    if not m:
        return None
    digits = m.group(0)
    # German thousands dot / English thousands comma; ',–' or ',00' cents are dropped.
    digits = re.sub(r"[.,](\d{3})(?!\d)", r"\1", digits)
    digits = re.split(r"[.,]", digits)[0]
    return int(digits) if digits.isdigit() else None


def parse(path: Path, linked_only: bool = True) -> list[dict]:
    options, section, cur = [], "", None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            section = line[4:].strip()
        elif line.startswith("#### "):
            cur = {"name": line[5:].strip(), "category": section, "availability": "", "package": "",
                   "price": "", "pages": ""}
            if section.lower() not in SKIP_SECTIONS:
                options.append(cur)
        elif cur and line.startswith("- "):
            key, _, val = line[2:].partition(":")
            k = {"Availability": "availability", "Package": "package", "Price": "price",
                 "Source pages": "pages"}.get(key.strip())
            if k:
                cur[k] = val.strip()
    seen, out = set(), []
    for o in options:
        key = o["name"].lower()
        parts = parts_for(o["name"] + " " + o["category"] if o["category"].lower() in ("wheels & tires",) else o["name"])
        if key in seen or (linked_only and not parts) or not o["availability"]:
            continue
        seen.add(key)
        out.append({**o, "price_eur": price_eur(o["price"]), "parts": parts})
    return out


def write_all(md_dir: Path, out_dir: Path, models: list[str]) -> None:
    import json
    for code in models:
        src = md_dir / f"{code.lower()}_options_features.md"
        if not src.is_file():
            log.warning("no option features for %s (%s)", code, src)
            continue
        opts = parse(src)
        (out_dir / f"options-{code}.json").write_text(json.dumps(
            {"model": code, "source": f"{code}_OptionList.PDF via {src.name}", "options": opts},
            ensure_ascii=False), encoding="utf-8")
        log.info("wrote options-%s.json (%d options linked to parts)", code, len(opts))
