# Why Rowboat, and how we integrated it

Torque is the decision cockpit, and it runs inside [Rowboat](https://github.com/rowboatlabs/rowboat). Rowboat
is an open-source AI coworker by RowBoat Labs under the Apache License 2.0. This page explains why we built on
Rowboat instead of writing our own shell, and how we connect to it without changing a line of its code.

## What the product needed

The challenge asks for an application that turns heterogeneous inputs into prioritised requirements. A human
must review every requirement, and there must be an audit trail from each source to each decision
([deliverables](deliverables.md)). For a product manager that means:

- **Traceability.** Requirements, findings, products, car parts and assumptions must link to each other, and
  you must be able to follow every link.
- **Local data.** The inputs include real customer comments. They should stay on the PM's machine and not end
  up in yet another SaaS backend.
- **An assistant that works on the same data.** It should answer questions, draft requirement texts and pull
  in outside evidence, using the PM's own model.
- **Something we could build in a weekend**, without writing auth, storage, sync and a chat client first.

## Why Rowboat fits

| Rowboat gives us | What we use it for |
| --- | --- |
| **Local-first knowledge vault**: plain Markdown files on disk (`~/.rowboat/knowledge`) | Every product, part, assumption, requirement and decision is a readable, diffable note. The audit trail is not locked inside our app. |
| **Knowledge graph** built from `[[Folder/Name]]` links | Requirements link to their products, parts, topics and markets. Rowboat draws the graph, so the PM can walk from a requirement to its evidence. |
| **Configurable note types** (`config/notes.json`) | We register `Brands`, `Models`, `Components`, `Feature Classes`, `Assumptions` and `Requirements` as types. Rowboat's own note agents then write these folders in the same shape as our scripts. |
| **Apps**: local web apps that Rowboat hosts, with a host API | Torque runs as a Rowboat app. It stores its state through `/_rowboat/data/*` and calls the user's configured model through `/_rowboat/llm/generate`. It needs no backend, login or API key of its own. |
| **Agent with MCP tools** (`config/mcp.json`) | Rowboat's agent gets our `ehl-market` MCP server: sources, live World Bank, Eurostat and NHTSA data, correlations. |
| **Bring your own model**: hosted with your own key, or local through Ollama or LM Studio | No model key in our repo. Each user decides where the data goes. |
| **Apache License 2.0** | We may run it, pin it, fork it and ship our own code next to it. Our code is under the same licence. |

The key benefit is a loop between the agent and the cockpit. When Rowboat's agent edits a requirement or a
component note, the cockpit and the 3D car show the change within seconds. When the PM decides in Torque, the
decision is written back to a note. AI and human both work on the same plain files, and those files are the
record.

## Integrated, not forked

The team fork [`Flissel/rowboat`](https://github.com/Flissel/rowboat), branch `ehl`, points at upstream
commit **`72e9d8c`** (9 Oct 2026) with **no changes**. Neither the team fork nor any member's fork has a
commit or pull request on top of upstream. The fork exists only to pin a reproducible base. Everything we
built connects through Rowboat's documented extension points:

| Extension point | What we put there | Written by |
| --- | --- | --- |
| `<workdir>/apps/torque` (a link to `demo/torque`) | The Torque app with its manifest `rowboat-app.json` (`entry: index.html`, capability `llm`) | `scripts/install.py` |
| `<workdir>/knowledge/` | Notes: `Brands/`, `Models/`, `Components/` (56 car parts), `Feature Classes/`, `Assumptions/`, `Requirements/`, `Purchase Drivers/`, `Data/BMW Dataset.xlsx` | `demo/visu/vault.py notes`, `demo/torque/sync.py` |
| `<workdir>/config/notes.json` | Our note types, each with a template and an extraction guide | `demo/visu/brand.py` (via `vault.py notes`) |
| `<workdir>/config/mcp.json` | The `ehl-market` server (stdio, `python -m ehl_market.server`) | `scripts/install.py` |
| App host API | `/_rowboat/data/*` stores Torque's state and logo; `/_rowboat/llm/generate` serves Nordi and the Concept 3D design prompt | `demo/torque/dist/index.html`, `demo/visu/src/lib/interpret.ts` |

What this gives us:

- **We can upgrade.** A newer Rowboat only needs a new pin. There is no patch set to rebase.
- **Clear authorship.** Everything the team wrote sits in this repository. Rowboat's code is untouched,
  so the jury can see exactly what is ours.
- **Simple licence compliance.** We do not distribute modified Rowboat files, so Apache 2.0 §4(b) (state your
  changes) never applies. We keep Rowboat's licence and credit, list it in [NOTICE](../NOTICE), and do not
  use its name to suggest endorsement (§6).

## What we tried and left out

- **Rowboat Spaces with a self-hosted Harbor server**, to share one live workspace across the team's PCs.
  Harbor needs an external OAuth 2.1 server and HTTPS, and it has no self-host guide yet. That was too risky
  for a weekend. Instead, every team member runs Rowboat locally with test data. Real company data stays on
  the demo PC only (spec decision D11).
- **The Rowboat web app** (Next.js), which we had customised in another project. We chose the desktop app
  instead, because it brings the local vault, apps and note types that Torque relies on.
- **Rowboat's scheduled background agents.** Upstream supports them, but we did not configure any. Refreshing
  evidence on a schedule (new comments, new market data) is the obvious next step.

## Where to look

- Rowboat source: https://github.com/rowboatlabs/rowboat (pin: `72e9d8c`)
- Our app manifest: [`demo/torque/rowboat-app.json`](../demo/torque/rowboat-app.json)
- Vault writers: [`demo/visu/vault.py`](../demo/visu/vault.py), [`demo/torque/sync.py`](../demo/torque/sync.py)
- MCP server: [`market/`](../market/README.md)
- Installer: [`scripts/install.py`](../scripts/install.py)
