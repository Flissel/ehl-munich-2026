# Vault folder rules: the VibeMind vault in the schema hierarchy

**Date:** 2026-10-13 · **Status:** implemented (plan 2026-10-13-vault-folder-rules-plan.md) · **Builds on:**
`2026-10-12-vault-schema-design.md` (schema) and `2026-10-12-brain-graph-hierarchy-design.md` (graph)

This is **part 1 of 2** of "bring the new Rowboat to VibeMind":

1. **This spec:** the existing VibeMind vault `~/.rowboat/knowledge` is placed into the schema hierarchy,
   and the schema grows the types VibeMind needs. We can see it right away: our fork runs on `~/.rowboat`.
2. **Next spec:** the Rowboat copy in `vibemind-os/spaces/rowboat/rowboat` gets `apps/x` at upstream
   `72e9d8c` + our graph patch, with VibeMind's renderer changes (plugin settings, video link) ported. Its
   web app `apps/rowboat` and `packages/openai-plugin-runtime` stay as they are (upstream deleted
   `apps/rowboat`; there is nothing to merge).

## 1. Goal

Every note of the VibeMind vault gets a type, a level, a domain and a parent, so the 3D brain graph shows
VibeMind as one tree (Company → Domains → Areas → entities → details) and the Rowboat agent can read the
hierarchy. **No existing note is moved, renamed or edited.**

**Success criteria**

- `python -m ehl_schema.cli map --workdir ~/.rowboat --profile vibemind` places every note: each note is
  either in the map with a parent that exists, or excluded on purpose (private). Lint on the VibeMind
  vault has 0 errors.
- Rowboat (our fork) on `~/.rowboat` shows the VibeMind tree in the 3D graph.
- The live writers keep working unchanged: brain curator (`Agents/`, `Hubs/`, `System/`), bubble sync
  (`Bubbles/`, `Projects/`), Marketing (`companys/<Firma>/…`). Their next write does not break the map; the
  next map run picks up new notes.
- The EHL vault behaves exactly as before (same lint result, same graph).

## 2. Findings that shaped this design

From reading `~/.rowboat/knowledge` (503 notes) on 2026-10-13:

| Finding | Consequence |
|---|---|
| `Agents/` (227), `Hubs/`, `System/` were rewritten today, `Bubbles/` two days ago. The writers produce whole files (curator: front matter `typ`, `titel`, nested `fakten`/`belege`; bubble sync: `idea_id`, `sync_version`, …) | **Do not write into existing notes.** Our keys would be overwritten on the next run, and nested YAML must not be touched |
| Marketing reads `companys/<Firma>/Marke.md` and writes `Agent-Notizen/`, `Marke-Verlauf/` by path | **Do not move or rename folders.** The hierarchy hangs on paths |
| Folders do not equal schema types: `companys/`, `vibemind-discourse/`, `Bubbles/`, `Hubs/`, `Videos/`, `Notes/`, `Investor Programs/`, `Coding-Projects/`, `Diary/`, `Bewerbung/` | Mapping needs **path rules**, not just "folder name = type" |
| `Projects/` has three root notes and 38 folders `VibeMind - <Name>/` with `_overview.md`; `VibeMind - E-Ticketing_DE/` holds 97 detail notes; 25 folders are `VibeMind - TODO …` gap items | `_overview` is the project note; other notes in a project folder are its children |
| The graph identifies nodes by `knowledge/<path>.md`; the renderer reads workdir files with `workspace:readFile` (e.g. `config/…`) | A generated `config/vault-map.json` is readable by the graph without a new IPC channel |
| `~/.rowboat/knowledge` is a git repo kept by Rowboat (auto-commits) | New structure notes appear there as normal changes; a backup is still taken before the first write |

## 3. Decisions

- **D1 Path rules, not file edits.** A profile file lists rules "path pattern → type (+ parent)". The
  schema tool resolves them into a map. Existing notes are only read.
- **D2 Front matter wins.** If a note has `type`/`parent`/`level`/`domain` in its own front matter (EHL
  notes), that is used. Rules fill in what is missing.
- **D3 Only new files are written:** structure notes (`Company`, `Domains/*`, `Areas/*`), the rules note
  `Agent Notes/Vault Schema`, and `config/vault-map.json`.
- **D4 One schema, several profiles.** `vault-schema.yaml` stays the single list of domains, areas, types
  and relations. A profile (`schema/profiles/<name>.yaml`) holds what is vault-specific: company name,
  folder rules, excluded paths. The EHL vault uses the built-in default (folder name = type), so nothing
  changes for EHL.
- **D5 Private stays out of the team graph.** `Diary/` and `Bewerbung/` are excluded from the map. Rowboat
  itself still lists them because they sit in the vault; moving them into a private vault is the user's
  later decision and not part of this work.

## 4. Schema changes (`vault-schema.yaml`)

New area:

| Area | Domain |
|---|---|
| Discourse | sources |

New types:

