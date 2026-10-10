"""Topic and keyword ranking: how often customers mention it, how often positively vs negatively,
and what external sources say about the same theme.

Score per row = base + external bonus (weights configurable, nothing is imputed):
  base = (w_frequency * frequency + w_tone * tone) / (w_frequency + w_tone)
  bonus = w_external * external   (0 when no external source covers the theme; outside evidence can
          only raise a topic, so themes NHTSA cannot measure are not pushed down or up by it)
  frequency   log-scaled, source-weighted number of comments
  tone        pain ranking: share negative; strength ranking: share positive (Laplace-smoothed)
  external    theme-level: NHTSA complaint share for the same BMW models (US, live API) and stated
              importance from surveys stored as `importance.<THEME>` (e.g. Deloitte) - if entered
Keywords inherit the external value of their theme.
"""

import collections
import logging
import math
import re
from functools import lru_cache

import pandas as pd

from . import bmw, fetch, store

log = logging.getLogger(__name__)

# NHTSA models per derivative (names as NHTSA writes them; model years with complaints)
NHTSA_MODELS = {
    "G60": [("530I", 2024), ("540I", 2024), ("I5", 2024), ("I5", 2025), ("5 SERIES HYBRID SEDAN", 2025),
            ("M5 HYBRID SEDAN", 2025), ("5 SERIES HYBRID SEDAN PHEV", 2026)],
    "G70": [("7 SERIES SEDAN", 2024), ("I7 SEDAN", 2024), ("I7", 2025), ("7 SERIES HYBRID SEDAN", 2025),
            ("I7 SEDAN BEV", 2026)],
}
NHTSA_THEME = {
    "FORWARD COLLISION AVOIDANCE": "ADAS", "LANE DEPARTURE": "ADAS", "BACK OVER PREVENTION": "ADAS",
    "VEHICLE SPEED CONTROL": "ADAS",
    "STEERING": "DRIVING", "SUSPENSION": "DRIVING", "POWER TRAIN": "DRIVING", "ENGINE": "DRIVING",
    "FUEL/PROPULSION SYSTEM": "DRIVING", "WHEELS": "DRIVING", "TIRES": "DRIVING",
    "ENGINE AND ENGINE COOLING": "DRIVING",
    "VISIBILITY/WIPER": "EXT", "VISIBILITY": "EXT", "EXTERIOR LIGHTING": "EXT",
    "LATCHES/LOCKS/LINKAGES": "ACCESS", "STRUCTURE": "ACCESS",
    "SEATS": "COMFORT",
    "SERVICE BRAKES": "OUT_SAFETY", "SERVICE BRAKES, HYDRAULIC": "OUT_SAFETY", "AIR BAGS": "OUT_SAFETY",
    "ELECTRONIC STABILITY CONTROL (ESC)": "OUT_SAFETY", "SEAT BELTS": "OUT_SAFETY",
    "PARKING BRAKE": "OUT_SAFETY", "CHILD SEAT": "OUT_SAFETY",
    "ELECTRICAL SYSTEM": "OUT_TECH", "EQUIPMENT": "OUT_TECH",
}

NHTSA_COVERED = set(NHTSA_THEME.values()) - {"OUT_TECH"}  # ELECTRICAL SYSTEM is too vague to assign

STOPWORDS = set("""
a about above after again against all also am an and any are as at be because been before being below
between both but by can cannot could did do does doing don down during each even ever every few for
from further get gets getting got had has have having he her here hers him his how i if in into is it
its itself just ll me more most much must my myself no nor not now of off on once one only or other
our ours out over own re really same she should so some still such than that the their them then there
these they this those through to too under until up upon us very was we were what when where which
while who whom why will with would you your yours ve d s t m isn wasn doesn didn don't can't won't
it's i'm i've i'd ive im dont cant wont doesnt didnt isnt wasnt thats theres also always never
car cars vehicle vehicles bmw bmws series model new make made makes way thing things lot lots bit
use used using since back well want wanted need needs time times year years day days first last
however though although yet etc even quite rather overall something anything nothing everything
good great bad love loved like liked nice excellent poor terrible happy disappointed best better worse
worst amazing awesome fantastic perfect problem problems issue issues fine ok okay pretty little
system side button feature features option options thing work works working drive driving
writer advised explained stated states client caller called asked inquired informed customer customers
cust contacted contact regarding provided assist assisted mentioned reported reports wanted dealer
""".split())
# Source B is a customer-care log written by agents ("writer advised ..."): their wording is not the customer's.

TOKEN = re.compile(r"[a-z][a-z'\-]{2,}")


def _terms(text: str) -> set[str]:
    words = [w for w in TOKEN.findall(str(text).lower()) if w not in STOPWORDS]
    return set(words) | {f"{a} {b}" for a, b in zip(words, words[1:])}


