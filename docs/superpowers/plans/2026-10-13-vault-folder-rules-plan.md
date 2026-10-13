# Vault Folder Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Place every note of the VibeMind vault (`~/.rowboat/knowledge`) into the schema hierarchy through
path rules, without editing any existing note, and show the result in our fork's 3D brain graph.

**Architecture:** A profile file (`schema/profiles/vibemind.yaml`) holds company name, excludes and path
rules. A new resolver turns notes + profile into a placement per note (type, level, domain, parent). A new
`map` command writes structure notes plus `config/vault-map.json`. Lint checks the resolved view. The Rowboat
renderer reads the map as a fallback for notes without hierarchy front matter. The installer gets a
`--profile vibemind` path without any BMW/EHL demo step.

**Tech Stack:** Python 3.12 + PyYAML + pytest (`schema/`), stdlib-only installer (`scripts/install.py`),
TypeScript + React + vitest in the Rowboat fork (`C:\Users\User\Desktop\rowboat`, branch `ehl-schema-graph`).

**Spec:** `docs/superpowers/specs/2026-10-13-vault-folder-rules-design.md`

## Global Constraints

- Python 3.12, `logging` (no `print`), runs on Windows and macOS; every text write uses `encoding="utf-8", newline="\n"`.
- `scripts/install.py` uses the standard library only (it runs before anything is installed).
- No existing vault note is moved, renamed or edited; only `Company.md`, `Domains/*`, `Areas/*`,
  `Agent Notes/Vault Schema.md` and `config/vault-map.json` are written.
- `migrate` must never run on a profile vault.
- The EHL vault without `--profile` behaves exactly as before (all existing tests keep passing, same lint result).
- Real data stays out of git: nothing from `~/.rowboat*` is committed; test fixtures use made-up names only.
- Commits: conventional commits, prefix the command with `ENTIRE_TEST_TTY=0` (the Entire hook hangs otherwise),
  end the message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- EHL repo branch: `feat/vault-folder-rules`. Rowboat fork branch: `ehl-schema-graph` (local, not pushed yet).
- Spec warning names map to lint codes: `W-no-rule` → warning `no-rule`, `W-parent-missing` → warning `rule-parent-missing`.
- Run schema tests with: `cd schema && py -3.12 -m pytest -q` (Windows) / `python3.12 -m pytest -q` (macOS).
- Run renderer tests with: `cd C:\Users\User\Desktop\rowboat\apps\x\apps\renderer && npx vitest run src/lib/graph-hierarchy.test.ts`, typecheck `npx tsc -b`.

## Review Focus

1. **The installer's VibeMind path runs `migrate`** → it would write front matter into 500 live notes. Expect: the
   profile command list contains no `migrate` (test in Task 7).
2. **`vault-map.json` rewritten on every run although nothing changed** (only `generated_at` differs) → Rowboat's
   knowledge git and the graph churn every minute. Expect: an unchanged map is not rewritten (test in Task 4).
3. **Real VibeMind file names** with spaces, parentheses, em dashes, umlauts and dots (`LinkedIn Launch — Agentic OS
   Beta opens (c1c67f)`, `Traction Metrics 2026-Q2`) → regex special characters must be escaped. Expect: they match
   their rule (test in Task 2).
4. **Curator front matter** (`typ:`, nested `fakten:` lists, a foreign `type: coding-project`) → must neither win
   placement nor produce lint errors. Expect: the rule places the note, lint is clean (tests in Tasks 3 and 5).
5. **Company name drift**: the EHL refresh loop calling `map` without `--company EHL` would rewrite `Company.md`
   to "Company". Expect: every installer `map` command carries the company (test in Task 7).

---

## File Structure

| File | Responsibility |
|---|---|
| `schema/vault-schema.yaml` (modify) | New area Discourse, types Ideas/Discourse/Hubs, widened parent lists |
| `schema/ehl_schema/model.py` (modify) | Accept domain `*` for index types (Hubs) |
| `schema/ehl_schema/issues.py` (create) | `Issue` dataclass shared by lint and resolver |
| `schema/ehl_schema/profile.py` (create) | Profile file loading, path pattern compiling and matching |
| `schema/ehl_schema/placement.py` (create) | Resolve every note to a `Placement` (front matter, rule, default, fallback) |
| `schema/ehl_schema/vaultmap.py` (create) | Build/write `config/vault-map.json`, run the whole `map` step |
| `schema/ehl_schema/build.py` (modify) | Rules note gains "Folders in this vault"; skip `*` types in notes.json |
| `schema/ehl_schema/lint.py` (modify) | Profile mode: check the resolved view |
| `schema/ehl_schema/migrate.py` (modify) | Leave `*` types (Hubs) alone |
| `schema/ehl_schema/cli.py` (modify) | `map` command, `--profile` on build/lint/map, `--watch` |
| `schema/profiles/vibemind.yaml` (create) | The VibeMind rules from spec §5 |
| `schema/tests/helpers.py` (modify) | `vibemind_like_vault()` fixture with made-up content |
| `schema/tests/test_profile.py`, `test_placement.py`, `test_vaultmap.py` (create) | Tests |
| `scripts/install.py` (modify) | `--profile`, backup, schema venv, map refresh job |
| `scripts/tests/test_install.py` (modify) | Tests for the new pure helpers |
| Fork `apps/x/apps/renderer/src/lib/graph-hierarchy.ts` (modify) | `parseVaultMap`, map fallback in `buildHierarchyGraph` |
| Fork `apps/x/apps/renderer/src/App.tsx` (modify) | Read `config/vault-map.json` when building the graph |

---

### Task 1: Schema additions (area, three types, wider parents, `*` domain)

**Files:**
- Modify: `schema/vault-schema.yaml` (areas block lines 24-80, types block from line 96)
- Modify: `schema/ehl_schema/model.py:106-138` (`_check`)
- Modify: `schema/ehl_schema/build.py:137-154` (`notes_json`), `build.py:67-71` (rules table)
- Modify: `schema/ehl_schema/migrate.py:76-81` (`plan`)
- Test: `schema/tests/test_model.py`, `schema/tests/test_build.py`, `schema/tests/test_migrate.py`

**Interfaces:**
- Produces: types `Ideas` (product, 3, parent `[Areas]`, default `Roadmap`), `Discourse` (sources, 4, `[Areas]`,
  default `Discourse`), `Hubs` (domain `"*"`, 3, `[Areas]`, no default); area `Discourse: sources`;
  `Requirements.parent = (Models, Products, Projects, Areas)`, `Content.parent = (Campaigns, Brands, Areas)`,
  `Agent Notes.parent = (Brands, Projects, Agents, Areas)`. `TypeDef.domain == "*"` marks an index type.

- [ ] **Step 1: Write the failing tests**

Append to `schema/tests/test_model.py`:

```python
def test_vibemind_types_and_area():
    schema = load_schema()
    assert schema.areas["Discourse"] == "sources"
    assert (schema.types["Ideas"].domain, schema.types["Ideas"].level, schema.types["Ideas"].default_parent) == ("product", 3, "Roadmap")
    assert (schema.types["Discourse"].domain, schema.types["Discourse"].level) == ("sources", 4)
    hubs = schema.types["Hubs"]
    assert (hubs.domain, hubs.level, hubs.parent, hubs.default_parent) == ("*", 3, ("Areas",), None)
    assert schema.types["Requirements"].parent == ("Models", "Products", "Projects", "Areas")
    assert schema.types["Content"].parent == ("Campaigns", "Brands", "Areas")
    assert schema.types["Agent Notes"].parent == ("Brands", "Projects", "Agents", "Areas")


def test_star_domain_needs_areas_as_only_parent(tmp_path):
    text = DEFAULT_SCHEMA.read_text(encoding="utf-8").replace(
        "Hubs:               {domain: \"*\", level: 3, parent: [Areas]}",
        "Hubs:               {domain: \"*\", level: 3, parent: [Agents, Areas]}")
    path = tmp_path / "schema.yaml"
    path.write_text(text, encoding="utf-8", newline="\n")
    with pytest.raises(SchemaError, match="Hubs"):
        load_schema(path)
```

Check the imports at the top of `test_model.py` include `DEFAULT_SCHEMA`, `SchemaError`, `load_schema` and `pytest`;
add what is missing (`from ehl_schema.model import DEFAULT_SCHEMA, SchemaError, load_schema`).

Append to `schema/tests/test_build.py`:

```python
def test_notes_json_skips_index_types(schema):
    entries = notes_json(schema, [])
    assert "Hubs" not in {e["type"] for e in entries}
    assert "Ideas" in {e["type"] for e in entries}
```

Append to `schema/tests/test_migrate.py` (it already imports `plan`, `write_note`, `valid_vault`, a `schema` fixture;
check and add if missing):

```python
def test_migrate_leaves_hub_notes_alone(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Hubs/Agents", None, "# Agents\n\n- [[alpha]]\n")
    report = plan(schema, vault)
    assert "Hubs/Agents" not in report.changes
    assert "Hubs/Agents" in report.unmapped
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd schema && py -3.12 -m pytest -q tests/test_model.py tests/test_build.py tests/test_migrate.py`
Expected: FAIL (`KeyError: 'Discourse'` / `'Ideas'` / `'Hubs'`).

- [ ] **Step 3: Change the schema file**

In `schema/vault-schema.yaml`, in the `areas:` block after `Agent notes: sources` add:

```yaml
  Discourse: sources
```

In the `types:` block replace the three lines

```yaml
  Content:            {domain: marketing, level: 4, parent: [Campaigns, Areas], default_parent: Content, optional: [owner, about, when], statuses: [draft, approved, published]}
```
```yaml
  Requirements:       {domain: product, level: 3, parent: [Models, Products, Areas], default_parent: Requirements, optional: [product, owner, evidence], statuses: [proposed, in_review, approved, rejected, challenged, edited]}
```
```yaml
  Agent Notes:        {domain: sources, level: 4, parent: [Areas], default_parent: Agent notes, builtin: true, optional: [about, executed_by]}
```

with

```yaml
  Content:            {domain: marketing, level: 4, parent: [Campaigns, Brands, Areas], default_parent: Content, optional: [owner, about, when], statuses: [draft, approved, published]}
```
```yaml
  Requirements:       {domain: product, level: 3, parent: [Models, Products, Projects, Areas], default_parent: Requirements, optional: [product, owner, evidence], statuses: [proposed, in_review, approved, rejected, challenged, edited]}
```
```yaml
  Agent Notes:        {domain: sources, level: 4, parent: [Brands, Projects, Agents, Areas], default_parent: Agent notes, builtin: true, optional: [about, executed_by]}
```

After the `Requirements:` line add:

