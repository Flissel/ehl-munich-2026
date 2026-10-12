# Vault schema: one hierarchy for all business data of an AI company

**Date:** 2026-10-12 · **Status:** draft for review (sub-project 1 of 4) · **Iterations:** 3
(draft → business critique + Rowboat/AI critique → this version)

## 1. Goal

One uniform, extensible and maintainable hierarchy for **all** business data of an AI company. It is
read by three consumers:

- **Rowboat's 3D brain graph** (sub-project 2) arranges notes as nested cells (octree) along this
  hierarchy.
- **AI agents** read, classify and write notes along it, without guessing from free text.
- **People** keep it up to date.

**Success criteria**

- Every note has exactly one `parent`, and the parents form one tree per vault (no cycles).
- A new note type or relation is a few lines in one schema file. Nobody touches code for it.
- A linter in CI proves that every note follows the schema.
- Rowboat keeps working unmodified with the vault: its own agents still write `People/`, `Organizations/`
  and the other built-in folders, links still resolve, and duplicate detection still works.

## 2. Findings that shaped this version

From reading Rowboat at `72e9d8c`:

| Finding | Where | Consequence |
|---|---|---|
| A note type's `folder` is not passed to the note agent. Prompts hard-code `knowledge/People/…`, `[[People/X]]`, `Meetings/…` | `core/src/knowledge/note_system.ts:242`, `note_creation.ts:145-179, 569-575, 1253` | **Folders stay flat, one folder per type (F1).** Domain folders (F2) would split data between old and new paths |
| People and Organizations are recognised by their **first** path segment. Dedup uses the body fields `**Aliases:**`, `**Email:**`, `**Domain:**` | `knowledge_index.ts:75-99, 254-266` | Built-in folders stay at the top level. Bridges write these body fields too |
| `[[Folder/Name]]` resolves by exact, case-sensitive path only. Renaming a folder does not rewrite links | `lib/wiki-links.ts:40-45`, `workspace/wiki-link-rewrite.ts:130` | Paths are IDs: never rename a folder, rename notes only through `aliases` |
| The properties editor drops nested YAML maps | `renderer/src/lib/frontmatter.ts:150-210` | **Front matter must be flat**: one top-level key per relation, links quoted |
| The graph groups by first path segment and skips `meetings/` | `App.tsx:7051, 7098` | Flat type folders keep today's graph usable until sub-project 2 replaces it |
| Rowboat knows one owner per workdir and sends everything under `knowledge/` to the LLM. It has no visibility filter | `note_creation.ts:44` | **One vault per tenant.** Private notes live outside company vaults |

From the business critique:

- Missing domains were legal and compliance, customer success, vendors, KPIs and decisions.
- Tenants and private data were not separated.
- People and organisations need one register, with their roles expressed as relations.
- Status must be a field, never a folder.

## 3. Vaults (tenancy and privacy)

| Vault (Rowboat workdir) | Contents | Who reads it |
|---|---|---|
| `~/.rowboat-<tenant>`, one per company or client (e.g. `vibemind`, `fin2gether`, `ehl`) | All business data of that tenant | That tenant's agents and team |
| `~/.rowboat-private` | Diary, applications, personal profile | The owner only. No company agent and no RAG index |

- Tenants never share a vault, so agents cannot read across tenants by design.
- Cross-tenant facts (e.g. one person working with two tenants) are duplicated on purpose, one note per
  vault, and linked by the same `id`.
- WP3's Qdrant index and every bridge must be configured per vault.

## 4. Levels and domains

Every note has a `level`:

| Level | Meaning |
|---|---|
| **L0** | The company: one note, `Company.md` |
| **L1** | Domain |
| **L2** | Area |
| **L3** | Entity: what you decide or act on |
| **L4** | Detail or evidence |

Domain and area are notes themselves, in `Domains/` and `Areas/`, so that every level is a real parent
in the tree.

### Business domains (L1) with areas (L2) and entity types (L3/L4)

