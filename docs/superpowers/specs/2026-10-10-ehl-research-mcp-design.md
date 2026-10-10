# Requirements Research Agent in Rowboat: MCP server `ehl-research`

**Date:** 2026-10-10 · **Status:** Draft, needs orchestrator approval (new MCP server + folder, see §8)
**Based on:** the starter package `bmw-requirements-agent` (`AGENT.md`, `reference/`, `scripts/`,
`config/`, `data/processed/`, `runs/`) and `docs/data-pipeline-plan.md`

## 1. Goal

The package defines a **Customer Requirements Research Agent**: raw customer evidence → signals →
requirements → explainable priority → PM decision → audit trail, in phases 0–8 with PM checkpoints
(`AGENT.md`). It assumes an agent that can run Python and write files (Claude Code).

Rowboat's chat agent cannot run Python. So we wrap the package in an MCP server, `ehl-research`:

- **The server** does everything `AGENT.md` says must be done *in code*: loading data, counting
  unique comments, source weights, study lookups, option search, the priority formula, ID
  assignment, schema validation, the append-only audit log, exports.
- **The Rowboat agent** does what needs an LLM, with the user's own model key: naming and merging
  clusters, writing requirement statements, scoring 0–5 with reasons, web research, and the PM
  conversation (the PM checkpoints become chat turns).
- **Rowboat's graph** shows the result: each requirement becomes a note linked to
  `[[Projects/G60]]` and `[[Topics/Market Research]]`.

Demo prompt: *"Run the requirements agent for G60 in the US and show me the top 10 for review."*

## 2. What we reuse from the package as-is

| Package part | Use |
|---|---|
| `data/processed/*` (from `scripts/prepare_data.py`) | Read-only data the server loads at start: `comments.csv` (10,128 unique, PII-masked), `evidence_tags.csv`, `study_scores.csv`, `sales.csv`, `options_<D>.csv/.txt`, `coverage.csv`, `manifest.json` |
| `runs/<RUN_ID>/candidate_clusters.csv`, `cluster_assignments.csv` (from `scripts/cluster_signals.py`, TF-IDF, reproducible) | Starting clusters per run (G60_US: 2,170 comments → 286 clusters; F70_GB also done) |
| `reference/theme_mapping.csv`, `issue_mapping.csv`, `study_mapping.csv` | Theme/scope/signal-type lookups |
| `reference/schemas.md` | Signal / WebEvidence / Requirement / AuditEvent, enforced by the server (pydantic) |
| `config/G60_US.yaml`, `config/F70_GB.yaml` | Run config: filter, studies, sales, option list, competitors, weights |
| `AGENT.md` | Becomes the Rowboat agent's instructions, with "run python / write file" replaced by tool names (§5) |

Data prep stays a one-off script step (`prepare_data.py`, needs `pdftotext`); the server never
re-parses raw files. Clustering can be re-run through a tool (§3) if the PM changes the filter.

## 3. MCP tools (one per `AGENT.md` step that needs code)

stdio server, Python 3.12, official `mcp` SDK (`FastMCP`), pandas + pydantic + pyyaml.
Every write tool appends its audit event itself, so the agent cannot forget to log.

