# Rowboat EHL Live Demo: Sales and Marketing as a Knowledge Graph

**Date:** 2026-10-10 · **Occasion:** EHL Munich 2026 Grand Finale (demo on Oct 11, 6-min pitch)
**Status:** Draft awaiting approval
**Replaces:** the earlier version of this file ("Rowboat Space EHL", Harbor-based, commit `2b871d0`)

## 1. Goal

Rowboat is the product we show. Sales-Claw and Marketing are **data sources and worker agents**
behind it. Their data lands in Rowboat as Markdown notes, so Rowboat's own knowledge graph shows
the cluster (companies ↔ products ↔ channels ↔ content). A Rowboat agent works on an intersection
of that cluster (e.g. machine F70 × newsletter), asks the Sales and Marketing agents via chat, and
the result appears as a new, linked note in the graph.

**Demo criterion:**
1. A contact created live in Sales-Claw appears as (part of) an organization note in Rowboat within
   ~60 s, and the graph grows visibly.
2. Asked "Create a newsletter about the F70 for all interested customers", the Rowboat agent finds the
   matching companies, has Marketing draft text and image, and files the result as
   `Content/…` note linked to product, channel and companies. Nothing is sent.

## 2. Current state (explored on 2026-10-10)

| System | Where | Interface | State |
|---|---|---|---|
| Sales-Claw (`Flissel/sales-claw`) | Mini PC `vibemind-offload-1`, Tailscale `100.67.177.45` | OpenClaw gateway `:18894` (loopback, operated via WhatsApp); sales-mcp `:8765` (streamable-http, path not `/mcp` – to be found); UI `:8791` | running |
| Marketing (`Flissel/vibemind-os`, `spaces/marketing`) | this PC | API `127.0.0.1:5510` (`/api/health` ok); MCP sidecar `:8130` (27 tools); brand chat `POST /api/pult/marke/chat`; editor chat `POST /api/pult/inhalte/{id}/chat` (both async via the chat worker, operated from a page in the Sales UI) | running |
| Rowboat Desktop (upstream `rowboatlabs/rowboat`, `apps/x`, checked at `72e9d8c`, 2026-10-09) | demo PC (this PC) | official installer | to be installed |

Facts about Rowboat Desktop that shape this design (verified in upstream code at `72e9d8c`):

- Knowledge vault is `~/.rowboat/knowledge/` (override: `ROWBOAT_WORKDIR`); only `.md` files count.
- Graph edges come **only** from `[[Folder/Name]]` wikilinks to existing notes; the top-level
  folder sets the node's colour group; `Meetings/` is excluded from the graph.
- Note types and template: `People`, `Organizations`, `Projects`, `Topics`, `Meetings`; each note is
  `# Title`, `## Info` with `**Key:** value` lines, then `## Connected to`, `## Activity`,
  `## Key facts`, `## Open items` (`packages/core/src/knowledge/note_system.ts`).
- Search is keyword-only (grep); there are no embeddings in the desktop app.
- Harbor Space files are **not** written into the vault, so they would not appear in the graph.
- User MCP servers are configured in `~/.rowboat/config/mcp.json` (`{"mcpServers": {...}}`,
  stdio or http) and usable by the agent.
- Markdown images render reliably from http(s) URLs; relative vault paths probably do not.