| # | Domain (`domain:`) | Areas (L2) | Note types (folder) |
|---|---|---|---|
| 1 | `strategy` – Strategy & steering | Goals, KPIs, Decisions, Risks | `OKRs`, `KPIs`, `Decisions`, `Risks` |
| 2 | `legal` – Legal & compliance | Contracts, Data protection, AI Act, IP & licences | `Contracts`, `Processing Records`, `AI Systems`, `Licences` |
| 3 | `finance` – Finance & funding | Budget, Invoices, Funding, Pricing | `Budgets`, `Invoices`, `Funding`, `Price Plans` |
| 4 | `team` – Team & HR | Roles, Recruiting, Onboarding | `Roles`, `Candidates` |
| 5 | `sales` – Market & sales | Segments, Pipeline, Competitors | `Segments`, `Leads`, `Deals`, `Competitors` |
| 6 | `success` – Customer success & support | Onboarding, Support, Feedback, Design partners | `Tickets`, `Feedback` |
| 7 | `partners` – Partners & vendors | Partnerships, Vendors (LLM, SaaS, hosting) | `Partnerships`, `Vendors` |
| 8 | `marketing` – Marketing & brand | Brand, Campaigns, Content, Channels | `Brands`, `Campaigns`, `Content`, `Assets` |
| 9 | `product` – Product & engineering | Products, Roadmap, Requirements, Releases, Incidents | `Products`, `Models`, `Components`, `Feature Classes`, `Requirements`, `Purchase Drivers`, `Releases`, `Incidents` |
| 10 | `ai` – AI & agents | Agents, Workflows, Models & evals, Datasets, Compute | `Agents`, `Workflows`, `AI Models`, `Evals`, `Datasets` |
| 11 | `delivery` – Projects & delivery | Client projects, Initiatives, Milestones | `Projects` (built-in), `Milestones`, `Tasks`, `Initiatives` |
| 12 | `operations` – Operations & IT | Infrastructure, Tools, Security, Runbooks | `Systems`, `Tools`, `Runbooks` |

### Cross-cutting domains (also L1, so the tree stays complete)

| # | Domain | Note types | Rule |
|---|---|---|---|
| 13 | `register` – People & organisations | `People`, `Organizations` (built-in) | **Identity only, once.** Roles are relations (`works_at`, `contact_at`, `investor_in`, `candidate_for`) |
| 14 | `sources` – Raw inputs | `Meetings` (built-in), `Mails`, `Chats`, `Voice Memos`, `Agent Notes` | Parent is a date bucket (`Areas/Sources 2026-10`). Entities are linked through `about` |
| 15 | `knowledge` – Knowledge & evidence | `Topics` (built-in), `Studies`, `Data`, `Assumptions` | Evidence for decisions. Linked through `evidence` |

### Parent rules

1. The parent is **who owns and decides**. Examples:
   - A requirement hangs under its product or model.
   - A paid client project hangs under `Areas/Client projects`, with `customer:` and `product:` as relations.
2. **Identity and role are separate.** A person exists once in `People/`. That they are an employee, a
   customer contact or an investor is a relation, never a second note.
3. **Agents:**
   - The agent's definition lives in `Agents/`, domain `ai`.
   - What an agent did hangs under the object it worked on, with `executed_by:`.
4. **Status is a field.** No `Veraltet/` or `Archive/` folders. Use `status: archived`.

## 5. Filesystem

```
knowledge/
  Company.md                      L0
  Domains/   Strategy.md … Knowledge.md        L1 (15 notes)
  Areas/     Contracts.md, Pipeline.md, …      L2
  People/ Organizations/ Projects/ Topics/ Meetings/ Agent Notes/ Voice Memos/   Rowboat built-ins, unchanged
  OKRs/ KPIs/ Decisions/ Risks/ Contracts/ … Runbooks/                            one flat folder per type
```

- **One folder per note type, directly under `knowledge/`.** No nesting by domain.
- Folder names are English plurals, matching Rowboat's built-ins.
- File name = note title. The file name never changes once other notes link to it.

## 6. Front matter (every note)

Flat YAML, keys in `snake_case`. Links are always quoted and always use the full path `Type/Name`.

```yaml
---
id: org-acme                     # stable slug, never changes, unique per vault
type: Organizations              # = folder = notes.json type
domain: register
level: 3
parent: "[[Areas/Customers]]"
status: active                   # active | planning | on-hold | done | archived
visibility: team                 # team | restricted (no 'private': private data lives in the private vault)
env: prod                        # prod | test (smoke tests and fakes)
# typed relations: one key each, always a list of links
works_at: []
contact_at: []
customer: []
project: ["[[Projects/EHL 2026]]"]
product: []
owner: ["[[People/Felix Baumann]]"]
about: []
evidence: []
executed_by: []
when: 2026-10-12
source: sales-claw               # who created it: rowboat | sales-claw | marketing | dataset | human | <agent>
managed_by: bridge               # whose script may rewrite it; empty = humans and Rowboat agents only
updated: 2026-10-12
schema_version: 1
---
```

- Rowboat dedup still reads the **body** fields `**Aliases:**`, `**Email:**`, `**Domain:**`. Bridges write them too.
- Relations in front matter also become (untyped) edges in today's Rowboat graph, because Rowboat reads
  `[[links]]` from the whole file. Sub-project 2 reads them typed.

### Relations (11)