```yaml
  Ideas:              {domain: product, level: 3, parent: [Areas], default_parent: Roadmap, optional: [owner, product], statuses: [pending_approval, active, done, rejected]}
```

After the `Agent Notes:` line add:

```yaml
  Discourse:          {domain: sources, level: 4, parent: [Areas], default_parent: Discourse, optional: [about]}
```

At the end of the `types:` block (after `Assumptions:`) add:

```yaml
  # index notes kept by a curator; their domain is the domain of their parent area
  Hubs:               {domain: "*", level: 3, parent: [Areas]}
```

- [ ] **Step 4: Teach `model._check` the `*` domain**

In `schema/ehl_schema/model.py` `_check`, replace

```python
        if td.domain not in schema.domains:
            errors.append(f"type {name!r}: unknown domain {td.domain!r}")
```

with

```python
        if td.domain == "*":
            if td.parent != ("Areas",):
                errors.append(f"type {name!r}: an index type (domain '*') must have parent [Areas] only")
        elif td.domain not in schema.domains:
            errors.append(f"type {name!r}: unknown domain {td.domain!r}")
```

- [ ] **Step 5: Skip index types in notes.json, show them in the rules table**

In `schema/ehl_schema/build.py` `notes_json`, replace

```python
        if name in STRUCTURE_TYPES or (td.builtin and name not in by_type):
```

with

```python
        if name in STRUCTURE_TYPES or td.domain == "*" or (td.builtin and name not in by_type):
```

In `rules_body`, replace

```python
        lines.append(f"| {name} | {td.domain} | {td.level} | {', '.join(td.parent)} | {td.default_parent or ''} | "
```

with

```python
        domain = "from its parent area" if td.domain == "*" else td.domain
        lines.append(f"| {name} | {domain} | {td.level} | {', '.join(td.parent)} | {td.default_parent or ''} | "
```

- [ ] **Step 6: Make migrate leave index types alone**

In `schema/ehl_schema/migrate.py` `plan`, replace

```python
        if tname is None:
            report.unmapped.append(path)
```

with

```python
        if tname is None or schema.types[tname].domain == "*":
            report.unmapped.append(path)
```

- [ ] **Step 7: Run the whole schema suite**

Run: `cd schema && py -3.12 -m pytest -q`
Expected: all PASS (the existing `len(notes) == 1 + len(schema.domains) + len(schema.areas) + 1` still holds).

- [ ] **Step 8: Commit**

```bash
cd C:/Users/User/Desktop/ehl-munich-2026
git add schema/vault-schema.yaml schema/ehl_schema/model.py schema/ehl_schema/build.py schema/ehl_schema/migrate.py schema/tests/test_model.py schema/tests/test_build.py schema/tests/test_migrate.py
ENTIRE_TEST_TTY=0 git commit -m "feat(schema): Ideas, Discourse and Hubs types, Discourse area, wider parents

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Profiles and path patterns

**Files:**
- Create: `schema/ehl_schema/profile.py`
- Create: `schema/profiles/vibemind.yaml`
- Test: `schema/tests/test_profile.py`

**Interfaces:**
- Consumes: `load_schema`, `Schema`, `SchemaError`, `STRUCTURE_TYPES`, `DEFAULT_SCHEMA` from `ehl_schema.model`.
- Produces:
  - `compile_pattern(pattern: str) -> re.Pattern[str]` (use with `.fullmatch`)
  - `@dataclass(frozen=True) class Rule: match: str; type: str; parent: str | None; regex: re.Pattern[str]`
  - `@dataclass(frozen=True) class Profile: company: str; rules: tuple[Rule, ...] = (); exclude: tuple[re.Pattern[str], ...] = (); name: str = "default"; exclude_raw: tuple[str, ...] = ()`
    with methods `excludes(path: str) -> bool`, `match(path: str) -> tuple[Rule, dict[str, str]] | None`,
    `has_rules -> bool` (property: rules or exclude present)
  - `default_profile(company: str) -> Profile`
  - `PROFILES_DIR: Path` (= `schema/profiles`)
  - `load_profile(ref: str, schema: Schema) -> Profile` (`ref` = a name in `PROFILES_DIR` or a path to a .yaml file)

- [ ] **Step 1: Write the failing tests**

Create `schema/tests/test_profile.py`:

```python
"""Checks for ehl_schema.profile."""
import pytest

from ehl_schema.model import SchemaError, load_schema
from ehl_schema.profile import PROFILES_DIR, compile_pattern, default_profile, load_profile


@pytest.fixture
def schema():
    return load_schema()


def fits(pattern, path):
    return compile_pattern(pattern).fullmatch(path) is not None


def test_star_stays_inside_one_segment():
    assert fits("Projects/*", "Projects/E-Ticketing")
    assert not fits("Projects/*", "Projects/A/_overview")
    assert fits("Notes/Traction Metrics*", "Notes/Traction Metrics 2026-Q2")


def test_double_star_spans_one_or_more_segments():
    assert fits("Diary/**", "Diary/Blue Rose Diary")
    assert fits("vibemind-discourse/**", "vibemind-discourse/2026-04-30/04-07")
    assert not fits("Diary/**", "Diary")


def test_captures_and_special_characters():
    m = compile_pattern("Projects/{p}/_overview").fullmatch("Projects/VibeMind - LinkedIn Launch — Beta (c1c67f)/_overview")
    assert m.group("p") == "VibeMind - LinkedIn Launch — Beta (c1c67f)"
    assert fits("Bubbles/**", "Bubbles/Grüne Idee (fa8d41)")
    assert fits("Projects/VibeMind - TODO */_overview", "Projects/VibeMind - TODO Tech-Stack (z. B. OAuth2)/_overview")
    assert not fits("Notes/a.b", "Notes/aXb")             # the dot is literal


def test_bad_patterns_are_rejected():
    for bad in ("Projects/{p", "Projects/a**b", "Projects/{p}/{p}"):
        with pytest.raises(SchemaError):
            compile_pattern(bad)


def test_vibemind_profile_loads_and_first_rule_wins(schema):
    profile = load_profile("vibemind", schema)
    assert profile.company == "VibeMind"
    assert profile.name == "vibemind"
    rule, caps = profile.match("Projects/VibeMind - TODO Tests/_overview")
    assert rule.type == "Tasks"
    rule, caps = profile.match("Projects/VibeMind - Shop/Payment Flow")
    assert (rule.type, rule.parent, caps) == ("Requirements", "Projects/{p}/_overview", {"p": "VibeMind - Shop"})
    assert profile.match("Agents/abo-probe (183dc8)") is None   # left to the default rule
    assert profile.excludes("Diary/Blue Rose Diary")
    assert profile.excludes("Welcome")
    assert not profile.excludes("Topics/AI")
    assert profile.has_rules


def test_default_profile_has_no_rules():
    profile = default_profile("EHL")
    assert (profile.company, profile.rules, profile.exclude, profile.has_rules) == ("EHL", (), (), False)


def write_profile(tmp_path, text):
    path = tmp_path / "p.yaml"
    path.write_text(text, encoding="utf-8", newline="\n")
    return str(path)


def test_profile_errors(tmp_path, schema):
    cases = {
        "unknown type": "company: X\nrules:\n  - {match: 'A/**', type: Nope}\n",
        "structure type": "company: X\nrules:\n  - {match: 'A/**', type: Areas}\n",
        "unknown capture": "company: X\nrules:\n  - {match: 'A/*', type: Topics, parent: 'B/{q}'}\n",
        "no company": "rules: []\n",
    }
    for text in cases.values():
        with pytest.raises(SchemaError):
            load_profile(write_profile(tmp_path, text), schema)
    with pytest.raises(SchemaError, match="no profile"):
        load_profile("does-not-exist", schema)
    assert (PROFILES_DIR / "vibemind.yaml").is_file()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd schema && py -3.12 -m pytest -q tests/test_profile.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'ehl_schema.profile'`.

- [ ] **Step 3: Write `profile.py`**

Create `schema/ehl_schema/profile.py`:

```python
"""Vault profiles: company name, excluded paths and folder rules (path pattern -> note type).

Pattern syntax (paths are vault-relative, without ".md"): `*` matches inside one segment, `**` matches one or
more whole segments, `{name}` captures one whole segment for use in a rule's `parent`. Case-sensitive.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .model import DEFAULT_SCHEMA, STRUCTURE_TYPES, Schema, SchemaError

PROFILES_DIR = DEFAULT_SCHEMA.parent / "profiles"
CAPTURE = re.compile(r"\{(\w+)\}")


def compile_pattern(pattern: str) -> re.Pattern[str]:
    parts = []
    for part in pattern.split("/"):
        whole = CAPTURE.fullmatch(part)
        if part == "**":
            parts.append(r"[^/]+(?:/[^/]+)*")
        elif whole:
            parts.append(f"(?P<{whole.group(1)}>[^/]+)")
        elif "{" in part or "}" in part or "**" in part or not part:
            raise SchemaError(f"bad path pattern {pattern!r}: {part!r}")
        else:
            parts.append("[^/]*".join(re.escape(s) for s in part.split("*")))
    try:
        return re.compile("/".join(parts))
    except re.error as err:  # e.g. the same capture twice
        raise SchemaError(f"bad path pattern {pattern!r}: {err}") from err


@dataclass(frozen=True)
class Rule:
    match: str
    type: str
    parent: str | None
    regex: re.Pattern[str]


@dataclass(frozen=True)
class Profile:
    company: str
    rules: tuple[Rule, ...] = ()
    exclude: tuple[re.Pattern[str], ...] = ()
    name: str = "default"
    exclude_raw: tuple[str, ...] = ()   # the exclude patterns as written, for the rules note

    @property
    def has_rules(self) -> bool:
        return bool(self.rules or self.exclude)

    def excludes(self, path: str) -> bool:
        return any(p.fullmatch(path) for p in self.exclude)

    def match(self, path: str) -> tuple[Rule, dict[str, str]] | None:
        for rule in self.rules:
            m = rule.regex.fullmatch(path)
            if m:
                return rule, m.groupdict()
        return None


def default_profile(company: str) -> Profile:
    """Every note lives in the folder of its type (the EHL vault)."""
    return Profile(company)


def _rule(raw: object, schema: Schema) -> Rule:
    if not isinstance(raw, dict) or not isinstance(raw.get("match"), str) or not isinstance(raw.get("type"), str):
        raise SchemaError(f"rule {raw!r}: needs 'match' and 'type'")
    tname, parent = raw["type"], raw.get("parent")
    if tname not in schema.types or tname in STRUCTURE_TYPES:
        raise SchemaError(f"rule {raw['match']!r}: {tname!r} is not a note type of the schema")
    regex = compile_pattern(raw["match"])
    if parent is not None:
        if not isinstance(parent, str):
            raise SchemaError(f"rule {raw['match']!r}: parent must be a path")
        unknown = set(CAPTURE.findall(parent)) - set(regex.groupindex)
        if unknown:
            raise SchemaError(f"rule {raw['match']!r}: parent uses {sorted(unknown)} not captured in match")
    return Rule(raw["match"], tname, parent, regex)


def load_profile(ref: str, schema: Schema) -> Profile:
    path = Path(ref) if ref.endswith((".yaml", ".yml")) else PROFILES_DIR / f"{ref}.yaml"
    if not path.is_file():
        raise SchemaError(f"no profile {ref!r} (looked for {path})")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("company"), str) or not raw["company"].strip():
        raise SchemaError(f"{path}: a profile needs 'company'")
    rules = tuple(_rule(r, schema) for r in raw.get("rules") or [])
    exclude_raw = tuple(str(p) for p in raw.get("exclude") or [])
    exclude = tuple(compile_pattern(p) for p in exclude_raw)
    return Profile(raw["company"].strip(), rules, exclude, path.stem, exclude_raw)
```

- [ ] **Step 4: Write the VibeMind profile**

Create `schema/profiles/vibemind.yaml`:

```yaml
# VibeMind vault (~/.rowboat/knowledge). Spec: docs/superpowers/specs/2026-10-13-vault-folder-rules-design.md
# First matching rule wins. Paths are vault-relative, without ".md". Notes no rule matches fall back to the
# default rule (first folder = type name, e.g. Agents/**, Workflows/**, Topics/**, People/**).
company: VibeMind
exclude:                     # never in the map, no warning
  - "Diary/**"
  - "Bewerbung/**"
  - "Welcome"                # Rowboat's own welcome note
rules:
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
```

- [ ] **Step 5: Run the tests**

Run: `cd schema && py -3.12 -m pytest -q tests/test_profile.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/User/Desktop/ehl-munich-2026
git add schema/ehl_schema/profile.py schema/profiles/vibemind.yaml schema/tests/test_profile.py
ENTIRE_TEST_TTY=0 git commit -m "feat(schema): vault profiles with folder rules, VibeMind profile

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Resolve every note to a placement

**Files:**
- Create: `schema/ehl_schema/issues.py`
- Create: `schema/ehl_schema/placement.py`
- Modify: `schema/ehl_schema/lint.py:15-24` (move `Issue` out, re-export)
- Modify: `schema/tests/helpers.py` (add `vibemind_like_vault`)
- Test: `schema/tests/test_placement.py`

**Interfaces:**
- Consumes: `Profile`, `load_profile`, `default_profile` (Task 2); `Note`, `read_vault`, `parent_target` from `ehl_schema.notes`.
- Produces:
  - `ehl_schema.issues.Issue(severity: str, path: str, code: str, message: str)` (frozen dataclass; `ehl_schema.lint.Issue` stays importable)
  - `@dataclass(frozen=True) class Placement: type: str; level: int; domain: str; parent: str | None; source: str` (`source` ∈ `"front"`, `"rule"`, `"default"`, `"fallback"`)
  - `@dataclass class Resolution: placements: dict[str, Placement]; excluded: list[str]; issues: list[Issue]`
  - `resolve(schema: Schema, profile: Profile, notes: dict[str, Note]) -> Resolution`
  - `helpers.vibemind_like_vault(tmp_path: Path, schema) -> Path` (returns the `knowledge` folder; structure notes written with company "TestCo")

- [ ] **Step 1: Move `Issue` into its own module**

Create `schema/ehl_schema/issues.py`:

```python
"""One finding about a note: lint errors and warnings, and the resolver's warnings."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    severity: str   # "error" | "warning"
    path: str
    code: str
    message: str