| Type | Domain | Level | Parent (in order) | Default area | Meaning |
|---|---|---|---|---|---|
| Ideas | product | 3 | Areas | Roadmap | Idea bubbles (VibeMind `Bubbles/`) |
| Discourse | sources | 4 | Areas | Discourse | Aggregated self-discourse logs |
| Hubs | `*` (from parent) | 3 | Areas | – | Index notes kept by a curator; domain = domain of their parent area |

Widened parent lists (existing EHL notes stay valid; only more parents become allowed):

| Type | Before | After |
|---|---|---|
| Requirements | Models, Products, Areas | Models, Products, **Projects**, Areas |
| Content | Campaigns, Areas | Campaigns, **Brands**, Areas |
| Agent Notes | Areas | **Brands, Projects, Agents**, Areas |

`model.py` learns the `*` domain for `Hubs` the same way it already handles structure types: lint takes the
expected domain from the parent area.

## 5. Profiles and folder rules

```yaml
# schema/profiles/vibemind.yaml
company: VibeMind
exclude:                     # never in the map, no warning
  - "Diary/**"
  - "Bewerbung/**"
  - "Welcome"                # Rowboat's own welcome note
rules:                       # first match wins; paths are vault-relative, without ".md"
  - {match: "Projects/VibeMind - TODO */_overview", type: Tasks}
  - {match: "Projects/{p}/_overview",               type: Projects}
  - {match: "Projects/{p}/**",                      type: Requirements, parent: "Projects/{p}/_overview"}
  - {match: "Projects/*",                           type: Projects}
  - {match: "Coding-Projects/**",                   type: Projects}
  - {match: "Bubbles/**",                           type: Ideas}
  - {match: "Hubs/Agents",                          type: Hubs, parent: "Areas/Agents"}
  - {match: "Hubs/Bubbles",                         type: Hubs, parent: "Areas/Roadmap"}
  - {match: "Hubs/People",                          type: Hubs, parent: "Areas/Contacts"}
  - {match: "Hubs/System",                          type: Hubs, parent: "Areas/Infrastructure"}
  - {match: "Hubs/*",                               type: Hubs, parent: "Areas/Topics"}
  - {match: "companys/{c}/Marke",                   type: Brands}
  - {match: "companys/{c}/Markenhandbuch",          type: Content, parent: "companys/{c}/Marke"}
  - {match: "companys/{c}/Marke-Verlauf/**",        type: Content, parent: "companys/{c}/Marke"}
  - {match: "companys/{c}/Agent-Notizen/**",        type: Agent Notes, parent: "companys/{c}/Marke"}
  - {match: "vibemind-discourse/**",                type: Discourse}
  - {match: "Videos/**",                            type: Assets}
  - {match: "System/**",                            type: Systems}
  - {match: "Notes/Traction Metrics*",              type: KPIs}
  - {match: "Notes/**",                             type: Topics}
  - {match: "Investor Programs/**",                 type: Funding}
  # everything else: default rule (first folder = type name), e.g. Agents/**, Workflows/**, Topics/**, People/**
```

**Pattern syntax:** `*` matches inside one path segment, `**` matches any number of segments, `{name}`
captures one whole segment and can be used in `parent`. Matching is case-sensitive, like Rowboat links.

**Resolution per note** (in this order):

1. Path in `exclude` → not in the map.
2. Front matter has a `type` that is a **schema type** → use front matter (`parent`, `level`, `domain`
   from it or from the type). A `type` the schema does not know (VibeMind has `type: coding-project` in
   `Coding-Projects/`) is ignored for placement and the note goes on to the rules.
3. First matching rule → its `type`; `parent` from the rule if given and the target note exists.
4. No rule, but the first folder is a type name → that type (the default rule; this is all the EHL vault
   needs).
5. Nothing fits → type `Topics` under `Areas/Topics`, warning `W-no-rule` with the path.

**Parent when the rule gives none, or its target is missing:** the type's default area
(`Areas/<default_parent>`). A missing rule target also gives warning `W-parent-missing`.

`level` and `domain` come from the type (Hubs: from the parent area). The **profile without a file**
(`--profile` omitted) is the EHL behaviour: company from `--company`, no excludes, only the default rule.

## 6. Generated output

`python -m ehl_schema.cli map --workdir <dir> [--profile <name>] [--company <name>]` reads the vault and
writes **only** these files (each only if its content changed):

- **Structure notes** as today (`Company.md`, `Domains/<Title>.md`, `Areas/<Name>.md`, front matter with
  `managed_by: schema`), including the new area.
- **`Agent Notes/Vault Schema.md`**: the rules note gains a section "Folders in this vault" with the
  profile's rules in plain words, so the agent knows where a new note of a type belongs.
- **`config/vault-map.json`**:

