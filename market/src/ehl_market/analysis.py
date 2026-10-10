"""Country-level panel, correlations with uncertainty, multiple-testing control and gap analysis.

Every result carries n, uncertainty and warnings: with 13 markets at most, a correlation is a
hypothesis for a validation study, never proof of a customer need.
"""

import numpy as np
import pandas as pd
from scipy import stats

from . import bmw, store

STRENGTH = [(0.3, "weak"), (0.6, "moderate"), (1.01, "strong")]


def _strength(r: float) -> str:
    return next(label for cut, label in STRENGTH if abs(r) < cut)


def series(metric: str, year: int | None = None, source_id: str | None = None,
           population: str | None = None, derivative: str | None = None,
           engine_type: str | None = None, min_comments: int = bmw.MIN_COMMENTS) -> tuple[pd.DataFrame, list[str]]:
    """One value per country. Returns (df[country, value, year, n], notes)."""
    notes: list[str] = []
    if metric.startswith("bmw."):
        df = bmw.country_metric(metric, derivative, engine_type, min_comments)
        dropped = df[~df["reliable"]]
        if len(dropped):
            notes.append(f"{metric}: excluded {', '.join(f'{c} (n={n})' for c, n in zip(dropped['country'], dropped['n']))} "
                         f"- fewer than {min_comments} Source A comments")
        df = df[df["reliable"] & df["value"].notna()]
        notes.append(f"{metric}: Source A comments only, pooled over all years (cross-sectional)")
        return df.assign(year=None)[["country", "value", "year", "n"]], notes

    obs = store.load()
    obs = obs[obs["metric"].eq(metric)]
    if obs.empty:
        raise ValueError(f"no observations for {metric!r}; see list_metrics or fetch it first")
    if source_id:
        obs = obs[obs["source_id"].eq(source_id)]
    elif obs["source_id"].nunique() > 1:
        raise ValueError(f"{metric!r} comes from several sources {sorted(obs['source_id'].unique())}; "
                         "pass source_id - never mix sources in one variable")
    if population:
        obs = obs[obs["population"].eq(population)]
    elif obs["population"].nunique() > 1:
        raise ValueError(f"{metric!r} has several populations {sorted(obs['population'].unique())}; "
                         "pass population (e.g. all_respondents vs ev_intenders)")
    obs = obs.assign(year=obs["year"].astype(int))
    if year is not None:
        obs = obs[obs["year"].eq(year)]
        if obs.empty:
            raise ValueError(f"{metric!r} has no data for {year}")
    else:
        latest = obs.groupby("country")["year"].transform("max")
        obs = obs[obs["year"].eq(latest)]
    # sub-annual periods (e.g. Eurostat 2025-S1/S2) -> annual mean
    df = obs.groupby(["country", "year"], as_index=False)["value"].mean()
    years = sorted(df["year"].unique().tolist())
    if len(years) > 1:
        notes.append(f"{metric}: latest year differs by country {years} - pass year= to align")
    if obs["sample_size"].notna().any():
        notes.append(f"{metric}: survey metric - a country-level context variable, not what an "
                     "individual BMW customer thinks")
    return df.assign(n=None)[["country", "value", "year", "n"]], notes


def _rank_partial(x, y, z) -> float:
    rx, ry, rz = (stats.rankdata(v) for v in (x, y, z))
    res = [a - np.polyval(np.polyfit(rz, a, 1), rz) for a in (rx, ry)]
    return float(np.corrcoef(*res)[0, 1])