| Phase | Tool | Does |
|---|---|---|
| 0 | `start_run(run_id)` | Loads config + manifest; returns derivative, market, powertrains, competitors, weights, coverage per source, data-quality notes, "thin evidence" warning (< 300 comments or 1 source). Logs `config_loaded`, `data_ingested` with file hashes |
| 0 | `update_run(run_id, competitors?, weights?, reason)` | PM checkpoint 0 edits; checks weights sum to 1.0; logs `weights_changed` |
| 1 | `list_clusters(run_id, theme_id?, offset=0, limit=20)` | Candidate clusters by `weighted_n`, with representative comments (ID + masked text) and mixes |
| 1 | `get_comments(comment_ids? \| run_id+filters, limit)` | Masked comments with source, engine, country, feedback types, survey severity |
| 1 | `list_unclassified(run_id, limit)` · `assign_comments(run_id, comment_ids, theme_id\|signal_id, reason)` | `UNCLASSIFIED` comments; assignments stored as `assigned_by: ai` |
| 1 | `save_signal(run_id, title, signal_type, theme_id, cluster_ids, comment_ids?, quotes, scope, route_to?, notes)` | Server computes `n_comments`, `weighted_n`, `n_sources`, source/engine/country/severity mixes **from the comment IDs**; assigns `SIG-<RUN_ID>-NNN`; merges = several `cluster_ids`; logs `signal_created` / `cluster_merged` |
| 1 | `drop_signal(signal_id, reason)` · `park_signal(signal_id, route_to, reason)` | Scope guard; nothing silently disappears |
| 2 | `study_lookup(run_id, theme_id?, query?)` | Matching study items: `pct_negative_bottom3`, `pct_delight_top2` (US) or `mean_score_0_10` + `rank_in_market` (CN/EU), with the comparison vehicles. Empty → "no study coverage" |
| 2–3 | `attach_to_signal(signal_id, study?, baseline?)` | Stores study matches and baseline status (`not_offered` … `standard_but_poorly_rated`) |
| 3 | `search_options(derivative, terms[])` | Full-text search over `options_<D>.txt` + `.csv` (German terms; ships the EN→DE examples from `AGENT.md`); returns code, German name, availability, price, with "DE market" flag |
| 4 | `add_web_evidence(url, publisher, published, reliability, competitor?, quote, finding, supports[])` | Assigns `WEB-NNN`, checks quote ≤ 25 words; logs `web_evidence_added`. The search itself is done by the agent (§5) |
| 4 | `add_market_evidence(signal_id\|req_id, kind, x, y, n, rho, ci95, q, influential_country, source_ids[], finding)` | Stores a result the agent got from `ehl-market` (§3a); assigns `MKT-NNN`; logs `market_evidence_added` |
| 5 | `save_requirement(run_id, title, statement, acceptance_hint, type, theme_id, target_segment, signals[], evidence, open_questions)` | Validates ≥ 3 comment IDs where available and that all IDs exist; assigns `REQ-<RUN_ID>-NNN` |
| 6 | `score_requirement(req_id, scores{factor: {score, reason}}, effort)` | Computes `priority = Σ weight × score − effort_penalty` and `confidence`; re-ranks; logs `score_computed` |
| 6–7 | `list_requirements(run_id, status?, top_n?)` | PM cards: title, statement, priority + breakdown, evidence summary, 2–3 quotes, study number, competitor finding, open questions |
| 7 | `pm_action(req_id, action, pm, reason?, changes?)` | approve / reject (reason required) / edit (version +1, old version in log) / challenge; logs `pm_*` |
| 7 | `reweight(run_id, weights, reason)` | Recomputes all priorities and returns what moved |
| 8 | `export_run(run_id)` | Writes `signals.json`, `web_evidence.json`, `requirements.json`, `requirements_backlog.csv` to `runs/<RUN_ID>/`; returns data for `summary.md`; logs `export_created` |
| 8 | `requirement_note(req_id)` | Ready-to-write Markdown note for the Rowboat vault (§4) |
| all | `audit_log(run_id, object_id?, limit)` | The trail, for "show me how you got here" |
| opt. | `recluster(run_id, filter?, distance_threshold?)` | Re-runs `cluster_signals.py` logic for a changed filter (e.g. BEV only) |

State lives in `runs/<RUN_ID>/` (JSON + `audit_log.jsonl`, append-only), exactly the package's
output layout, so Claude Code and Rowboat runs are interchangeable.

## 3a. Handoff with `ehl-market` (external market data)

`ehl-market` (folder `market/`, README there) is a second MCP server. It stores external data from
credible sources (World Bank, Eurostat, IEA, NHTSA, Deloitte, ...) with provenance, and correlates it
with BMW per-country metrics computed from the same `data/processed/` files. The two servers never
call each other. The Rowboat agent calls both in one conversation and carries results across.

**Shared keys:** `theme_id` (from `reference/theme_mapping.csv`; `ehl-market` metrics are named
`bmw.theme_share.<THEME>` and `bmw.theme_negative_share.<THEME>`) and ISO2 country codes.

**Flow (phase 4, next to web research):**
1. For a signal with `theme_id = T`, the agent calls `ehl-market.sensitivity("bmw.theme_share.T")`
   or `correlate(<external metric>, "bmw.theme_negative_share.T")`, or calls `gap_analysis` to see
   which markets show the same pain.
2. It calls `add_market_evidence` with the numbers *as returned*. The server rejects a record
   without `n`, `ci95` and `q`, and stores `kind` = `correlation` | `gap` | `sensitivity`.
3. In phase 6, market evidence may raise a requirement's `market_relevance` score only if
   `q < 0.10` and the CI excludes 0. Otherwise it is shown on the PM card as "context, not
   significant". This rule is enforced in `score_requirement`, and the reason is logged.

**PM card / note line (§4):** `Market: GDP per capita × Comfort mentions ρ +0.80 (n 9, q 0.39), context only`.

**Visual:** `ehl-market.export_explorer` writes `market/out/explorer.html`. It is a clickable
correlation matrix, a per-country scatter with leave-one-country-out, and a sensitivity slider. The
demo opens it next to the requirement list.

## 4. Notes in Rowboat's graph

The agent writes the note from `requirement_note` into the vault itself (agent-written notes,
no `managed_by`); the server never writes into the vault. Proposed folder: `Requirements/`
(own colour group in the graph); fallback `Content/` if the new folder is not approved.

