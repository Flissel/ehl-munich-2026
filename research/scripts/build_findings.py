#!/usr/bin/env python3
"""
build_findings.py - turn the processed data into the standard findings dataset.

Reads data/processed/ (output of prepare_data.py: cleaned feedback, studies, sales, option-list text)
and writes research/findings/: theme shares, study-vs-complaint correlation, sales growth, 2030
scenarios, keywords and a list of headline findings. Every number carries its base (n), method and
confidence, so the agent and the MCP server can cite it.

Usage:
    python scripts/build_findings.py --processed data/processed --out findings
    python scripts/build_findings.py --bev-shares 0.2,0.35,0.5     # scenario assumptions

Standard library only, so it runs on every team PC without installs.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("build_findings")

THEMES = {
    "COMFORT": "Comfort, seats & climate",
    "SPACE": "Space, storage & practicality",
    "HMI": "Infotainment & operation",
    "DIGITAL": "Connectivity & digital services",
    "CHARGING": "Range & charging (as experienced)",
    "DRIVING": "Driving experience & performance",
    "EXT": "Exterior design & lighting",
    "INT": "Interior design & quality perception",
    "ACCESS": "Access, doors & convenience",
    "ADAS": "Driver assistance & parking (experience)",
}
PAIN = {"unmet_need", "usability_pain", "performance_gap", "defect"}
EU_COUNTRIES = {"GB", "FR", "SE", "DK", "FI", "NO", "ES", "LV"}
ROW_COUNTRIES = {"KR", "JP", "AU", "CA", "ZA"}
MIN_REPORT_N = 10          # below this a share is not written at all
STOPWORDS = set("""
a about above after again against all also am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have having
he her here hers him his how i if in into is it its itself just me more most my no nor not now of off on
once only or other our out over own same she should so some such than that the their them then there these
they this those through to too under until up very was we were what when where which while who whom why
will with would you your yours i'm it's don't can't doesn't didn't isn't wasn't i've i'd i'll get got one
customer stated vehicle car bmw really like new mentioned explained writer series asked inquired advised
would also even still much well make made way time use using used thing things lot need wants want feel
confirmed acknowledged noted indicated commented states suggested clarified currently prior additional
reported advised provided requested informed contacted regarding
""".split())  # last two lines: Source B call-centre wording, not customer content


def confidence(n: int) -> str:
    return "high" if n >= 300 else "medium" if n >= 50 else "low"


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        log.warning("no rows for %s", path.name)
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    log.info("wrote %s (%d rows)", path.name, len(rows))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def is_pain(c: dict) -> bool:
    return bool(set(c["signal_types"].split("|")) & PAIN)


def themes_of(c: dict) -> set[str]:
    return set(c["themes"].split("|"))


def ranks(values: list[float]) -> list[float]:
    """Average ranks (ties share their mean rank)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2
        i = j + 1
    return out


