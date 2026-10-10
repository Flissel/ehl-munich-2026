"""Customer-feedback heat map scores from the EHL Munich 2026 dataset.

Source: <repo root>/Dataset/{F70,G60,G70}_feedback_hackathon.xlsx (sheet Feedback_Explorer).
Each row = one classified customer comment with a Feedback Type (Likes / Defect / Difficult to Use /
Wants) and a vehicle feature class ("Vfc level2 Name"). We map feature classes onto the 3D model's
component IDs and turn the balance of positive vs. negative comments into a 0-100 score.

Important: the dataset describes the BMW 1/5/7 Series (F70/G60/G70), not the M4. The M4 glTF is used
as the visual stand-in, so scores mean "customer sentiment about this kind of part" for the chosen
series. Components without a specific feature class fall back to general exterior feedback.
"""
from __future__ import annotations

import logging
import os
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("bmw.feedback")

SERIES = {"F70": "BMW 1 Series (F70)", "G60": "BMW 5 Series (G60)", "G70": "BMW 7 Series (G70)"}

# Markets as in Torque (demo/torque): EU, CN, US, RoW. Country codes of the Dataset rows.
MARKETS = {"EU": "Europe", "CN": "China", "US": "USA", "RoW": "Rest of world"}
EUROPE = {"AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GB", "GR", "HR", "HU", "IE",
          "IS", "IT", "LT", "LU", "LV", "MT", "NL", "NO", "PL", "PT", "RO", "SE", "SI", "SK"}


def market_of(country: str) -> str:
    c = country.strip().upper()
    return "US" if c == "US" else "CN" if c == "CN" else "EU" if c in EUROPE else "RoW"

BODY = ["hood", "roof", "trunk-lid", "fender-front-left", "fender-front-right", "quarter-rear-left",
        "quarter-rear-right", "pillars-sills", "door-left", "door-right"]
WHEELS = ["wheel-front-left", "wheel-front-right", "wheel-rear-left", "wheel-rear-right"]
DOORS = ["door-left", "door-right"]
ALL_EXTERIOR = BODY + WHEELS + [
    "underbody", "front-splitter", "front-bumper", "rear-diffuser", "rear-bumper", "side-skirt-left",
    "side-skirt-right", "rear-spoiler", "kidney-grille", "lower-intake", "mirror-left", "mirror-right",
    "windshield", "rear-window", "window-left", "window-right", "headlight-left", "headlight-right",
    "taillight-left", "taillight-right", "exhaust", "roof-fin", "badges", "license-plate"]

FRONT_SEATS = ["seat-driver", "seat-passenger"]
DOOR_TRIMS = ["door-trim-left", "door-trim-right"]
INTERIOR = FRONT_SEATS + DOOR_TRIMS + [
    "rear-seats", "instrument-cluster", "central-display", "climate-controls", "center-console", "dashboard",
    "steering-wheel", "pedals", "overhead-console", "headliner", "interior-side-panels", "seat-belts",
    "interior-mirror", "sun-visors"]