## 3. Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Rowboat Desktop **as it is** (no fork, no code changes); our work is data, MCP tools and an agent skill | Least risk by tomorrow; official installer |
| D2 | **Live data and agents on the demo PC only**: the bridge writes real notes straight into its `~/.rowboat/knowledge/`. No Harbor, GoTrue or Funnel | The graph only exists for vault notes; drops the riskiest part of the old design |
| D3 | Notes follow Rowboat's own template plus YAML frontmatter for origin (`source`, ids, `managed_by`) | Graph and entity index work out of the box; frontmatter serves as search filter |
| D4 | Extra **semantic search** via local Qdrant + MCP, as a separable add-on | "RAG" from the sketch; the demo still works without it |
| D5 | Embeddings computed **locally** (fastembed, multilingual model) | Data stays on the PC; content is German |
| D6 | Rowboat talks to the **Sales and Marketing agents via chat** (MCP wrapper tools) rather than their raw tool sets | Agent-to-agent is the story; each agent keeps its own rules |
| D7 | No sending and no approving from Rowboat: the raw Marketing MCP (incl. `versand_beauftragen`) is not exposed; the chat path must not trigger sends or approvals | Approval gate stays with the human (WhatsApp / UI) |
| D8 | Real **companies** from Sales-Claw; **people** only for team members who agreed. No customer individuals, no email addresses or phone numbers; leads marked private are skipped | Projector + embeddings; data minimisation (GDPR) |
| D9 | Products are the machines **F70, G60, G68, G70** from the test dataset `Dataset/` (option lists, customer studies, feedback, sales volumes); product and roadmap notes are derived from it by WP1 | The team's test data; neither Sales nor Marketing has products (decided 2026-10-10, board Q1) |
| D10 | The bridge reads Sales/Marketing **read-only** through their interfaces and only ever writes files it owns (`managed_by: ehl-bridge`) | Never clobbers hand-written or agent-written notes |
| D11 | **Every team member runs Rowboat Desktop on their own PC** for development: repo data (products from `Dataset/`, topics, team), **fake companies** from the bridge's fixtures, and local `ehl-search` + Qdrant. Sales/Marketing agents (`ehl-agents`) and real company data only on the demo PC. Real company notes are never committed to git | Everyone can test in their own graph; Marketing API (loopback) and OpenClaw (Tailscale) are wired once; real data stays on one machine (decided 2026-10-10) |

## 4. Architecture

```
 Sales-Claw (mini PC)              Marketing (this PC)
  OpenClaw gateway · sales-mcp      API :5510 · chat worker
        │ read / chat                   │ read / chat
        ▼                               ▼
 ┌──────────── bridge (every 60 s) ─────────────┐   ehl-agents (MCP): sales_ask ·
 │ companies, campaigns, content → Markdown     │     brand_ask · content_design
 └───────────────┬──────────────────────────────┘          ▲ MCP
                 ▼ writes (managed_by: ehl-bridge)          │
   ~/.rowboat/knowledge/  (demo PC)                         │
   Organizations/  People/ (team)  Projects/ (P, R)         │
   Topics/ (channels, trends)  Content/                     │
                 │ watched                                  │
                 ▼                                          │
   indexer ──upserts──► Qdrant ◄──query── ehl-search (MCP): semantic_search
                                                 ▲ MCP      │
                                                 │          │
   Rowboat Desktop + agent (+ EHL skill) ────────┴──────────┘
       reads vault, graph from [[links]]
```

Everything runs on the demo PC except Sales-Claw, which is reached over Tailscale. All local
services bind to `127.0.0.1`.

## 5. Components

### 5.1 Note model

| Folder | Content | Written by |
|---|---|---|
| `Organizations/` | One note per company from Sales-Claw (leads grouped by company): industry, website, pipeline stage, owner (team member), interest in products, recent activity | bridge |
| `People/` | Team members only | example data |
| `Projects/` | Machines F70, G60, G68, G70 and their roadmaps, derived from `Dataset/` | WP1 (from `Dataset/`) |
| `Topics/` | Channels (Newsletter, Social Media, Email), market research / trends | example data |
| `Content/` | Marketing campaigns and drafts (bridge); results of demo part 2 (agent) | bridge / agent |

Example (`Organizations/Muster GmbH.md`):

```markdown
---
source: sales-claw
sales_ids: [L-0412, L-0419]
relationship: prospect
managed_by: ehl-bridge
---
# Muster GmbH

## Info
**Industry:** Logistics
**Website:** https://muster.example
**Pipeline stage:** Interested
**Owner:** [[People/Anna (Team)]]

## Connected to
- [[Projects/F70]] – interest from first call
- [[Topics/Newsletter]]

## Activity
- 2026-10-08 – stage: first contact → interested
```

Rules:
- Links always use the full path `[[Folder/Name]]`; the bridge only links to notes that exist or that
  it writes in the same run.
- Images only as http(s) links (e.g. Marketing API URLs).
- Files without `managed_by: ehl-bridge` are never written by the bridge.
- Field labels and section names follow Rowboat's template; values may be German.

### 5.2 `bridge/` – Sales/Marketing → vault

Python 3.12, runs on the demo PC.

