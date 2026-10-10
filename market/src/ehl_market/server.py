"""MCP server `ehl-market`: Customer-Market Correlation Engine.

Bridges what the market says customers want (external sources) and what BMW customers actually say
(Dataset/ comments). The agent does the reading and judgement; this server does sourcing rules,
retrieval, storage with provenance and all statistics.
"""

import logging

from mcp.server.fastmcp import FastMCP

from . import analysis, bmw, explore, fetch, methods, ranking, store
from .countries import COUNTRIES
from .sources import NEEDS, TIER_RULES, find

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
mcp = FastMCP("ehl-market")


@mcp.tool()
def list_sources(need: str | None = None, country: str | None = None, max_tier: int = 3) -> dict:
    """Credible external sources with tier, what they measure, coverage and how to retrieve them.

    need: affordability | ev_convenience | safety_tech | context. country: ISO2 (one of the 13 markets).
    Tier 1 = official/regulator/test body, 2 = commercial survey with published method, 3 = context only.
    `tool` says which tool retrieves it; None = read the report and use add_observation.
    """
    if need and need not in NEEDS:
        raise ValueError(f"need must be one of {NEEDS}")
    return {"tier_rules": TIER_RULES, "markets": sorted(COUNTRIES),
            "sources": [s.as_dict() for s in find(need, country.upper() if country else None, max_tier)]}


@mcp.tool()
def research_methods(method: str | None = None) -> dict:
    """How companies weight customer needs (stated/derived importance, MaxDiff, conjoint, Kano, QFD,
    observed behaviour), company examples, and the 'safety vs price' decision framework."""
    if method:
        if method not in methods.METHODS:
            raise ValueError(f"unknown method; choose from {sorted(methods.METHODS)}")
        return {method: methods.METHODS[method],
                "examples": [e for e in methods.EXAMPLES if e["method"] == method]}
    return {"methods": methods.METHODS, "examples": methods.EXAMPLES,
            "safety_vs_price": methods.SAFETY_VS_PRICE}


@mcp.tool()
def willingness_to_pay(beta_attribute: float, beta_price: float, price_unit: float = 1.0) -> dict:
    """Marginal WTP from choice-model coefficients estimated on real choice data (not invented ones).
    price_unit: euros per unit of the price variable (e.g. 1000 if price was coded in thousands)."""
    return methods.wtp(beta_attribute, beta_price, price_unit)


@mcp.tool()
def fetch_worldbank(metric: str, start_year: int = 2019, end_year: int = 2025,
                    indicator: str | None = None) -> dict:
    """Fetch a World Bank indicator for all 13 markets and store it.
    Presets: gdp_per_capita_ppp, gni_per_capita_ppp, inflation_cpi_pct, lending_interest_rate_pct,
    urban_population_pct, renewable_electricity_pct, population. Or any code via indicator=."""
    rows = fetch.worldbank(metric, start_year, end_year, indicator)
    return {"metric": metric, "rows": len(rows), "countries": sorted({r["country"] for r in rows}),
            **store.upsert(rows)}


@mcp.tool()
def fetch_eurostat(metric: str, start_year: int = 2019, dataset: str | None = None,
                   filters: dict | None = None, unit: str = "") -> dict:
    """Fetch a Eurostat dataset for DK ES FI FR SE NO and store it.
    Preset: electricity_price_household_eur_kwh. Or dataset code + dimension filters (one value each)."""
    rows = fetch.eurostat(metric, start_year, dataset, filters, unit)
    return {"metric": metric, "rows": len(rows), "countries": sorted({r["country"] for r in rows}),
            **store.upsert(rows)}


@mcp.tool()
def nhtsa_vehicle(make: str, model: str, model_year: int) -> dict:
    """US safety evidence for one vehicle: complaints by component, recalls, NCAP stars (live NHTSA API).
    Model names as NHTSA writes them, e.g. make='BMW', model='I5' or '530I'."""
    return fetch.nhtsa_vehicle(make, model, model_year)


@mcp.tool()
def import_iea_ev(path: str) -> dict:
    """Import the IEA Global EV Data Explorer CSV (downloaded by hand): EV sales/stock share and public
    chargers per country, historical rows only."""
    rows = fetch.import_iea_ev(path)
    return {"rows": len(rows), "metrics": sorted({r["metric"] for r in rows}), **store.upsert(rows)}


@mcp.tool()
def import_table(path: str, metric: str, source_id: str, country_col: str, year_col: str,
                 value_col: str, unit: str = "", url: str = "", sheet: str | None = None,
                 filters: dict | None = None) -> dict:
    """Import any long-format CSV/XLSX (national registrations, EAFO, OECD export...) as one metric.
    filters: {column: value} equality filters applied before import. source_id must be in list_sources."""
    rows = fetch.import_table(path, metric, source_id, country_col, year_col, value_col, unit, url,
                              sheet, filters)
    for r in rows:
        store.validate_manual(r | {"url": r["url"] or path})
    return {"rows": len(rows), **store.upsert(rows)}


@mcp.tool()
def add_observation(country: str, year: int, metric: str, value: float, unit: str, source_id: str,
                    url: str, population: str = "all", sample_size: int | None = None,
                    question_id: str | None = None, question_wording: str | None = None,
                    fieldwork: str | None = None, period: str | None = None, note: str | None = None) -> dict:
    """Store one value read from a report (Deloitte, J.D. Power, Euro NCAP datasheet...).

    Survey metrics need question_wording, population (e.g. all_respondents / ev_intenders), sample_size
    and fieldwork (e.g. '2025-09/10'). `year` = fieldwork year, not publication year. Only enter values
    printed in the source - never values read off a chart or estimated.
    """
    row = store.validate_manual(dict(country=country, year=year, period=period or str(year), metric=metric,
                                     value=value, unit=unit, source_id=source_id, url=url,
                                     population=population, sample_size=sample_size,
                                     question_id=question_id, question_wording=question_wording,
                                     fieldwork=fieldwork, note=note))
    return store.upsert([row])


