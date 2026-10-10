# ehl-market: Customer–Market Correlation Engine (MCP server)

This server connects what the market says customers want (external sources) with what BMW customers
actually say (the `Dataset/` comments, prepared in `research/data/processed/`). The agent reads reports and
makes the judgement calls. The server applies the sourcing rules, retrieves the data, stores it with
provenance and computes all statistics.

## Tools

| Group | Tool | Does |
|---|---|---|
| Sources | `list_sources(need?, country?, max_tier?)` | Credible sources by tier, what they measure, coverage, how to retrieve, cost, caveats |
| Methods | `research_methods(method?)` | How companies weight needs (stated vs derived importance, MaxDiff, CBC conjoint, Kano, QFD, observed behaviour), company examples, the "safety vs price" framework |
| | `willingness_to_pay(beta_attribute, beta_price)` | WTP = −β_attr / β_price, for coefficients from real choice data only |
| Retrieve | `fetch_worldbank(metric)` | Live API, all 13 markets (GDP/GNI PPP, inflation, lending rate, ...) |
| | `fetch_eurostat(metric)` | Live API, DK ES FI FR SE NO (household electricity price preset, or any dataset) |
| | `nhtsa_vehicle(make, model, year)` | Live: US complaints by component, recalls, NCAP stars |
| | `import_iea_ev(path)` | IEA Global EV Data Explorer CSV → EV sales/stock share, public chargers |
| | `import_table(path, ...)` | Any long-format CSV/XLSX (national registrations, EAFO, OECD export) |
| | `add_observation(...)` | One value read from a report; survey values must include the question wording, base, sample size and fieldwork period |
| Analyse | `list_metrics()` | External metrics stored so far, plus BMW metrics (`bmw.comments`, `bmw.negative_share`, `bmw.theme_share.<THEME>`, `bmw.theme_negative_share.<THEME>`) |
| | `bmw_country_metric`, `bmw_sales` | BMW variables per country, regional sales |
| | `correlate(x, y, control?)` | Spearman ρ, p-value, bootstrap 95 % CI, the most influential country, partial ρ controlling for a third metric |
| | `scan_correlations(y)` | All external metrics against y, ranked, with Benjamini–Hochberg q-values |
| | `gap_analysis(demand, bmw_metric)` | Markets where external demand is high and the BMW signal is weak |
| Rank | `fetch_nhtsa_themes()` | NHTSA complaints for the US G60/G70 models (530i, 540i, i5, i7, …), mapped to BMW themes and stored as outside evidence |
| | `rank_topics(level, kind, ...)` | Ranks themes or keywords. score = base + outside bonus. base = 0.5 × frequency (log, source-weighted) + 0.3 × tone (share negative for `pain`, share positive for `strength`), rescaled. Outside bonus = 0.2 × NHTSA complaint share (pain only) or stated importance `importance.<THEME>`, and 0 when no outside source covers the theme. Filters: derivative, country, engine, theme |
| Visualise | `correlation_matrix(metrics?)` | All metric pairs: ρ, Pearson r with bootstrap CI, p, q, most influential country, per-country values |
| | `sensitivity(metric, delta_sd)` | For markets where `metric` is Δ SD higher: expected difference in every other metric (r × Δ), with 95 % interval |
| | `export_explorer(path?)` | Writes `out/explorer.html`: a self-contained interactive page that works offline (see below) |

## Explorer (`out/explorer.html`)

- **Matrix:** click a cell to open the pair. A ring marks pairs that survive multiple testing (q < 0.10).
- **Scatter:** each dot is a country. Click a dot to see ρ without that market, which shows whether
  one country carries the result.
- **Sensitivity:** pick a metric and move the slider (−2 … +2 SD). The bars show how much higher or
  lower every other metric tends to be in such markets, with a 95 % interval. Grey means the interval
  includes zero. Click a bar to open that pair.
- It has a table of all pairs, data notes and dark mode, and works at phone width.

Sensitivity is a cross-country association, not "if BMW changes feature X, metric Y moves". A causal
answer needs an experiment (a CBC price/feature test, or an A/B test on option pricing).

Hand-off to the requirements agent: see §3a of
`docs/superpowers/specs/2026-10-10-ehl-research-mcp-design.md` (`add_market_evidence`).

## Source credibility rules

- **Tier 1:** official statistics, regulators and independent test bodies (World Bank, OECD, Eurostat,
  IEA, NHTSA, Euro NCAP, national registries). These can be used directly as model variables.
- **Tier 2:** commercial research with a published method (Deloitte, J.D. Power, EY, McKinsey,
  Cox/KBB). These can be used as model variables only when the question wording, base, sample size and
  fieldwork period are stored. "47 % concerned about range" is not the same as "47 % won't buy an EV".
- **Tier 3:** press, forums, blogs and marketing. These are context only and are never stored.
  `add_observation` rejects any source that is not in the registry.

## Setup

```bash
cd market
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"     # macOS: .venv/bin/python
.venv/Scripts/python -m pytest
```

Requires `research/data/processed/` (from `research/scripts/prepare_data.py`) for the BMW metrics.

Rowboat / Claude `mcp.json`:

```json
{
  "mcpServers": {
    "ehl-market": {
      "command": "C:/Users/<you>/.../ehl-munich-2026/market/.venv/Scripts/python.exe",
      "args": ["-m", "ehl_market.server"],
      "env": {
        "EHL_MARKET_HOME": "C:/Users/<you>/.../ehl-munich-2026/market",
        "EHL_RESEARCH_HOME": "C:/Users/<you>/.../ehl-munich-2026/research"
      }
    }
  }
}
```

## What the data can and cannot support (say this in the pitch)

- **About 9 usable countries.** Only Source A covers all 13 markets. ES, FI, NO and ZA have fewer than
  20 comments and are excluded. A correlation needs |ρ| > ~0.7 to reach significance at this sample size.
- **Cross-sectional.** Comments have no reliable year, so BMW metrics are pooled. Lagged models are not
  possible with `Dataset/` alone.
- **Sales are regional** (EU/US/CN/RoW), so BMW sales cannot be correlated with country-level variables.
  Doing that needs BMW country sales and option take rates.
- **Results are hypotheses.** They show where to run a validation study (MaxDiff for ranking, CBC for
  willingness to pay), not what customers want.
- **Missing values stay missing.** Nothing is imputed.

Example with real data (2026-10-10): GDP per capita PPP compared with `bmw.negative_share` gives n = 9,
ρ = 0.23, p = 0.55, CI [−0.74, 0.82]. This is no evidence of an association, and the result flips without JP.