@lru_cache(maxsize=1)
def _comments() -> pd.DataFrame:
    p = bmw.research_home() / "data" / "processed" / "comments.csv"
    df = pd.read_csv(p, usecols=["comment_id", "derivative", "country", "engine_type", "source",
                                 "source_weight", "text"])
    return df[df["text"].notna() & df["text"].astype(str).str.len().gt(3)]


@lru_cache(maxsize=1)
def _polarity() -> pd.DataFrame:
    """comment_id x theme_id -> neg (bool), pos (bool), from BMW's own tagging."""
    p = bmw.research_home() / "data" / "processed" / "evidence_tags.csv"
    t = pd.read_csv(p, usecols=["comment_id", "theme_id", "polarity"])
    t = t[t["theme_id"].ne("UNCLASSIFIED")]
    return (t.assign(neg=t["polarity"].eq("negative"), pos=t["polarity"].eq("positive"))
             .groupby(["comment_id", "theme_id"])[["neg", "pos"]].any().reset_index())


# ----------------------------------------------------------------------------- external signals

def fetch_nhtsa_themes(derivatives: tuple[str, ...] = ("G60", "G70")) -> dict:
    """Pull NHTSA complaints for the BMW models of each derivative and store the share per theme (US)."""
    rows, summary = [], {}
    for der in derivatives:
        theme_hits, total, models = collections.Counter(), 0, []
        for model, year in NHTSA_MODELS[der]:
            try:
                body = fetch._get_json("https://api.nhtsa.gov/complaints/complaintsByVehicle",
                                       {"make": "BMW", "model": model, "modelYear": year})
            except Exception as e:  # one missing model must not stop the others
                log.warning("NHTSA %s %s: %s", year, model, e)
                continue
            res = body.get("results") or []
            models.append(f"{year} {model} ({len(res)})")
            for c in res:
                comps = [x.strip() for x in re.split(r",(?! )", c.get("components") or "")]
                themes = {NHTSA_THEME[x] for x in comps if x in NHTSA_THEME}
                total += 1
                theme_hits.update(themes)
        summary[der] = {"complaints": total, "models": models, "by_theme": dict(theme_hits)}
        if not total:
            continue
        for theme in bmw.THEMES:
            rows.append({"country": "US", "year": 2026, "period": "MY2024-2026",
                         "metric": f"nhtsa_complaint_share.{theme}", "value": round(100 * theme_hits[theme] / total, 2),
                         "unit": "% of NHTSA complaints", "source_id": "nhtsa", "population": der,
                         "sample_size": total, "url": "https://api.nhtsa.gov/complaints/complaintsByVehicle",
                         "note": "; ".join(models)})
    return {"stored": store.upsert(rows), "summary": summary}


def _external(derivative: str | None, kind: str = "pain") -> tuple[dict[str, float], dict[str, dict]]:
    """theme -> external score 0-1 (mean of available signals), plus the raw values per theme.
    NHTSA complaints are evidence of pain only; stated importance counts for both rankings."""
    obs = store.load()
    raw: dict[str, dict] = collections.defaultdict(dict)
    nh = obs[obs["metric"].astype(str).str.startswith("nhtsa_complaint_share.")]
    if derivative:
        nh = nh[nh["population"].eq(derivative)]
    if len(nh):
        nh = nh.assign(theme=nh["metric"].str.split(".").str[1])
        # pooled over derivatives: weight by number of complaints
        pooled = nh.groupby("theme").apply(
            lambda d: (d["value"] * d["sample_size"]).sum() / d["sample_size"].sum())
        for th, v in pooled.items():
            if th in NHTSA_COVERED:  # NHTSA has no component for HMI, connectivity, space, interior, charging
                raw[th]["nhtsa_complaint_share_pct"] = round(float(v), 1)
    imp = obs[obs["metric"].astype(str).str.startswith("importance.")]
    for th, d in imp.assign(theme=imp["metric"].str.split(".").str[1]).groupby("theme"):
        raw[th]["stated_importance_pct"] = round(float(d["value"].mean()), 1)
        raw[th]["importance_countries"] = sorted(d["country"].unique().tolist())
    score: dict[str, float] = {}
    keys = ("nhtsa_complaint_share_pct", "stated_importance_pct") if kind == "pain" else ("stated_importance_pct",)
    for key in keys:
        vals = {t: r[key] for t, r in raw.items() if key in r}
        hi = max(vals.values(), default=0)
        for t, v in vals.items():
            score.setdefault(t, []).append(v / hi if hi else 0.0)
    return {t: sum(v) / len(v) for t, v in score.items()}, dict(raw)


# ----------------------------------------------------------------------------- ranking

def _base(freq_n: float, tone: float, w: dict) -> float:
    return (w["frequency"] * freq_n + w["tone"] * tone) / (w["frequency"] + w["tone"])