```

In `schema/ehl_schema/lint.py` delete the `Issue` class (lines 15-20 including the `@dataclass(frozen=True)` line) and
change the imports to:

```python
from .issues import Issue
from .model import Schema, TypeDef
from .notes import DATE, Note, link_value, links, parent_target, read_vault
```

Remove `from dataclasses import dataclass` from `lint.py` if nothing else uses it.

Run: `cd schema && py -3.12 -m pytest -q`
Expected: PASS (pure move).

- [ ] **Step 2: Add the fixture vault helper**

Append to `schema/tests/helpers.py`:

```python
CURATOR_FRONT = ("---\ntyp: agent\nid: 0000\ntitel: {name}\nfakten:\n- schluessel: zustand\n  wert: Running\n"
                 "  beleg: 1\n---\n# {name}\n")


def write_raw(vault: Path, path: str, text: str) -> None:
    file = vault / f"{path}.md"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding="utf-8", newline="\n")


def vibemind_like_vault(tmp_path: Path, schema) -> Path:
    """A small vault laid out like the VibeMind vault. All names and texts are made up."""
    from ehl_schema.build import write_structure
    from ehl_schema.profile import load_profile

    vault = tmp_path / "knowledge"
    write_structure(schema, vault, "TestCo", load_profile("vibemind", schema))
    write_raw(vault, "Agents/alpha-bot (abc123)", CURATOR_FRONT.format(name="alpha-bot"))
    write_raw(vault, "Agents/Veraltet/old-bot (def456)", CURATOR_FRONT.format(name="old-bot"))
    write_raw(vault, "Bubbles/Green Idea — Beta (fa8d41)", CURATOR_FRONT.format(name="Green Idea"))
    write_raw(vault, "Hubs/Agents", "# Agents\n\n- [[alpha-bot (abc123)]]\n")
    write_raw(vault, "Hubs/Misc", "# Misc\n")
    write_raw(vault, "Projects/Demo Root", "# Demo Root\n")
    write_raw(vault, "Projects/TestCo - Shop/_overview", "---\nidea_id: x1\ntitle: null\ntags: []\n---\n# Shop\n")
    write_raw(vault, "Projects/TestCo - Shop/Payment Flow", "# Payment Flow\n")
    write_raw(vault, "Projects/VibeMind - TODO Write tests (z. B. unit)/_overview", "# TODO\n")
    write_raw(vault, "Projects/TestCo - Orphan/Lonely", "# Lonely\n")   # project folder without _overview
    write_raw(vault, "companys/Acme Brand/Marke", "# Marke\n")
    write_raw(vault, "companys/Acme Brand/Markenhandbuch", "# Handbuch\n")
    write_raw(vault, "companys/Acme Brand/Marke-Verlauf/2026-01-01 v1", "# v1\n")
    write_raw(vault, "companys/Acme Brand/Agent-Notizen/2026-01-02 hint", "# hint\n")
    write_raw(vault, "vibemind-discourse/2026-01-01/04-07", "# Discourse\n")
    write_raw(vault, "Videos/Demo Clip", "# Clip\n")
    write_raw(vault, "System/PC (system)", CURATOR_FRONT.format(name="PC"))
    write_raw(vault, "Notes/Traction Metrics 2026-Q1", "# Traction\n")
    write_raw(vault, "Notes/Random", "# Random\n")
    write_raw(vault, "Investor Programs/Grant X/Questions", "# Questions\n")
    write_raw(vault, "Coding-Projects/tool-a", "---\ntype: coding-project\n---\n# tool-a\n")
    write_raw(vault, "Workflows/flow-a", "# flow\n")
    write_raw(vault, "Topics/AI", "# AI\n")
    write_raw(vault, "People/Jane Doe", "# Jane Doe\n")
    write_raw(vault, "People/Design Partners/Partner Co", "# Partner Co\n")
    write_raw(vault, "Strange Folder/thing", "# thing\n")
    write_raw(vault, "Diary/Secret", "# private\n")
    write_raw(vault, "Bewerbung/Firm/Letter", "# private\n")
    write_raw(vault, "Welcome", "# Welcome\n")
    return vault
```

- [ ] **Step 3: Write the failing tests**

Create `schema/tests/test_placement.py`:

```python
"""Checks for ehl_schema.placement."""
import pytest
from helpers import valid_vault, vibemind_like_vault

from ehl_schema.model import load_schema
from ehl_schema.notes import read_vault
from ehl_schema.placement import Placement, resolve
from ehl_schema.profile import default_profile, load_profile


@pytest.fixture
def schema():
    return load_schema()


@pytest.fixture
def resolution(tmp_path, schema):
    notes, _ = read_vault(vibemind_like_vault(tmp_path, schema))
    return resolve(schema, load_profile("vibemind", schema), notes)


EXPECTED = {
    "Agents/alpha-bot (abc123)": ("Agents", 3, "ai", "Areas/Agents", "default"),
    "Agents/Veraltet/old-bot (def456)": ("Agents", 3, "ai", "Areas/Agents", "default"),
    "Bubbles/Green Idea — Beta (fa8d41)": ("Ideas", 3, "product", "Areas/Roadmap", "rule"),
    "Hubs/Agents": ("Hubs", 3, "ai", "Areas/Agents", "rule"),
    "Hubs/Misc": ("Hubs", 3, "knowledge", "Areas/Topics", "rule"),
    "Projects/Demo Root": ("Projects", 3, "delivery", "Areas/Client projects", "rule"),
    "Projects/TestCo - Shop/_overview": ("Projects", 3, "delivery", "Areas/Client projects", "rule"),
    "Projects/TestCo - Shop/Payment Flow": ("Requirements", 3, "product", "Projects/TestCo - Shop/_overview", "rule"),
    "Projects/VibeMind - TODO Write tests (z. B. unit)/_overview": ("Tasks", 4, "delivery", "Areas/Milestones", "rule"),
    "Projects/TestCo - Orphan/Lonely": ("Requirements", 3, "product", "Areas/Requirements", "rule"),
    "companys/Acme Brand/Marke": ("Brands", 3, "marketing", "Areas/Brand", "rule"),
    "companys/Acme Brand/Markenhandbuch": ("Content", 4, "marketing", "companys/Acme Brand/Marke", "rule"),
    "companys/Acme Brand/Marke-Verlauf/2026-01-01 v1": ("Content", 4, "marketing", "companys/Acme Brand/Marke", "rule"),
    "companys/Acme Brand/Agent-Notizen/2026-01-02 hint": ("Agent Notes", 4, "sources", "companys/Acme Brand/Marke", "rule"),
    "vibemind-discourse/2026-01-01/04-07": ("Discourse", 4, "sources", "Areas/Discourse", "rule"),
    "Videos/Demo Clip": ("Assets", 4, "marketing", "Areas/Content", "rule"),
    "System/PC (system)": ("Systems", 3, "operations", "Areas/Infrastructure", "rule"),
    "Notes/Traction Metrics 2026-Q1": ("KPIs", 3, "strategy", "Areas/KPIs", "rule"),
    "Notes/Random": ("Topics", 3, "knowledge", "Areas/Topics", "rule"),
    "Investor Programs/Grant X/Questions": ("Funding", 3, "finance", "Areas/Funding", "rule"),
    "Coding-Projects/tool-a": ("Projects", 3, "delivery", "Areas/Client projects", "rule"),
    "Workflows/flow-a": ("Workflows", 3, "ai", "Areas/Workflows", "default"),
    "Topics/AI": ("Topics", 3, "knowledge", "Areas/Topics", "default"),
    "People/Jane Doe": ("People", 3, "register", "Areas/Contacts", "default"),
    "People/Design Partners/Partner Co": ("People", 3, "register", "Areas/Contacts", "default"),
    "Strange Folder/thing": ("Topics", 3, "knowledge", "Areas/Topics", "fallback"),
}