def correlate(x: str, y: str, year: int | None = None, control: str | None = None,
              derivative: str | None = None, engine_type: str | None = None,
              x_source: str | None = None, x_population: str | None = None,
              min_comments: int = bmw.MIN_COMMENTS, min_n: int = 5) -> dict:
    xs, nx = series(x, year, x_source, x_population, derivative, engine_type, min_comments)
    ys, ny = series(y, year, None, None, derivative, engine_type, min_comments)
    panel = xs.merge(ys, on="country", suffixes=("_x", "_y"))
    notes = nx + ny
    if control:
        cs, nc = series(control, year, derivative=derivative, engine_type=engine_type)
        panel = panel.merge(cs[["country", "value"]].rename(columns={"value": "value_c"}), on="country")
        notes += nc
    n = len(panel)
    result = {"x": x, "y": y, "n_countries": n, "countries": panel["country"].tolist(), "notes": notes}
    if n < min_n:
        result["status"] = f"not computed: only {n} countries overlap (need >= {min_n})"
        return result
    a, b = panel["value_x"].to_numpy(float), panel["value_y"].to_numpy(float)
    rho, p = stats.spearmanr(a, b)
    rng = np.random.default_rng(0)
    boots = []
    for _ in range(2000):
        idx = rng.integers(0, n, n)
        if len(set(idx)) > 2:
            r = stats.spearmanr(a[idx], b[idx])[0]
            if not np.isnan(r):
                boots.append(r)
    loo = {c: float(stats.spearmanr(np.delete(a, i), np.delete(b, i))[0]) for i, c in enumerate(panel["country"])}
    most_influential = max(loo, key=lambda c: abs(loo[c] - rho))
    result.update({
        "spearman_rho": round(float(rho), 3),
        "p_value": round(float(p), 4),
        "ci95_bootstrap": [round(float(np.percentile(boots, 2.5)), 3), round(float(np.percentile(boots, 97.5)), 3)],
        "strength": _strength(rho),
        "significant_at_5pct": bool(p < 0.05),
        "most_influential_country": {"country": most_influential, "rho_without_it": round(loo[most_influential], 3)},
        "table": panel.rename(columns={"value_x": x, "value_y": y}).round(3)
                      .drop(columns=[c for c in ("year_y", "n_x") if c in panel]).to_dict(orient="records"),
    })
    warnings = []
    if n < 8:
        warnings.append(f"n={n}: very small - only |rho| > ~0.75 can reach significance")
    if abs(loo[most_influential] - rho) > 0.2:
        warnings.append(f"result hinges on {most_influential} (rho {rho:.2f} -> {loo[most_influential]:.2f} without it)")
    if control:
        pr = _rank_partial(a, b, panel["value_c"].to_numpy(float))
        result["partial_rho_controlling_" + control] = round(pr, 3)
        if abs(pr) < abs(rho) / 2:
            warnings.append(f"association mostly disappears after controlling for {control} - likely confounded")
    elif "gdp_per_capita_ppp" not in (x, y):
        warnings.append("no control variable - consider control='gdp_per_capita_ppp' (income drives many "
                        "market variables at once)")
    warnings.append("association, not causation; use it to choose what to validate (MaxDiff/CBC, A/B), "
                    "not as a finding")
    result["warnings"] = warnings
    return result


def scan(y: str, year: int | None = None, control: str | None = None, derivative: str | None = None,
         min_n: int = 6) -> dict:
    """Correlate every stored external metric with y; Benjamini-Hochberg q-values against data dredging."""
    results, skipped = [], []
    for m in store.load()["metric"].dropna().unique():
        try:
            r = correlate(m, y, year=year, control=control, derivative=derivative, min_n=min_n)
        except ValueError as e:
            skipped.append({"metric": m, "reason": str(e)})
            continue
        if "spearman_rho" in r:
            results.append({k: r.get(k) for k in ("x", "n_countries", "spearman_rho", "p_value",
                                                  "ci95_bootstrap", "most_influential_country")}
                           | ({"partial_rho": r.get("partial_rho_controlling_" + control)} if control else {}))
        else:
            skipped.append({"metric": m, "reason": r["status"]})
    if results:
        p = np.array([r["p_value"] for r in results])
        order = np.argsort(p)
        q = np.empty_like(p)
        prev = 1.0
        for rank, i in reversed(list(enumerate(order, start=1))):
            prev = min(prev, p[i] * len(p) / rank)
            q[i] = prev
        for r, qi in zip(results, q):
            r["q_value_bh"] = round(float(qi), 4)
        results.sort(key=lambda r: (r["q_value_bh"], -abs(r["spearman_rho"])))
    return {"y": y, "tested": len(results), "results": results, "skipped": skipped,
            "note": "q_value_bh corrects for testing many metrics at once; with q > 0.1 treat as noise."}


def gap(demand: str, bmw_metric: str, bmw_direction: str = "pain", year: int | None = None,
        derivative: str | None = None, demand_source: str | None = None,
        demand_population: str | None = None) -> dict:
    """Where external demand is high and BMW's own signal is weak.

    bmw_direction: 'pain' if a higher BMW value is worse (e.g. negative share), 'performance' if better.
    """
    ds, nd = series(demand, year, demand_source, demand_population)
    bs, nb = series(bmw_metric, derivative=derivative)
    p = ds.merge(bs, on="country", suffixes=("_demand", "_bmw"))
    if len(p) < 3:
        return {"status": f"only {len(p)} countries overlap", "notes": nd + nb}
    z = lambda s: (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) else s * 0
    p["z_demand"] = z(p["value_demand"])
    p["z_bmw_pain"] = z(p["value_bmw"]) * (1 if bmw_direction == "pain" else -1)
    p["gap_score"] = p["z_demand"] + p["z_bmw_pain"]

    def label(r):
        if r.z_demand > 0 and r.z_bmw_pain > 0:
            return "priority: need is salient and BMW customers report pain"
        if r.z_demand > 0:
            return "served: need is salient, BMW signal is comparatively good - protect"
        if r.z_bmw_pain > 0:
            return "BMW-specific: pain without strong market demand - check product/quality cause"
        return "low priority"

    p["quadrant"] = p.apply(label, axis=1)
    p = p.sort_values("gap_score", ascending=False)
    return {
        "demand": demand, "bmw_metric": bmw_metric, "n_countries": len(p),
        "table": p.drop(columns=[c for c in ("year_bmw", "n_demand") if c in p]).round(3).to_dict(orient="records"),
        "notes": nd + nb + ["z-scores are relative to these countries only; next step is a validation "
                            "test (survey/MaxDiff/CBC or pricing experiment) in the top market"],
    }
