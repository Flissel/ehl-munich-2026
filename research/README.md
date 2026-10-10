# BMW Customer Requirements Agent — starter package

Everything an AI agent (Claude) needs to go from **raw customer evidence → prioritized requirements → PM decision → audit trail**.

```
AGENT.md                     ← the agent's instructions (system prompt / CLAUDE.md / Project instructions)
config/G60_US.yaml           ← demo run: BMW 5 Series, USA (richest data: 4 sources, ICE/PHEV/BEV, US study)
config/F70_GB.yaml           ← second run to prove it is not a one-off
reference/theme_mapping.csv  ← 226 BMW components → 12 themes + scope
reference/issue_mapping.csv  ← 84 BMW issue codes → signal type
reference/study_mapping.csv  ← 139 study items → theme
reference/data_dictionary.md ← every file and column
reference/schemas.md         ← Signal / WebEvidence / Requirement / AuditEvent
scripts/prepare_data.py      ← clean + merge all raw files (PII masking, de-duplication, study + options parsing)
scripts/cluster_signals.py   ← reproducible pre-clustering per theme
data/raw/                    ← put the hackathon files here
```

## Run it

```bash
pip install pandas openpyxl scikit-learn pyyaml        # + poppler-utils for pdftotext
python scripts/prepare_data.py --raw data/raw --out data/processed
python scripts/cluster_signals.py --config config/G60_US.yaml --out runs/G60_US
```
Then let the agent continue from Phase 1 in `AGENT.md` (naming clusters, study severity, option check,
web research, requirements, scoring, PM review).

## Three ways to use it with Claude

1. **Claude Code** (best for the hackathon): put this folder in your repo, rename `AGENT.md` to `CLAUDE.md`
   (or reference it from there), and say: *"Run the agent for config/G60_US.yaml."* Claude can run the
   scripts, search the web and write the output files and audit log itself.
2. **Claude Agent SDK / API**: use `AGENT.md` as the system prompt. Give the agent tools for
   `run_python` (or bash), `web_search`, `web_fetch`, `read_file`, `write_file`, and an
   `ask_pm` tool that pauses for the human. Your UI shows requirement cards and calls the agent with PM actions.
3. **Claude Project (claude.ai)**: paste `AGENT.md` into the Project instructions and upload
   `data/processed/*` + `reference/*` as knowledge. Good for testing prompts; no scripts run there.

## Adapting to another vehicle / market
Copy a config, change `derivative`, `market`, `filter`, `studies`, `sales`, `option_list`, `competitors`.
New derivative data → drop the files into `data/raw` with the same naming pattern and rerun `prepare_data.py`.
New BMW components → add rows to `theme_mapping.csv` (unmapped ones show up as `UNCLASSIFIED`).

## Known data caveats (also written to manifest.json)
- Sources A–D are anonymised; types are inferred from wording.
- Raw rows ≠ comments (one row per tag). Always count unique `comment_id`.
- ~12 % of comments have no BMW tag → LLM classification, logged as `ai_assigned`.
- Option lists are the German market; US/UK availability can differ.
- F70 China 2024 volume is a broken formula → missing.
- B, C, D are US-only → outside the US only Source A exists.