# Feature class (Vfc level2 Name) -> component ids. Specific classes only.
SPECIFIC: dict[str, list[str]] = {
    "Wheels / tires": WHEELS, "RSC tire": WHEELS, "Tirefit": WHEELS, "Tire pressure control": WHEELS,
    "Braking": WHEELS,
    "Door, open / close": DOORS, "Automatic doors": DOORS, "Resting state after door opening": DOORS,
    "Door, front": DOORS, "Door, finisher panel, front": DOORS, "Outer door handle, front": DOORS,
    "Outer door handle, rear": DOORS,
    "Side window, open / close": ["window-left", "window-right"],
    "Exterior rearview mirror": ["mirror-left", "mirror-right"],
    "Panorama glass roof": ["roof"], "Roof": ["roof"], "Roof function centre": ["roof"],
    "Exterior lighting": ["headlight-left", "headlight-right", "taillight-left", "taillight-right"],
    "Fog light": ["headlight-left", "headlight-right"],
    "non-contact trunk lid opening": ["trunk-lid"], "Trunk lid, open / close": ["trunk-lid"],
    "Trunk lid": ["trunk-lid"], "Trunk light": ["trunk-lid"],
    "Windshield": ["windshield"], "Windshield wiper": ["windshield"],
    "Heated rear window": ["rear-window"], "Rear wiper": ["rear-window"],
    "Radiator grille": ["kidney-grille"],
    "Hood": ["hood"], "Hood, open / close": ["hood"],
    "Bumper, front": ["front-bumper", "front-splitter"], "Bumper, rear": ["rear-bumper", "rear-diffuser"],
    "Towing eye": ["front-bumper", "rear-bumper"],
    "Exhaust system": ["exhaust"],
    "Side sill trim panel": ["side-skirt-left", "side-skirt-right"],
    # --- interior
    "Seats": FRONT_SEATS + ["rear-seats"], "Seating, ventilate / heat": FRONT_SEATS, "Seat massage": FRONT_SEATS,
    "Seat memory": FRONT_SEATS, "Child restraint seat, use": ["rear-seats"], "Child restraint seat": ["rear-seats"],
    "Touch screen, operation": ["central-display"], "Screen mirroring": ["central-display"],
    "ConnectedDrive and Infotainment, overall technology": ["central-display"], "Navigation": ["central-display"],
    "Apple CarPlay": ["central-display"], "Operating concept, operating system": ["central-display"],
    "Instrument cluster": ["instrument-cluster"], "Head-Up Display": ["instrument-cluster"],
    "Display, time": ["instrument-cluster"],
    "Vehicle, climatization": ["climate-controls"],
    "Instrument panel": ["dashboard"], "Glove box": ["dashboard"], "Ambient light": ["dashboard"] + DOOR_TRIMS,
    "Center console, front": ["center-console"], "Mobile device, wireless charging": ["center-console"],
    "Cupholder": ["center-console"], "Center armrest, front": ["center-console"],
    "Storage compartments": ["center-console"],
    "Steering wheel": ["steering-wheel"], "Heated steering wheel": ["steering-wheel"],
    "Multi-function steering wheel operation": ["steering-wheel"],
    "Pedals, operate": ["pedals"],
    "Upholstery / interior trim": DOOR_TRIMS + ["interior-side-panels"], "Audio mode, sound": DOOR_TRIMS,
    "Vehicle interior, lighting": ["overhead-console", "headliner"],
    "Seat belts": ["seat-belts"],
    "Interior rearview mirror": ["interior-mirror"], "Interior mirror, garage door opener": ["interior-mirror"],
    "Sun visor, front": ["sun-visors"],
}
GENERAL_INTERIOR = {"Interior design", "Interior", "Interior comfort"}
# Interior feedback classes that have no matching geometry in the M4 model.
NO_GEOMETRY = {"Rear seat entertainment": "no rear screens in this model",
               "Cooling": "no cooling compartment / fridge in this model"}
# General exterior classes: used as the baseline for every exterior component.
GENERAL = {"Exterior design", "Exterior", "Body equipment, overall technology"}

WEIGHTS = {"Likes": 1.0, "Defect": -1.5, "Difficult to Use": -1.0, "Wants": -0.5}
PRIOR = 2.0  # Bayesian prior (pseudo-counts on each side) so tiny samples stay near 50


@dataclass
class Row:
    series: str
    country: str
    ftype: str
    vfc: str
    text: str


@dataclass
class Bucket:
    pos: float = 0.0
    neg: float = 0.0
    counts: dict = field(default_factory=lambda: defaultdict(int))
    quotes: list = field(default_factory=list)

    def add(self, row: Row):
        w = WEIGHTS[row.ftype]
        if w > 0:
            self.pos += w
        else:
            self.neg += -w
        self.counts[row.ftype] += 1
        self.quotes.append(row)

    @property
    def n(self) -> int:
        return sum(self.counts.values())

    def positive_share(self) -> float:
        """Weighted share of positive feedback (0..1), smoothed with a prior."""
        return (self.pos + PRIOR) / (self.pos + self.neg + 2 * PRIOR)