| Key | Points to | Example |
|---|---|---|
| `works_at` | Organizations | Person → own company |
| `contact_at` | Organizations | Person → customer or partner |
| `investor_in` / `candidate_for` | Organizations / Roles | Person → company / open role |
| `customer` | Organizations | Deal, project, ticket → customer |
| `project` | Projects | Task, mail, campaign → project |
| `product` | Products, Models | Requirement, release, project → product |
| `owner` | People, Agents | Anything → who is responsible |
| `about` | any | Mail, meeting, feedback → what it is about |
| `evidence` | Studies, Data, Topics, Meetings | Requirement, decision → its sources |
| `executed_by` | Agents | Result → the agent that produced it |
| `when` | date | Due date, meeting date, publish date |

## 7. Schema as code (single source)

```
schema/
  vault-schema.yaml      domains, areas, levels, types (folder, domain, level, allowed parent types,
                         required relations, template body), relations, schema_version
  build.py               writes <workdir>/config/notes.json (template with the front matter block,
                         extractionGuide with the parent and relation rules) and
                         knowledge/Agent Notes/Vault Schema.md (readable rules for every agent)
  lint.py                checks a vault; exit code ≠ 0 on errors
  migrate.py             adds front matter to existing notes (dry run by default, writes a diff)
  tests/                 pytest
```

**`lint.py` checks:**

- YAML parses and the keys are flat.
- `type` matches the folder.
- `id` is unique.
- `parent` exists, has an allowed type and a lower level, and the tree has no cycles.
- Required relations are present.
- Every `[[link]]` resolves to an existing path (exact match).
- Possible duplicates: same normalised name or same email/domain in `People/` and `Organizations/`.

**`migrate.py`:**

1. Proposes `domain`, `level` and `parent` per note. The type comes from the schema. The parent comes from
   the existing links: the linked note of the highest allowed parent type.
2. Writes them only after review.
3. Never renames files.

## 8. Mapping of existing data

**EHL vault** (`~/.rowboat-ehl`, ~190 notes):

| Folder | Domain |
|---|---|
| Brands | marketing |
| Models, Components, Feature Classes, Requirements, Purchase Drivers | product |
| Assumptions, Topics, Data | knowledge |
| Projects | delivery |

Parents:

- Model → Brand
- Component → its first model
- Feature Class → its component
- Requirement and Purchase Driver → their model

**VibeMind vault** (`~/.rowboat`):

| Folder | Domain / target |
|---|---|
| Agents/ | ai: `Agents` (`Veraltet/` → `status: archived`) |
| Workflows/ | ai: `Workflows` |
| Videos/ | marketing: `Assets` (eval runs → ai: `Evals`) |
| Bubbles/ | delivery: `Initiatives` (smoke tests → `env: test`) |
| Projects/ | delivery (requirement gaps → product: `Requirements`) |
| Topics/ | knowledge |
| Hubs/ | `Areas` |
| Investor Programs/ | finance: `Funding` |
| Notes/Traction Metrics | strategy: `KPIs` |
| System/ | operations: `Systems` |
| People/Design Partners | register: `Organizations` + success |
| companys/<Firma>/ | per-tenant vault: marketing `Brands` |
| Diary/, Bewerbung/, User_Profile | → **`~/.rowboat-private`** |

**Sales-Claw** (via the bridge, sub-project 4):

| Source | Target |
|---|---|
| leads | `People` + `Organizations` (register) + `Leads` (sales) |
| personas | `Segments` |
| activities | `Agent Notes`/sources, with `about` |

- Drafts, consent and block list (`compliance.sperrliste`) **stay in Sales-Claw**. Personal data that is not
  needed is never copied.

**Marketing** (via the bridge):

| Source | Target |
|---|---|
| Campaigns, contents | `Campaigns`, `Content` |
| Crowdfunding | `Funding` |
| Mandanten | one vault each |
| Send orders | stay in Marketing/Sales-Claw (spec D7: we never send) |

## 9. Out of scope

- **Payroll, bank data, full HR files.** The vault only holds references, such as "contract signed, see HR
  system".
- **Moving data between the existing vaults.** This spec only defines the target. Moving the VibeMind
  vault is a separate, manual step after review.
- **Sub-projects 2–4:**
  - 3D view in Rowboat.
  - Agents writing the fields.
  - Bridges for Sales-Claw and Marketing.

## 10. Decisions on the former open questions (2026-10-12)

1. **L0–L2 are real notes** (`Company.md`, `Domains/`, `Areas/`). The 3D graph needs them as nodes, and
   people and agents can link to them. `schema/build.py` generates them from the schema; nobody edits them
   by hand. A generated note carries `managed_by: schema`.
2. **Finance may hold amounts** as flat fields, `amount` (number) and `currency` (ISO code), on `Budgets`,
   `Invoices`, `Funding` and `Deals`. The accounting system stays the source of truth: each such note links
   to it in its body. Bank details, payroll and salaries never go into a vault.