def test_every_vibemind_note_is_placed(resolution):
    for path, (tname, level, domain, parent, source) in EXPECTED.items():
        assert resolution.placements[path] == Placement(tname, level, domain, parent, source), path


def test_private_notes_are_excluded(resolution):
    assert sorted(resolution.excluded) == ["Bewerbung/Firm/Letter", "Diary/Secret", "Welcome"]
    assert not any(p in resolution.placements for p in resolution.excluded)


def test_structure_notes_come_from_their_front_matter(resolution):
    assert resolution.placements["Company"] == Placement("Company", 0, "company", None, "front")
    assert resolution.placements["Areas/Agents"] == Placement("Areas", 2, "ai", "Domains/AI & agents", "front")


def test_warnings(resolution):
    found = {(i.severity, i.path, i.code) for i in resolution.issues}
    assert found == {
        ("warning", "Strange Folder/thing", "no-rule"),
        ("warning", "Projects/TestCo - Orphan/Lonely", "rule-parent-missing"),
    }


def test_ehl_vault_with_default_profile_uses_front_matter_only(tmp_path, schema):
    notes, _ = read_vault(valid_vault(tmp_path, schema))
    res = resolve(schema, default_profile("EHL"), notes)
    assert {p.source for p in res.placements.values()} == {"front"}
    assert res.placements["Deals/Acme deal"] == Placement("Deals", 3, "sales", "Areas/Pipeline", "front")
    assert res.issues == [] and res.excluded == []
```

- [ ] **Step 4: Run them to verify they fail**

Run: `cd schema && py -3.12 -m pytest -q tests/test_placement.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'ehl_schema.placement'`.

- [ ] **Step 5: Write `placement.py`**

Create `schema/ehl_schema/placement.py`:

```python
"""Where every note sits in the hierarchy: from its own front matter, a profile rule, the default rule
(first folder = type) or the fallback (Topics). Reads notes only; never writes."""
from __future__ import annotations

from dataclasses import dataclass, field

from .issues import Issue
from .model import STRUCTURE_TYPES, Schema
from .notes import Note, parent_target
from .profile import Profile

FALLBACK_TYPE = "Topics"


@dataclass(frozen=True)
class Placement:
    type: str
    level: int
    domain: str
    parent: str | None   # vault-relative path without ".md"; None only for the Company note
    source: str          # "front" | "rule" | "default" | "fallback"


@dataclass
class Resolution:
    placements: dict[str, Placement] = field(default_factory=dict)
    excluded: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


def _from_front(schema: Schema, note: Note) -> Placement | None:
    front = note.front or {}
    tname = front.get("type")
    if not isinstance(tname, str) or tname not in schema.types:
        return None
    td = schema.types[tname]
    level = front.get("level") if isinstance(front.get("level"), int) else td.level
    domain = str(front.get("domain") or td.domain)
    return Placement(tname, level, domain, parent_target(note), "front")


def _area_domain(schema: Schema, parent: str) -> str:
    folder, _, name = parent.partition("/")
    return schema.areas.get(name, "knowledge") if folder == "Areas" else "knowledge"


def resolve(schema: Schema, profile: Profile, notes: dict[str, Note]) -> Resolution:
    res = Resolution()
    pending: dict[str, tuple[str, str | None, str]] = {}
    for path in sorted(notes):
        if profile.excludes(path):
            res.excluded.append(path)
            continue
        placed = _from_front(schema, notes[path])
        if placed is not None:
            res.placements[path] = placed
            continue
        hit = profile.match(path)
        folder, sep, _ = path.partition("/")
        if hit is not None:
            rule, captures = hit
            parent = rule.parent.format_map(captures) if rule.parent else None
            pending[path] = (rule.type, parent, "rule")
        elif sep and folder in schema.types and folder not in STRUCTURE_TYPES:
            pending[path] = (folder, None, "default")
        else:
            pending[path] = (FALLBACK_TYPE, None, "fallback")
            res.issues.append(Issue("warning", path, "no-rule",
                                    f"no folder rule for this path; placed under Areas/{FALLBACK_TYPE}"))
    for path, (tname, parent, source) in pending.items():
        td = schema.types[tname]
        if parent is not None and (parent not in notes or profile.excludes(parent)):
            res.issues.append(Issue("warning", path, "rule-parent-missing",
                                    f"rule parent [[{parent}]] does not exist; placed under its default area"))
            parent = None
        if parent is None:
            parent = schema.area_note(td.default_parent or FALLBACK_TYPE)
        domain = _area_domain(schema, parent) if td.domain == "*" else td.domain
        res.placements[path] = Placement(tname, td.level, domain, parent, source)
    return res
