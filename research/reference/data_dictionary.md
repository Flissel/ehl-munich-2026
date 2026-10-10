# Data dictionary

## Raw files (hackathon)

| File | Content | Notes |
|---|---|---|
| `F70_feedback_hackathon.xlsx` | BMW 1 Series feedback, ~4.1k rows / 2.1k comments | Source A only, ICE only, mostly GB + JP |
| `G60_feedback_hackathon.xlsx` | BMW 5 Series feedback, ~5.0k rows / 4.0k comments | Sources A–D, ICE/PHEV/BEV, ~87 % US |
| `G70_feedback_hackathon.xlsx` | BMW 7 Series feedback, ~4.7k rows / 4.0k comments | Sources A–D, ICE/PHEV/BEV, ~94 % US |
| `F70_G60_G68_G70_customer_studies.xlsx` | Sheet `CN_EU_2025`: mean scores 0–10 on ~38 attributes. Sheet `US_2025`: 7-level rating distributions on ~100 items | China: G68 (5 Series LWB), G70. EU: F70, G60, G70. US: G60, G70 |
| `sales_volumes.xlsx` | Volumes 2024 / 2025 / 2030 per region (EU, CN, US, RoW); sheets F70, G60_G68, G70 | F70/CN 2024 is a broken formula (`=-D3-C10`) → missing |
| `*_OptionList.PDF` | German price lists (July 2026): models, standard equipment, packages, options with SA-code and price | DE market only |

Raw feedback columns: `ID, Source, Brand, Sales Description, Country, Derivate (e-code), Engine Type,
Feedback Type, Customer Feedback, Vfc level2 3 Name, Vfc level2 Name, Vfc level3 Name`.
**One comment appears in several rows** when BMW gave it several tags.

## Processed files (`data/processed/`, made by `scripts/prepare_data.py`)

### comments.csv — one row per unique comment
| Column | Meaning |
|---|---|
| comment_id | e.g. `G60-0003` — use this as evidence ID |
| derivative / model / country / engine_type | `engine_type`: ICE, PHEV, BEVE (= BEV) |
| source | Source A–D (anonymised) |
| source_type | inferred: owner_review_or_online_survey, customer_care_log, quality_survey_IQS_style, appeal_survey_sentence_completion |
| voice | `customer` or `agent_paraphrase` (Source B) |
| source_weight | 1.0 / 0.8 / 1.0 / 0.9 for A / B / C / D — editable |
| text | cleaned (survey boilerplate removed) and PII-masked text — **quote this** |
| survey_severity / survey_item | Source C only: very serious / serious / moderate / minor / unspecified + the IQS problem item |
| pii_masked | number of regex masks applied |
| feedback_types | Likes, Wants, Difficult to Use, Defect, unclassified (pipe-separated) |
| signal_types | strength, unmet_need, usability_pain, performance_gap, defect, unknown |
| themes / components | theme IDs and BMW components (Vfc level2) of all tags |
| is_empty | text shorter than 3 characters |

### evidence_tags.csv — one row per comment × BMW tag
`tag_id, comment_id, derivative, country, engine_type, source, feedback_type, vfc_level2 (component),
vfc_level3 (issue), theme_id, theme_name, scope, signal_type, polarity, requirement_relevance, text`

### study_scores.csv — long format
| Column | Meaning |
|---|---|
| study | CN_EU_2025 or US_2025 |
| market / derivative / vehicle | e.g. US / G60 / BMW 5 Series G60 |
| item | study question (e.g. "Menu structure of infotainment system") |
| metric | `mean_score_0_10` (CN_EU) · `share_<level>` (US, 7 levels) · `pct_negative_bottom3` · `pct_delight_top2` |
| value | number (shares are 0–1) |
| theme_id / scope | from `reference/study_mapping.csv` |
| rank_in_market | rank among the BMW vehicles of the same study + market (1 = lowest value). For `mean_score` low = weak; for `pct_negative` low = good |

### sales.csv
`derivative_group, derivatives, market, market_code, year, volume, quality_flag`

### options_<D>.csv / options_<D>.txt
`derivative, section (German heading), option_name (German), option_code (SA-Nr.), price_eur_gross,
n_variants_standard (■), n_variants_optional (□), availability (standard_only | standard_some | optional)`.
The CSV catches lines with availability symbols; use the `.txt` for full-text search (packages, standard equipment lists, technical data like DC charging power or luggage volume).

### coverage.csv
`derivative, country, source, n_comments` — how much evidence exists per slice.

## Reference files (`reference/`)
| File | Purpose |
|---|---|
| `theme_mapping.csv` | 226 BMW components (Vfc level2) → 12 themes + scope (in / borderline / out / review). Editable by the team; changes must be logged |
| `issue_mapping.csv` | 84 BMW issue codes (Vfc level3) → signal_type, polarity, requirement relevance |
| `study_mapping.csv` | 139 study items → theme + scope |
| `schemas.md` | JSON schemas for Signal, WebEvidence, Requirement, AuditEvent |

## Themes
| ID | Theme |
|---|---|
| COMFORT | Comfort, seats & climate |
| SPACE | Space, storage & practicality |
| HMI | Infotainment & operation |
| DIGITAL | Connectivity & digital services |
| CHARGING | Range & charging (as experienced) |
| DRIVING | Driving experience & performance |
| EXT | Exterior design & lighting |
| INT | Interior design & quality perception |
| ACCESS | Access, doors & convenience |
| ADAS | Driver assistance & parking (experience) |
| PACKAGES | Equipment level, variants & packages (study items) |
| OUT_SAFETY / OUT_TECH | out of scope — park, do not derive requirements |
| UNCLASSIFIED | no BMW tag — classify with the LLM, log as `ai_assigned` |
