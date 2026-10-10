# Output schemas

All IDs are stable strings. `run_id` comes from the config (e.g. `G60_US`).

## Signal  (`runs/<RUN_ID>/signals.json` — list)
| Field | Type | Notes |
|---|---|---|
| signal_id | str | `SIG-<RUN_ID>-NNN` |
| title | str | customer language, ≤ 12 words |
| description | str | 1–2 sentences: what customers experience |
| theme_id | str | from theme list |
| signal_type | enum | complaint · unmet_need · usability_pain · strength_to_protect · competitor_advantage · market_trend |
| origin | enum | provided_data · web_only · both |
| cluster_ids | list[str] | from candidate_clusters.csv (after merges) |
| comment_ids | list[str] | all supporting unique comments |
| n_comments / weighted_n / n_sources | int / float / int | computed in code |
| source_mix / engine_mix / country_mix | dict | counts |
| survey_severity_mix | dict | Source C only |
| quotes | list[{comment_id, text}] | 2–5 verbatim, ≤ 25 words, PII-masked |
| study | list[{study, market, item, metric, value, rank_in_market, compared_with}] | may be empty → say "no study coverage" |
| baseline | {status, option_codes, option_names_de, note} | status: not_offered · optional · in_package:<name> · standard · standard_but_poorly_rated · unknown |
| web_evidence_ids | list[str] | |
| scope | enum | in · borderline (state reading) · out (with route_to) |
| route_to | enum/null | quality · sales_service · regulatory · engineering |
| assigned_by | enum | bmw_tag · ai · pm |
| notes | str | merges/splits, caveats |

## WebEvidence  (`web_evidence.json` — list)
| Field | Type | Notes |
|---|---|---|
| web_evidence_id | str | `WEB-NNN` |
| url | str | page actually opened |
| publisher | str | |
| published | date/null | |
| accessed | date | |
| reliability | enum | official · expert_test · owner_forum · app_review · blog_other |
| competitor | str/null | model name if competitor-related |
| market | str/null | |
| quote | str | verbatim ≤ 25 words |
| finding | str | one sentence: what it shows |
| supports | list[str] | signal / requirement IDs |
| contradicts | list[str] | if it weakens a signal |

## Requirement  (`requirements.json` — list; flat copy in `requirements_backlog.csv`)
| Field | Type | Notes |
|---|---|---|
| req_id | str | `REQ-<RUN_ID>-NNN` |
| title | str | ≤ 10 words |
| statement | str | "As a <customer> in <market>, I want <capability> so that <benefit>." |
| acceptance_hint | str | observable, customer-side |
| type | enum | new_feature · improve_existing · package_change · make_standard · protect_strength |
| theme_id | str | |
| target_segment | str | e.g. "BEV drivers", "all", "rear-seat passengers" |
| signals | list[str] | |
| evidence | {comment_ids, study_items, option_codes, web} | ≥ 3 comment IDs where available |
| scores | {factor: {score 0–5, reason}} | customer_impact, severity, competitive_gap, market_relevance, strategic_fit |
| effort | enum | S · M · L (rough) |
| priority | float | Σ weight × score − effort_penalty, computed in code |
| rank | int | |
| confidence | enum | high (≥ 3 sources + study) · medium · low (single source / web only) |
| open_questions | list[str] | for the PM |
| status | enum | proposed · approved · rejected · edited · challenged · parked |
| pm_comment | str/null | |
| version | int | +1 on every edit; previous versions live in the audit log |

## AuditEvent  (`audit_log.jsonl` — one JSON object per line, append-only)
| Field | Type | Notes |
|---|---|---|
| ts | ISO datetime with offset | |
| run_id | str | |
| actor | str | agent · system · pm:<name> |
| action | enum | data_ingested · config_loaded · cluster_merged · cluster_split · signal_created · signal_dropped · signal_parked · web_evidence_added · requirement_created · score_computed · weights_changed · pm_approved · pm_rejected · pm_edited · pm_challenged · agent_responded · export_created · data_viewed |
| object_id | str | |
| before / after | object/null | full record for edits |
| reason | str | required for rejects, drops, merges, weight changes |
| evidence_refs | list[str] | |
| model | str | model ID used |
| inputs_hash | str/dict | file hashes from manifest.json |