```

Note on `Projects/TestCo - Orphan/Lonely`: rule 3 (`Projects/{p}/**`) matches, its parent
`Projects/TestCo - Orphan/_overview` does not exist → warning + default area `Areas/Requirements`. Rule 1 and 2 do
not match because the note is not `_overview`.

- [ ] **Step 6: Run the tests**

Run: `cd schema && py -3.12 -m pytest -q`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
cd C:/Users/User/Desktop/ehl-munich-2026
git add schema/ehl_schema/issues.py schema/ehl_schema/placement.py schema/ehl_schema/lint.py schema/tests/helpers.py schema/tests/test_placement.py
ENTIRE_TEST_TTY=0 git commit -m "feat(schema): resolve every note to a placement from front matter or folder rules

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `map` command – structure notes, rules note section, `vault-map.json`

**Files:**
- Create: `schema/ehl_schema/vaultmap.py`
- Modify: `schema/ehl_schema/build.py` (`structure_notes`, `rules_body`, `write_structure`, `build` take an optional profile)
- Modify: `schema/ehl_schema/cli.py` (new `map` command; `--profile` on build/lint/map; `--company` default None)
- Test: `schema/tests/test_vaultmap.py`, `schema/tests/test_cli.py`

**Interfaces:**
- Consumes: `resolve`, `Resolution`, `Placement` (Task 3); `Profile`, `load_profile`, `default_profile` (Task 2).
- Produces:
  - `build.structure_notes(schema, company, profile: Profile | None = None) -> dict[str, str]`
  - `build.write_structure(schema, vault, company, profile: Profile | None = None) -> int`
  - `build.build(schema, workdir, company, profile: Profile | None = None) -> dict`
  - `vaultmap.MAP_FILE = Path("config") / "vault-map.json"`
  - `vaultmap.map_document(company: str, res: Resolution) -> dict` (keys `version`, `company`, `generated_at`, `notes`)
  - `vaultmap.write_map(workdir: Path, doc: dict) -> bool` (True if written; ignores `generated_at` when comparing)
  - `@dataclass class MapResult: structure: int; notes: int; excluded: int; issues: list[Issue]; written: bool`
  - `vaultmap.run_map(schema, profile, workdir) -> MapResult`
  - CLI: `python -m ehl_schema.cli map --workdir W [--profile NAME] [--company NAME] [--watch SECONDS]`

- [ ] **Step 1: Write the failing tests**

Create `schema/tests/test_vaultmap.py`:

```python
"""Checks for ehl_schema.vaultmap and the profile-aware rules note."""
import json

import pytest
from helpers import vibemind_like_vault, write_raw

from ehl_schema.build import RULES_NOTE, structure_notes
from ehl_schema.model import load_schema
from ehl_schema.profile import default_profile, load_profile
from ehl_schema.vaultmap import MAP_FILE, run_map


@pytest.fixture
def schema():
    return load_schema()


@pytest.fixture
def workdir(tmp_path, schema):
    vibemind_like_vault(tmp_path, schema)
    return tmp_path


def test_map_lists_every_placed_note(workdir, schema):
    result = run_map(schema, load_profile("vibemind", schema), workdir)
    doc = json.loads((workdir / MAP_FILE).read_text(encoding="utf-8"))
    assert (doc["version"], doc["company"]) == (1, "VibeMind")
    assert doc["notes"]["Hubs/Agents"] == {"type": "Hubs", "level": 3, "domain": "ai", "parent": "Areas/Agents"}
    assert doc["notes"]["Company"] == {"type": "Company", "level": 0, "domain": "company", "parent": None}
    assert "Diary/Secret" not in doc["notes"]
    assert result.excluded == 3 and result.written
    assert result.notes == len(doc["notes"])


def test_existing_notes_are_never_touched(workdir, schema):
    vault = workdir / "knowledge"
    before = {p: p.read_bytes() for p in vault.rglob("*.md") if not p.relative_to(vault).parts[0] in ("Areas", "Domains")
              and p.name != "Company.md" and p.relative_to(vault).as_posix() != f"{RULES_NOTE}.md"}
    run_map(schema, load_profile("vibemind", schema), workdir)
    assert {p: p.read_bytes() for p in before} == before


def test_unchanged_map_is_not_rewritten(workdir, schema):
    profile = load_profile("vibemind", schema)
    assert run_map(schema, profile, workdir).written
    stamp = (workdir / MAP_FILE).stat().st_mtime_ns
    second = run_map(schema, profile, workdir)
    assert not second.written and second.structure == 0
    assert (workdir / MAP_FILE).stat().st_mtime_ns == stamp
    write_raw(workdir / "knowledge", "Agents/new-bot (999999)", "# new\n")
    assert run_map(schema, profile, workdir).written


def test_company_comes_from_the_profile(workdir, schema):
    run_map(schema, load_profile("vibemind", schema), workdir)
    assert "# VibeMind" in (workdir / "knowledge" / "Company.md").read_text(encoding="utf-8")


def test_rules_note_lists_the_folders_only_for_profiles_with_rules(schema):
    with_rules = structure_notes(schema, "VibeMind", load_profile("vibemind", schema))[RULES_NOTE]
    assert "## Folders in this vault" in with_rules
    assert "| `companys/{c}/Marke` | Brands |" in with_rules
    assert "Diary/**" in with_rules
    plain = structure_notes(schema, "EHL", default_profile("EHL"))[RULES_NOTE]
    assert plain == structure_notes(schema, "EHL")[RULES_NOTE]
    assert "Folders in this vault" not in plain
```

Append to `schema/tests/test_cli.py`:

```python
def test_map_and_lint_with_profile(tmp_path):
    from helpers import vibemind_like_vault
    from ehl_schema.model import load_schema

    vibemind_like_vault(tmp_path, load_schema())
    assert main(["map", "--workdir", str(tmp_path), "--profile", "vibemind"]) == 0
    assert (tmp_path / "config" / "vault-map.json").is_file()
    assert main(["map", "--workdir", str(tmp_path), "--profile", "nope"]) == 2


def test_map_without_profile_keeps_the_company(tmp_path):
    (tmp_path / "knowledge").mkdir()
    assert main(["map", "--workdir", str(tmp_path), "--company", "EHL"]) == 0
    assert "# EHL" in (tmp_path / "knowledge" / "Company.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd schema && py -3.12 -m pytest -q tests/test_vaultmap.py tests/test_cli.py`
Expected: FAIL (`No module named 'ehl_schema.vaultmap'`; `invalid choice: 'map'`).

- [ ] **Step 3: Make build profile-aware**

In `schema/ehl_schema/build.py`:

Add the import `from .profile import Profile`.

Change `structure_notes` signature and the rules note call:

```python
def structure_notes(schema: Schema, company: str, profile: Profile | None = None) -> dict[str, str]:
```

```python
        rules_body(schema, profile))
```

Change `rules_body`:

```python
def rules_body(schema: Schema, profile: Profile | None = None) -> str:
```

and replace its final `return` line with:

```python
    if profile is not None and profile.has_rules:
        lines += ["", "## Folders in this vault", "",
                  f"This vault ({profile.company}) keeps its own folders. A new note goes into the folder whose rule "
                  "gives the type you need; the first matching rule wins. `*` is any text inside one folder name, "
                  "`**` any sub-path, `{x}` one folder name.", "",
                  "| Path pattern | Type | Parent |", "|---|---|---|"]
        for rule in profile.rules:
            lines.append(f"| `{rule.match}` | {rule.type} | {rule.parent or 'default area of the type'} |")
        lines.append("| any other `<Type>/…` | the folder name | default area of the type |")
        if profile.exclude_raw:
            lines += ["", "Private, not part of the team graph: "
                      + ", ".join(f"`{p}`" for p in profile.exclude_raw) + "."]
    return "\n".join(lines) + "\n"
```

Change `write_structure` and `build`:

```python
def write_structure(schema: Schema, vault: Path, company: str, profile: Profile | None = None) -> int:
    written = 0
    for path, text in structure_notes(schema, company, profile).items():
```

```python
def build(schema: Schema, workdir: Path, company: str, profile: Profile | None = None) -> dict:
    written = write_structure(schema, workdir / "knowledge", company, profile)
```

- [ ] **Step 4: Write `vaultmap.py`**

Create `schema/ehl_schema/vaultmap.py`:

```python
"""config/vault-map.json: the resolved hierarchy of every note, read by Rowboat's brain graph as a fallback for
notes without hierarchy front matter. Spec: docs/superpowers/specs/2026-10-13-vault-folder-rules-design.md §6."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .build import write_structure
from .issues import Issue
from .model import Schema
from .notes import read_vault
from .placement import Resolution, resolve
from .profile import Profile

log = logging.getLogger("ehl_schema.vaultmap")

MAP_FILE = Path("config") / "vault-map.json"
MAP_VERSION = 1


@dataclass
class MapResult:
    structure: int
    notes: int
    excluded: int
    issues: list[Issue]
    written: bool


def map_document(company: str, res: Resolution) -> dict:
    notes = {path: {"type": p.type, "level": p.level, "domain": p.domain, "parent": p.parent}
             for path, p in sorted(res.placements.items())}
    return {"version": MAP_VERSION, "company": company,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "notes": notes}


def _same(old_text: str, doc: dict) -> bool:
    try:
        old = json.loads(old_text)
    except json.JSONDecodeError:
        return False
    if not isinstance(old, dict):
        return False
    return {k: v for k, v in old.items() if k != "generated_at"} == {k: v for k, v in doc.items() if k != "generated_at"}


def write_map(workdir: Path, doc: dict) -> bool:
    file = workdir / MAP_FILE
    if file.exists() and _same(file.read_text(encoding="utf-8"), doc):
        return False
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return True


def run_map(schema: Schema, profile: Profile, workdir: Path) -> MapResult:
    vault = workdir / "knowledge"
    structure = write_structure(schema, vault, profile.company, profile)
    notes, _ = read_vault(vault)
    res = resolve(schema, profile, notes)
    written = write_map(workdir, map_document(profile.company, res))
    return MapResult(structure, len(res.placements), len(res.excluded), res.issues, written)
```

- [ ] **Step 5: CLI `map` and `--profile`**

Replace `schema/ehl_schema/cli.py` with:

```python
"""Command line: python -m ehl_schema.cli build|lint|migrate|map --workdir <Rowboat data folder>."""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from .build import build
from .lint import errors, lint
from .migrate import apply, diff, plan
from .model import DEFAULT_SCHEMA, SchemaError, load_schema
from .profile import Profile, default_profile, load_profile
from .vaultmap import run_map

log = logging.getLogger("ehl_schema")


def _profile(args: argparse.Namespace, schema) -> Profile:
    if getattr(args, "profile", None):
        return load_profile(args.profile, schema)
    return default_profile(getattr(args, "company", None) or "Company")


def _map_once(schema, profile: Profile, workdir: Path) -> None:
    result = run_map(schema, profile, workdir)
    for issue in result.issues:
        log.info("%s %s [%s] %s", issue.severity.upper(), issue.path, issue.code, issue.message)
    log.info("map: %d note(s) placed, %d excluded, %d structure note(s) written, vault-map.json %s",
             result.notes, result.excluded, result.structure, "updated" if result.written else "unchanged")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(prog="ehl-schema", description="Vault schema: build, lint, migrate, map")
    ap.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="schema file (default: schema/vault-schema.yaml)")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, text in (("build", "write structure notes, rules note and notes.json"),
                       ("lint", "check every note"), ("migrate", "add missing front matter (dry run by default)"),
                       ("map", "write structure notes and config/vault-map.json (never edits existing notes)")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--workdir", type=Path, required=True, help="Rowboat data folder, e.g. ~/.rowboat-ehl")
        if name != "migrate":
            p.add_argument("--profile", help="vault profile: a name in schema/profiles or a .yaml path")
    for name in ("build", "map"):
        sub.choices[name].add_argument("--company", default=None,
                                       help="title of the L0 note (default: from the profile, else 'Company')")
    sub.choices["migrate"].add_argument("--write", action="store_true", help="write the changes")
    sub.choices["map"].add_argument("--watch", type=float, default=0,
                                    help="repeat every N seconds until Ctrl+C (0 = once)")
    args = ap.parse_args(argv)

    schema = load_schema(args.schema)
    workdir = args.workdir.expanduser()
    vault = workdir / "knowledge"
    if not vault.is_dir():
        log.error("no vault at %s", vault)
        return 2
    try:
        profile = _profile(args, schema) if args.command != "migrate" else None
    except SchemaError as err:
        log.error("%s", err)
        return 2
    if args.command == "build":
        result = build(schema, workdir, profile.company, profile if args.profile else None)
        log.info("build: %d structure note(s) written, notes.json %s", result["notes"], result["notes_json"])
        return 0
    if args.command == "map":
        while True:
            try:
                _map_once(schema, profile, workdir)
            except OSError as err:  # a writer replaced a file while we read it; the next run catches up
                log.warning("map: %s", err)
            if not args.watch:
                return 0
            try:
                time.sleep(args.watch)
            except KeyboardInterrupt:
                return 0
    if args.command == "lint":
        issues = lint(schema, vault, profile if args.profile else None)
        for issue in issues:
            log.info("%s %s [%s] %s", issue.severity.upper(), issue.path, issue.code, issue.message)
        n_errors = len(errors(issues))
        log.info("lint: %d error(s), %d warning(s)", n_errors, len(issues) - n_errors)
        return 1 if n_errors else 0
    report = plan(schema, vault)
    if args.write:
        log.info("migrate: wrote %d note(s)", apply(report, vault))
    else:
        if report.changes:
            log.info("%s", diff(report))
        log.info("migrate (dry run): %d note(s) would change; add --write to apply", len(report.changes))
    for path in report.unmapped:
        log.warning("unmapped (folder not in the schema): %s", path)
    for path in report.unresolved:
        log.warning("unresolved (no parent found, no default area): %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`lint(schema, vault, profile)` gets its third parameter in Task 5. Until then, add a temporary
`profile=None` parameter to `lint` that is ignored, so this task's tests run:

```python
def lint(schema: Schema, vault: Path, profile=None) -> list[Issue]:
```

- [ ] **Step 6: Run the tests**

Run: `cd schema && py -3.12 -m pytest -q`
Expected: all PASS, including the old `test_build_migrate_lint` (`build --company EHL` still works).

- [ ] **Step 7: Commit**

```bash
cd C:/Users/User/Desktop/ehl-munich-2026
git add schema/ehl_schema/vaultmap.py schema/ehl_schema/build.py schema/ehl_schema/cli.py schema/ehl_schema/lint.py schema/tests/test_vaultmap.py schema/tests/test_cli.py
ENTIRE_TEST_TTY=0 git commit -m "feat(schema): map command writes structure notes and config/vault-map.json

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Lint checks the resolved view when a profile is given

**Files:**
- Modify: `schema/ehl_schema/lint.py`
- Test: `schema/tests/test_lint.py`

**Interfaces:**
- Consumes: `resolve`, `Placement` (Task 3), `Profile` (Task 2), `write_structure` (Task 4).
- Produces: `lint(schema: Schema, vault: Path, profile: Profile | None = None) -> list[Issue]`. With `None` the result
  is byte-for-byte today's behaviour.

- [ ] **Step 1: Write the failing tests**

Append to `schema/tests/test_lint.py`:

```python
from helpers import vibemind_like_vault, write_raw  # noqa: E402

from ehl_schema.profile import load_profile  # noqa: E402


def test_vibemind_vault_lints_clean_except_the_two_warnings(tmp_path, schema):
    vault = vibemind_like_vault(tmp_path, schema)
    issues = lint(schema, vault, load_profile("vibemind", schema))
    assert errors(issues) == []
    assert {(i.path, i.code) for i in issues} == {
        ("Strange Folder/thing", "no-rule"),
        ("Projects/TestCo - Orphan/Lonely", "rule-parent-missing"),
    }


def test_profile_lint_still_reports_broken_yaml_and_cycles(tmp_path, schema):
    vault = vibemind_like_vault(tmp_path, schema)
    write_raw(vault, "Agents/broken", "---\nfoo: [unclosed\n---\n# broken\n")
    write_raw(vault, "Topics/Loop A", '---\nid: a\ntype: Topics\ndomain: knowledge\nlevel: 3\nparent: "[[Topics/Loop B]]"\n---\n')
    write_raw(vault, "Topics/Loop B", '---\nid: b\ntype: Topics\ndomain: knowledge\nlevel: 3\nparent: "[[Topics/Loop A]]"\n---\n')
    found = {(i.path, i.code) for i in errors(lint(schema, vault, load_profile("vibemind", schema)))}
    assert ("Agents/broken", "bad-yaml") in found
    assert any(code == "cycle" for _, code in found)


def test_profile_lint_checks_parent_types_of_placed_notes(tmp_path, schema):
    vault = vibemind_like_vault(tmp_path, schema)
    profile_file = tmp_path / "bad.yaml"
    profile_file.write_text("company: TestCo\nrules:\n  - {match: 'Videos/**', type: Assets, parent: 'Topics/AI'}\n",
                            encoding="utf-8", newline="\n")
    issues = lint(schema, vault, load_profile(str(profile_file), schema))
    assert ("Videos/Demo Clip", "parent-type") in {(i.path, i.code) for i in errors(issues)}


def test_ehl_lint_is_unchanged_without_profile(tmp_path, schema):
    assert lint(schema, valid_vault(tmp_path, schema), None) == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd schema && py -3.12 -m pytest -q tests/test_lint.py`
Expected: FAIL (the profile is still ignored, so `no-front-matter` / `unknown-type` errors appear).

- [ ] **Step 3: Implement profile mode in `lint.py`**

In `schema/ehl_schema/lint.py` add imports:

```python
from collections.abc import Callable

from .placement import Placement, resolve
from .profile import Profile
```

Replace `lint` with:

```python
def lint(schema: Schema, vault: Path, profile: Profile | None = None) -> list[Issue]:
    notes, files = read_vault(vault)
    if profile is None:
        issues: list[Issue] = []
        ids: dict[str, str] = {}
        for note in notes.values():
            issues.extend(_check_note(schema, note, notes, files, ids))
        issues.extend(_check_cycles(notes))
        issues.extend(_check_duplicates(notes))
        return sorted(issues, key=lambda i: (i.path, i.code, i.message))
    res = resolve(schema, profile, notes)
    placed = res.placements

    def type_of(path: str) -> str | None:
        return placed[path].type if path in placed else schema.type_of_path(path)

    issues = list(res.issues)
    ids = {}
    for path, pl in placed.items():
        note = notes[path]
        if pl.source == "front":
            issues.extend(_check_note(schema, note, notes, files, ids, pl.type, type_of))
        elif note.error:
            issues.append(Issue("error", path, "bad-yaml", note.error))
        else:
            issues.extend(_check_placed_parent(schema, path, pl, placed))
    issues.extend(_cycles({p: pl.parent for p, pl in placed.items() if pl.parent}))
    issues.extend(_check_duplicates({p: notes[p] for p in placed}))
    return sorted(issues, key=lambda i: (i.path, i.code, i.message))


def _check_placed_parent(schema: Schema, path: str, pl: Placement, placed: dict[str, Placement]) -> list[Issue]:
    parent = pl.parent
    if parent not in placed:
        return [Issue("error", path, "parent-missing", f"parent [[{parent}]] does not exist")]
    td, ptype = schema.types[pl.type], placed[parent].type
    if ptype not in td.parent:
        return [Issue("error", path, "parent-type", f"parent [[{parent}]] is a {ptype}; allowed: {', '.join(td.parent)}")]
    if placed[parent].level > pl.level:
        return [Issue("error", path, "parent-level", f"parent [[{parent}]] is on a lower level than the note")]
    return []
```

Change `_check_note` to take the type and the type lookup (defaults keep today's behaviour):

```python
def _check_note(schema: Schema, note: Note, notes: dict, files: set, ids: dict,
                tname: str | None = None, type_of: Callable[[str], str | None] | None = None) -> list[Issue]:
    out: list[Issue] = []
    type_of = type_of or schema.type_of_path

    def add(severity: str, code: str, message: str) -> None:
        out.append(Issue(severity, note.path, code, message))

    tname = tname or schema.type_of_path(note.path)
```

(the rest of `_check_note` stays; replace its two calls at the end with)

```python
    if tname != "Company":
        out.extend(_check_parent(schema, note, td, notes, type_of))
    out.extend(_check_relations(schema, note, td, notes, files, type_of))
```

In `_check_note`, the check `if front["type"] != tname:` stays. Change `_check_parent` and `_check_relations`:

```python
def _check_parent(schema: Schema, note: Note, td: TypeDef, notes: dict,
                  type_of: Callable[[str], str | None]) -> list[Issue]:
    target = parent_target(note)
    if target is None:
        return [Issue("error", note.path, "parent-format", 'parent must be one quoted link like "[[Areas/Pipeline]]"')]
    if target not in notes:
        return [Issue("error", note.path, "parent-missing", f"parent [[{target}]] does not exist")]
    ptype = type_of(target)
    if ptype not in td.parent:
        return [Issue("error", note.path, "parent-type",
                      f"parent [[{target}]] is a {ptype}; allowed: {', '.join(td.parent)}")]
    if schema.types[ptype].level > td.level:
        return [Issue("error", note.path, "parent-level", f"parent [[{target}]] is on a lower level than the note")]
    return []
```

```python
def _check_relations(schema: Schema, note: Note, td: TypeDef, notes: dict, files: set,
                     type_of: Callable[[str], str | None]) -> list[Issue]:
```

and inside it replace `schema.type_of_path(target)` with `type_of(target)`.

Split the cycle check so it runs on any parent mapping:

```python
def _check_cycles(notes: dict[str, Note]) -> list[Issue]:
    return _cycles({p: t for p, n in notes.items() if (t := parent_target(n)) is not None})


def _cycles(parent: dict[str, str]) -> list[Issue]:
    out, reported = [], set()
    for start in parent:
        seen, node = [], start
        while node in parent and node not in seen:
            seen.append(node)
            node = parent[node]
        if node in seen:
            cycle = seen[seen.index(node):]
            key = frozenset(cycle)
            if key not in reported:
                reported.add(key)
                out.append(Issue("error", min(cycle), "cycle", "parent chain loops: " + " -> ".join(cycle + [node])))
    return out
```

In the domain check in `_check_note`, `_expected_domain` uses `schema.types[tname].domain`; for `Hubs` with front
matter (not expected in practice) it would compare against `"*"`. Leave it: Hubs are placed by rules, not front matter.

- [ ] **Step 4: Run all schema tests**

Run: `cd schema && py -3.12 -m pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/User/Desktop/ehl-munich-2026
git add schema/ehl_schema/lint.py schema/tests/test_lint.py
ENTIRE_TEST_TTY=0 git commit -m "feat(schema): lint checks the resolved hierarchy when a profile is given

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Brain graph reads `config/vault-map.json` (Rowboat fork)

Work in `C:\Users\User\Desktop\rowboat` on branch `ehl-schema-graph`.

**Files:**
- Modify: `apps/x/apps/renderer/src/lib/graph-hierarchy.ts:140-175`
- Modify: `apps/x/apps/renderer/src/App.tsx:7071` (inside `buildGraph`) and the import on line 90
- Test: `apps/x/apps/renderer/src/lib/graph-hierarchy.test.ts`

**Interfaces:**
- Consumes: the JSON written by Task 4 (`{version: 1, company, generated_at, notes: {path: {type, level, domain, parent}}}`, paths vault-relative without `.md`).
- Produces:
  - `parseVaultMap(text: string, toNodeId: (wikiPath: string) => string | null): Map<string, NodeInfo>` (node id → info; empty map on any problem)
  - `buildHierarchyGraph(contents, nodeSet, toNodeId, fallback?: Map<string, NodeInfo>)` (new optional 4th parameter)

- [ ] **Step 1: Write the failing tests**

In `graph-hierarchy.test.ts`, add `parseVaultMap` to the import from `'./graph-hierarchy'` and append:

```ts
describe('parseVaultMap', () => {
  const toNodeId = (wiki: string) => `knowledge/${wiki}.md`
  const doc = (notes: unknown, version: unknown = 1) => JSON.stringify({ version, company: 'X', notes })

  it('maps note paths to node ids with level, domain and parent', () => {
    const map = parseVaultMap(doc({
      'Agents/a (1)': { type: 'Agents', level: 3, domain: 'ai', parent: 'Areas/Agents' },
      Company: { type: 'Company', level: 0, domain: 'company', parent: null },
    }), toNodeId)
    expect(map.get('knowledge/Agents/a (1).md')).toEqual({ level: 3, domain: 'ai', parentId: 'knowledge/Areas/Agents.md' })
    expect(map.get('knowledge/Company.md')).toEqual({ level: 0, domain: 'company', parentId: undefined })
  })

  it('returns an empty map for broken JSON, a wrong version or a wrong shape', () => {
    expect(parseVaultMap('{nope', toNodeId).size).toBe(0)
    expect(parseVaultMap(doc({}, 2), toNodeId).size).toBe(0)
    expect(parseVaultMap(JSON.stringify([1, 2]), toNodeId).size).toBe(0)
    expect(parseVaultMap(doc({ 'A/b': 'x' }), toNodeId).size).toBe(0)
  })

  it('skips entries whose level is not an integer', () => {
    const map = parseVaultMap(doc({ 'A/b': { level: 'three', domain: 'ai', parent: null } }), toNodeId)
    expect(map.size).toBe(0)
  })
})

describe('buildHierarchyGraph with a vault map', () => {
  const toNodeId = (wiki: string) => `knowledge/${wiki.split('|')[0].split('#')[0].trim()}.md`
  const node = (path: string, data: string) => ({ path: `knowledge/${path}.md`, data })

  it('uses the map for notes without hierarchy front matter and adds the parent edge', () => {
    const contents = [
      node('Areas/Agents', '---\nlevel: 2\ndomain: ai\n---\n'),
      node('Agents/a (1)', '---\ntyp: agent\nfakten:\n- schluessel: zustand\n---\n# a\n'),
    ]
    const nodeSet = new Set(contents.map((c) => c.path))
    const fallback = new Map([['knowledge/Agents/a (1).md', { level: 3, domain: 'ai', parentId: 'knowledge/Areas/Agents.md' }]])
    const { edges, info } = buildHierarchyGraph(contents, nodeSet, toNodeId, fallback)
    expect(info.get('knowledge/Agents/a (1).md')).toEqual({ level: 3, parentId: 'knowledge/Areas/Agents.md', domain: 'ai' })
    expect(edges).toContainEqual({ source: 'knowledge/Agents/a (1).md', target: 'knowledge/Areas/Agents.md', kind: 'parent' })
  })

  it('lets front matter win over the map', () => {
    const contents = [
      node('Areas/Pipeline', '---\nlevel: 2\ndomain: sales\n---\n'),
      node('Areas/Agents', '---\nlevel: 2\ndomain: ai\n---\n'),
      node('Deals/X', '---\nlevel: 3\ndomain: sales\nparent: "[[Areas/Pipeline]]"\n---\n'),
    ]
    const nodeSet = new Set(contents.map((c) => c.path))
    const fallback = new Map([['knowledge/Deals/X.md', { level: 4, domain: 'ai', parentId: 'knowledge/Areas/Agents.md' }]])
    const { edges, info } = buildHierarchyGraph(contents, nodeSet, toNodeId, fallback)
    expect(info.get('knowledge/Deals/X.md')).toEqual({ level: 3, parentId: 'knowledge/Areas/Pipeline.md', domain: 'sales' })
    expect(edges.filter((e) => e.kind === 'parent')).toEqual([
      { source: 'knowledge/Deals/X.md', target: 'knowledge/Areas/Pipeline.md', kind: 'parent' },
    ])
  })

  it('ignores a map parent that is not a node', () => {
    const contents = [node('Agents/a', '# a\n')]
    const nodeSet = new Set(contents.map((c) => c.path))
    const fallback = new Map([['knowledge/Agents/a.md', { level: 3, domain: 'ai', parentId: 'knowledge/Areas/Agents.md' }]])
    const { edges, info } = buildHierarchyGraph(contents, nodeSet, toNodeId, fallback)
    expect(info.get('knowledge/Agents/a.md')).toEqual({ level: 3, parentId: undefined, domain: 'ai' })
    expect(edges).toEqual([])
  })
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd C:\Users\User\Desktop\rowboat\apps\x\apps\renderer && npx vitest run src/lib/graph-hierarchy.test.ts`
Expected: FAIL (`parseVaultMap` is not exported).

- [ ] **Step 3: Implement in `graph-hierarchy.ts`**

After the `NodeInfo` type (line 142) add:

```ts
const VAULT_MAP_VERSION = 1

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** config/vault-map.json (written by `ehl-schema map`): node id -> hierarchy info. Any problem gives an empty map,
 * so the graph falls back to front matter only. */