class FeedbackDataset:
    def __init__(self, dataset_dir: Path):
        self.dir = dataset_dir
        self.rows: list[Row] = []
        self.error: str | None = None

    def load(self) -> None:
        try:
            from openpyxl import load_workbook
        except ImportError:
            self.error = "openpyxl not installed (pip install -r requirements.txt)"
            return
        if not self.dir.is_dir():
            self.error = f"Dataset folder not found: {self.dir} (set FEEDBACK_DATASET_DIR)"
            return
        for code in SERIES:
            path = self.dir / f"{code}_feedback_hackathon.xlsx"
            if not path.is_file():
                log.warning("missing %s", path)
                continue
            ws = load_workbook(path, read_only=True, data_only=True).worksheets[0]
            it = ws.iter_rows(values_only=True)
            header = list(next(it))
            col = {name: header.index(name) for name in
                   ("Country", "Feedback Type", "Customer Feedback", "Vfc level2 Name")}
            for r in it:
                ftype, vfc = r[col["Feedback Type"]], r[col["Vfc level2 Name"]]
                if ftype in WEIGHTS and vfc and vfc != "no_class_found":
                    self.rows.append(Row(code, str(r[col["Country"]] or ""), ftype, str(vfc),
                                         str(r[col["Customer Feedback"]] or "")[:400]))
        if not self.rows:
            self.error = f"No feedback rows found in {self.dir}"
        log.info("Loaded %d classified feedback rows from %s", len(self.rows), self.dir)

    def scores(self, series: str | None, market: str | None = None) -> dict:
        rows = [r for r in self.rows if (not series or r.series == series)
                and (not market or market_of(r.country) == market)]
        general, general_int, specific = Bucket(), Bucket(), defaultdict(Bucket)
        no_geometry = defaultdict(Bucket)
        for r in rows:
            if r.vfc in GENERAL:
                general.add(r)
            if r.vfc in GENERAL_INTERIOR:
                general_int.add(r)
            if r.vfc in NO_GEOMETRY:
                no_geometry[r.vfc].add(r)
            for cid in SPECIFIC.get(r.vfc, []):
                specific[cid].add(r)
        rnd = random.Random(42)  # deterministic quote sampling
        sources = {}
        for cid in ALL_EXTERIOR + INTERIOR:
            b = specific.get(cid)
            fallback = (general_int, "general interior") if cid in INTERIOR else (general, "general exterior")
            sources[cid] = (b, "specific") if b and b.n else fallback
        # Specific feature feedback is complaint-heavy, so absolute shares are all low. The heat map
        # therefore uses a RELATIVE score: rank of the positive share among the car's components
        # (0 = most criticised part, 100 = best-rated part) for the chosen series.
        # General exterior feedback (mostly styling praise) is not comparable with feature-specific
        # feedback, so components without specific feedback get a neutral 50 and are flagged.
        # Exterior and interior are ranked separately (interior feedback is far more positive overall).
        def ranking(ids):
            shares = sorted({round(sources[i][0].positive_share(), 6) for i in ids if sources[i][1] == "specific"})
            return {s: (round(100 * k / (len(shares) - 1)) if len(shares) > 1 else 50) for k, s in enumerate(shares)}
        rank_ext, rank_int = ranking(ALL_EXTERIOR), ranking(INTERIOR)
        out = {}
        for cid, (src, basis) in sources.items():
            negatives = [q for q in src.quotes if WEIGHTS[q.ftype] < 0]
            positives = [q for q in src.quotes if WEIGHTS[q.ftype] > 0]
            sample = rnd.sample(negatives, min(2, len(negatives))) + rnd.sample(positives, min(1, len(positives)))
            out[cid] = {
                "score": ((rank_int if cid in INTERIOR else rank_ext)[round(src.positive_share(), 6)]
                          if basis == "specific" else 50),
                "group": "interior" if cid in INTERIOR else "exterior",
                "positive_share": round(100 * src.positive_share(), 1),
                "basis": basis,
                "n": src.n,
                "counts": dict(src.counts),
                "classes": sorted({q.vfc for q in src.quotes})[:8],
                "quotes": [{"type": q.ftype, "series": q.series, "country": q.country, "text": q.text} for q in sample],
            }
        return {
            "series": series or "ALL",
            "series_label": SERIES.get(series, "All series (F70, G60, G70)"),
            "market": market or "ALL",
            "market_label": MARKETS.get(market, "All markets"),
            "rows_used": len(rows),
            "no_geometry": [{"feature": k, "reason": NO_GEOMETRY[k], "n": b.n,
                             "positive_share": round(100 * b.positive_share(), 1)} for k, b in no_geometry.items()],
            "components": out,
            "method": "positive share = (likes+2)/(likes + 1.5*defects + difficult_to_use + 0.5*wants + 4); "
                      "score = rank of that share among this car's exterior (or interior) components "
                      "(0 = most criticised, 100 = best rated). Components without a specific feature class get a neutral 50 "
                      "and show general exterior feedback for context.",
        }


_dataset: FeedbackDataset | None = None


def get_dataset() -> FeedbackDataset:
    global _dataset
    if _dataset is None:
        default = Path(__file__).resolve().parents[2] / "Dataset"
        _dataset = FeedbackDataset(Path(os.environ.get("FEEDBACK_DATASET_DIR") or default))
        _dataset.load()
    return _dataset
