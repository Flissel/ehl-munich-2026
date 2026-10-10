# WP1 – Demo Content, Rowboat Setup and Dress Rehearsal

**Branch:** `feat/ehl-demo-content` · **Folder:** `demo/` · **Parent spec:** `2026-10-10-rowboat-ehl-space-design.md` (§12 contracts)
**Status:** Draft awaiting approval

## 1. Goal

Rowboat on the demo PC is installed, configured and filled with example data, so the graph shows a
believable cluster before any live data arrives. WP1 also owns the demo script and the dress
rehearsal where all packages come together.

**Done when:** Rowboat Desktop on the demo PC shows the example notes as a connected graph
(products ↔ roadmaps ↔ topics ↔ team), both MCP servers are registered, the EHL skill is active, and
the demo flow (parent spec §10) has run twice end to end.

## 2. Scope

| Item | Content |
|---|---|
| `demo/example-data/Projects/` | Machines F70, G60, G68, G70 from `Dataset/` (option lists, feedback, sales volumes → `## Info`, `## Key facts`, `## Connected to`) and their roadmaps if derivable; a small converter `demo/dataset_to_notes.py` is fine. Customer studies/feedback only as aggregated facts – no customer individuals (spec D8) |
| `demo/example-data/Topics/` | `Newsletter`, `Social Media`, `Email`, `Market Research` (+ 2–3 trend notes) |
| `demo/example-data/People/` | Team members who agreed (name + role only) |
| `demo/install.py` | Python, runs on **every team PC, Windows and macOS** (spec D11): copy repo notes into `EHL_VAULT` (never overwrite existing notes) and merge the `ehl-search` entry into `mcp.json` (keep existing servers). With `--demo` (demo PC only): additionally register `ehl-agents` and start the bridge against the real sources. Template: `demo/mcp.json.example` |
| `demo/SETUP.md` | Short guide for team members: set up Rowboat in dev mode (see `SETUP.md` on `main`), run `install.py`, start Qdrant + indexer, run `bridge --fake` for fake companies |
| `demo/skill/` | EHL skill/instruction for the Rowboat agent (see §4) |
| `demo/DEMO.md` | Minute-by-minute demo script, prompts to type, fallback for each step |
| Dress rehearsal | Two full runs, one with Sales switched off; findings fed back to WP2–WP4 |

## 3. First task: freeze link targets (blocks WP2)

Publish the exact note names WP2 links to, as a table in this spec, then commit and tell the team.

**Frozen 2026-10-10 by WP1 (Peter).** Machine-readable copy: `demo/link-targets.json`.
Links are full vault paths without `.md`, e.g. `[[Projects/G60]]`.

| Link target | Exact note names | Basis |
|---|---|---|
| Products | `Projects/F70`, `Projects/G60`, `Projects/G68`, `Projects/G70` | confirmed: the four derivatives in `Dataset/` |
| Roadmaps | `Projects/F70 Roadmap`, `Projects/G60 Roadmap`, `Projects/G70 Roadmap` | `sales_volumes.xlsx` has volumes 2024, 2025 and a 2030 plan per region. G60 and G68 share one sheet, so `Projects/G60 Roadmap` covers both and links both products; there is no separate G68 roadmap |
| Channels | `Topics/Newsletter`, `Topics/Social Media`, `Topics/Email` | confirmed |
| Research | `Topics/Market Research` | confirmed |
| Team | `People/<Display name> (Team)`, so far `People/Peter (Team)` | pattern frozen; further names only after the person agrees (spec D8), announced on the board |

**Product keywords** (WP2 links a company to a product when one of these appears; case-insensitive,
whole words). Generic words like "BMW", "Limousine" or a bare "Series" link nothing.

| Product | Model | Keywords |
|---|---|---|
| `Projects/F70` | BMW 1 Series | `F70`, `1 Series`, `1er`, `BMW 1`, `116`, `118d`, `120`, `120d`, `123 xDrive`, `M135`, `M135 xDrive` |
| `Projects/G60` | BMW 5 Series (sedan) | `G60`, `5 Series`, `5er`, `BMW 5`, `520i`, `520d`, `520d xDrive`, `530e`, `530e xDrive`, `540d xDrive`, `550e xDrive`, `i5`, `i5 eDrive40`, `i5 xDrive40`, `i5 M60` |
| `Projects/G68` | BMW 5 Series long wheelbase (China) | `G68`, `5 Series G68`, `5 Series Long Wheelbase`, `5 Series LWB` |
| `Projects/G70` | BMW 7 Series | `G70`, `7 Series`, `7er`, `BMW 7`, `740 xDrive`, `i7`, `i7 eDrive50`, `i7 xDrive60`, `i7 M70`, `i7 M70 xDrive` |

Rules for overlaps: the bare numbers (`116`, `120`) only count together with "BMW" or a series word
in the same note. `5 Series`/`5er`/`i5` go to G60; G68 only on its own keywords or when the company is
in China and names the 5 Series. Model names come from the option lists (German price lists, July
2026), the customer studies and the feedback files; the G68 long-wheelbase keywords are general
knowledge, not from `Dataset/`.

## 4. EHL skill (agent instructions)

- To find customers by meaning, call `ehl-search.semantic_search` first; use grep only as fallback.
- To ask Sales, use `ehl-agents.sales_ask`; for brand/newsletter content, `brand_ask` /
  `content_design`.
- Never send, approve or schedule anything.
- File every result as `Content/<YYYY-MM-DD> <Title>.md` using the note template, linking the
  product, channel and every company used; images as http links.

## 5. Tests

- Script check: after `install.py` every `[[link]]` in example data resolves to an existing note.
- `install.py` without `--demo` never registers `ehl-agents`; tested on a second team PC.
- `mcp.json` merge keeps pre-existing servers (unit test on a temp file).
- Manual: graph view shows one connected cluster; skill prompt yields a `Content/` note.

## 6. Risks

| Risk | Fallback |
|---|---|
| Rowboat ignores the skill and greps | Name the tools explicitly in the demo prompt |
| Live step fails on stage | Pre-recorded result note + screenshot in `DEMO.md` |