export function parseVaultMap(text: string, toNodeId: (wikiPath: string) => string | null): Map<string, NodeInfo> {
  const out = new Map<string, NodeInfo>()
  let doc: unknown
  try {
    doc = JSON.parse(text)
  } catch {
    return out
  }
  if (!isRecord(doc) || doc.version !== VAULT_MAP_VERSION || !isRecord(doc.notes)) return out
  for (const [path, entry] of Object.entries(doc.notes)) {
    if (!isRecord(entry) || !Number.isInteger(entry.level)) continue
    const id = toNodeId(path)
    if (!id) continue
    const parentId = typeof entry.parent === 'string' ? toNodeId(entry.parent) ?? undefined : undefined
    out.set(id, {
      level: entry.level as number,
      domain: typeof entry.domain === 'string' ? entry.domain : undefined,
      parentId,
    })
  }
  return out
}
```

Replace `buildHierarchyGraph` with:

```ts
/** Typed edges (one per unordered pair, strongest kind wins) and hierarchy info per node. Front matter wins;
 * `fallback` (from the vault map) fills in level, domain and parent for notes that have none. */
export function buildHierarchyGraph(
  contents: { path: string; data: string }[],
  nodeSet: Set<string>,
  toNodeId: (wikiTarget: string) => string | null,
  fallback?: Map<string, NodeInfo>,
): { edges: HierarchyEdge[]; info: Map<string, NodeInfo> } {
  const edges = new Map<string, HierarchyEdge>()
  const info = new Map<string, NodeInfo>()
  const addEdge = (source: string, target: string, kind: EdgeKind, relation?: string) => {
    if (target === source || !nodeSet.has(target)) return
    const key = source < target ? `${source}|${target}` : `${target}|${source}`
    const existing = edges.get(key)
    if (existing && RANK[existing.kind] >= RANK[kind]) return
    edges.set(key, relation ? { source, target, kind, relation } : { source, target, kind })
  }
  const add = (source: string, rawTarget: string, kind: EdgeKind, relation?: string) => {
    const target = toNodeId(rawTarget)
    if (target) addEdge(source, target, kind, relation)
  }
  for (const { path, data } of contents) {
    const hierarchy = parseHierarchy(data)
    const mapped = fallback?.get(path)
    const frontParent = hierarchy.parent ? toNodeId(hierarchy.parent) : null
    const mappedParent = !hierarchy.parent && mapped?.parentId && nodeSet.has(mapped.parentId) ? mapped.parentId : undefined
    info.set(path, {
      level: hierarchy.level ?? mapped?.level,
      parentId: frontParent && nodeSet.has(frontParent) ? frontParent : mappedParent,
      domain: hierarchy.domain ?? mapped?.domain,
    })
    if (hierarchy.parent) add(path, hierarchy.parent, 'parent')
    else if (mappedParent) addEdge(path, mappedParent, 'parent')
    for (const relation of hierarchy.relations) add(path, relation.target, 'relation', relation.name)
    for (const match of data.matchAll(LINK)) add(path, match[1], 'link')
  }
  return { edges: Array.from(edges.values()), info }
}
```

- [ ] **Step 4: Read the map in `App.tsx`**

Change line 90 to:

```ts
import { buildHierarchyGraph, parseVaultMap } from '@/lib/graph-hierarchy'
```

In `buildGraph`, replace

```ts
      const { edges: typedEdges, info: hierarchyInfo } = buildHierarchyGraph(contents, nodeSet, toKnowledgePath)