@mcp.tool()
def list_metrics() -> dict:
    """All variables available for analysis: stored external metrics (with country/period coverage)
    and BMW internal metrics derived from Dataset/ comments."""
    return {"external": store.metrics_summary(), "bmw": bmw.available_metrics(),
            "bmw_themes": bmw.THEMES,
            "bmw_note": "Source A comments only (the one source in all 13 markets); countries with fewer "
                        f"than {bmw.MIN_COMMENTS} comments are excluded. Sales: see bmw_sales (regions only)."}


@mcp.tool()
def bmw_country_metric(metric: str, derivative: str | None = None, engine_type: str | None = None,
                       min_comments: int = bmw.MIN_COMMENTS) -> list[dict]:
    """One BMW metric per country with numerator, denominator and reliability flag.
    derivative: F70 | G60 | G70. engine_type: ICE | PHEV | BEV."""
    return bmw.country_metric(metric, derivative, engine_type, min_comments).round(2).to_dict(orient="records")


@mcp.tool()
def bmw_sales() -> dict:
    """BMW sales volumes by derivative group x region x year (EU, US, CN, RoW; 2030 = plan)."""
    return {"rows": bmw.sales(), "country_map": {c.iso2: c.sales_region for c in COUNTRIES.values()},
            "note": "Regional only - cannot be correlated at country level. 2030 values are plan, not observed."}


@mcp.tool()
def correlate(x: str, y: str, year: int | None = None, control: str | None = None,
              derivative: str | None = None, engine_type: str | None = None,
              x_source: str | None = None, x_population: str | None = None,
              min_comments: int = bmw.MIN_COMMENTS) -> dict:
    """Spearman correlation across countries with p-value, bootstrap 95% CI, leave-one-country-out
    influence and optional partial correlation controlling for a third metric (e.g. gdp_per_capita_ppp).
    x/y: metric names from list_metrics (external or bmw.*)."""
    return analysis.correlate(x, y, year, control, derivative, engine_type, x_source, x_population, min_comments)


@mcp.tool()
def scan_correlations(y: str, year: int | None = None, control: str | None = None,
                      derivative: str | None = None) -> dict:
    """Correlate every stored external metric with y and rank them, with Benjamini-Hochberg q-values
    so that testing many metrics does not produce false discoveries."""
    return analysis.scan(y, year, control, derivative)


@mcp.tool()
def gap_analysis(demand: str, bmw_metric: str, bmw_direction: str = "pain", year: int | None = None,
                 derivative: str | None = None, demand_source: str | None = None,
                 demand_population: str | None = None) -> dict:
    """Markets where external demand for a need is high and BMW's own customer signal is weak.
    bmw_direction: 'pain' (higher BMW value = worse, e.g. bmw.theme_negative_share.CHARGING) or
    'performance' (higher = better)."""
    if bmw_direction not in ("pain", "performance"):
        raise ValueError("bmw_direction must be 'pain' or 'performance'")
    return analysis.gap(demand, bmw_metric, bmw_direction, year, derivative, demand_source, demand_population)


@mcp.tool()
def correlation_matrix(metrics: list[str] | None = None, derivative: str | None = None, min_n: int = 5) -> dict:
    """All pairs of metrics (default: every stored external metric + BMW theme shares): Spearman rho,
    Pearson r with bootstrap CI, p, BH q, most influential country, and per-country values."""
    return explore.matrix(metrics, derivative, min_n)


@mcp.tool()
def sensitivity(metric: str, delta_sd: float = 1.0, derivative: str | None = None) -> list[dict]:
    """For markets where `metric` is delta_sd standard deviations higher: expected difference in every
    other metric (in SD, r x delta) with 95% interval. Cross-country association, not a causal effect."""
    return explore.sensitivity(metric, delta_sd, derivative=derivative)


@mcp.tool()
def export_explorer(path: str | None = None, derivative: str | None = None, min_n: int = 5) -> dict:
    """Write the interactive explorer (one self-contained HTML, works offline): clickable correlation
    matrix, per-country scatter with leave-one-country-out, sensitivity slider. Default: market/out/explorer.html."""
    return explore.export_html(path, derivative=derivative, min_n=min_n)


@mcp.tool()
def fetch_nhtsa_themes() -> dict:
    """Pull NHTSA complaints for the US G60 (5 Series, i5) and G70 (7 Series, i7) models, map NHTSA
    components to BMW themes and store the share per theme (external evidence for rank_topics)."""
    return ranking.fetch_nhtsa_themes()


@mcp.tool()
def rank_topics(level: str = "theme", kind: str = "pain", derivative: str | None = None,
                country: str | None = None, engine_type: str | None = None, theme: str | None = None,
                weights: dict | None = None, top: int = 25) -> dict:
    """Rank themes or keywords by how often customers mention them, how often positively vs negatively,
    plus a bonus from outside evidence on the same theme.

    level: theme | keyword. kind: pain (what to fix: high share negative) | strength (what to protect).
    weights: {"frequency": 0.5, "tone": 0.3, "external": 0.2} by default.
    Each row shows base, external_bonus, counts, % negative / % positive and the raw external values.
    """
    return ranking.rank(level, kind, derivative, country, engine_type, theme, weights, top)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
