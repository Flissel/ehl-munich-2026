# WORKBOARD – EHL Munich 2026 Rowboat Live Demo

Single source of truth for all sessions. Lives on the **`board` branch** (the only unprotected
shared branch); update it as described in `CLAUDE.md` on `main`. Fresh PC: `SETUP.md` on `main`.
**Demo:** 2026-10-11, 6-min pitch (3–4 min live demo). **Parent spec:**
`docs/superpowers/specs/2026-10-10-rowboat-ehl-space-design.md` (on every `feat/ehl-*` branch).
**Orchestrator:** Flissel – reviews and merges all PRs into `main` (this repo) and `ehl` (fork `Flissel/rowboat`).
**Team (GitHub):** syed-rayyanadil · yunes-mahan · Paolabeiia · PedroLemonade – assign yourself a WP by claiming its row.

## Work packages

| WP | Branch | Owner (person / session) | Status | Plan | PR | Now doing | Blockers |
|---|---|---|---|---|---|---|---|
| WP1 Demo content & setup | `feat/ehl-demo-content` | Peter (PedroLemonade) / cloud Claude session · 2026-10-10 17:16 | in progress | [plan](https://github.com/Flissel/ehl-munich-2026/blob/feat/ehl-demo-content/docs/superpowers/plans/2026-10-10-ehl-wp1-demo-content-plan.md) | [#4](https://github.com/Flissel/ehl-munich-2026/pull/4) (draft) | M1 done; steps 2+3: 29 notes from `Dataset/` pushed (f234854); next: `People/Peter (Team)`, installer (step 4) | own fork `PedroLemonade/rowboat` not created yet (only needed for Rowboat changes) |
| WP2 Bridge | `feat/ehl-bridge` | – | open | – | – | – | waits for WP1 link targets (can start with sales-mcp access check) |
| WP3 Semantic search | `feat/ehl-search` | – | open | – | – | – | – |
| WP4 Agent chat | `feat/ehl-agent-chat` | – | open | – | – | – | – |

Status values: `open` · `claimed` · `planning` · `in progress` · `blocked` · `review` · `done`.
A claim is active if the row was updated less than 2 h ago.

## Milestones

| # | Milestone | Owner | Status |
|---|---|---|---|
| M1 | Link targets + product keywords frozen (spec §12) | WP1 | done 2026-10-10 (WP1 spec §3, `demo/link-targets.json`) |
| M2 | Time-boxed first tasks done (sales-mcp access, embedding model, OpenClaw chat endpoint) | WP2 / WP3 / WP4 | open |
| M3 | Each WP works against test vault / fakes, tests green | all | open |
| M4 | Integration on the demo PC (vault, Qdrant, both MCP servers in `mcp.json`) | WP1 | open |
| M5 | Dress rehearsal ×2 (once with Sales off) | WP1 | open |

## Frozen contracts (copy of decisions taken; see parent spec §12)

| Contract | Value | State |
|---|---|---|
| Vault path | `EHL_VAULT`, default `~/.rowboat/knowledge` | frozen |
| Qdrant | `127.0.0.1:6333`, collection `ehl_notes` | frozen |
| MCP servers | `ehl-search` (WP3), `ehl-agents` (WP4), stdio | frozen |
| Products in the graph | The machines from `Dataset/`: F70, G60, G68, G70 (test data; replaces invented P1–P3, spec D9) | frozen |
| PC roles (spec D11) | Every team member runs Rowboat (dev mode, fork `ehl`) locally: WP1 installer (repo notes + `ehl-search`) and `bridge --fake` (fake companies). Demo PC only: installer `--demo` (+ `ehl-agents`, bridge on real sources). Real company notes never in git | frozen |
| Rowboat source (replaces D1) | Team fork `Flissel/rowboat`, branch `ehl` (pinned `72e9d8c`), run with `npm run dev`; each member forks `Flissel/rowboat` and PRs `ehl/<wp>-<topic>` from their fork into `ehl` | frozen |
| Link targets (exact note names for products, roadmaps, topics, team) | `Projects/F70`, `Projects/G60`, `Projects/G68`, `Projects/G70` · roadmaps `Projects/F70 Roadmap`, `Projects/G60 Roadmap` (covers G60 + G68), `Projects/G70 Roadmap` · `Topics/Newsletter`, `Topics/Social Media`, `Topics/Email`, `Topics/Market Research` · `People/<Display name> (Team)`; keywords per product in WP1 spec §3 | frozen (WP1, 2026-10-10) |

## Handoffs

| From → To | What | State |
|---|---|---|
| WP1 → WP2 | Exact link-target names + product keyword list (for F70/G60/G68/G70) | **delivered**: WP1 spec §3 + `demo/link-targets.json` on `feat/ehl-demo-content` |
| WP3 → WP1 | `mcp.json` entry for `ehl-search` | open |
| WP4 → WP1 | `mcp.json` entry for `ehl-agents` | open |
| WP2 → all | `bridge/fixtures/` fake companies + `bridge --fake` (needed on every team PC – deliver early) | open |
| WP1 → all | `demo/install.py` (Windows + macOS, replaces `install.ps1`) + `demo/SETUP.md` for team PCs | open |

## Open questions

| # | Question | For | State |
|---|---|---|---|
| Q1 | `Dataset/` landed on `main` (F70, G60, G68, G70: option lists, customer studies, feedback, sales volumes). Should the products in the graph be these machines instead of invented P1–P3 (changes spec D9)? | user / WP1 | **decided 2026-10-10: yes – `Dataset/` is the test data; products = F70, G60, G68, G70.** WP1 builds product notes (and roadmaps if derivable) from it; customer studies/feedback may feed notes too, privacy rules (spec D8) apply. |

## Contract change requests

| # | Change | Requested by | Agreed by | State |
|---|---|---|---|---|
| – | – | – | – | – |

## Log (newest first)
- 2026-10-10 17:21: WP1 pitch showcase `demo/showcase/index.html` on `feat/ehl-demo-content`: data basis, customer voice, workflow, requirement records, audit trail, demo steps, graph and top 10 at the end. Real numbers from `Dataset/` via `fill_data.py`; open items are marked placeholders (counter in the header). Fallback for live steps.
- 2026-10-10 17:16: WP1 steps 2 and 3 (topics) pushed by Peter's second Claude session: `demo/dataset_to_notes.py` writes 29 notes (F70, G60, G68, G70, 3 roadmaps, fixed topics, 11 customer themes, 4 markets, 3 BMW trends). All frozen link targets exist; WP2 and WP3 can test against `demo/example-data/` now. Other WP1 session: please pull before step 4.
- 2026-10-10 17:25: WP1 (Peter): M1 done, link targets + product keywords frozen (WP1 spec §3, `demo/link-targets.json`); WP2 can start linking. Draft PR #4 with the WP1 plan.
- 2026-10-10 17:05: WP1 claimed by Peter (PedroLemonade). Setup via SETUP.md quick path in a cloud Claude session; next: read parent + WP1 spec, then plan and M1 link targets.
- 2026-10-10 – Team PC setup: `scripts/setup_pc.py` + requirements in `SETUP.md` (PR #3, awaiting merge). Rowboat dev mode verified on the orchestrator PC (Windows). Requirements: **Node 22 LTS or 24.15+** (24.4 crashes `pnpm install`), pnpm 10, Python 3.12, Docker, ~5 GB disk, own LLM API key. `dev:sandbox` broken on Windows → `npm run dev` + `ROWBOAT_WORKDIR`.

- 2026-10-10 – Rowboat changes now via **personal forks**: fork `Flissel/rowboat`, push `ehl/<wp>-<topic>` to your fork, PR into `Flissel/rowboat:ehl` (CLAUDE.md + SETUP.md updated, PR #2 merged). Open for review: PR #1 (Paolabeiia) – data pipeline plan + deliverables for the BMW challenge.
- 2026-10-10 – Orchestration set up: `main` PR-only (review by Flissel, CODEOWNERS); board moved to `board` branch; `SETUP.md` for team PCs. Rowboat now runs **from source in dev mode** (fork `Flissel/rowboat`, branch `ehl` pinned to `72e9d8c`; changes via `ehl/<wp>-<topic>` + PR) – replaces spec D1. Installer scripts must run on Windows and macOS (WP1: `install.ps1` → cross-platform).
- 2026-10-10 – Decided (spec D11): everyone runs Rowboat on their own PC with repo notes + fake companies + local search; Sales/Marketing agents and real data only on the demo PC. WP1/WP2 specs updated.
- 2026-10-10 – Q1 decided: `Dataset/` is the test data; products = F70, G60, G68, G70 (spec D9 updated on `feat/rowboat-ehl-space` and in the WP1 spec).
- 2026-10-10 – board created; WP specs on their branches; all WPs open.
