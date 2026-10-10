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
| `demo/example-data/Projects/` | P1–P3 (products) and R1–R3 (roadmaps), each with `## Info`, `## Key facts`, `## Connected to` |
| `demo/example-data/Topics/` | `Newsletter`, `Social Media`, `Email`, `Market Research` (+ 2–3 trend notes) |
| `demo/example-data/People/` | Team members who agreed (name + role only) |
| `demo/install.ps1` | Copy example data into `EHL_VAULT` (never overwrite existing notes); write `mcp.json` entries for `ehl-search` and `ehl-agents` from `demo/mcp.json.example` (merge, keep existing servers) |
| `demo/skill/` | EHL skill/instruction for the Rowboat agent (see §4) |
| `demo/DEMO.md` | Minute-by-minute demo script, prompts to type, fallback for each step |
| Dress rehearsal | Two full runs, one with Sales switched off; findings fed back to WP2–WP4 |

## 3. First task: freeze link targets (blocks WP2)

Publish the exact note names WP2 links to, as a table in this spec, then commit and tell the team:

| Link target | Example |
|---|---|
| Products | `Projects/P1 Route Planner`, `Projects/P2 …`, `Projects/P3 …` |
| Roadmaps | `Projects/R1 Rollout Route Planner`, … |
| Channels | `Topics/Newsletter`, `Topics/Social Media`, `Topics/Email` |
| Research | `Topics/Market Research` |
| Team | `People/<Name> (Team)` |

Also publish the **product keyword list** per product (used by WP2 to link companies to products).

## 4. EHL skill (agent instructions)

- To find customers by meaning, call `ehl-search.semantic_search` first; use grep only as fallback.
- To ask Sales, use `ehl-agents.sales_ask`; for brand/newsletter content, `brand_ask` /
  `content_design`.
- Never send, approve or schedule anything.
- File every result as `Content/<YYYY-MM-DD> <Title>.md` using the note template, linking the
  product, channel and every company used; images as http links.

## 5. Tests

- Script check: after `install.ps1` every `[[link]]` in example data resolves to an existing note.
- `mcp.json` merge keeps pre-existing servers (unit test on a temp file).
- Manual: graph view shows one connected cluster; skill prompt yields a `Content/` note.

## 6. Risks

| Risk | Fallback |
|---|---|
| Rowboat ignores the skill and greps | Name the tools explicitly in the demo prompt |
| Live step fails on stage | Pre-recorded result note + screenshot in `DEMO.md` |