| Module | Responsibility |
|---|---|
| `sources/sales.py` | Companies, leads, pipeline stages via sales-mcp (read-only); skips private leads; drops email/phone |
| `sources/marketing.py` | Campaigns and content of all tenants via the Marketing API |
| `model.py` | Neutral types (`Organization`, `Content`, `Activity`) |
| `render.py` | Pure functions: model → Markdown note |
| `vault.py` | Write a note only if owned by the bridge and content hash changed; never touch other files |
| `run.py` | Loop every `INTERVAL_S` (default 60): read → render → write changes |

### 5.3 `indexer/` – vault → Qdrant

Watches `~/.rowboat/knowledge/` (full pass on start, then changed files only). One point per note:
title, Info fields and body as text; frontmatter, folder and outgoing links as payload for filters.
Deleted notes are removed from the collection. Local Qdrant in Docker on `127.0.0.1`.

The indexer ships with its own MCP server `ehl-search` exposing
`semantic_search(query, folder?, limit?)` → note paths + snippets.

### 5.4 `agents-mcp/` – chat tools for the Rowboat agent

MCP server `ehl-agents`, registered in `~/.rowboat/config/mcp.json`:

| Tool | Calls | Notes |
|---|---|---|
| `sales_ask(text)` | Sales agent (the one behind WhatsApp) via the OpenClaw gateway's OpenAI-compatible chat endpoint over Tailscale | Endpoint must be enabled in `openclaw.json`; see §8 |
| `brand_ask(text)` | Brand agent: `POST /api/pult/marke/chat`, then poll for the answer | async, with timeout |
| `content_design(content_id, text)` | Editor agent for a draft: `POST /api/pult/inhalte/{id}/chat`, then poll | async, with timeout |

### 5.5 `example-data/` and agent skill

- Hand-written notes for `Projects/`, `Topics/`, `People/` (team), copied into the vault once.
- A Rowboat skill/instruction "EHL": use `semantic_search` to find customers, the chat tools to produce
  content, and file every result as a `Content/` note linked to product, channel and companies.

## 6. Error handling

| Case | Behaviour |
|---|---|
| Source unreachable | Its notes stay unchanged; warning logged; retried next run |
| Single malformed record | Skipped and logged; the rest is written |
| Qdrant unreachable | `semantic_search` returns a clear error; the agent falls back to grep search |
| Chat tool gets no answer within its timeout | Returns "no answer within N s" instead of hanging; on stage we trigger the same task in the Sales UI |
| Invalid credentials (401/403) | Clear error, no silent retry loop |

Logging via Python's `logging` module, one logger per module, no `print`.

## 7. Security and privacy

- Secrets (Marketing keys, OpenClaw token) only in `.env` files excluded via `.gitignore`;
  templates as `.env.example`.
- No email addresses, phone numbers or customer individuals in the vault or in Qdrant (D8).
- No send/approve capability reachable from Rowboat (D7).
- Changing `openclaw.json` on the mini PC is a machine-wide change: claim it in the coordination
  log first.

## 8. Risks and fallback

| Risk | Check | Fallback |
|---|---|---|
| OpenClaw `2026.7.1` has no OpenAI-compatible chat endpoint, or a non-WhatsApp caller gets the wrong rights | First plan step, time-boxed | Bridge data only for Sales; the demo shows chat with Marketing only |
| sales-mcp path/auth unknown (`/mcp` returns 404) | Find the mount path when building `sources/sales.py` | Read-only access via the existing sales-claw configuration |
| Marketing chats are async and slow on stage | Measure in the dress rehearsal | Pre-generated draft; trigger in Sales UI |
| Rowboat agent prefers grep over our MCP tools | Skill instruction; dress rehearsal | Ask explicitly in the prompt |
| Images not shown in notes | Test one note with an http image early | Link instead of embed |

**Order:** Sales chat check (time-boxed) → note model + example data → bridge → indexer + MCP →
skill → dress rehearsal.

## 9. Tests

- **Unit (pytest):** render (umlauts, empty lists, links); bridge never overwrites files without
  `managed_by`; private leads and contact details absent; unchanged content → no write.
- **Integration:** bridge with fake sources into a test vault, indexer over it, `semantic_search`
  finds the expected company; chat wrappers against the real Marketing API.
- **Dress rehearsal:** full demo twice on the demo PC, once with Sales switched off.

## 10. Demo flow (3–4 min within the 6-min pitch)

