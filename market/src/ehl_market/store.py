"""Observation store: one row per country x period x metric x source x population, with provenance.

Missing countries stay missing - nothing here imputes values.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .countries import to_iso2
from .sources import BY_ID

log = logging.getLogger(__name__)

COLUMNS = [
    "country", "year", "period", "metric", "value", "unit", "source_id", "population",
    "sample_size", "question_id", "question_wording", "fieldwork", "url", "note", "retrieved_at",
]
KEY = ["country", "period", "metric", "source_id", "population"]


def home() -> Path:
    env = os.environ.get("EHL_MARKET_HOME")
    return Path(env) if env else Path(__file__).resolve().parents[2]


def obs_path() -> Path:
    return home() / "data" / "observations.csv"


def load() -> pd.DataFrame:
    p = obs_path()
    if not p.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(p, dtype={"period": str, "question_id": str})
    return df.reindex(columns=COLUMNS)


def upsert(rows: list[dict]) -> dict:
    """Insert or replace rows by KEY. Returns counts."""
    if not rows:
        return {"inserted": 0, "replaced": 0, "total": len(load())}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new = pd.DataFrame(rows).reindex(columns=COLUMNS)
    new["retrieved_at"] = new["retrieved_at"].fillna(now)
    new["population"] = new["population"].fillna("all")
    new["period"] = new["period"].fillna(new["year"]).astype(str)
    cur = load()
    cur_keys = set(map(tuple, cur[KEY].astype(str).values)) if len(cur) else set()
    new_keys = list(map(tuple, new[KEY].astype(str).values))
    replaced = sum(k in cur_keys for k in new_keys)
    if len(cur):
        keep = ~cur[KEY].astype(str).apply(tuple, axis=1).isin(set(new_keys))
        cur = cur[keep]
    out = pd.concat([cur, new], ignore_index=True) if len(cur) else new
    out = out.sort_values(["metric", "country", "period"]).reset_index(drop=True)
    p = obs_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(p, index=False)
    log.info("stored %d rows (%d replaced) -> %s", len(new), replaced, p)
    return {"inserted": len(new) - replaced, "replaced": replaced, "total": len(out)}


def validate_manual(obs: dict) -> dict:
    """Checks for a hand-entered value (survey report, NCAP datasheet). Returns the cleaned row."""
    errors = []
    iso2 = to_iso2(obs.get("country", ""))
    if not iso2:
        errors.append(f"country {obs.get('country')!r} is not one of the 13 markets")
    src = BY_ID.get(obs.get("source_id", ""))
    if src is None:
        errors.append(f"source_id {obs.get('source_id')!r} not in registry - call list_sources; "
                      "tier-3 sources (press, blogs) are never model variables")
    if not obs.get("url"):
        errors.append("url is required (page or PDF the value comes from)")
    try:
        float(obs.get("value"))
    except (TypeError, ValueError):
        errors.append("value must be a number")
    if src is not None and src.kind == "consumer_survey":
        for f in ("question_wording", "population", "sample_size", "fieldwork"):
            if not obs.get(f):
                errors.append(f"{f} is required for survey metrics (e.g. 'concerned about range' "
                              "is not 'will not buy an EV'; base and fieldwork period must be known)")
    if errors:
        raise ValueError("; ".join(errors))
    row = {k: obs.get(k) for k in COLUMNS}
    row["country"] = iso2
    row["value"] = float(obs["value"])
    return row


def metrics_summary() -> list[dict]:
    df = load()
    if df.empty:
        return []
    g = df.groupby(["metric", "source_id", "unit"], dropna=False)
    out = []
    for (metric, src, unit), d in g:
        out.append({
            "metric": metric, "source_id": src, "unit": unit,
            "countries": sorted(d["country"].unique().tolist()),
            "n_countries": int(d["country"].nunique()),
            "periods": sorted(d["period"].astype(str).unique().tolist()),
        })
    return sorted(out, key=lambda r: (-r["n_countries"], r["metric"]))
