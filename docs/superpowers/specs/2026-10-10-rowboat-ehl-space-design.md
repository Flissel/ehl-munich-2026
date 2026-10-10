# Rowboat Space "EHL": Sales and Marketing Data on the Team's PCs

**Date:** 2026-10-10 · **Occasion:** EHL Munich 2026 Grand Finale (demo on Oct 11, 6-min pitch)
**Status:** Draft awaiting approval

## 1. Goal

Rowboat becomes the team's shared project overview. Data from the existing deployments
(Sales-Claw, Marketing) flows automatically into a shared Rowboat Space "EHL". Every member
sees it in the Rowboat desktop app on their own PC.

**Success criterion:** A member installs *only* the official Rowboat desktop app, opens an
invite link, signs in with email + password and sees the Space "EHL" with overview, contacts,
send schedule, campaigns and feed. No other software (no Tailscale, no Docker) on the member's PC.

**Demo criterion:** A contact created in Sales-Claw, or an approval granted there, appears within
~60 s in the feed and in the Space's files on a second machine outside the home network.

## 2. Current state (explored on 2026-10-10)

| System | Where | Access | State |
|---|---|---|---|
| Sales-Claw (`Flissel/sales-claw`, branch `feat/stufe-1-fundament`) | Mini PC `vibemind-offload-1`, Tailscale `100.67.177.45` | sales-mcp `:8765` (MCP streamable-http), UI `:8791` | running |
| Marketing (`Flissel/vibemind-os`, `spaces/marketing`) | this PC | API `127.0.0.1:5510`, MCP sidecar `:8130` | running, `/api/health` ok |
| Rowboat Desktop (upstream `rowboatlabs/rowboat`, `apps/x`) | members' PCs | official installers | being installed |
| Harbor (upstream, `apps/harbor`, Spaces server) | – | – | to be set up |

The fork in `vibemind-os/spaces/rowboat/rowboat` (Next.js web app) is **not** needed for this
project; its Electron app is only a stub there. We use the upstream desktop app and the upstream
Spaces server Harbor (Apache 2.0).

## 3. Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Shared state via Rowboat **Spaces / Harbor**, self-hosted on this PC | Data stays with the team; Rowboat's built-in tools instead of a custom build |
| D2 | Harbor pinned to upstream commit **`72e9d8c`** (2026-10-09); our changes kept as patch files | Reproducible; upstream changes daily |
| D3 | **Dedicated** Postgres and GoTrue containers in the Harbor compose file; the existing Supabase swarm stays untouched | No collision with running VibeMind services |
| D4 | Sign-in via **Supabase GoTrue `v2.188.1`** as OAuth 2.1 server (email + password) | Only sign-in server tested with Harbor; image already available locally |
| D5 | Reachability via **Tailscale Funnel** (public HTTPS at `https://<pc>.<tailnet>.ts.net`) | Members only need Rowboat; the desktop app only accepts `https://` |
| D6 | The **bridge** reads only through existing interfaces (sales-mcp, Marketing API), never directly from other systems' databases | Encapsulation of foreign schemas |
| D7 | Sales: **only our own Claw** (main store, schema `sales`, sales-mcp on the mini PC). Marketing: **all tenants** | Requirement |
| D8 | **Read-only towards Rowboat.** No path back from Rowboat into Sales/Marketing; approvals and sending stay in Sales-Claw | YAGNI until the demo; the approval gate is preserved |
| D9 | No phone numbers or email addresses of contacts in the Space | Data minimisation (GDPR); contact details stay in Sales-Claw |

## 4. Architecture

```
 Mini PC (Tailscale)                    this PC                                     Internet
┌──────────────────┐     ┌───────────────────────────────────────────────┐
│ sales-mcp :8765  │◄────┤ bridge  (Python, every 60 s)                  │
└──────────────────┘     │   │ reads                     │ writes        │
┌──────────────────┐     │   ▼                           ▼ rbk_ key      │
│ Marketing :5510  │◄────┤                     harbor :4272 ──┐          │
└──────────────────┘     │                     gotrue :9999 ──┤ postgres │
                         │                                    │          │
                         │  tailscale funnel :443  → harbor   │          │      Rowboat Desktop
                         │  tailscale funnel :8443 → gotrue   │          │◄──── (member 1..n)
                         └───────────────────────────────────────────────┘
```

