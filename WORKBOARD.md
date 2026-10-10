# WORKBOARD – EHL Munich 2026 Rowboat Live Demo

Single source of truth for all sessions. Lives on `main`; update it as described in `CLAUDE.md`.
**Demo:** 2026-10-11, 6-min pitch (3–4 min live demo). **Parent spec:**
`docs/superpowers/specs/2026-10-10-rowboat-ehl-space-design.md` (on every `feat/ehl-*` branch).

## Work packages

| WP | Branch | Owner (person / session) | Status | Plan | Now doing | Blockers |
|---|---|---|---|---|---|---|
| WP1 Demo content & setup | `feat/ehl-demo-content` | – | open | – | – | – |
| WP2 Bridge | `feat/ehl-bridge` | – | open | – | – | waits for WP1 link targets (can start with sales-mcp access check) |
| WP3 Semantic search | `feat/ehl-search` | – | open | – | – | – |
| WP4 Agent chat | `feat/ehl-agent-chat` | – | open | – | – | – |

Status values: `open` · `claimed` · `planning` · `in progress` · `blocked` · `review` · `done`.
A claim is active if the row was updated less than 2 h ago.

## Milestones

| # | Milestone | Owner | Status |
|---|---|---|---|
| M1 | Link targets + product keywords frozen (spec §12) | WP1 | open |
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
| Link targets (exact note names for products, roadmaps, topics, team) | – | **pending WP1 (M1)** |

## Handoffs

| From → To | What | State |
|---|---|---|
| WP1 → WP2 | Exact link-target names + product keyword list (for F70/G60/G68/G70) | open |
| WP3 → WP1 | `mcp.json` entry for `ehl-search` | open |
| WP4 → WP1 | `mcp.json` entry for `ehl-agents` | open |

## Open questions

| # | Question | For | State |
|---|---|---|---|
| Q1 | `Dataset/` landed on `main` (F70, G60, G68, G70: option lists, customer studies, feedback, sales volumes). Should the products in the graph be these machines instead of invented P1–P3 (changes spec D9)? | user / WP1 | **decided 2026-10-10: yes – `Dataset/` is the test data; products = F70, G60, G68, G70.** WP1 builds product notes (and roadmaps if derivable) from it; customer studies/feedback may feed notes too, privacy rules (spec D8) apply. |

## Contract change requests

| # | Change | Requested by | Agreed by | State |
|---|---|---|---|---|
| – | – | – | – | – |

## Log (newest first)

- 2026-10-10 – Q1 decided: `Dataset/` is the test data; products = F70, G60, G68, G70 (spec D9 updated on `feat/rowboat-ehl-space` and in the WP1 spec).
- 2026-10-10 – board created; WP specs on their branches; all WPs open.
