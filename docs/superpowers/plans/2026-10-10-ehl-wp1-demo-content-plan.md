# WP1 plan: Demo content, Rowboat setup, dress rehearsal

Owner: Peter (PedroLemonade). Spec: `docs/superpowers/specs/2026-10-10-ehl-wp1-demo-content-design.md`.
Parent spec §5.1 (note format) and §12 (contracts) apply to every note written here.

## Step groups

| # | Step group | Output | Done when |
|---|---|---|---|
| 1 | M1: freeze link targets and product keywords | WP1 spec §3, `demo/link-targets.json` | pushed, WP2 told on the board (**done 2026-10-10**) |
| 2 | Product and roadmap notes from `Dataset/` | `demo/dataset_to_notes.py` → `demo/example-data/Projects/` (F70, G60, G68, G70 + 3 roadmaps) | notes have `## Info`, `## Key facts`, `## Connected to`; only aggregated facts (study means, feedback counts per type and category, packages from option lists, volumes); no customer text with names (D8); F70 China volume shown as "no data" |
| 3 | Topic and team notes | `demo/example-data/Topics/` (Newsletter, Social Media, Email, Market Research + 2 to 3 trends), `demo/example-data/People/Peter (Team).md` | every link target from §3 exists as a note |
| 4 | Installer | `demo/install.py`, `demo/mcp.json.example`, `demo/pyproject.toml`, tests | copies notes into `EHL_VAULT` without overwriting; merges `ehl-search` into `mcp.json` keeping other servers; `--demo` adds `ehl-agents`; pytest green on Windows paths and macOS paths |
| 5 | EHL skill | `demo/skill/` | agent calls `ehl-search.semantic_search` first, never sends or schedules, files results as `Content/<date> <Title>.md` |
| 6 | Team guide | `demo/SETUP.md` | a team member gets from Rowboat dev mode to a filled test graph |
| 7 | Demo script | `demo/DEMO.md` | minute by minute flow (parent spec §10), prompts to type, fallback per step |
| 8 | Integration and rehearsal (M4, M5) | on the demo PC with the orchestrator | both MCP servers registered, two full runs, one with Sales off; findings on the board |

## Tests (spec §5)

- After `install.py`, every `[[link]]` in `demo/example-data/` resolves to a note.
- `install.py` without `--demo` never registers `ehl-agents`.
- `mcp.json` merge keeps existing servers (unit test on a temp file).
- Manual: graph view shows one connected cluster; a skill prompt yields a `Content/` note.

## Order and timing

Steps 2 and 3 first (WP2 and WP3 test against these notes), then 4, then 5 to 7.
Step 8 needs WP2 to WP4 and the demo PC, so it runs Sunday morning before the 12:00 deadline.