All containers bind to `127.0.0.1` only. Only Harbor and GoTrue are exposed, and only via Funnel.

## 5. Components

### 5.1 `harbor/` – Spaces server, sign-in, reachability

- `docker-compose.yml` with three services:
  - `postgres` (`postgres:16`, volume, two databases `harbor` and `auth`)
  - `gotrue` (`public.ecr.aws/supabase/gotrue:v2.188.1`, OAuth 2.1 server mode with
    dynamic client registration on, open sign-up **off**, email confirmation off)
  - `harbor` (built from upstream `72e9d8c` + `patches/`, `DATABASE_URL`, `BLOBS_DIR` on a volume,
    `AUTH_ISSUER` = public GoTrue address, `AUTH_PUBLISHABLE_KEY` for Harbor's
    sign-in/consent page `/oauth/consent`, `HARBOR_ORG=EHL`, `HARBOR_ADDRESS` = Funnel address)
- `patches/`:
  - `0001-org-address-from-env.patch`: org address from `HARBOR_ADDRESS` instead of
    `localhost:<port>` (affects invite links and deep links).
  - `0002-no-rowboat-seeds.patch`: no automatic creation of the Rowboat staff members and the
    Space "Roadboard" in the single-org path.
- `funnel.ps1`: sets up `tailscale funnel` for `:443 → harbor` and `:8443 → gotrue`.
- `add-member.ps1 <email> <name>`: creates the account via the GoTrue admin API and prints an
  initial password.