def rank(level: str = "theme", kind: str = "pain", derivative: str | None = None,
         country: str | None = None, engine_type: str | None = None, theme: str | None = None,
         weights: dict | None = None, top: int = 25, min_comments: int = 8) -> dict:
    """level: theme | keyword. kind: pain (fix) | strength (protect)."""
    w = {"frequency": 0.5, "tone": 0.3, "external": 0.2} | (weights or {})
    c = _comments()
    if derivative:
        c = c[c["derivative"].eq(derivative)]
    if country:
        c = c[c["country"].eq(country)]
    if engine_type:
        c = c[c["engine_type"].eq(engine_type)]
    pol = _polarity().merge(c[["comment_id", "source_weight", "text", "country"]], on="comment_id")
    if theme:
        pol = pol[pol["theme_id"].eq(theme)]
    ext, ext_raw = _external(derivative, kind)

    if level == "theme":
        g = pol.groupby("theme_id")
        rows = pd.DataFrame({
            "n_comments": g.size(), "weighted_n": g["source_weight"].sum(),
            "n_negative": g["neg"].sum(), "n_positive": g["pos"].sum(),
            "n_countries": g["country"].nunique(),
        }).reset_index().rename(columns={"theme_id": "theme"})
        rows["label"] = rows["theme"].map(bmw.THEMES)
    elif level == "keyword":
        recs = collections.defaultdict(lambda: {"n": 0, "w": 0.0, "neg": 0, "pos": 0, "countries": set()})
        overall = collections.Counter()
        for r in pol.itertuples():
            ts = _terms(r.text)
            overall.update(ts)
            for t in ts:
                d = recs[(r.theme_id, t)]
                d["n"] += 1; d["w"] += r.source_weight; d["neg"] += r.neg; d["pos"] += r.pos
                d["countries"].add(r.country)
        theme_n = pol.groupby("theme_id").size().to_dict()
        n_all = len(pol)
        out = []
        for (th, t), d in recs.items():
            if d["n"] < min_comments:
                continue
            lift = (d["n"] / theme_n[th]) / (overall[t] / n_all)
            if lift < 1.5:  # must be typical for its theme, not a generic word
                continue
            out.append({"theme": th, "keyword": t, "n_comments": d["n"], "weighted_n": d["w"],
                        "n_negative": d["neg"], "n_positive": d["pos"], "n_countries": len(d["countries"]),
                        "lift_in_theme": round(lift, 2)})
        rows = pd.DataFrame(out)
        if rows.empty:
            return {"rows": [], "note": "no keyword reaches min_comments in this slice"}
    else:
        raise ValueError("level must be 'theme' or 'keyword'")

    rows["share_negative_pct"] = (100 * rows["n_negative"] / rows["n_comments"]).round(1)
    rows["share_positive_pct"] = (100 * rows["n_positive"] / rows["n_comments"]).round(1)
    tone_neg = (rows["n_negative"] + 1) / (rows["n_negative"] + rows["n_positive"] + 2)
    rows["tone"] = tone_neg if kind == "pain" else 1 - tone_neg
    rows["frequency_norm"] = (rows["weighted_n"].apply(math.log1p) / math.log1p(rows["weighted_n"].max())).round(3)
    rows["external_norm"] = rows["theme"].map(ext)
    rows["base"] = [round(_base(f, t, w), 3) for f, t in zip(rows["frequency_norm"], rows["tone"])]
    rows["external_bonus"] = (w["external"] * rows["external_norm"].fillna(0)).round(3)
    rows["score"] = (rows["base"] + rows["external_bonus"]).round(3)
    rows["external"] = rows["theme"].map(lambda t: ext_raw.get(t, {}))
    rows["scope_note"] = rows["theme"].map(lambda t: "out of scope - route to quality/safety"
                                           if str(t).startswith("OUT_") else "")
    rows = rows.sort_values("score", ascending=False).head(top)
    cols = [c for c in ("theme", "label", "keyword", "score", "base", "external_bonus", "n_comments", "share_negative_pct",
                        "share_positive_pct", "n_countries", "lift_in_theme", "frequency_norm", "tone",
                        "external_norm", "external", "scope_note") if c in rows]
    return {
        "level": level, "kind": kind, "weights": w,
        "filters": {"derivative": derivative, "country": country, "engine_type": engine_type, "theme": theme},
        "rows": rows[cols].round(3).to_dict(orient="records"),
        "method": "score = base + external_bonus. base = weighted mean of frequency (log, source-weighted) "
                  f"and tone (share {'negative' if kind == 'pain' else 'positive'}, smoothed). external_bonus = "
                  "w_external x theme-level outside evidence (NHTSA complaint share for the same BMW models; "
                  "stated importance from surveys if stored); 0 where no outside source covers the theme.",
        "caveats": ["Polarity comes from BMW's tagging (evidence_tags.polarity); a comment can be both.",
                    "US sources B-D dominate pooled counts; filter by country or source for market views.",
                    "NHTSA covers US G60/G70 only and is safety-skewed (brakes, ADAS); F70 has no NHTSA data.",
                    "External is theme-level; keywords inherit their theme's value."],
    }