def pearson(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 3:
        return None
    mx, my = sum(x) / n, sum(y) / n
    sx = sum((a - mx) ** 2 for a in x) ** 0.5
    sy = sum((b - my) ** 2 for b in y) ** 0.5
    if not sx or not sy:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def spearman(x: list[float], y: list[float]) -> float | None:
    return pearson(ranks(x), ranks(y))


# --------------------------------------------------------------------------- theme shares

GROUPINGS = [
    # (dimension, description, filter, key) - each group is compared on the same base
    ("country", "all derivatives, all sources", lambda c: True, lambda c: c["country"]),
    ("derivative_country", "per model and country, all sources",
     lambda c: True, lambda c: f"{c['derivative']}|{c['country']}"),
    ("country_G60_sourceA", "G60 only, Source A only (same car, same source)",
     lambda c: c["derivative"] == "G60" and c["source"] == "Source A", lambda c: c["country"]),
    ("engine_US", "US, G60+G70 (same country, same models)",
     lambda c: c["country"] == "US", lambda c: c["engine_type"]),
    ("derivative_US", "US only", lambda c: c["country"] == "US", lambda c: c["derivative"]),
    ("source_US", "US, G60+G70", lambda c: c["country"] == "US", lambda c: c["source"]),
    ("derivative_engine_US", "US, per model and powertrain",
     lambda c: c["country"] == "US", lambda c: f"{c['derivative']}|{c['engine_type']}"),
]


def theme_shares(comments: list[dict]) -> tuple[list[dict], dict]:
    rows, lookup = [], {}
    for dim, desc, keep, key in GROUPINGS:
        groups = collections.defaultdict(list)
        for c in comments:
            if keep(c):
                groups[key(c)].append(c)
        for group, cs in sorted(groups.items()):
            pain = [c for c in cs if is_pain(c)]
            n = len(pain)
            if n < MIN_REPORT_N:
                continue
            for t in THEMES:
                k = sum(t in themes_of(c) for c in pain)
                share = round(100 * k / n, 1)
                lookup[(dim, group, t)] = (share, n)
                rows.append({
                    "dimension": dim, "group": group, "base": desc, "n_comments": len(cs),
                    "n_pain": n, "pain_pct": round(100 * n / len(cs), 1), "theme_id": t,
                    "theme_name": THEMES[t], "n_theme": k, "share_pct": share,
                    "confidence": confidence(n),
                })
    return rows, lookup


# --------------------------------------------------------------------------- study vs complaints

def study_vs_complaints(study: list[dict], lookup: dict) -> tuple[list[dict], list[dict]]:
    rows, corr = [], []
    for der in ("G60", "G70"):
        neg = collections.defaultdict(list)
        for s in study:
            if (s["study"] == "US_2025" and s["derivative"] == der
                    and s["metric"] == "pct_negative_bottom3" and s["theme_id"] in THEMES):
                neg[s["theme_id"]].append(float(s["value"]))
        xs, ys = [], []
        for t in THEMES:
            if not neg[t] or ("derivative_US", der, t) not in lookup:
                continue
            pct_neg = 100 * sum(neg[t]) / len(neg[t])
            share, n = lookup[("derivative_US", der, t)]
            xs.append(pct_neg)
            ys.append(share)
            rows.append({
                "study": "US_2025", "market": "US", "derivative": der, "theme_id": t,
                "theme_name": THEMES[t], "study_items": len(neg[t]),
                "study_pct_negative_mean": round(pct_neg, 1),
                "complaint_share_pct": share, "n_pain": n,
            })
        rho = spearman(xs, ys)
        corr.append({"derivative": der, "n_themes": len(xs),
                     "spearman_rho": None if rho is None else round(rho, 2)})
    return rows, corr


# --------------------------------------------------------------------------- sales

def sales_growth(sales: list[dict]) -> tuple[list[dict], dict]:
    vol = {}
    for s in sales:
        vol[(s["derivative_group"], s["market_code"], s["year"])] = (
            float(s["volume"]) if s["volume"] else None, s["quality_flag"])
    rows = []
    for (group, market, year) in sorted({(g, m, "x") for g, m, _ in vol}):
        v24, f24 = vol.get((group, market, "2024"), (None, ""))
        v25, _ = vol.get((group, market, "2025"), (None, ""))
        v30, _ = vol.get((group, market, "2030"), (None, ""))
        growth = round(100 * (v30 / v25 - 1), 1) if v25 and v30 is not None else None
        rows.append({
            "derivative_group": group, "market_code": market, "volume_2024": v24,
            "volume_2025": v25, "volume_2030": v30, "growth_2025_2030_pct": growth,
            "quality_flag": f24 or ("no volume in this market" if not v25 else ""),
            "origin": "provided_data (BMW plan)",
        })
    return rows, vol


# --------------------------------------------------------------------------- 2030 scenarios

def scenarios(lookup: dict, comments: list[dict], vol: dict, bev_shares: list[float]) -> list[dict]:
    rows = []
    # S1: powertrain mix - US G60+G70 profile per powertrain, mixed by an assumed BEV share
    for b in bev_shares:
        for t in THEMES:
            ice = lookup.get(("engine_US", "ICE", t))
            bev = lookup.get(("engine_US", "BEVE", t))
            if not ice or not bev:
                continue
            rows.append({
                "scenario": "S1_bev_share", "market": "US", "derivatives": "G60+G70", "year": 2030,
                "assumption": f"BEV share of buyers = {int(b * 100)}%; ICE and BEV keep today's complaint profile; PHEV counted as ICE",
                "theme_id": t, "theme_name": THEMES[t],
                "today_share_pct": lookup.get(("derivative_US", "G60", t), (None,))[0],
                "projected_share_pct": round((1 - b) * ice[0] + b * bev[0], 1),
                "basis_n": f"ICE {ice[1]} / BEV {bev[1]} pain comments",
                "origin": "scenario (assumption + provided_data)",
            })
    # S2: volume shift - G60 theme profile per region weighted with BMW's 2025 and 2030 volumes
    region_of = lambda c: "US" if c["country"] == "US" else "EU" if c["country"] in EU_COUNTRIES else "RoW" if c["country"] in ROW_COUNTRIES else None
    by_region = collections.defaultdict(list)
    for c in comments:
        if c["derivative"] == "G60" and is_pain(c) and region_of(c):
            by_region[region_of(c)].append(c)
    for year in ("2025", "2030"):
        totals, weight = collections.Counter(), 0.0
        for region, cs in by_region.items():
            v = vol.get(("G60_G68", region, year), (None,))[0] or 0.0
            weight += v
            for t in THEMES:
                totals[t] += v * sum(t in themes_of(c) for c in cs) / len(cs)
        for t in THEMES:
            rows.append({
                "scenario": "S2_volume_weighted", "market": "US+EU+RoW", "derivatives": "G60",
                "year": int(year),
                "assumption": "regional G60 complaint profile x BMW volume plan; China excluded (no comments); "
                              + ", ".join(f"{r} n={len(cs)}" for r, cs in sorted(by_region.items())),
                "theme_id": t, "theme_name": THEMES[t], "today_share_pct": None,
                "projected_share_pct": round(100 * totals[t] / weight, 1) if weight else None,
                "basis_n": sum(len(cs) for cs in by_region.values()),
                "origin": "scenario (provided_data only)",
            })
    return rows


# --------------------------------------------------------------------------- keywords

TOKEN = re.compile(r"[a-z][a-z'\-]{2,}")


def terms(text: str) -> set[str]:
    words = [w for w in TOKEN.findall(text.lower()) if w not in STOPWORDS]
    bigrams = {f"{a} {b}" for a, b in zip(words, words[1:])}
    return set(words) | bigrams


def keywords(comments: list[dict], top: int = 15, min_count: int = 8) -> list[dict]:
    pain = [c for c in comments if is_pain(c) and c["text"]]
    doc_terms = [terms(c["text"]) for c in pain]
    overall = collections.Counter(t for ts in doc_terms for t in ts)
    n_all = len(pain)
    scopes = [("theme", t, lambda c, t=t: t in themes_of(c)) for t in THEMES]
    countries = collections.Counter(c["country"] for c in pain)
    scopes += [("country", k, lambda c, k=k: c["country"] == k) for k, v in countries.items() if v >= 40]
    scopes += [("engine", e, lambda c, e=e: c["engine_type"] == e) for e in ("ICE", "PHEV", "BEVE")]
    rows = []
    for scope_type, scope, keep in scopes:
        idx = [i for i, c in enumerate(pain) if keep(c)]
        if not idx:
            continue
        counts = collections.Counter(t for i in idx for t in doc_terms[i])
        scored = []
        for term, k in counts.items():
            if k < min_count:
                continue
            lift = (k / len(idx)) / (overall[term] / n_all)
            if lift > 1.2:
                scored.append((lift * (k ** 0.5), term, k, lift))
        for _, term, k, lift in sorted(scored, reverse=True)[:top]:
            rows.append({
                "scope_type": scope_type, "scope": scope, "term": term, "n_comments": k,
                "share_in_scope_pct": round(100 * k / len(idx), 1), "lift": round(lift, 2),
                "n_scope": len(idx),
            })
    return rows


# --------------------------------------------------------------------------- headline findings

def headline_findings(lookup: dict, corr: list[dict], study_rows: list[dict], growth: list[dict]) -> list[dict]:
    out = []

    def add(category, statement, metric, value, unit, n, scope, method, caveat, keywords_):
        out.append({
            "finding_id": f"F-{len(out) + 1:03d}", "category": category, "statement": statement,
            "metric": metric, "value": value, "unit": unit, "n": n, "scope": scope,
            "confidence": confidence(n) if isinstance(n, int) else "low", "method": method,
            "origin": "provided_data" if category != "scenario" else "scenario",
            "caveat": caveat, "keywords": keywords_,
        })

    ice, phev, bev = (lookup.get(("engine_US", e, "CHARGING")) for e in ("ICE", "PHEV", "BEVE"))
    if ice and bev:
        add("correlation", f"Charging complaints rise with electrification: ICE {ice[0]}%, "
            f"PHEV {phev[0] if phev else 'n/a'}%, BEV {bev[0]}% of pain comments",
            "charging_share_BEV_minus_ICE", round(bev[0] - ice[0], 1), "pp", bev[1],
            "US, G60+G70, by powertrain", "share of pain comments tagged CHARGING",
            "PHEV n is smaller", "charging|range|BEV|powertrain")
    hmi = [lookup.get(("engine_US", e, "HMI")) for e in ("ICE", "PHEV", "BEVE")]
    if all(hmi):
        add("correlation", "Infotainment & operation is equally frequent for every powertrain "
            f"({min(h[0] for h in hmi)}-{max(h[0] for h in hmi)}%), i.e. independent of the drivetrain",
            "hmi_share_range", round(max(h[0] for h in hmi) - min(h[0] for h in hmi), 1), "pp",
            sum(h[1] for h in hmi), "US, G60+G70, by powertrain", "share of pain comments tagged HMI",
            "", "infotainment|operation|screen|platform")
    diffs = [abs(lookup[("derivative_US", "G60", t)][0] - lookup[("derivative_US", "G70", t)][0])
             for t in THEMES if ("derivative_US", "G60", t) in lookup and ("derivative_US", "G70", t) in lookup]
    if diffs:
        add("correlation", "G60 and G70 have almost the same complaint profile in the US: issues are "
            "platform-wide rather than model-specific", "max_theme_share_diff_G60_G70",
            round(max(diffs), 1), "pp", lookup[("derivative_US", "G60", "HMI")][1],
            "US, G60 vs G70", "max absolute difference of theme shares", "",
            "platform|G60|G70")
    for c in corr:
        add("correlation", f"US study dissatisfaction vs complaint share per theme, {c['derivative']}: "
            f"Spearman rho = {c['spearman_rho']}", "spearman_rho", c["spearman_rho"], "rho",
            c["n_themes"], f"US_2025 study vs US comments, {c['derivative']}",
            "rank correlation over themes", "only ~10 themes, so rho is indicative",
            "study|severity|validation")
    g70 = {r["theme_id"]: r for r in study_rows if r["derivative"] == "G70"}
    g60 = {r["theme_id"]: r for r in study_rows if r["derivative"] == "G60"}
    for t in ("HMI", "DIGITAL"):
        if t in g70 and t in g60:
            add("study", f"{THEMES[t]}: G70 {g70[t]['study_pct_negative_mean']}% negative vs "
                f"G60 {g60[t]['study_pct_negative_mean']}% in the US study",
                "study_pct_negative_mean_G70", g70[t]["study_pct_negative_mean"], "%",
                g70[t]["study_items"], f"US_2025, {t}", "mean pct_negative_bottom3 over mapped items",
                "n = number of study items, not respondents", f"{t.lower()}|study|G70")
    drv = g60.get("DRIVING")
    if drv:
        add("study", f"Driving is frequent in complaints ({drv['complaint_share_pct']}%) but rarely "
            f"rated negatively in the study ({drv['study_pct_negative_mean']}%)",
            "complaint_minus_study_pp", round(drv["complaint_share_pct"] - drv["study_pct_negative_mean"], 1),
            "pp", drv["n_pain"], "US, G60", "complaint share vs study pct_negative", "",
            "driving|frequency-vs-severity")
    for country, t in (("KR", "SPACE"), ("KR", "INT"), ("SE", "CHARGING")):
        v = lookup.get(("country_G60_sourceA", country, t))
        if v:
            add("country", f"{country} G60 owners: {THEMES[t]} in {v[0]}% of pain comments",
                f"share_{t}", v[0], "%", v[1], f"G60, Source A, {country}",
                "share of pain comments", "small sample" if v[1] < 50 else "", f"{country}|{t.lower()}")
    for g in growth:
        if g["growth_2025_2030_pct"] is not None:
            add("market", f"{g['derivative_group']} {g['market_code']} volume 2025->2030: "
                f"{g['growth_2025_2030_pct']:+}%", "growth_2025_2030_pct", g["growth_2025_2030_pct"], "%",
                "BMW plan", f"{g['derivative_group']} {g['market_code']}", "volume_2030 / volume_2025 - 1",
                "planning figure, not actual", "sales|2030|growth")
    return out


# --------------------------------------------------------------------------- main

def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--processed", type=Path, default=Path("data/processed"))
    ap.add_argument("--out", type=Path, default=Path("findings"))
    ap.add_argument("--bev-shares", default="0.2,0.35,0.5")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    comments = read_csv(args.processed / "comments.csv")
    study = read_csv(args.processed / "study_scores.csv")
    sales = read_csv(args.processed / "sales.csv")
    bev_shares = [float(x) for x in args.bev_shares.split(",")]

    shares, lookup = theme_shares(comments)
    study_rows, corr = study_vs_complaints(study, lookup)
    growth, vol = sales_growth(sales)
    scen = scenarios(lookup, comments, vol, bev_shares)
    kw = keywords(comments)
    heads = headline_findings(lookup, corr, study_rows, growth)

    write_csv(args.out / "theme_shares.csv", shares)
    write_csv(args.out / "study_vs_complaints.csv", study_rows)
    write_csv(args.out / "sales_growth.csv", growth)
    write_csv(args.out / "scenario_2030.csv", scen)
    write_csv(args.out / "keywords.csv", kw)
    write_csv(args.out / "findings.csv", heads)

    inputs = ["comments.csv", "study_scores.csv", "sales.csv"]
    manifest = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inputs": {f: file_hash(args.processed / f) for f in inputs},
        "parameters": {"bev_shares": bev_shares, "min_report_n": MIN_REPORT_N,
                       "pain_signal_types": sorted(PAIN),
                       "confidence": "high n>=300, medium n>=50, low otherwise"},
        "outputs": {"theme_shares": len(shares), "study_vs_complaints": len(study_rows),
                    "sales_growth": len(growth), "scenario_2030": len(scen), "keywords": len(kw),
                    "findings": len(heads)},
        "correlations": corr,
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("wrote manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
