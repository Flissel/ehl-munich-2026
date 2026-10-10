"""BMW-side variables per country, derived from research/data/processed (prepared from Dataset/).

What Dataset/ supports at country level: Source A comments (owner reviews / online survey), the only
source present in all 13 markets. Sources B-D are US-only and would distort cross-country shares, so
they are excluded here. Sales exist only for 4 regions (EU, US, CN, RoW), not per country.
"""

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .countries import COUNTRIES

THEMES = {
    "ACCESS": "Access, doors & convenience", "ADAS": "Driver assistance & parking (experience)",
    "CHARGING": "Range & charging (as experienced)", "COMFORT": "Comfort, seats & climate",
    "DIGITAL": "Connectivity & digital services", "DRIVING": "Driving experience & performance",
    "EXT": "Exterior design & lighting", "HMI": "Infotainment & operation (HMI)",
    "INT": "Interior design & quality perception", "SPACE": "Space, storage & practicality",
    "OUT_SAFETY": "Out of scope - safety / regulatory", "OUT_TECH": "Out of scope - technical",
}
MIN_COMMENTS = 20


def research_home() -> Path:
    env = os.environ.get("EHL_RESEARCH_HOME")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "research"


@lru_cache(maxsize=1)
def _tags() -> pd.DataFrame:
    p = research_home() / "data" / "processed" / "evidence_tags.csv"
    if not p.exists():
        raise FileNotFoundError(f"{p} missing - run research/scripts/prepare_data.py first")
    df = pd.read_csv(p, usecols=["comment_id", "derivative", "country", "engine_type", "source",
                                 "theme_id", "polarity"])
    return df[df["source"].eq("Source A") & df["country"].isin(list(COUNTRIES))]


def available_metrics() -> list[str]:
    out = ["bmw.comments", "bmw.negative_share"]
    for t in THEMES:
        out += [f"bmw.theme_share.{t}", f"bmw.theme_negative_share.{t}"]
    return out


def country_metric(metric: str, derivative: str | None = None, engine_type: str | None = None,
                   min_comments: int = MIN_COMMENTS) -> pd.DataFrame:
    """Columns: country, value, n (denominator), numerator, reliable."""
    df = _tags()
    if derivative:
        df = df[df["derivative"].eq(derivative)]
    if engine_type:
        df = df[df["engine_type"].eq(engine_type)]
    per_comment = df.groupby(["country", "comment_id"]).agg(
        themes=("theme_id", lambda s: set(s)),
        neg=("polarity", lambda s: (s == "negative").any()),
    ).reset_index()
    neg_theme = (df[df["polarity"].eq("negative")].groupby(["country", "comment_id"])["theme_id"]
                 .agg(set).rename("neg_themes"))
    per_comment = per_comment.merge(neg_theme, on=["country", "comment_id"], how="left")
    per_comment["neg_themes"] = per_comment["neg_themes"].apply(lambda x: x if isinstance(x, set) else set())

    parts = metric.split(".")
    rows = []
    for country, d in per_comment.groupby("country"):
        total = len(d)
        if metric == "bmw.comments":
            num, den, val = total, total, float(total)
        elif metric == "bmw.negative_share":
            num, den = int(d["neg"].sum()), total
            val = 100 * num / den
        elif len(parts) == 3 and parts[1] == "theme_share" and parts[2] in THEMES:
            num, den = int(d["themes"].apply(lambda s: parts[2] in s).sum()), total
            val = 100 * num / den
        elif len(parts) == 3 and parts[1] == "theme_negative_share" and parts[2] in THEMES:
            in_theme = d[d["themes"].apply(lambda s: parts[2] in s)]
            den = len(in_theme)
            num = int(in_theme["neg_themes"].apply(lambda s: parts[2] in s).sum())
            val = 100 * num / den if den else None
        else:
            raise ValueError(f"unknown BMW metric {metric!r}; see list_metrics")
        rows.append({"country": country, "value": val, "numerator": num, "n": den,
                     "reliable": den >= min_comments})
    return pd.DataFrame(rows)


def sales() -> list[dict]:
    p = research_home() / "data" / "processed" / "sales.csv"
    df = pd.read_csv(p)
    df["volume"] = df["volume"].astype(object).where(df["volume"].notna(), None)
    df["quality_flag"] = df["quality_flag"].fillna("")
    return df.to_dict(orient="records")