1. Rowboat open on the graph view (companies, products, channels).
2. Create a contact live in Sales-Claw → the organization note appears/updates, the graph grows (~1 min).
3. Ask the Rowboat agent: "Create a newsletter about the F70 for all interested customers."
4. The agent finds companies (semantic search / Sales chat), has Marketing draft text and image,
   and files `Content/…` linked to F70, Newsletter and the companies; the new node appears (2–3 min).

## 11. Out of scope

- Harbor / Spaces / Funnel; real company data or agent access on team PCs (D11; later possible via folder sync).
- Sending or approving from Rowboat.
- Customer individuals as notes.
- Changes to Rowboat's code; the Rowboat fork in `vibemind-os/spaces/rowboat`.

## 12. Work split and shared contracts

Four work packages, each on its own branch with its own spec, each owning one top-level folder so
branches merge without conflicts:

| # | Branch | Spec | Folder | Owns |
|---|---|---|---|---|
| WP1 | `feat/ehl-demo-content` | `2026-10-10-ehl-wp1-demo-content-design.md` | `demo/` | Product notes from `Dataset/`, example data (topics, team), EHL skill, Rowboat setup (`mcp.json`), demo script, dress rehearsal |
| WP2 | `feat/ehl-bridge` | `2026-10-10-ehl-wp2-bridge-design.md` | `bridge/` | Sales/Marketing → `Organizations/`, `Content/` notes |
| WP3 | `feat/ehl-search` | `2026-10-10-ehl-wp3-search-design.md` | `search/` | Qdrant, indexer, MCP server `ehl-search` |
| WP4 | `feat/ehl-agent-chat` | `2026-10-10-ehl-wp4-agent-chat-design.md` | `agents-mcp/` | OpenClaw check, MCP server `ehl-agents` (chat tools) |

**Shared contracts** (changes only by agreement of all owners, recorded here):

| Contract | Value |
|---|---|
| Vault path | env `EHL_VAULT`, default `~/.rowboat/knowledge` |
| Note format | §5.1 (template, full-path links, `managed_by: ehl-bridge` ownership, http images only) |
| Folder ownership in the vault | `Organizations/` and bridge-written `Content/` notes: WP2 · `Projects/`, `Topics/`, `People/`: WP1 · agent-written `Content/` notes: the Rowboat agent (no `managed_by`) |
| Fixed link targets | `Topics/Newsletter`, `Topics/Social Media`, `Topics/Email`, `Topics/Market Research`, `Projects/F70`, `Projects/G60`, `Projects/G68`, `Projects/G70` (exact names incl. roadmaps defined by WP1 first, then frozen) |
| Qdrant | `127.0.0.1:6333`, collection `ehl_notes` |
| MCP servers | `ehl-search` (WP3), `ehl-agents` (WP4); stdio; `mcp.json` entries collected by WP1 |
| Python | 3.12, own `pyproject.toml` per folder, pytest, `logging` (no `print`), secrets in `.env` + `.env.example` |
| PC roles (D11) | **Team PC:** `demo/install.ps1` → repo notes + `ehl-search`; `bridge --fake` writes fake companies from `bridge/fixtures/`. **Demo PC:** `demo/install.ps1 -Demo` additionally registers `ehl-agents` and runs the bridge against the real sources |
| Fake companies | `bridge/fixtures/` (WP2): 8–10 invented companies with stages, owners and product interest in F70/G60/G68/G70; same note format as real ones (`managed_by: ehl-bridge`, `source: fixture`) |

**Dependencies:** WP1 publishes the link-target names first (needed by WP2). WP2–WP4 develop
against a test vault and fakes, so none blocks another; integration happens in WP1's dress rehearsal.

## 13. Prior work and licences

| Part | Origin | Licence |
|---|---|---|
| Sales-Claw | `github.com/Flissel/sales-claw` (before the hackathon) | own |
| Marketing | `github.com/Flissel/vibemind-os`, `spaces/marketing` (before the hackathon) | own |
| Rowboat Desktop | `github.com/rowboatlabs/rowboat` | Apache 2.0 |
| Qdrant, mcp-server-qdrant, fastembed | upstream | Apache 2.0 |
| **New at the hackathon** | `bridge/`, `indexer/`, `agents-mcp/`, `example-data/`, EHL skill | own |
