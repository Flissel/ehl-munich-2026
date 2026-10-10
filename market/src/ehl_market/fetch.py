"""Retrieval: public APIs (World Bank, Eurostat, NHTSA) and file importers (IEA CSV, any table)."""

import json
import logging
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

import pandas as pd

from .countries import COUNTRIES, to_iso2

log = logging.getLogger(__name__)
TIMEOUT = 60


def _get_json(url: str, params=None):
    """GET -> parsed JSON. params: dict or list of (key, value) pairs (repeated keys allowed)."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params, safe=';:')}"
    req = urllib.request.Request(url, headers={"User-Agent": "ehl-market/0.1", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))

WORLDBANK_PRESETS = {
    "gdp_per_capita_ppp": ("NY.GDP.PCAP.PP.CD", "current international $"),
    "gni_per_capita_ppp": ("NY.GNP.PCAP.PP.CD", "current international $"),
    "inflation_cpi_pct": ("FP.CPI.TOTL.ZG", "%"),
    "lending_interest_rate_pct": ("FR.INR.LEND", "%"),
    "urban_population_pct": ("SP.URB.TOTL.IN.ZS", "%"),
    "renewable_electricity_pct": ("EG.ELC.RNEW.ZS", "%"),
    "population": ("SP.POP.TOTL", "people"),
}

EUROSTAT_PRESETS = {
    "electricity_price_household_eur_kwh": (
        "nrg_pc_204",
        {"siec": "E7000", "nrg_cons": "KWH2500-4999", "unit": "KWH", "tax": "I_TAX", "currency": "EUR"},
        "EUR/kWh",
    ),
}


def worldbank(metric: str, start: int, end: int, indicator: str | None = None) -> list[dict]:
    if indicator is None:
        if metric not in WORLDBANK_PRESETS:
            raise ValueError(f"unknown preset {metric!r}; presets: {sorted(WORLDBANK_PRESETS)} "
                             "or pass indicator=<World Bank code>")
        indicator, unit = WORLDBANK_PRESETS[metric]
    else:
        unit = ""
    iso3 = ";".join(c.iso3 for c in COUNTRIES.values())
    url = f"https://api.worldbank.org/v2/country/{iso3}/indicator/{indicator}"
    body = _get_json(url, {"format": "json", "per_page": 2000, "date": f"{start}:{end}"})
    if len(body) < 2 or body[1] is None:
        raise ValueError(f"World Bank returned no data: {body[0] if body else body}")
    rows = []
    for x in body[1]:
        if x["value"] is None:
            continue
        iso2 = to_iso2(x["countryiso3code"])
        if iso2:
            rows.append({"country": iso2, "year": int(x["date"]), "period": x["date"], "metric": metric,
                         "value": float(x["value"]), "unit": unit, "source_id": "worldbank",
                         "url": f"{url}?date={start}:{end}", "note": indicator})
    return rows


def _jsonstat_rows(body: dict) -> list[dict]:
    """Flatten a Eurostat JSON-stat 2.0 response to {dim: code, ..., value}."""
    ids, sizes = body["id"], body["size"]
    cats = []
    for d in ids:
        index = body["dimension"][d]["category"]["index"]
        cats.append(sorted(index, key=index.get))
    out = []
    for flat, val in body.get("value", {}).items():
        flat = int(flat)
        rec = {}
        for d, size, codes in zip(reversed(ids), reversed(sizes), reversed(cats)):
            rec[d] = codes[flat % size]
            flat //= size
        rec["value"] = val
        out.append(rec)
    return out


def eurostat(metric: str, start: int, dataset: str | None = None, filters: dict | None = None,
             unit: str = "") -> list[dict]:
    if dataset is None:
        if metric not in EUROSTAT_PRESETS:
            raise ValueError(f"unknown preset {metric!r}; presets: {sorted(EUROSTAT_PRESETS)} "
                             "or pass dataset + filters")
        dataset, filters, unit = EUROSTAT_PRESETS[metric]
    geos = [c.eurostat for c in COUNTRIES.values() if c.eurostat]
    params = [(k, v) for k, v in (filters or {}).items()] + [("geo", g) for g in geos]
    params.append(("sinceTimePeriod", str(start)))
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
    rows = []
    for rec in _jsonstat_rows(_get_json(url, params)):
        iso2 = to_iso2(rec["geo"])
        if not iso2 or rec["value"] is None:
            continue
        period = str(rec["time"])
        rows.append({"country": iso2, "year": int(period[:4]), "period": period, "metric": metric,
                     "value": float(rec["value"]), "unit": unit, "source_id": "eurostat",
                     "url": url, "note": dataset})
    return rows


def nhtsa_vehicle(make: str, model: str, model_year: int) -> dict:
    """Complaints (by component), recalls and NCAP ratings for one US vehicle. Not stored: model-level."""
    base = "https://api.nhtsa.gov"
    q = {"make": make, "model": model, "modelYear": model_year}
    comp = _get_json(f"{base}/complaints/complaintsByVehicle", q)
    rec = _get_json(f"{base}/recalls/recallsByVehicle", q)
    path = "/".join(urllib.parse.quote(str(x)) for x in (model_year, "make", make, "model", model))
    variants = _get_json(f"{base}/SafetyRatings/modelyear/{path}")
    ratings = []
    for v in (variants.get("Results") or [])[:5]:
        vid = v.get("VehicleId")
        if not vid:
            continue
        d = (_get_json(f"{base}/SafetyRatings/VehicleId/{vid}").get("Results") or [{}])[0]
        ratings.append({k: d.get(k) for k in ("VehicleDescription", "OverallRating",
                                              "OverallFrontCrashRating", "OverallSideCrashRating",
                                              "RolloverRating")})
    complaints = comp.get("results") or []
    components = Counter(p.strip() for x in complaints for p in (x.get("components") or "").split(","))
    return {
        "vehicle": f"{model_year} {make} {model}",
        "complaints": len(complaints),
        "complaints_by_component": dict(components.most_common(10)),
        "complaints_crash_or_fire": sum(bool(x.get("crash") or x.get("fire")) for x in complaints),
        "recalls": [{"campaign": x.get("NHTSACampaignNumber"), "component": x.get("Component"),
                     "summary": (x.get("Summary") or "")[:240]} for x in rec.get("results") or []],
        "ncap_ratings": ratings or "not rated for this model year",
        "caveat": "Complaint counts are self-reported and not exposure-adjusted; divide by US sales or "
                  "fleet before comparing models.",
        "source_id": "nhtsa",
    }


def import_iea_ev(path: str) -> list[dict]:
    """IEA Global EV Data Explorer CSV -> EV sales share, EV stock share, public chargers (Historical only)."""
    df = pd.read_csv(Path(path))
    need = {"region", "category", "parameter", "mode", "powertrain", "year", "unit", "value"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"not an IEA EV data CSV, missing columns {sorted(missing)}")
    df = df[df["category"].eq("Historical")]
    wanted = {
        ("EV sales share", "Cars", "EV"): "ev_sales_share_pct",
        ("EV stock share", "Cars", "EV"): "ev_stock_share_pct",
        ("EV charging points", "EV", "Publicly available fast"): "public_fast_chargers",
        ("EV charging points", "EV", "Publicly available slow"): "public_slow_chargers",
    }
    rows = []
    for _, r in df.iterrows():
        metric = wanted.get((r["parameter"], r["mode"], r["powertrain"]))
        iso2 = to_iso2(r["region"])
        if metric and iso2 and pd.notna(r["value"]):
            rows.append({"country": iso2, "year": int(r["year"]), "period": str(int(r["year"])),
                         "metric": metric, "value": float(r["value"]), "unit": r["unit"],
                         "source_id": "iea_gevo", "url": "https://www.iea.org/data-and-statistics/"
                         "data-tools/global-ev-data-explorer", "note": Path(path).name})
    return rows


def import_table(path: str, metric: str, source_id: str, country_col: str, year_col: str,
                 value_col: str, unit: str = "", url: str = "", sheet: str | None = None,
                 filters: dict | None = None) -> list[dict]:
    """Any CSV/XLSX in long format: pick the country, year and value columns, optional equality filters."""
    p = Path(path)
    df = pd.read_excel(p, sheet_name=sheet or 0) if p.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(p)
    for col, val in (filters or {}).items():
        df = df[df[col].astype(str).eq(str(val))]
    rows = []
    for _, r in df.iterrows():
        iso2 = to_iso2(str(r[country_col]))
        if not iso2 or pd.isna(r[value_col]):
            continue
        period = str(r[year_col])
        rows.append({"country": iso2, "year": int(period[:4]), "period": period, "metric": metric,
                     "value": float(r[value_col]), "unit": unit, "source_id": source_id,
                     "url": url, "note": p.name})
    return rows
