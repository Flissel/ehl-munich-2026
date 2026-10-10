"""All-pairs correlation matrix + sensitivity, and the interactive explorer (one self-contained HTML).

Sensitivity is the cross-country association, not a causal effect: "markets where x is 1 SD higher
have, on average, y higher by r SD". The explorer says so on every view.
"""

import json
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy import stats

from . import analysis, bmw, store

DEFAULT_BMW = ["bmw.negative_share"] + [f"bmw.theme_share.{t}" for t in bmw.THEMES if not t.startswith("OUT_")]
LABELS = {
    "gdp_per_capita_ppp": "GDP per capita (PPP)", "gni_per_capita_ppp": "GNI per capita (PPP)",
    "inflation_cpi_pct": "Inflation (CPI)", "lending_interest_rate_pct": "Lending rate",
    "urban_population_pct": "Urban population", "renewable_electricity_pct": "Renewable electricity",
    "electricity_price_household_eur_kwh": "Household electricity price",
    "ev_sales_share_pct": "EV sales share", "ev_stock_share_pct": "EV stock share",
    "public_fast_chargers": "Public fast chargers", "public_slow_chargers": "Public slow chargers",
    "bmw.negative_share": "BMW: negative share",
}


THEME_SHORT = {
    "ACCESS": "Access & doors", "ADAS": "Driver assistance", "CHARGING": "Range & charging",
    "COMFORT": "Comfort & seats", "DIGITAL": "Connectivity", "DRIVING": "Driving experience",
    "EXT": "Exterior design", "HMI": "Infotainment & HMI", "INT": "Interior quality",
    "SPACE": "Space & storage", "OUT_SAFETY": "Safety (out of scope)", "OUT_TECH": "Technical (out of scope)",
}


def _label(m: str) -> str:
    if m in LABELS:
        return LABELS[m]
    p = m.split(".")
    if len(p) == 3 and p[2] in bmw.THEMES:
        return f"BMW: {THEME_SHORT[p[2]]}" + (" (neg.)" if p[1] == "theme_negative_share" else " mentions")
    return m


def _bh(p: list[float]) -> list[float]:
    p = np.asarray(p, float)
    order = np.argsort(p)
    q = np.empty_like(p)
    prev = 1.0
    for rank, i in reversed(list(enumerate(order, start=1))):
        prev = min(prev, p[i] * len(p) / rank)
        q[i] = prev
    return q.tolist()


def matrix(metrics: list[str] | None = None, derivative: str | None = None, min_n: int = 5,
           n_boot: int = 1000) -> dict:
    if metrics is None:
        # single-country series (NHTSA theme shares, US-only surveys) cannot be correlated across markets
        metrics = sorted(r["metric"] for r in store.metrics_summary() if r["n_countries"] >= min_n) + DEFAULT_BMW
    data, meta, notes = {}, [], []
    obs = store.load()
    for m in metrics:
        try:
            df, nts = analysis.series(m, derivative=derivative)
        except ValueError as e:
            notes.append(f"skipped {m}: {e}")
            continue
        notes += nts
        data[m] = dict(zip(df["country"], df["value"].astype(float)))
        if m.startswith("bmw."):
            unit = "% of comments"
        else:
            units = obs.loc[obs["metric"].eq(m), "unit"].dropna()
            unit = str(units.iloc[0]) if len(units) else ""
        years = sorted({int(y) for y in df["year"].dropna()})
        meta.append({"id": m, "label": _label(m), "group": "bmw" if m.startswith("bmw.") else "external",
                     "unit": unit, "years": years, "n_countries": len(df)})
    rng = np.random.default_rng(0)
    pairs = []
    for a, b in combinations(data, 2):
        cs = sorted(set(data[a]) & set(data[b]))
        rec = {"x": a, "y": b, "n": len(cs), "countries": cs}
        if len(cs) >= min_n:
            x = np.array([data[a][c] for c in cs]); y = np.array([data[b][c] for c in cs])
            if x.std() == 0 or y.std() == 0:
                pairs.append(rec | {"status": "constant"})
                continue
            rho, p = stats.spearmanr(x, y)
            r = float(np.corrcoef(x, y)[0, 1])
            boots = []
            for _ in range(n_boot):
                i = rng.integers(0, len(cs), len(cs))
                if len(set(i)) > 2 and x[i].std() and y[i].std():
                    boots.append(np.corrcoef(x[i], y[i])[0, 1])
            loo = [float(stats.spearmanr(np.delete(x, k), np.delete(y, k))[0]) for k in range(len(cs))]
            k = int(np.argmax(np.abs(np.array(loo) - rho)))
            rec |= {"rho": round(float(rho), 3), "p": round(float(p), 4), "r": round(r, 3),
                    "r_ci95": [round(float(np.percentile(boots, 2.5)), 3), round(float(np.percentile(boots, 97.5)), 3)],
                    "slope_y_per_x": float(r * y.std() / x.std()), "slope_x_per_y": float(r * x.std() / y.std()),
                    "influential": {"country": cs[k], "rho_without": round(loo[k], 3)}}
        pairs.append(rec)
    tested = [p for p in pairs if "p" in p]
    for p, q in zip(tested, _bh([p["p"] for p in tested])):
        p["q"] = round(q, 4)
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "derivative": derivative, "min_n": min_n, "metrics": meta,
        "values": {m: {c: round(v, 4) for c, v in d.items()} for m, d in data.items()},
        "pairs": pairs, "notes": sorted(set(notes)),
        "caveat": "Cross-country associations (n <= 13, mostly ~9). Not causal. Sensitivity = 'markets "
                  "where x is higher tend to have y higher/lower by r SD', not 'changing x changes y'.",
    }


def sensitivity(metric: str, delta_sd: float = 1.0, **kw) -> list[dict]:
    """Expected difference in every other metric for markets where `metric` is delta_sd SD higher."""
    m = matrix(**kw)
    out = []
    for p in m["pairs"]:
        if "r" not in p or metric not in (p["x"], p["y"]):
            continue
        other = p["y"] if p["x"] == metric else p["x"]
        lo, hi = p["r_ci95"]
        out.append({"metric": other, "label": _label(other), "n": p["n"],
                    "expected_change_sd": round(p["r"] * delta_sd, 3),
                    "ci95_sd": sorted([round(lo * delta_sd, 3), round(hi * delta_sd, 3)]),
                    "q": p.get("q"), "uncertain": lo <= 0 <= hi})
    return sorted(out, key=lambda r: -abs(r["expected_change_sd"]))


def export_html(path: str | None = None, **kw) -> dict:
    m = matrix(**kw)
    tpl = (Path(__file__).parent / "explorer_template.html").read_text(encoding="utf-8")
    payload = json.dumps(m, ensure_ascii=False).replace("</", "<\\/")
    out = Path(path) if path else store.home() / "out" / "explorer.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(tpl.replace("/*__DATA__*/null", payload), encoding="utf-8")
    return {"path": str(out), "metrics": len(m["metrics"]), "pairs_computed": sum("r" in p for p in m["pairs"])}