```

with

```ts
      // config/vault-map.json (ehl-schema map) places notes that carry no hierarchy front matter; optional.
      let vaultMap: Map<string, NodeInfo> | undefined
      try {
        const mapFile = await window.ipc.invoke('workspace:readFile', { path: 'config/vault-map.json', encoding: 'utf8' })
        vaultMap = parseVaultMap(mapFile.data as string, toKnowledgePath)
      } catch {
        vaultMap = undefined
      }
      const { edges: typedEdges, info: hierarchyInfo } = buildHierarchyGraph(contents, nodeSet, toKnowledgePath, vaultMap)
```

and extend the import from `@/lib/graph-hierarchy` with `type NodeInfo`:

```ts
import { buildHierarchyGraph, parseVaultMap, type NodeInfo } from '@/lib/graph-hierarchy'
```

- [ ] **Step 5: Run tests and typecheck**

Run: `cd C:\Users\User\Desktop\rowboat\apps\x\apps\renderer && npx vitest run src/lib/graph-hierarchy.test.ts && npx tsc -b`
Expected: all graph tests PASS (22 old + 6 new), tsc without errors.

- [ ] **Step 6: Commit (in the Rowboat fork)**

```bash
cd C:/Users/User/Desktop/rowboat
git add apps/x/apps/renderer/src/lib/graph-hierarchy.ts apps/x/apps/renderer/src/lib/graph-hierarchy.test.ts apps/x/apps/renderer/src/App.tsx
ENTIRE_TEST_TTY=0 git commit -m "feat(graph): place notes without hierarchy front matter via config/vault-map.json

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Installer `--profile vibemind`

**Files:**
- Modify: `scripts/install.py`
- Test: `scripts/tests/test_install.py`

**Interfaces:**
- Consumes: CLI from Task 4 (`build|map|lint --profile`, `map --watch`).
- Produces (pure helpers, tested):
  - `PROFILES = ROOT / "schema" / "profiles"`
  - `profile_company(name: str) -> str` (reads `company:` from `schema/profiles/<name>.yaml` without PyYAML; raises `InstallError` if missing)
  - `schema_commands(py: Path, workdir: Path, company: str, profile: str | None) -> list[list[str]]`
  - `map_watch_command(py: Path, workdir: Path, company: str, profile: str | None, seconds: int = 60) -> list[str]`
  - `backup_vault(vault: Path, stamp: str) -> Path | None` (copy without `.git`; None if no vault)

- [ ] **Step 1: Write the failing tests**

Append to `scripts/tests/test_install.py`:

```python
def test_profile_company_reads_the_profile():
    assert install.profile_company("vibemind") == "VibeMind"


def test_profile_company_unknown_profile():
    import pytest
    with pytest.raises(install.InstallError):
        install.profile_company("nope")


def test_profile_commands_never_migrate(tmp_path):
    cmds = install.schema_commands(Path("py"), tmp_path, "VibeMind", "vibemind")
    assert [c[3] for c in cmds] == ["build", "map"]
    assert all(["--profile", "vibemind"] == c[c.index("--profile"):c.index("--profile") + 2] for c in cmds)
    assert not any("migrate" in c for c in cmds)


def test_ehl_commands_keep_migrate_and_the_company(tmp_path):
    cmds = install.schema_commands(Path("py"), tmp_path, "EHL", None)
    assert [c[3] for c in cmds] == ["build", "migrate", "map"]
    for c in cmds:
        if c[3] in ("build", "map"):
            assert c[c.index("--company") + 1] == "EHL"
    watch = install.map_watch_command(Path("py"), tmp_path, "EHL", None)
    assert watch[watch.index("--company") + 1] == "EHL" and "--watch" in watch


def test_backup_copies_notes_but_not_git(tmp_path):
    vault = tmp_path / "knowledge"
    (vault / ".git").mkdir(parents=True)
    (vault / ".git" / "HEAD").write_text("x", encoding="utf-8")
    (vault / "Agents").mkdir()
    (vault / "Agents" / "a.md").write_text("# a\n", encoding="utf-8")
    dest = install.backup_vault(vault, "20261013-1200")
    assert dest == tmp_path / "knowledge.bak-20261013-1200"
    assert (dest / "Agents" / "a.md").read_text(encoding="utf-8") == "# a\n"
    assert not (dest / ".git").exists()
    assert install.backup_vault(tmp_path / "missing", "x") is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd C:/Users/User/Desktop/ehl-munich-2026 && py -3.12 -m pytest -q scripts/tests/test_install.py`
Expected: FAIL (`module 'install' has no attribute 'profile_company'`).

- [ ] **Step 3: Add the pure helpers**

In `scripts/install.py`, after `MODELS = ...` add:

```python
PROFILES = ROOT / "schema" / "profiles"
MAP_REFRESH_SECONDS = 60
```

After `missing_cars` add:

```python
def profile_company(name: str) -> str:
    """The company name of a vault profile (schema/profiles/<name>.yaml); stdlib only, so no YAML parser."""
    path = PROFILES / f"{name}.yaml"
    if not path.is_file():
        raise InstallError(f"no profile {name!r} in {PROFILES}")
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == "company" and value.split("#")[0].strip():
            return value.split("#")[0].strip().strip("'\"")
    raise InstallError(f"{path} has no company")


def _schema_cli(py: Path) -> list[str]:
    return [str(py), "-m", "ehl_schema.cli"]


def schema_commands(py: Path, workdir: Path, company: str, profile: str | None) -> list[list[str]]:
    """build (+ migrate for the EHL vault only) + map. A profile vault is never migrated: its notes belong to
    live writers and must not be edited."""
    w = ["--workdir", str(workdir)]
    prof = ["--profile", profile] if profile else []
    cmds = [_schema_cli(py) + ["build", *w, "--company", company, *prof]]
    if profile is None:
        cmds.append(_schema_cli(py) + ["migrate", *w, "--write"])
    cmds.append(_schema_cli(py) + ["map", *w, "--company", company, *prof])
    return cmds


def map_watch_command(py: Path, workdir: Path, company: str, profile: str | None,
                      seconds: int = MAP_REFRESH_SECONDS) -> list[str]:
    prof = ["--profile", profile] if profile else []
    return _schema_cli(py) + ["map", "--workdir", str(workdir), "--company", company, *prof, "--watch", str(seconds)]


def backup_vault(vault: Path, stamp: str) -> Path | None:
    """Copy the vault next to itself (knowledge.bak-<stamp>), without its .git folder."""
    if not vault.is_dir():
        return None
    dest = vault.with_name(f"{vault.name}.bak-{stamp}")
    shutil.copytree(vault, dest, ignore=shutil.ignore_patterns(".git"), dirs_exist_ok=True)
    return dest
```

- [ ] **Step 4: Use them in the steps**

Replace `setup_schema` with:

```python
def setup_schema(py: Path, workdir: Path, company: str, profile: str | None = None) -> None:
    """Vault schema (schema/): one hierarchy for every note. Specs: docs/superpowers/specs/2026-10-12-vault-schema-design.md,
    2026-10-13-vault-folder-rules-design.md (profiles)."""
    setup_pc.run([str(py), "-m", "pip", "install", "-q", "-e", str(ROOT / "schema")])
    for cmd in schema_commands(py, workdir, company, profile):
        setup_pc.run(cmd)
    lint = _schema_cli(py) + ["lint", "--workdir", str(workdir)] + (["--profile", profile] if profile else [])
    if setup_pc.run(lint, check=False).returncode != 0:
        log.warning("The vault does not follow the schema yet; see the lint output above")
```

Replace `start` with:

```python
def start(rowboat: Path, workdir: Path, company: str = "EHL", profile: str | None = None) -> int:
    """Start Rowboat and its helpers; Ctrl+C stops all of them. With a profile only Rowboat and the
    vault-map refresh run (no BMW demo syncs, no RAG)."""
    vault = str(workdir / "knowledge")
    env = {**os.environ, "ROWBOAT_WORKDIR": str(workdir), "EHL_VAULT": vault}
    jobs = [("Rowboat", ["npm", "run", "dev"], rowboat / "apps" / "x")]
    if profile:
        schema_py = venv_python(ROOT / "schema" / ".venv")
        jobs.append(("vault map", map_watch_command(schema_py, workdir, company, profile), ROOT))
    else:
        market_py, search_py = venv_python(ROOT / "market" / ".venv"), venv_python(ROOT / "search" / ".venv")
        jobs += [("vault sync", [str(market_py), str(ROOT / "demo" / "visu" / "vault.py"), "sync", "--watch",
                                 "--vault", vault], ROOT),
                 ("Torque sync", [str(market_py), str(ROOT / "demo" / "torque" / "sync.py"), "--watch",
                                  "--vault", vault], ROOT),
                 ("vault map", map_watch_command(market_py, workdir, company, None), ROOT)]
        if search_py.exists():
            jobs.append(("RAG", [str(search_py), "-m", "uvicorn", "app:app", "--port", str(RAG_PORT)], ROOT))
    procs = []
    for name, cmd, cwd in jobs:
        log.info("starting %s: %s", name, " ".join(cmd))
        procs.append(subprocess.Popen(cmd, cwd=cwd, env=env, shell=IS_WINDOWS and cmd[0] == "npm"))
    log.info("Rowboat opens after its first build (a few minutes). Ctrl+C stops everything.")
    try:
        procs[0].wait()
    except KeyboardInterrupt:
        pass
    finally:
        for proc in procs:
            stop(proc)
    return 0
```

Add `import time` to the imports (for the backup stamp). In `main`, add the option after `--company`:

```python
    ap.add_argument("--profile", help="vault profile from schema/profiles (e.g. vibemind): set up and start Rowboat "
                    "on that vault only - no market data, Torque, 3D cars or RAG; workdir default ~/.rowboat")
```

and replace everything from `workdir = (args.workdir or setup_pc.rowboat_workdir()).expanduser()` to the end of
`main` with:

```python
    if args.profile:
        try:
            company = profile_company(args.profile)
        except InstallError as err:
            log.error("%s", err)
            return 2
        workdir = (args.workdir or Path.home() / ".rowboat").expanduser()
    else:
        company = args.company
        workdir = (args.workdir or setup_pc.rowboat_workdir()).expanduser()

    profile_mode = bool(args.profile)
    problems = check_tools(need_docker=not profile_mode and not args.skip_rag and not args.start,
                           need_build=not args.no_build and not args.start)
    if problems:
        log.error("Missing prerequisites:\n- %s", "\n- ".join(problems))
        return 2
    log.info("Prerequisites ok. Rowboat data folder: %s", workdir)
    if args.check:
        return 0
    if args.start:
        return start(args.rowboat, workdir, company, args.profile)

    try:
        setup_rowboat(args.rowboat, build=not args.no_build)
        if profile_mode:
            py = make_venv(ROOT / "schema" / ".venv")
            backup = backup_vault(workdir / "knowledge", time.strftime("%Y%m%d-%H%M%S"))
            log.info("Vault backup: %s", backup or "none (no vault yet)")
            setup_schema(py, workdir, company, args.profile)
        else:
            py = setup_market(args.refresh)
            setup_vault(py, workdir, args.refresh)
            setup_schema(py, workdir, company)
            link_torque(workdir)
            register_market(py, workdir)
            setup_3d(py, args.cars)
            if not args.skip_rag:
                setup_rag(interactive=sys.stdin.isatty())
    except (InstallError, setup_pc.SetupError) as err:
        log.error("Install stopped: %s", err)
        return 1
    if profile_mode:
        log.info("Done. Next: python scripts/install.py --profile %s --start", args.profile)
    else:
        log.info("Done. Next: python scripts/install.py --start, then in Rowboat set a model provider "
                 "(Settings) and open Apps -> Torque.")
    return 0
```

Add to the module docstring after the `--start` line:

```
    python scripts/install.py --profile vibemind [--start]   # another company's vault (~/.rowboat): schema,
                                                               # map and graph only - no BMW demo parts
```

- [ ] **Step 5: Run the tests**

Run: `cd C:/Users/User/Desktop/ehl-munich-2026 && py -3.12 -m pytest -q scripts/tests/test_install.py && cd schema && py -3.12 -m pytest -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/User/Desktop/ehl-munich-2026
git add scripts/install.py scripts/tests/test_install.py
ENTIRE_TEST_TTY=0 git commit -m "feat(install): --profile vibemind sets up and starts Rowboat on another vault without the BMW demo

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Real run on `~/.rowboat`, docs

**Files:**
- Modify: `README.md` (one row/paragraph for `--profile`)
- Modify: `docs/superpowers/specs/2026-10-13-vault-folder-rules-design.md` (status line → "implemented", plus real-run numbers)

- [ ] **Step 1: Check nothing else uses `~/.rowboat` right now**

Run (PowerShell): `Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'Rowboat|electron' } | Select-Object ProcessId, Name, CommandLine | Format-List`
If an installed VibeMind Rowboat (`%LOCALAPPDATA%\Rowboat`) or our EHL dev Rowboat is running, **ask the user** to
close it before Step 4 (two Rowboat apps on the same machine compete for the dev port; two on the same vault both
auto-commit). Do not kill it yourself.

- [ ] **Step 2: Set up the VibeMind profile**

Run: `cd C:/Users/User/Desktop/ehl-munich-2026 && py -3.12 -u scripts/install.py --profile vibemind --no-build`
Expected: backup path logged (`~/.rowboat/knowledge.bak-…`), `build`, `map` (≈ 500 notes placed, 3+ excluded), `lint`
with 0 errors. Write down the counts and every `no-rule` / `rule-parent-missing` warning.

- [ ] **Step 3: Verify nothing existing changed**

Run: `git -C ~/.rowboat/knowledge status --short | grep -v '^??' | grep -v -E '(Company|Domains/|Areas/|Agent Notes/Vault Schema)' | head`
Expected: only changes that were there before this run (compare with the backup if unsure:
`diff -rq ~/.rowboat/knowledge ~/.rowboat/knowledge.bak-<stamp> --exclude=.git` lists only the new structure notes).
If any existing note changed, **stop** and report.

- [ ] **Step 4: Start Rowboat on the VibeMind vault**

Run in the background: `py -3.12 -u scripts/install.py --profile vibemind --start`
Wait until Rowboat is up (as before: poll the log for the window). Ask the user to open **Brain → Graph** (3D) and
check that VibeMind sits in the centre with domains, areas, agents, ideas, projects around it. Send a screenshot if
the user wants one.

- [ ] **Step 5: Docs**

In `README.md`, in the install section next to `scripts/install.py --start`, add:

```markdown
- `python scripts/install.py --profile vibemind [--start]` – runs our Rowboat on another company's vault
  (`~/.rowboat`). Its notes stay untouched: folder rules in `schema/profiles/vibemind.yaml` place them in the
  hierarchy (`config/vault-map.json`). No BMW demo parts (market data, Torque, 3D cars, RAG).
```

In the spec, change the status line to `**Status:** implemented (plan 2026-10-13-vault-folder-rules-plan.md)` and add
under §11 a line with the real-run numbers from Step 2 (notes placed, excluded, warnings).

- [ ] **Step 6: Commit and push**

```bash
cd C:/Users/User/Desktop/ehl-munich-2026
git add README.md docs/superpowers/specs/2026-10-13-vault-folder-rules-design.md docs/superpowers/plans/2026-10-13-vault-folder-rules-plan.md
ENTIRE_TEST_TTY=0 git commit -m "docs: vault profiles in the README, real-run numbers in the spec

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin feat/vault-folder-rules
```

Do **not** push the Rowboat fork branch or open PRs in this task; that is decided together with part 2.