- `setup.ps1` (one-off, after the admin's first sign-in):
  1. Create Space "EHL" (`POST /v1/spaces`).
  2. Create agent "Bridge" (`POST /v1/agents`, `kind: custom`, `connection: contract`);
     write the `rbk_…` key to `bridge/.env`.
  3. Add the agent to the Space (`POST /v1/spaces/:id/members`, `actingMode: direct`).
  4. Create an invite link (`POST /v1/invites`) and print it.
- The first admin member is inserted via SQL into `member_identities` (`iss`, `sub`, `member_id`);
  according to the upstream code this is the intended way in the single-org path.

### 5.2 `bridge/` – Sync Sales/Marketing → Space

Python 3.12, Docker container, runs on this PC. Split into clearly separated units:

| Module | Responsibility | Dependency |
|---|---|---|
| `sources/sales.py` | Contacts, pipeline stages, open drafts via sales-mcp (MCP client) | `SALES_MCP_URL` |
| `sources/marketing.py` | Campaigns, send jobs, content of all tenants via the Marketing API | `MARKETING_API_URL`, `MARKETING_API_KEY` |
| `model.py` | Neutral data types (`Contact`, `Send`, `Campaign`, `Event`) | – |
| `render.py` | Pure functions: model → Markdown per file | – |
| `events.py` | Compare old/new state → new events | state file |
| `harbor.py` | Harbor REST client: create/update file, post feed message | `HARBOR_URL`, `HARBOR_SPACE_ID`, `HARBOR_AGENT_KEY` |
| `run.py` | Loop every `INTERVAL_S` (default 60): read → render → write on change → post events | all of the above |

**Files in Space "EHL":**

| File | Content |
|---|---|
| `Overview.md` | Key figures: contacts total / new today, contacts per pipeline stage, open approvals, next 3 sends; timestamp of the last sync |
| `Contacts.md` | Table: name, company, stage, source, created on (no phone/email, D9) |
| `Send-Schedule.md` | Chronological: date, channel, subject/title, origin (Marketing/Sales), status (draft / approved / sent / rejected) |
| `Campaigns/<tenant>/<campaign>.md` | Title, status, scheduled date, text, image links |

**Feed events:** new contact, contact changes pipeline stage, send approved, send sent,
send failed. Several events of the same kind within one run are bundled into one message
("🆕 3 new contacts: …").

**Write logic:**
- Each file is fully regenerated on every run; a SHA-256 of the content is compared with the last
  one written. Only on a difference is it written.
- File does not exist yet → `POST /v1/spaces/:id/assets`; otherwise fetch the version and
  `POST /v1/spaces/:id/changes` with `baseVersion`. On conflict: re-fetch the version, retry
  once, otherwise defer to the next run.
- Seen event keys are kept in `state.json` (volume) so nothing is posted twice after a restart.
  On the very first run no events are posted; only the files are written.

## 6. Error handling

| Case | Behaviour |
|---|---|
| Source (sales-mcp or Marketing API) unreachable | Affected files keep their last content plus a header line "⚠️ As of HH:MM – source unreachable"; no events from this source; the next run retries |
| Harbor unreachable | Run is skipped, state is not advanced → nothing is lost |
| Invalid key (401/403) | Clear log error; container exits with an error code (no silent continuation) |
| Single malformed record | Skipped and logged; the rest of the file is written |

Logging via Python's `logging` module, one logger per module, no `print`.

## 7. Security

- Containers bind to `127.0.0.1` only; only Harbor and GoTrue are public, via Funnel.
- Harbor's dev mode (sign-in without `AUTH_ISSUER`) is **never** run behind Funnel. It is only
  allowed during development while Funnel is off.
- GoTrue: open sign-up off; only the admin creates accounts.
- Secrets (`rbk_` key, GoTrue JWT secret, service role key, Marketing API key) only in
  `.env` files excluded via `.gitignore`; templates as `.env.example`.
- The Bridge agent is a member of Space "EHL" only.

## 8. Tests

- **Unit (`bridge/tests/`, pytest):**
  - `render`: sample models → expected Markdown (snapshot), including empty lists and
    special characters in names.
  - `events`: new contact, stage change, approval, no duplicate after restart,
    no messages on the first run.
  - `run`: source fails → warning, last content kept; unchanged content → no write call
    (Harbor client mocked).
- **Integration (local):** Harbor + GoTrue + Postgres via compose; bridge against Harbor with
  fake sources; verify that files and feed messages are readable via the Harbor API.
- **End-to-end:** create a test contact in Sales-Claw → within ~60 s in `Contacts.md` and in the feed.
- **Member access:** Rowboat Desktop on a second machine outside the home network
  (phone hotspot): invite link → sign-in → Space visible.

## 9. Demo flow (3–4 min within the 6-min pitch)

1. A member has Rowboat Desktop open with Space "EHL" (Overview, Send Schedule).
2. Live in Sales-Claw: create a contact or approve a send.
3. A feed message appears; `Overview.md` and `Send-Schedule.md` update.
4. The member asks their Rowboat agent: "What's going out this week?"

## 10. Risks and fallback

| Risk | Check | Fallback |
|---|---|---|
| GoTrue `v2.188.1` has no, or an incompatible, OAuth 2.1 server mode (DCR, PKCE, RFC 8414 metadata) | First plan step, time-boxed | Newer GoTrue image; otherwise the fallback below |
| Rowboat Desktop doesn't accept a custom org address or fails to sign in against our server | Test early with one desktop as soon as Harbor + GoTrue are up behind Funnel | Rowboat-hosted Harbor with test data; the bridge only gets a different `HARBOR_URL` |
| sales-mcp requires authentication or is only meant for the compose network (`:8765` answers over Tailscale, auth unverified) | When building `sources/sales.py`, test a read call first | Read access via the existing sales-claw configuration; no write access |
| Funnel ports: only 443, 8443, 10000 allowed | Two services split across 443/8443 | – |
| Harbor upstream code changes assumptions the patches rely on | Pinned commit (D2) | – |

**Order:** The riskiest part first (GoTrue OAuth + Harbor + Funnel + one desktop sign-in),
the bridge in parallel or afterwards. The bridge can be tested independently of sign-in (Harbor
in dev mode locally without Funnel).

## 11. Out of scope

- Path back from Rowboat to Sales/Marketing (changing dates, approving, creating contacts).
- Syncing other members' Claws (possible later via additional `SALES_MCP_URL`s).
- Images as files in the Space (links only).
- Own domain, reverse proxy, single sign-on.
- Task/kanban objects (Harbor has none; possibly later as Markdown files).
- The Rowboat fork in `vibemind-os/spaces/rowboat`.

## 12. Prior work and licences

| Part | Origin | Licence |
|---|---|---|
| Sales-Claw | `github.com/Flissel/sales-claw` (before the hackathon) | own |
| Marketing | `github.com/Flissel/vibemind-os`, `spaces/marketing` (before the hackathon) | own |
| Rowboat Desktop, Harbor | `github.com/rowboatlabs/rowboat` | Apache 2.0 |
| **New at the hackathon** | `harbor/` (compose, patches, scripts), `bridge/` | own |