```json
{
  "version": 1,
  "company": "VibeMind",
  "generated_at": "2026-10-13T14:00:00Z",
  "notes": {
    "Agents/abo-probe (183dc8)": {"type": "Agents", "level": 3, "domain": "ai", "parent": "Areas/Agents"},
    "Areas/Agents": {"type": "Areas", "level": 2, "domain": "ai", "parent": "Domains/AI"}
  }
}
```

Keys and `parent` are vault-relative paths without `.md`. Structure notes are in the map too, so the
graph needs nothing else.

`build` keeps working as today and calls `map` at the end. `install.py` and the vault sync loop run `map`
after every sync, so new notes from the writers appear within one sync interval.

## 7. Graph (fork branch `ehl-schema-graph`)

- `graph-hierarchy.ts` gets `parseVaultMap(json): Map<string, NodeInfo>` (tolerant: wrong version,
  broken JSON or missing fields → empty map) and `buildHierarchyGraph` takes an optional map as fallback:
  per note, front matter values win, the map fills in `level`, `parentId`, `domain`, and a `parent` edge
  for the map's parent.
- `App.tsx` reads `config/vault-map.json` with `workspace:readFile` when building the graph. If the file
  is missing, behaviour is exactly as today.
- The graph reloads the map with the knowledge files (same trigger as today). No new IPC.

## 8. Lint

`lint` takes `--profile` and checks the resolved view (front matter + rules) instead of front matter only:

- Notes placed by a rule are not reported for missing front matter keys, nor for foreign front matter
  (`typ`, nested `fakten`, a non-schema `type`).
- New warnings: `W-no-rule` (no rule and first folder is no type), `W-parent-missing` (rule parent does
  not exist).
- All existing checks (cycles, parent level ≤ note level, allowed parent types, relation targets) run on
  the resolved values.
- For the EHL vault (no profile) the result is unchanged.

## 9. Install and start

`scripts/install.py --profile vibemind [--start]`:

- Workdir `~/.rowboat` (overridable with `--workdir`), company from the profile.
- Skips everything BMW/EHL-demo: market venv and data, quotes, Torque app link, `ehl-market` MCP entry, 3D
  car data, demo example data, EHL notes.
- Keeps: tool check, Rowboat clone of our fork, schema install, backup, `build` + `map` + `lint`, start of
  Rowboat in dev mode with `ROWBOAT_WORKDIR=~/.rowboat`, vault-map refresh loop.
- **Backup before the first write:** a copy of `~/.rowboat/knowledge` to
  `~/.rowboat/knowledge.bak-<timestamp>` (once per install run).
- Does not touch `~/.rowboat/config/mcp.json` or other config of the VibeMind installation.

## 10. Error handling

| Case | Behaviour |
|---|---|
| Note matches no rule | `Topics` under `Areas/Topics`, warning `W-no-rule` |
| Rule parent missing | Default area of the type, warning `W-parent-missing` |
| Broken front matter or not UTF-8 | Note skipped, reported by lint (as today) |
| Profile file malformed (unknown type, bad pattern, unknown capture in `parent`) | `SchemaError` before anything is written |
| `config/vault-map.json` missing or broken | Graph uses front matter only (today's behaviour) |
| Writer replaces a note while `map` runs | The note is read as it is at that moment; the next run fixes the map |

## 11. Tests

- **pytest** (schema package): pattern matching (`*`, `**`, captures), rule order, excludes, front
  matter precedence, parent fallback + warnings, Hubs domain from parent, map JSON content, "unchanged
  file is not rewritten", profile validation errors, EHL vault result unchanged (existing tests keep
  passing). A fixture vault mirrors the VibeMind folder layout with **made-up** names and content only.
- **vitest** (fork): `parseVaultMap` (good, broken, wrong version), `buildHierarchyGraph` with map
  fallback and front matter precedence.
- **Real run** (not in CI): `map` + `lint` on `~/.rowboat` after the backup; numbers per type and
  warnings reported; Rowboat started on `~/.rowboat`; the user checks the 3D graph.
- **Real run 2026-10-13:** 574 notes placed (500 existing + 74 structure notes), 3 excluded (`Diary/`,
  `Bewerbung/`, `Welcome`), lint 0 errors / 0 warnings. A diff against the backup shows only the new
  `Company.md`, `Domains/`, `Areas/` and `Agent Notes/`. Types: Agents 227, Requirements 98, Assets 37,
  Topics 30, Tasks 25, Discourse 24, Projects 18, Ideas 13, People 6, Workflows 6, Agent Notes 5, Hubs 4,
  Content 3, Brands 2, Funding 1, KPIs 1, Systems 1.

## 12. Out of scope

- Part 2: updating the Rowboat copy in vibemind-os (own spec).
- Changing the VibeMind writers (curator, bubble sync, Marketing) to write schema front matter.
- Typed relations for VibeMind notes (e.g. a project's `bubble_id` → its idea); only `parent` edges and
  ordinary body links for now.
- Moving `Diary/` and `Bewerbung/` into a private vault.
- Committing anything from `~/.rowboat` to git (real data stays out of the repo).