```markdown
---
source: ehl-research
req_id: REQ-G60_US-003
run_id: G60_US
status: proposed
---
# REQ-G60_US-003 HUD readable with polarized sunglasses

## Info
**Statement:** As a G60 driver in the US, I want the head-up display to stay readable with polarized sunglasses so that I keep my eyes on the road.
**Type:** improve_existing
**Priority:** 3.85 (rank 2) · confidence high
**Effort:** S

## Connected to
- [[Projects/G60]]
- [[Topics/Market Research]]

## Key facts
- 14 comments, weighted 13.2, 3 sources (B 8 · C 4 · A 2)
- US_2025 "Head-up Display": 6 % negative
- Option list (DE): Head-Up Display, code 610, optional
- Mercedes E-Class HUD readable with polarized glasses (WEB-031)

## Open items
- PM decision
```

## 5. Rowboat agent instructions

`AGENT.md` becomes a Rowboat skill/instruction "Requirements Research" (added to WP1's EHL skill),
with these edits:

- "Run `prepare_data.py` / `cluster_signals.py`" → `start_run` / `list_clusters` (already prepared).
- "Compute with code" → the matching tool; **never compute counts or priorities in the chat**.
- "Write to `runs/<RUN_ID>/`" → `save_*`, `export_run`; "append audit line" → automatic.
- PM checkpoints ⏸ → stop and ask the user in the chat, one question at a time.
- After the PM review: write each top requirement note via `requirement_note`.
- **Web research (phase 4):** check which web tools Rowboat's agent has (built-in search/fetch or an
  MCP like a search API). If none, phase 4 uses evidence the team collects beforehand and enters via
  `add_web_evidence`; the demo states this honestly.

## 6. Setup

```
research/                       # = the starter package + the server
  AGENT.md  README.md  config/  reference/  scripts/
  data/processed/               # generated by prepare_data.py from Dataset/
  runs/                         # gitignored except committed demo runs, see §8
  src/ehl_research/server.py  data.py  stats.py  store.py  notes.py  models.py
  pyproject.toml  .env.example  tests/
```

`~/.rowboat/config/mcp.json` (or `~/.rowboat-ehl/config/mcp.json`):

```json
{
  "mcpServers": {
    "ehl-research": {
      "command": "C:/Users/<you>/ehl/ehl-munich-2026/research/.venv/Scripts/python.exe",
      "args": ["-m", "ehl_research.server"],
      "env": { "EHL_RESEARCH_HOME": "C:/Users/<you>/ehl/ehl-munich-2026/research" }
    },
    "ehl-market": {
      "command": "C:/Users/<you>/ehl/ehl-munich-2026/market/.venv/Scripts/python.exe",
      "args": ["-m", "ehl_market.server"],
      "env": {
        "EHL_MARKET_HOME": "C:/Users/<you>/ehl/ehl-munich-2026/market",
        "EHL_RESEARCH_HOME": "C:/Users/<you>/ehl/ehl-munich-2026/research"
      }
    }
  }
}
```

macOS: `.venv/bin/python`. Check whether Rowboat's `mcp.json` supports `cwd`; otherwise absolute paths.

## 7. Build order (demo Oct 11, time-boxed)

| Step | Scope | Box |
|---|---|---|
| 1 | Import package into `research/`; `data.py` loads processed CSVs; `start_run`, `list_clusters`, `get_comments`, `audit_log` | 1.5 h |
| 2 | Register in Rowboat, chat test with the G60_US prompt | 30 min |
| 3 | `save_signal` (stats from IDs), `drop/park_signal`, `study_lookup`, `search_options`, `attach_to_signal` | 2 h |
| 4 | `save_requirement`, `score_requirement`, `list_requirements`, `pm_action`, `reweight` | 2 h |
| 5 | `requirement_note`, `export_run`, Rowboat skill text | 1 h |
| 6 | `add_web_evidence` + web path; F70_GB run to show reuse | 1 h |
| 7 | `list_unclassified`/`assign_comments`, `recluster` | if time |

**Fallback for the stage:** pre-run G60_US through phase 6 the evening before; live in the demo:
PM review (approve / challenge / reweight) and notes appearing in the graph.

## 8. Fit with the team design (needs agreement)

- **New MCP server** `ehl-research`, **new folder** `research/`, optionally a new vault folder
  `Requirements/`: all are §12 contracts → **Contract change request** on the board; Flissel
  decides and assigns the owning WP.
- The repo is **public**. `comments.csv` is derived from `Dataset/` (already in the repo) and
  PII-masked, but residual names are possible (`manifest.json`: "LLM must still mask residual
  names"). Before committing `data/processed/` or `runs/`, check them or keep them gitignored and
  generate them on each PC.
- `prepare_data.py` needs `pdftotext` (poppler); on Windows this is an extra install. Alternative:
  commit the processed option files only.
- No sending or approving outside the local audit log (D7). Notes link only to fixed targets.

## 9. Tests

- Unit: stats from comment IDs match the package's counts (G60_US cluster sizes); unique-comment
  counting; priority formula and effort penalty; weights must sum to 1.0; reject needs a reason;
  edit bumps version and keeps the old one in the log; audit log only appends; unknown IDs rejected.
- Integration: stdio session runs phases 0→8 for G60_US with scripted agent inputs.
- Rowboat: demo prompt end to end; requirement notes appear linked in the graph.
