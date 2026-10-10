# Findings dataset (standard results)

The standard set of numbers, keywords and findings derived from the hackathon data. The agent, the
MCP server and the pitch use these values instead of recomputing them ad hoc. Rebuild after any
change to the data or mappings:

```bash
python scripts/prepare_data.py --raw data/raw --out data/processed   # raw xlsx/pdf -> processed (once)
python scripts/build_findings.py --processed data/processed --out findings
python scripts/build_findings.py --bev-shares 0.2,0.35,0.5           # other 2030 scenario assumptions
```

Input file hashes, parameters and the correlation results are in `manifest.json`.

## Rules for using these numbers

- **Base:** shares are **% of pain comments** (signal types `unmet_need`, `usability_pain`,
  `performance_gap`, `defect`) in the group, counted on unique comments. A comment can touch
  several themes, so the shares in a group do not add up to 100 %.
- **Confidence** from the base n: `high` ≥ 300 · `medium` ≥ 50 · `low` < 50. Groups below 10
  pain comments are not written.
- **Compare like with like:** countries differ in model and source mix (GB/JP mostly F70, US mostly
  Source B). For country comparisons use `dimension = country_G60_sourceA`; for powertrain use
  `engine_US`.
- **Origin:** `provided_data` = computed from the BMW dataset · `scenario` = computed with stated
  assumptions, never present it as a forecast. The comments have no dates, so there are no time trends.
- Always cite `finding_id` or the table row (dimension, group, theme) together with n.

## Files

| File | One row per | Key columns |
|---|---|---|
| `findings.csv` | headline finding | `finding_id`, `category` (correlation · study · country · market · scenario), `statement`, `metric`, `value`, `unit`, `n`, `scope`, `confidence`, `method`, `origin`, `caveat`, `keywords` |
| `theme_shares.csv` | grouping × group × theme | `dimension`, `group`, `base`, `n_comments`, `n_pain`, `pain_pct`, `theme_id`, `share_pct`, `n_theme`, `confidence` |
| `study_vs_complaints.csv` | model × theme (US) | `study_pct_negative_mean` (mean of `pct_negative_bottom3` over mapped study items), `complaint_share_pct`, `study_items`, `n_pain` |
| `sales_growth.csv` | model group × market | `volume_2024/2025/2030`, `growth_2025_2030_pct`, `quality_flag` (BMW plan figures) |
| `scenario_2030.csv` | scenario × theme | `scenario`, `assumption`, `today_share_pct`, `projected_share_pct`, `basis_n`, `origin` |
| `keywords.csv` | scope × term | `scope_type` (theme · country · engine), `scope`, `term`, `n_comments`, `share_in_scope_pct`, `lift` (how much more often the term appears in this scope than overall), `n_scope` |

### Groupings in `theme_shares.csv`

| dimension | Compares | Base |
|---|---|---|
| `country` | countries | all models, all sources (mixed; see rules) |
| `derivative_country` | model × country | all sources |
| `country_G60_sourceA` | countries | same car (G60), same source (A) |
| `engine_US` | ICE / PHEV / BEVE | US, G60 + G70 |
| `derivative_US` | G60 / G70 | US |
| `source_US` | Source A–D | US |
| `derivative_engine_US` | model × powertrain | US |

### Scenarios in `scenario_2030.csv`

| Scenario | Question | Method |
|---|---|---|
| `S1_bev_share` | How does the US need profile change if the BEV share of buyers grows? | today's ICE and BEV complaint profiles mixed by the assumed BEV share (PHEV counted as ICE) |
| `S2_volume_weighted` | Does BMW's 2030 volume plan shift which themes matter for the G60? | regional complaint profile × regional volume 2025 vs 2030 (China excluded: no comments) |

## Themes

`COMFORT` Comfort, seats & climate · `SPACE` Space, storage & practicality · `HMI` Infotainment &
operation · `DIGITAL` Connectivity & digital services · `CHARGING` Range & charging · `DRIVING`
Driving experience & performance · `EXT` Exterior design & lighting · `INT` Interior design &
quality perception · `ACCESS` Access, doors & convenience · `ADAS` Driver assistance & parking.
Mapping from BMW components: `reference/theme_mapping.csv`.
