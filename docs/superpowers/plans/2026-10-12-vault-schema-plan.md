# Vault Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `schema/`, a single-source vault schema with a generator, a linter and a migration, and
move the EHL vault (`~/.rowboat-ehl`) onto it.

**Architecture:** `schema/vault-schema.yaml` is the only place that defines domains, areas, note types
and relations. A small Python package `ehl_schema` loads it and uses it in three commands:

- `build` writes the structure notes (Company, Domains, Areas), Rowboat's `config/notes.json` and a
  rules note for agents.
- `lint` checks every note of a vault.
- `migrate` adds the missing front matter keys to existing notes. It only proposes changes unless you
  pass `--write`.

Folders stay flat, one per type, as Rowboat expects. The hierarchy lives in flat YAML front matter.

**Tech Stack:** Python 3.12, PyYAML, pytest, GitHub Actions. It runs in `market/.venv`, which the
installer already creates and which already has PyYAML and pytest.

**Spec:** `docs/superpowers/specs/2026-10-12-vault-schema-design.md`

## Global Constraints

- **Language and dependencies:**
  - Python `>=3.12`, own `pyproject.toml` in `schema/`.
  - Only runtime dependency: `pyyaml>=6`.
  - Tests: pytest.
- **Logging:** use `logging`, never `print`.
- **Platforms:** everything runs on Windows and macOS. Read files as UTF-8 and accept CRLF and a BOM.
- **Front matter:**
  - Flat YAML only: every value is a scalar or a list of strings.
  - Links are always quoted, full path: `parent: "[[Areas/Pipeline]]"`, `customer: ["[[Organizations/Acme]]"]`.
- **Files:** never rename or move a note file. Never rewrite a key a note already has. Existing front
  matter lines stay first and unchanged; new keys are appended.
- **Generated notes:** they carry `managed_by: schema`. Only those are ever rewritten by `build`.
- **Rowboat stays unmodified.** We only write `<workdir>/config/notes.json` and notes in `<workdir>/knowledge/`.
- **Never commit a vault (`~/.rowboat*`) or its notes** (CLAUDE.md data rules).
- **Commits:** Conventional commits ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Python interpreter in commands:** `market/.venv/Scripts/python` (Windows) or `market/.venv/bin/python`
  (macOS). The commands below use the Windows form.

## Review Focus

1. **Windows files with CRLF and a BOM.**
   - The notes written by `brand.py` on Windows are CRLF.
   - Front matter must still parse, and a migrated file must keep its CRLF.
   - Test: Task 2 `test_split_accepts_bom_and_crlf`, `test_add_keys_keeps_crlf_and_existing_lines`.
2. **Note names with `&`, commas, brackets, umlauts, and links with alias, heading or attachment.**
   - `[[Brands/BMW|BMW]]`, `[[Models/5er G60#Sales]]` and `[[Data/BMW Dataset.xlsx]]` must resolve.
   - `Badges & logos` must round-trip through YAML.
   - Test: Task 2 `test_links_strip_alias_and_heading`, `test_format_value_round_trips`; Task 3
     `test_alias_and_attachment_links_resolve`.
3. **Re-running is harmless.**
   - A second `build` writes nothing.
   - The schema rules are not appended to `notes.json` twice.
   - A second `migrate` proposes nothing.
   - Test: Task 4 `test_build_is_idempotent`; Task 5 `test_migrate_is_idempotent`.
4. **Existing front matter survives.**
   - `managed_by: torque` must stay within the first 300 characters (`demo/torque/sync.py` checks `old[:300]`).
   - Unknown keys (`part_id`, `req_id`) are untouched.
   - Torque's sync must not drop the new keys when it rewrites a note.
   - Test: Task 2 `test_add_keys_keeps_crlf_and_existing_lines`; Task 7 `test_write_if_changed_keeps_schema_keys`.
5. **Mutual links between notes of the same type** (`Projects/G60` ↔ `Projects/G60 Roadmap`) must not
   produce an inverted parent or a cycle.
   - Test: Task 5 `test_plan_chooses_parents`, which also covers the incoming-link case
     (driver → its top 10 note).

## File Structure

| File | Responsibility |
|---|---|
| `schema/pyproject.toml` | Package `ehl-schema`, dependency, script entry |
| `schema/vault-schema.yaml` | The schema: domains, areas, relations, types |
| `schema/ehl_schema/__init__.py` | Package marker |
| `schema/ehl_schema/model.py` | Load and check the schema → `Schema`, `TypeDef`, `RelationDef` |
| `schema/ehl_schema/notes.py` | Read a vault; split, format and extend front matter; parse links |
| `schema/ehl_schema/lint.py` | `lint(schema, vault) -> list[Issue]` |
| `schema/ehl_schema/build.py` | Structure notes, rules note, `notes.json` |
| `schema/ehl_schema/migrate.py` | `plan`, `apply` and `diff` for missing front matter |
| `schema/ehl_schema/cli.py` | `python -m ehl_schema.cli build|lint|migrate` |
| `schema/tests/helpers.py` | Test helpers: write notes, build small vaults |
| `schema/tests/test_*.py` | One test file per module |
| `demo/torque/sync.py` (modify) | Keep foreign front matter keys on rewrite |
| `demo/tests/test_sync_frontmatter.py` | Test for that |
| `scripts/install.py` (modify) | Install the package; run build, migrate and lint after the vault notes |
| `.github/workflows/schema.yml` | CI: run `schema/tests` |
| `README.md`, the spec (modify) | Document `schema/`; record the parent rule and the channel areas |

---

### Task 1: Package, schema file and schema loader

**Files:**
- Create: `schema/pyproject.toml`, `schema/vault-schema.yaml`, `schema/ehl_schema/__init__.py`, `schema/ehl_schema/model.py`
- Test: `schema/tests/test_model.py`

**Interfaces:**
- Produces:
  - `DEFAULT_SCHEMA: Path`
  - `STRUCTURE_TYPES = ("Company", "Domains", "Areas")`
  - `class SchemaError(ValueError)`
  - `TypeDef(name, domain, level, parent: tuple[str, ...], default_parent: str | None, builtin: bool, required: tuple[str, ...], optional: tuple[str, ...], statuses: tuple[str, ...], template: str | None)`
  - `RelationDef(name, targets: tuple[str, ...] | None, kind: str)`
  - `Schema(version: int, domains: dict[str, str], cross_cutting: frozenset[str], areas: dict[str, str], relations: dict[str, RelationDef], types: dict[str, TypeDef])` with methods:
    - `domain_note(key) -> str` (`"Domains/<title>"`)
    - `area_note(name) -> str` (`"Areas/<name>"`)
    - `domain_key(title) -> str | None`
    - `type_of_path(path) -> str | None`
  - `load_schema(path: Path = DEFAULT_SCHEMA) -> Schema`

- [ ] **Step 1: Create the package files**

`schema/pyproject.toml`:

```toml
[project]
name = "ehl-schema"
version = "0.1.0"
description = "Vault schema: one hierarchy for all business data (build, lint, migrate)"
requires-python = ">=3.12"
dependencies = ["pyyaml>=6"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
ehl-schema = "ehl_schema.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["ehl_schema*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`schema/ehl_schema/__init__.py`:

```python
"""Vault schema: one hierarchy for all business data of a company (see schema/vault-schema.yaml)."""
```

`schema/vault-schema.yaml`:

```yaml
# Vault schema: one hierarchy for all business data. The single source of truth.
# Spec: docs/superpowers/specs/2026-10-12-vault-schema-design.md
# Company (L0), Domains (L1) and Areas (L2) are generated notes (schema build); the types below are L3/L4.
# Folder name = type. parent = allowed parent types, in order of preference.
schema_version: 1

domains:
  strategy:   {title: "Strategy & steering"}
  legal:      {title: "Legal & compliance"}
  finance:    {title: "Finance & funding"}
  team:       {title: "Team & HR"}
  sales:      {title: "Market & sales"}
  success:    {title: "Customer success & support"}
  partners:   {title: "Partners & vendors"}
  marketing:  {title: "Marketing & brand"}
  product:    {title: "Product & engineering"}
  ai:         {title: "AI & agents"}
  delivery:   {title: "Projects & delivery"}
  operations: {title: "Operations & IT"}
  register:   {title: "People & organisations", cross_cutting: true}
  sources:    {title: "Raw inputs", cross_cutting: true}
  knowledge:  {title: "Knowledge & evidence", cross_cutting: true}

areas:        # area name (unique; note Areas/<name>) -> domain
  Goals: strategy
  KPIs: strategy
  Decisions: strategy
  Risks: strategy
  Contracts: legal
  Data protection: legal
  AI Act: legal
  IP & licences: legal
  Budget: finance
  Invoices: finance
  Funding: finance
  Pricing: finance
  Roles: team
  Recruiting: team
  Onboarding: team
  Segments: sales
  Pipeline: sales
  Competitors: sales
  Customer onboarding: success
  Support: success
  Feedback: success
  Design partners: success
  Partnerships: partners
  Vendors: partners
  Brand: marketing
  Campaigns: marketing
  Content: marketing
  Channels: marketing
  Products: product
  Roadmap: product
  Requirements: product
  Releases: product
  Incidents: product
  Agents: ai
  Workflows: ai
  Models & evals: ai
  Datasets: ai
  Compute: ai
  Client projects: delivery
  Initiatives: delivery
  Milestones: delivery
  Infrastructure: operations
  Tools: operations
  Security: operations
  Runbooks: operations
  Contacts: register
  Companies: register
  Meetings: sources
  Mails: sources
  Chats: sources
  Voice memos: sources
  Agent notes: sources
  Topics: knowledge
  Studies: knowledge
  Data: knowledge
  Assumptions: knowledge

relations:    # flat front matter keys; link values are lists of quoted [[Folder/Name]] links
  works_at:      {targets: [Organizations]}
  contact_at:    {targets: [Organizations]}
  investor_in:   {targets: [Organizations]}
  candidate_for: {targets: [Roles]}
  customer:      {targets: [Organizations]}
  project:       {targets: [Projects]}
  product:       {targets: [Products, Models]}
  owner:         {targets: [People, Agents]}
  about:         {targets: any}
  evidence:      {targets: [Studies, Data, Topics, Meetings, Assumptions]}
  executed_by:   {targets: [Agents]}
  when:          {kind: date}

types:
  # strategy
  OKRs:               {domain: strategy, level: 3, parent: [Areas], default_parent: Goals, optional: [owner, when]}
  KPIs:               {domain: strategy, level: 3, parent: [Areas], default_parent: KPIs, optional: [owner, product, evidence]}
  Decisions:          {domain: strategy, level: 3, parent: [Projects, Products, Areas], default_parent: Decisions, optional: [owner, about, evidence, when]}
  Risks:              {domain: strategy, level: 3, parent: [Areas], default_parent: Risks, optional: [owner, about]}
  # legal
  Contracts:          {domain: legal, level: 3, parent: [Areas], default_parent: Contracts, optional: [customer, owner, project, when], statuses: [draft, sent, signed, expired, terminated]}
  Processing Records: {domain: legal, level: 3, parent: [Areas], default_parent: Data protection, optional: [owner, about]}
  AI Systems:         {domain: legal, level: 3, parent: [Areas], default_parent: AI Act, optional: [owner, product]}
  Licences:           {domain: legal, level: 3, parent: [Areas], default_parent: IP & licences, optional: [owner, about]}
  # finance
  Budgets:            {domain: finance, level: 3, parent: [Projects, Areas], default_parent: Budget, optional: [owner, project, when]}
  Invoices:           {domain: finance, level: 4, parent: [Deals, Projects, Areas], default_parent: Invoices, required: [customer, when], optional: [project], statuses: [draft, sent, paid, overdue, cancelled]}
  Funding:            {domain: finance, level: 3, parent: [Areas], default_parent: Funding, optional: [owner, when, evidence], statuses: [idea, applied, granted, rejected, closed]}
  Price Plans:        {domain: finance, level: 3, parent: [Products, Areas], default_parent: Pricing, optional: [product]}
  # team
  Roles:              {domain: team, level: 3, parent: [Areas], default_parent: Roles, optional: [owner]}
  Candidates:         {domain: team, level: 4, parent: [Roles, Areas], default_parent: Recruiting, optional: [owner, when], statuses: [new, interview, offer, hired, rejected]}
  # sales
  Segments:           {domain: sales, level: 3, parent: [Areas], default_parent: Segments}
  Leads:              {domain: sales, level: 3, parent: [Segments, Areas], default_parent: Pipeline, optional: [customer, owner, when], statuses: [new, researched, qualified, contacted, replied, meeting, won, lost]}
  Deals:              {domain: sales, level: 3, parent: [Areas], default_parent: Pipeline, required: [customer, owner], optional: [project, product, evidence, when], statuses: [lead, qualified, proposal, won, lost]}
  Competitors:        {domain: sales, level: 3, parent: [Segments, Areas], default_parent: Competitors, optional: [evidence]}
  # success
  Tickets:            {domain: success, level: 4, parent: [Projects, Products, Areas], default_parent: Support, required: [customer], optional: [owner, product, when], statuses: [open, waiting, solved, closed]}
  Feedback:           {domain: success, level: 4, parent: [Components, Models, Products, Areas], default_parent: Feedback, optional: [customer, product, evidence]}
  # partners
  Partnerships:       {domain: partners, level: 3, parent: [Areas], default_parent: Partnerships, optional: [customer, owner, when]}
  Vendors:            {domain: partners, level: 3, parent: [Areas], default_parent: Vendors, optional: [owner, about]}
  # marketing
  Brands:             {domain: marketing, level: 3, parent: [Areas], default_parent: Brand}
  Campaigns:          {domain: marketing, level: 3, parent: [Projects, Areas], default_parent: Campaigns, optional: [owner, project, product, when], statuses: [draft, scheduled, running, done]}
  Content:            {domain: marketing, level: 4, parent: [Campaigns, Areas], default_parent: Content, optional: [owner, about, when], statuses: [draft, approved, published]}
  Assets:             {domain: marketing, level: 4, parent: [Campaigns, Content, Areas], default_parent: Content, optional: [about, executed_by]}
  # product
  Products:           {domain: product, level: 3, parent: [Areas], default_parent: Products, optional: [owner]}
  Models:             {domain: product, level: 3, parent: [Brands, Products, Areas], default_parent: Products}
  Components:         {domain: product, level: 4, parent: [Models, Products, Areas], default_parent: Products}
  Feature Classes:    {domain: product, level: 4, parent: [Components, Models, Areas], default_parent: Products}
  Requirements:       {domain: product, level: 3, parent: [Models, Products, Areas], default_parent: Requirements, optional: [product, owner, evidence], statuses: [proposed, in_review, approved, rejected, challenged, edited]}
  Purchase Drivers:   {domain: product, level: 3, parent: [Projects, Purchase Drivers, Models, Areas], default_parent: Requirements, optional: [product, evidence]}
  Releases:           {domain: product, level: 3, parent: [Products, Areas], default_parent: Releases, optional: [product, when]}
  Incidents:          {domain: product, level: 4, parent: [Products, Systems, Areas], default_parent: Incidents, optional: [product, owner, when], statuses: [open, mitigated, resolved]}
  # ai
  Agents:             {domain: ai, level: 3, parent: [Areas], default_parent: Agents, optional: [owner], statuses: [active, paused, archived]}
  Workflows:          {domain: ai, level: 3, parent: [Agents, Areas], default_parent: Workflows, optional: [owner, executed_by]}
  AI Models:          {domain: ai, level: 3, parent: [Areas], default_parent: Models & evals, optional: [owner]}
  Evals:              {domain: ai, level: 4, parent: [AI Models, Agents, Areas], default_parent: Models & evals, optional: [executed_by, evidence, when]}
  Datasets:           {domain: ai, level: 3, parent: [Areas], default_parent: Datasets, optional: [owner, evidence]}
  # delivery
  Projects:           {domain: delivery, level: 3, parent: [Projects, Areas], default_parent: Client projects, builtin: true, optional: [customer, product, owner, when], statuses: [active, planning, on-hold, done, cancelled]}
  Milestones:         {domain: delivery, level: 4, parent: [Projects, Areas], default_parent: Milestones, optional: [owner, when]}
  Tasks:              {domain: delivery, level: 4, parent: [Milestones, Projects, Areas], default_parent: Milestones, optional: [owner, project, when], statuses: [open, doing, done]}
  Initiatives:        {domain: delivery, level: 3, parent: [Areas], default_parent: Initiatives, optional: [owner, when]}
  # operations
  Systems:            {domain: operations, level: 3, parent: [Areas], default_parent: Infrastructure, optional: [owner]}
  Tools:              {domain: operations, level: 3, parent: [Areas], default_parent: Tools, optional: [owner]}
  Runbooks:           {domain: operations, level: 4, parent: [Systems, Tools, Areas], default_parent: Runbooks, optional: [owner, about]}
  # register (Rowboat built-ins)
  People:             {domain: register, level: 3, parent: [Areas], default_parent: Contacts, builtin: true, optional: [works_at, contact_at, investor_in, candidate_for]}
  Organizations:      {domain: register, level: 3, parent: [Areas], default_parent: Companies, builtin: true}
  # sources (raw inputs; parent = channel area)
  Meetings:           {domain: sources, level: 4, parent: [Areas], default_parent: Meetings, builtin: true, optional: [about, customer, project, when]}
  Mails:              {domain: sources, level: 4, parent: [Areas], default_parent: Mails, required: [about], optional: [customer, project, when]}
  Chats:              {domain: sources, level: 4, parent: [Areas], default_parent: Chats, optional: [about, customer, project, when]}
  Voice Memos:        {domain: sources, level: 4, parent: [Areas], default_parent: Voice memos, builtin: true, optional: [about, when]}
  Agent Notes:        {domain: sources, level: 4, parent: [Areas], default_parent: Agent notes, builtin: true, optional: [about, executed_by]}
  # knowledge
  Topics:             {domain: knowledge, level: 3, parent: [Areas], default_parent: Topics, builtin: true}
  Studies:            {domain: knowledge, level: 3, parent: [Areas], default_parent: Studies, optional: [about, evidence]}
  Data:               {domain: knowledge, level: 4, parent: [Areas], default_parent: Data, optional: [about]}
  Assumptions:        {domain: knowledge, level: 3, parent: [Areas], default_parent: Assumptions, optional: [about, evidence]}
```

- [ ] **Step 2: Install the package into the market venv**

Run: `market/.venv/Scripts/python -m pip install -q -e "schema[dev]"`
Expected: exits 0.

- [ ] **Step 3: Write the failing tests**

`schema/tests/test_model.py`:

```python
"""Checks for ehl_schema.model: the real schema file loads and is consistent; bad schemas are rejected."""
import pytest

from ehl_schema.model import STRUCTURE_TYPES, SchemaError, load_schema

MINI = """
schema_version: 1
domains: {sales: {title: Sales}}
areas: {Pipeline: sales}
relations: {owner: {targets: [People]}, about: {targets: any}, when: {kind: date}}
types:
  People: {domain: sales, level: 3, parent: [Areas], default_parent: Pipeline, builtin: true, optional: [owner]}
"""


def test_real_schema_loads_and_is_consistent():
    schema = load_schema()
    assert schema.version == 1
    assert len(schema.domains) == 15
    assert {"register", "sources", "knowledge"} == set(schema.cross_cutting)
    assert {"People", "Organizations", "Projects", "Topics", "Meetings"} <= set(schema.types)
    for name, td in schema.types.items():
        if name in STRUCTURE_TYPES:
            continue
        assert td.default_parent in schema.areas, name
        assert all(p in schema.types for p in td.parent), name


def test_every_domain_has_an_area():
    schema = load_schema()
    assert set(schema.areas.values()) == set(schema.domains)


def test_structure_types_are_added():
    schema = load_schema()
    assert schema.types["Company"].level == 0
    assert schema.types["Domains"].parent == ("Company",)
    assert schema.types["Areas"].parent == ("Domains",)


def test_type_of_path_and_note_names():
    schema = load_schema()
    assert schema.type_of_path("Company") == "Company"
    assert schema.type_of_path("Components/Hood") == "Components"
    assert schema.type_of_path("Unknown/Thing") is None
    assert schema.type_of_path("Loose") is None
    assert schema.domain_note("sales") == "Domains/Market & sales"
    assert schema.domain_key("Market & sales") == "sales"
    assert schema.area_note("Pipeline") == "Areas/Pipeline"


def test_relation_targets_any_and_date():
    schema = load_schema()
    assert schema.relations["about"].targets is None
    assert schema.relations["when"].kind == "date"
    assert schema.relations["customer"].targets == ("Organizations",)


def test_mini_schema_loads(tmp_path):
    path = tmp_path / "s.yaml"
    path.write_text(MINI, encoding="utf-8")
    assert load_schema(path).types["People"].default_parent == "Pipeline"


@pytest.mark.parametrize("old, new, message", [
    ("domain: sales, level", "domain: nope, level", "unknown domain"),
    ("default_parent: Pipeline", "default_parent: Nowhere", "unknown default_parent"),
    ("optional: [owner]", "optional: [boss]", "unknown relation"),
    ("parent: [Areas]", "parent: [Domains]", "not an allowed parent"),
    ("level: 3", "level: 2", "level must be 3 or 4"),
])
def test_bad_schema_is_rejected(tmp_path, old, new, message):
    path = tmp_path / "s.yaml"
    path.write_text(MINI.replace(old, new), encoding="utf-8")
    with pytest.raises(SchemaError, match=message):
        load_schema(path)


def test_reserved_type_name_is_rejected(tmp_path):
    path = tmp_path / "s.yaml"
    path.write_text(MINI + "  Areas: {domain: sales, level: 3, parent: [Areas]}\n", encoding="utf-8")
    with pytest.raises(SchemaError, match="reserved"):
        load_schema(path)
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `market/.venv/Scripts/python -m pytest schema/tests/test_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ehl_schema.model'`.

- [ ] **Step 5: Implement `schema/ehl_schema/model.py`**

```python
"""Load the vault schema (schema/vault-schema.yaml) and check that it is consistent."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

log = logging.getLogger("ehl_schema.model")

DEFAULT_SCHEMA = Path(__file__).resolve().parents[1] / "vault-schema.yaml"
STRUCTURE_TYPES = ("Company", "Domains", "Areas")


class SchemaError(ValueError):
    """The schema file is malformed or contradicts itself."""


@dataclass(frozen=True)
class TypeDef:
    name: str
    domain: str                      # domain key; "*" for the generated structure types
    level: int                       # 0 Company, 1 Domains, 2 Areas, 3 entity, 4 detail
    parent: tuple[str, ...]          # allowed parent types, in order of preference
    default_parent: str | None = None  # area name used when no linked note fits
    builtin: bool = False            # a Rowboat type: keep its template body
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    template: str | None = None


@dataclass(frozen=True)
class RelationDef:
    name: str
    targets: tuple[str, ...] | None  # None = any note type
    kind: str = "link"               # "link" or "date"


@dataclass(frozen=True)
class Schema:
    version: int
    domains: dict[str, str]          # key -> title
    cross_cutting: frozenset[str]
    areas: dict[str, str]            # area name -> domain key
    relations: dict[str, RelationDef]
    types: dict[str, TypeDef]

    def domain_note(self, key: str) -> str:
        return f"Domains/{self.domains[key]}"

    def area_note(self, name: str) -> str:
        return f"Areas/{name}"

    def domain_key(self, title: str) -> str | None:
        return next((k for k, t in self.domains.items() if t == title), None)

    def type_of_path(self, path: str) -> str | None:
        """Schema type of a vault-relative note path without '.md', or None if the schema does not know it."""
        if path == "Company":
            return "Company"
        folder, sep, _ = path.partition("/")
        return folder if sep and folder in self.types else None


def _structure_types() -> dict[str, TypeDef]:
    return {
        "Company": TypeDef("Company", "*", 0, ()),
        "Domains": TypeDef("Domains", "*", 1, ("Company",)),
        "Areas": TypeDef("Areas", "*", 2, ("Domains",)),
    }


def load_schema(path: Path = DEFAULT_SCHEMA) -> Schema:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SchemaError(f"{path}: the schema must be a mapping")
    try:
        domains = {str(k): str(v["title"]) for k, v in raw["domains"].items()}
        cross = frozenset(str(k) for k, v in raw["domains"].items() if v.get("cross_cutting"))
        areas = {str(k): str(v) for k, v in raw["areas"].items()}
        relations = {}
        for name, spec in raw["relations"].items():
            spec = spec or {}
            targets = spec.get("targets")
            relations[str(name)] = RelationDef(
                str(name), None if targets in (None, "any") else tuple(targets), spec.get("kind", "link"))
        types = _structure_types()
        for name, spec in raw["types"].items():
            if name in types:
                raise SchemaError(f"type {name!r} is reserved for the generated structure notes")
            types[str(name)] = TypeDef(
                name=str(name), domain=str(spec["domain"]), level=int(spec["level"]),
                parent=tuple(spec["parent"]), default_parent=spec.get("default_parent"),
                builtin=bool(spec.get("builtin", False)), required=tuple(spec.get("required", ())),
                optional=tuple(spec.get("optional", ())), statuses=tuple(spec.get("statuses", ())),
                template=spec.get("template"))
        schema = Schema(int(raw["schema_version"]), domains, cross, areas, relations, types)
    except (KeyError, TypeError, AttributeError) as err:
        raise SchemaError(f"{path}: malformed schema ({err!r})") from err
    _check(schema)
    return schema


def _check(schema: Schema) -> None:
    errors = []
    for area, domain in schema.areas.items():
        if domain not in schema.domains:
            errors.append(f"area {area!r}: unknown domain {domain!r}")
    for key in schema.domains:
        if key not in schema.areas.values():
            errors.append(f"domain {key!r} has no area")
    for rel in schema.relations.values():
        if rel.kind not in ("link", "date"):
            errors.append(f"relation {rel.name!r}: kind must be link or date")
        for target in rel.targets or ():
            if target not in schema.types:
                errors.append(f"relation {rel.name!r}: unknown target type {target!r}")
    for name, td in schema.types.items():
        if name in STRUCTURE_TYPES:
            continue
        if td.domain not in schema.domains:
            errors.append(f"type {name!r}: unknown domain {td.domain!r}")
        if td.level not in (3, 4):
            errors.append(f"type {name!r}: level must be 3 or 4")
        if not td.parent:
            errors.append(f"type {name!r}: parent must list at least one type")
        for parent in td.parent:
            if parent not in schema.types or parent in ("Company", "Domains"):
                errors.append(f"type {name!r}: {parent!r} is not an allowed parent")
        if td.default_parent is not None and td.default_parent not in schema.areas:
            errors.append(f"type {name!r}: unknown default_parent {td.default_parent!r}")
        for rel in td.required + td.optional:
            if rel not in schema.relations:
                errors.append(f"type {name!r}: unknown relation {rel!r}")
    if errors:
        raise SchemaError("\n".join(errors))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `market/.venv/Scripts/python -m pytest schema/tests/test_model.py -v`
Expected: all PASS (11 tests).

- [ ] **Step 7: Commit**

```bash
git add schema/pyproject.toml schema/vault-schema.yaml schema/ehl_schema/__init__.py schema/ehl_schema/model.py schema/tests/test_model.py
git commit -m "feat(schema): vault schema file and loader" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Notes – front matter, links, vault reading

**Files:**
- Create: `schema/ehl_schema/notes.py`
- Test: `schema/tests/test_notes.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `LINK` (compiled regex)
  - `class FrontMatterError(ValueError)`
  - `Note(path, raw, front: dict | None, front_text: str, body: str, newline: str, error: str | None)`
  - `split(text) -> tuple[dict | None, str, str]`
  - `format_value(value) -> str`
  - `render_front(fields: dict) -> str`
  - `note_text(fields: dict, body: str) -> str`
  - `add_keys(note: Note, fields: dict) -> str`
  - `link_target(raw) -> str`
  - `links(text) -> list[str]`
  - `link_value(value) -> str | None`
  - `parent_target(note) -> str | None`
  - `read_vault(vault: Path) -> tuple[dict[str, Note], set[str]]`
  - `slug(text) -> str`

- [ ] **Step 1: Write the failing tests**

`schema/tests/test_notes.py`:

```python
"""Checks for ehl_schema.notes: front matter, links, values and reading a vault."""
import pytest
import yaml

from ehl_schema.notes import (FrontMatterError, add_keys, format_value, link_value, links, parent_target,
                              read_vault, slug, split)


def test_split_accepts_bom_and_crlf():
    front, raw, body = split("﻿---\r\nid: a\r\nwhen: 2026-10-12\r\n---\r\n# T\r\n")
    assert front == {"id": "a", "when": "2026-10-12"}
    assert raw == "id: a\nwhen: 2026-10-12"
    assert body == "# T\n"


def test_split_without_front_matter():
    assert split("# Just text\n") == (None, "", "# Just text\n")


def test_split_empty_front_matter():
    assert split("---\n---\nBody\n") == ({}, "", "Body\n")


def test_split_rejects_bad_yaml():
    with pytest.raises(FrontMatterError):
        split("---\nid: [unclosed\n---\nBody\n")


def test_links_strip_alias_and_heading():
    text = "[[Brands/BMW|BMW]] and [[Models/5er G60#Sales]] and [[Data/BMW Dataset.xlsx]]"
    assert links(text) == ["Brands/BMW", "Models/5er G60", "Data/BMW Dataset.xlsx"]


@pytest.mark.parametrize("value, rendered", [
    (3, "3"),
    ("prod", "prod"),
    ("2026-10-12", "2026-10-12"),
    ("yes", '"yes"'),
    ("[[Areas/Pipeline]]", '"[[Areas/Pipeline]]"'),
    ("Badges & logos", '"Badges & logos"'),
    (["[[Organizations/Acme]]"], '["[[Organizations/Acme]]"]'),
])
def test_format_value(value, rendered):
    assert format_value(value) == rendered


@pytest.mark.parametrize("value", ["[[Areas/IP & licences]]", "Ümlaut, comma: (x)", ["[[A/b]]", "[[C/d]]"], "yes", 4])
def test_format_value_round_trips(value):
    assert yaml.safe_load(f"k: {format_value(value)}")["k"] == value


def test_link_value_and_parent_target(tmp_path):
    assert link_value(' "[[Areas/Pipeline]]" '.strip().strip('"')) == "Areas/Pipeline"
    assert link_value("Areas/Pipeline") is None
    (tmp_path / "Deals").mkdir()
    (tmp_path / "Deals" / "D.md").write_text('---\nparent: "[[Areas/Pipeline|P]]"\n---\n', encoding="utf-8")
    notes, _ = read_vault(tmp_path)
    assert parent_target(notes["Deals/D"]) == "Areas/Pipeline"


def test_read_vault(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x.md").write_text("ignored", encoding="utf-8")
    (tmp_path / "Data").mkdir()
    (tmp_path / "Data" / "BMW Dataset.xlsx").write_bytes(b"x")
    (tmp_path / "Components").mkdir()
    (tmp_path / "Components" / "Badges & logos.md").write_bytes(b"---\r\nid: c\r\n---\r\nBody\r\n")
    (tmp_path / "Broken.md").write_text("---\nid: [x\n---\n", encoding="utf-8")
    notes, files = read_vault(tmp_path)
    assert set(notes) == {"Components/Badges & logos", "Broken"}
    assert "Data/BMW Dataset.xlsx" in files and ".git/x.md" not in files
    note = notes["Components/Badges & logos"]
    assert note.front == {"id": "c"} and note.newline == "\r\n" and note.error is None
    assert notes["Broken"].error


def test_add_keys_keeps_crlf_and_existing_lines(tmp_path):
    (tmp_path / "Brands").mkdir()
    (tmp_path / "Brands" / "BMW.md").write_bytes(b"---\r\nsource: dataset\r\nmanaged_by: torque\r\n---\r\nBody\r\n")
    notes, _ = read_vault(tmp_path)
    text = add_keys(notes["Brands/BMW"], {"id": "brands-bmw", "source": "other", "parent": "[[Areas/Brand]]"})
    assert text == ('---\r\nsource: dataset\r\nmanaged_by: torque\r\nid: brands-bmw\r\n'
                    'parent: "[[Areas/Brand]]"\r\n---\r\nBody\r\n')
    assert text.index("managed_by: torque") < 300


def test_add_keys_to_note_without_front_matter(tmp_path):
    (tmp_path / "Topics").mkdir()
    (tmp_path / "Topics" / "T.md").write_text("# T\n", encoding="utf-8")
    notes, _ = read_vault(tmp_path)
    assert add_keys(notes["Topics/T"], {"id": "topics-t"}) == "---\nid: topics-t\n---\n# T\n"


def test_slug():
    assert slug("Feature Classes-Hood, open / close") == "feature-classes-hood-open-close"
    assert slug("Ümlaut Ärger") == "umlaut-arger"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `market/.venv/Scripts/python -m pytest schema/tests/test_notes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ehl_schema.notes'`.

- [ ] **Step 3: Implement `schema/ehl_schema/notes.py`**

```python
"""Vault notes: read a vault, split and extend flat front matter, parse [[links]]."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

LINK = re.compile(r"\[\[([^\]\n]+)\]\]")
PLAIN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
RESERVED = {"true", "false", "yes", "no", "on", "off", "null", "none", "y", "n"}


class FrontMatterError(ValueError):
    """The front matter is not valid YAML or not a mapping."""


@dataclass
class Note:
    path: str                 # vault-relative, forward slashes, without ".md"
    raw: str                  # the file as read (decoded, original newlines)
    front: dict | None        # parsed front matter; None if the note has none (or it is broken)
    front_text: str           # the lines between the --- fences, "\n"-separated
    body: str                 # everything after the closing fence, "\n" newlines
    newline: str              # "\r\n" or "\n", as found in the file
    error: str | None = None  # why the front matter could not be read


def _normalise(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    if isinstance(value, list):
        return [_normalise(v) for v in value]
    return value


def split(text: str) -> tuple[dict | None, str, str]:
    """(front matter or None, raw front matter lines, body). Accepts a BOM and CRLF."""
    t = text.lstrip("﻿").replace("\r\n", "\n")
    if not t.startswith("---\n"):
        return None, "", t
    if t.startswith("---\n---\n"):
        return {}, "", t[8:]
    end = t.find("\n---\n", 3)
    if end == -1:
        if t.endswith("\n---"):
            end = len(t) - 4
        else:
            return None, "", t
    raw = t[4:end]
    body = t[end + 5:]
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as err:
        raise FrontMatterError(f"front matter is not valid YAML: {err}") from err
    if not isinstance(data, dict):
        raise FrontMatterError("front matter is not a mapping")
    return {str(k): _normalise(v) for k, v in data.items()}, raw, body


def format_value(value) -> str:
    """One YAML value as it is written into front matter: plain when safe, JSON-quoted otherwise."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return json.dumps([str(v) for v in value], ensure_ascii=False)
    text = str(value)
    if DATE.fullmatch(text) or (PLAIN.fullmatch(text) and text.lower() not in RESERVED):
        return text
    return json.dumps(text, ensure_ascii=False)


def render_front(fields: dict) -> str:
    return "\n".join(f"{key}: {format_value(value)}" for key, value in fields.items())


def note_text(fields: dict, body: str) -> str:
    return f"---\n{render_front(fields)}\n---\n{body}"


def add_keys(note: Note, fields: dict) -> str:
    """The note's text with every key of `fields` it does not have yet appended to its front matter.
    Existing lines stay first and unchanged; the file's newline style is kept."""
    existing = note.front or {}
    lines = [line for line in note.front_text.split("\n") if line.strip()] if note.front is not None else []
    lines += [f"{key}: {format_value(value)}" for key, value in fields.items() if key not in existing]
    text = "---\n" + "\n".join(lines) + "\n---\n" + note.body
    return text.replace("\n", "\r\n") if note.newline == "\r\n" else text


def link_target(raw: str) -> str:
    return raw.split("|", 1)[0].split("#", 1)[0].strip()


def links(text: str) -> list[str]:
    return [t for t in (link_target(m) for m in LINK.findall(text)) if t]


def link_value(value) -> str | None:
    """Target of a value that is exactly one [[link]], else None."""
    m = LINK.fullmatch(value.strip()) if isinstance(value, str) else None
    return link_target(m.group(1)) if m else None


def parent_target(note: Note) -> str | None:
    return link_value((note.front or {}).get("parent"))


def read_vault(vault: Path) -> tuple[dict[str, Note], set[str]]:
    """All notes (path without .md -> Note) and all file paths; skips hidden folders such as .git."""
    notes: dict[str, Note] = {}
    files: set[str] = set()
    for file in sorted(vault.rglob("*")):
        rel = file.relative_to(vault)
        if not file.is_file() or any(part.startswith(".") for part in rel.parts):
            continue
        key = rel.as_posix()
        files.add(key)
        if file.suffix != ".md":
            continue
        raw = file.read_bytes().decode("utf-8")
        newline = "\r\n" if "\r\n" in raw else "\n"
        try:
            front, front_text, body = split(raw)
            error = None
        except FrontMatterError as err:
            front, front_text, body, error = None, "", raw.replace("\r\n", "\n"), str(err)
        notes[key[:-3]] = Note(key[:-3], raw, front, front_text, body, newline, error)
    return notes, files


def slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `market/.venv/Scripts/python -m pytest schema/tests/test_notes.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add schema/ehl_schema/notes.py schema/tests/test_notes.py
git commit -m "feat(schema): read vault notes, flat front matter and links" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Linter

**Files:**
- Create: `schema/ehl_schema/lint.py`, `schema/tests/helpers.py`
- Test: `schema/tests/test_lint.py`

**Interfaces:**
- Consumes:
  - Task 1: `Schema`, `STRUCTURE_TYPES`, `load_schema`
  - Task 2: `LINK`, `Note`, `link_value`, `links`, `parent_target`, `read_vault`, `note_text`
- Produces:
  - `Issue(severity: str, path: str, code: str, message: str)`, where `severity` is `"error"` or `"warning"`
  - `lint(schema, vault: Path) -> list[Issue]`
  - `errors(issues) -> list[Issue]`
  - Helpers (tests only):
    - `write_note(vault, path, front: dict | None, body="") -> Path`
    - `valid_vault(tmp_path, schema) -> Path`

Error codes: `unknown-type`, `bad-yaml`, `no-front-matter`, `nested`, `missing-key`,
`type-mismatch`, `not-in-schema`, `domain-mismatch`, `level-mismatch`, `duplicate-id`, `parent-format`,
`parent-missing`, `parent-type`, `parent-level`, `cycle`, `relation-format`, `relation-missing`,
`relation-target`, `required-relation`.

Warning codes: `status-value`, `broken-link` (a link in the body), `possible-duplicate`.

- [ ] **Step 1: Write the test helpers**

`schema/tests/helpers.py`:

```python
"""Helpers for the schema tests: write notes and small valid vaults."""
from pathlib import Path

from ehl_schema.notes import note_text


def write_note(vault: Path, path: str, front: dict | None, body: str = "") -> Path:
    file = vault / f"{path}.md"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(note_text(front, body) if front is not None else body, encoding="utf-8")
    return file


def structure(schema, key: str, area: str) -> dict:
    """front matter of the domain note and the area note a test needs."""
    return {
        schema.domain_note(key): {"id": f"domain-{key}", "type": "Domains", "domain": key, "level": 1,
                                  "parent": "[[Company]]"},
        schema.area_note(area): {"id": f"area-{area.lower()}", "type": "Areas", "domain": key, "level": 2,
                                 "parent": f"[[{schema.domain_note(key)}]]"},
    }


def valid_vault(tmp_path: Path, schema) -> Path:
    vault = tmp_path / "knowledge"
    write_note(vault, "Company", {"id": "company", "type": "Company", "domain": "company", "level": 0})
    notes = {**structure(schema, "sales", "Pipeline"), **structure(schema, "register", "Companies")}
    notes[schema.area_note("Contacts")] = {"id": "area-contacts", "type": "Areas", "domain": "register",
                                           "level": 2, "parent": f"[[{schema.domain_note('register')}]]"}
    for path, front in notes.items():
        write_note(vault, path, front)
    write_note(vault, "Organizations/Acme", {"id": "org-acme", "type": "Organizations", "domain": "register",
                                             "level": 3, "parent": "[[Areas/Companies]]"})
    write_note(vault, "People/Felix Baumann", {"id": "person-felix", "type": "People", "domain": "register",
                                               "level": 3, "parent": "[[Areas/Contacts]]",
                                               "works_at": ["[[Organizations/Acme]]"]})
    write_note(vault, "Deals/Acme deal", {"id": "deal-acme", "type": "Deals", "domain": "sales", "level": 3,
                                          "parent": "[[Areas/Pipeline]]", "status": "proposal",
                                          "customer": ["[[Organizations/Acme]]"],
                                          "owner": ["[[People/Felix Baumann]]"], "when": "2026-10-20"},
               "# Acme deal\n\nWith [[Organizations/Acme|Acme]].\n")
    return vault
```

- [ ] **Step 2: Write the failing tests**

`schema/tests/test_lint.py`:

```python
"""Checks for ehl_schema.lint."""
import pytest
from helpers import valid_vault, write_note

from ehl_schema.lint import errors, lint
from ehl_schema.model import load_schema


@pytest.fixture
def schema():
    return load_schema()


def codes(issues, path=None):
    return {i.code for i in issues if path is None or i.path == path}


def deal(**changes):
    front = {"id": "deal-x", "type": "Deals", "domain": "sales", "level": 3, "parent": "[[Areas/Pipeline]]",
             "customer": ["[[Organizations/Acme]]"], "owner": ["[[People/Felix Baumann]]"]}
    front.update(changes)
    return {k: v for k, v in front.items() if v is not None}


def test_valid_vault_has_no_issues(tmp_path, schema):
    assert lint(schema, valid_vault(tmp_path, schema)) == []


def test_unknown_folder_and_missing_front_matter(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Random/Thing", {"id": "x"})
    write_note(vault, "Topics/Loose", None, "# Loose\n")
    issues = lint(schema, vault)
    assert codes(issues, "Random/Thing") == {"unknown-type"}
    assert codes(issues, "Topics/Loose") == {"no-front-matter"}


def test_bad_yaml(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    (vault / "Topics").mkdir()
    (vault / "Topics" / "Bad.md").write_text("---\nid: [x\n---\n", encoding="utf-8")
    assert codes(lint(schema, vault), "Topics/Bad") == {"bad-yaml"}


def test_wrong_type_domain_level(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Deals/X", deal(type="Leads", domain="legal", level=4))
    assert codes(lint(schema, vault), "Deals/X") >= {"type-mismatch", "domain-mismatch", "level-mismatch"}


def test_missing_key_and_nested_value(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Deals/X", deal(parent=None))
    (vault / "Deals" / "Y.md").write_text(
        '---\nid: deal-y\ntype: Deals\ndomain: sales\nlevel: 3\nparent: "[[Areas/Pipeline]]"\n'
        'owner:\n  name: Felix\n---\n', encoding="utf-8")
    issues = lint(schema, vault)
    assert "missing-key" in codes(issues, "Deals/X")
    assert "nested" in codes(issues, "Deals/Y")


def test_parent_rules(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Deals/A", deal(id="a", parent="[[People/Felix Baumann]]"))
    write_note(vault, "Deals/B", deal(id="b", parent="[[Areas/Nowhere]]"))
    write_note(vault, "Deals/C", deal(id="c", parent="Areas/Pipeline"))
    issues = lint(schema, vault)
    assert "parent-type" in codes(issues, "Deals/A")
    assert "parent-missing" in codes(issues, "Deals/B")
    assert "parent-format" in codes(issues, "Deals/C")


def test_cycle(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    base = {"type": "Projects", "domain": "delivery", "level": 3}
    write_note(vault, "Projects/A", {**base, "id": "pa", "parent": "[[Projects/B]]"})
    write_note(vault, "Projects/B", {**base, "id": "pb", "parent": "[[Projects/A]]"})
    assert "cycle" in codes(lint(schema, vault))


def test_relations(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Deals/A", deal(id="a", customer=None))
    write_note(vault, "Deals/B", deal(id="b", customer=["[[People/Felix Baumann]]"]))
    write_note(vault, "Deals/C", deal(id="c", customer="[[Organizations/Acme]]"))
    write_note(vault, "Deals/D", deal(id="d", customer=["[[Organizations/Nobody]]"]))
    write_note(vault, "Deals/E", deal(id="e", when="next week"))
    issues = lint(schema, vault)
    assert "required-relation" in codes(issues, "Deals/A")
    assert "relation-target" in codes(issues, "Deals/B")
    assert "relation-format" in codes(issues, "Deals/C")
    assert "relation-missing" in codes(issues, "Deals/D")
    assert "relation-format" in codes(issues, "Deals/E")


def test_duplicate_id_and_status(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Deals/Copy", deal(id="deal-acme", status="maybe"))
    issues = lint(schema, vault)
    assert "duplicate-id" in codes(issues, "Deals/Copy")
    assert any(i.code == "status-value" and i.severity == "warning" for i in issues)


def test_broken_body_link_is_a_warning(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Deals/X", deal(), "See [[Topics/Nope]].\n")
    issues = lint(schema, vault)
    assert codes(issues, "Deals/X") == {"broken-link"}
    assert errors(issues) == []


def test_alias_and_attachment_links_resolve(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    (vault / "Data").mkdir()
    (vault / "Data" / "BMW Dataset.xlsx").write_bytes(b"x")
    write_note(vault, "Deals/X", deal(), "[[Organizations/Acme|Acme]] [[Data/BMW Dataset.xlsx|data]] [[Deals/Acme deal#Top]]\n")
    assert codes(lint(schema, vault), "Deals/X") == set()


def test_possible_duplicate_people(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "People/Felix-Baumann", {"id": "p2", "type": "People", "domain": "register", "level": 3,
                                               "parent": "[[Areas/Contacts]]"})
    issues = lint(schema, vault)
    assert {i.path for i in issues if i.code == "possible-duplicate"} == {"People/Felix Baumann",
                                                                          "People/Felix-Baumann"}
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `market/.venv/Scripts/python -m pytest schema/tests/test_lint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ehl_schema.lint'`.

- [ ] **Step 4: Implement `schema/ehl_schema/lint.py`**

```python
"""Check a vault against the schema. Errors break the hierarchy; warnings are worth a look."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .model import Schema, TypeDef
from .notes import DATE, Note, link_value, links, parent_target, read_vault

FIELD = re.compile(r"^\*\*(Email|Domain):\*\*\s*(\S+)", re.M)
BASE_KEYS = ("id", "type", "domain", "level")


@dataclass(frozen=True)
class Issue:
    severity: str   # "error" | "warning"
    path: str
    code: str
    message: str


def errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "error"]


def lint(schema: Schema, vault: Path) -> list[Issue]:
    notes, files = read_vault(vault)
    issues: list[Issue] = []
    ids: dict[str, str] = {}
    for note in notes.values():
        issues.extend(_check_note(schema, note, notes, files, ids))
    issues.extend(_check_cycles(notes))
    issues.extend(_check_duplicates(notes))
    return sorted(issues, key=lambda i: (i.path, i.code, i.message))


def _expected_domain(schema: Schema, tname: str, path: str) -> str | None:
    name = path.partition("/")[2]
    if tname == "Domains":
        return schema.domain_key(name)
    if tname == "Areas":
        return schema.areas.get(name)
    return schema.types[tname].domain


def _check_note(schema: Schema, note: Note, notes: dict, files: set, ids: dict) -> list[Issue]:
    out: list[Issue] = []

    def add(severity: str, code: str, message: str) -> None:
        out.append(Issue(severity, note.path, code, message))

    tname = schema.type_of_path(note.path)
    if tname is None:
        add("error", "unknown-type", "the folder of this note is not a note type in the schema")
        return out
    if note.error:
        add("error", "bad-yaml", note.error)
        return out
    if note.front is None:
        add("error", "no-front-matter", "the note has no front matter (run: ehl-schema migrate)")
        return out
    front = note.front
    for key, value in front.items():
        if isinstance(value, dict) or (isinstance(value, list) and not all(isinstance(v, str) for v in value)):
            add("error", "nested", f"{key!r} must be flat: a value or a list of strings")
    needed = BASE_KEYS + (() if tname == "Company" else ("parent",))
    for key in needed:
        if front.get(key) in (None, ""):
            add("error", "missing-key", f"{key!r} is missing")
    if out:
        return out
    td = schema.types[tname]
    if front["type"] != tname:
        add("error", "type-mismatch", f"type is {front['type']!r}, but the folder says {tname!r}")
    if tname != "Company":
        expected = _expected_domain(schema, tname, note.path)
        if expected is None:
            add("error", "not-in-schema", f"{note.path!r} is not a domain or area of the schema")
        elif front["domain"] != expected:
            add("error", "domain-mismatch", f"domain is {front['domain']!r}, expected {expected!r}")
    if front["level"] != td.level:
        add("error", "level-mismatch", f"level is {front['level']!r}, expected {td.level}")
    first = ids.setdefault(str(front["id"]), note.path)
    if first != note.path:
        add("error", "duplicate-id", f"id {front['id']!r} is also used by {first!r}")
    if tname != "Company":
        out.extend(_check_parent(schema, note, td, notes))
    out.extend(_check_relations(schema, note, td, notes, files))
    if td.statuses and "status" in front and front["status"] not in td.statuses:
        add("warning", "status-value", f"status {front['status']!r} is not one of {', '.join(td.statuses)}")
    for target in links(note.body):
        if target not in notes and target not in files:
            add("warning", "broken-link", f"[[{target}]] does not exist")
    return out


def _check_parent(schema: Schema, note: Note, td: TypeDef, notes: dict) -> list[Issue]:
    target = parent_target(note)
    if target is None:
        return [Issue("error", note.path, "parent-format", 'parent must be one quoted link like "[[Areas/Pipeline]]"')]
    if target not in notes:
        return [Issue("error", note.path, "parent-missing", f"parent [[{target}]] does not exist")]
    ptype = schema.type_of_path(target)
    if ptype not in td.parent:
        return [Issue("error", note.path, "parent-type",
                      f"parent [[{target}]] is a {ptype}; allowed: {', '.join(td.parent)}")]
    if schema.types[ptype].level > td.level:
        return [Issue("error", note.path, "parent-level", f"parent [[{target}]] is on a lower level than the note")]
    return []


def _check_relations(schema: Schema, note: Note, td: TypeDef, notes: dict, files: set) -> list[Issue]:
    out: list[Issue] = []
    front = note.front or {}
    for name, rel in schema.relations.items():
        if name not in front:
            if name in td.required:
                out.append(Issue("error", note.path, "required-relation", f"{name!r} is required"))
            continue
        value = front[name]
        if rel.kind == "date":
            if not isinstance(value, str) or not DATE.fullmatch(value):
                out.append(Issue("error", note.path, "relation-format", f"{name!r} must be a date YYYY-MM-DD"))
            continue
        targets = [link_value(v) for v in value] if isinstance(value, list) else [None]
        if None in targets:
            out.append(Issue("error", note.path, "relation-format",
                             f'{name!r} must be a list of quoted links like ["[[Folder/Name]]"]'))
            continue
        if not targets and name in td.required:
            out.append(Issue("error", note.path, "required-relation", f"{name!r} must not be empty"))
        for target in targets:
            if target not in notes and target not in files:
                out.append(Issue("error", note.path, "relation-missing", f"{name}: [[{target}]] does not exist"))
            elif rel.targets is not None and schema.type_of_path(target) not in rel.targets:
                out.append(Issue("error", note.path, "relation-target",
                                 f"{name}: [[{target}]] must be a {' or '.join(rel.targets)}"))
    return out


def _check_cycles(notes: dict[str, Note]) -> list[Issue]:
    parent = {p: t for p, n in notes.items() if (t := parent_target(n)) is not None}
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


def _check_duplicates(notes: dict[str, Note]) -> list[Issue]:
    groups: dict[tuple[str, str], list[str]] = {}
    for path, note in notes.items():
        folder, _, name = path.partition("/")
        if folder not in ("People", "Organizations") or not name:
            continue
        keys = {("name", folder + ":" + re.sub(r"[^a-z0-9]", "", name.lower()))}
        for kind, value in FIELD.findall(note.body):
            value = value.strip().lower()
            if value and not value.startswith("{"):
                keys.add((kind.lower(), value))
        for key in keys:
            groups.setdefault(key, []).append(path)
    out = []
    for (kind, _), paths in groups.items():
        if len(paths) > 1:
            for path in paths:
                others = ", ".join(p for p in paths if p != path)
                out.append(Issue("warning", path, "possible-duplicate", f"same {kind} as {others}"))
    return out
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `market/.venv/Scripts/python -m pytest schema/tests -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add schema/ehl_schema/lint.py schema/tests/helpers.py schema/tests/test_lint.py
git commit -m "feat(schema): linter for the vault hierarchy" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Build – structure notes, rules note, notes.json

**Files:**
- Create: `schema/ehl_schema/build.py`
- Test: `schema/tests/test_build.py`

**Interfaces:**
- Consumes:
  - Task 1: `Schema`, `STRUCTURE_TYPES`, `load_schema`
  - Task 2: `note_text`, `split`, `slug`
  - Task 3: `lint`
- Produces:
  - `MANAGED = "schema"`, `RULES_NOTE = "Agent Notes/Vault Schema"`, `RULES_MARK = "\n\nSchema rules ("`
  - `structure_notes(schema, company: str) -> dict[str, str]`: path → full text, includes the rules note
  - `write_structure(schema, vault: Path, company: str) -> int`: number of notes written
  - `notes_json(schema, existing: list[dict]) -> list[dict]`
  - `build(schema, workdir: Path, company: str) -> dict`: `{"notes": int, "notes_json": "updated" | "unchanged" | "missing"}`

- [ ] **Step 1: Write the failing tests**

`schema/tests/test_build.py`:

```python
"""Checks for ehl_schema.build."""
import json

import pytest
from helpers import write_note

from ehl_schema.build import RULES_MARK, RULES_NOTE, build, notes_json, structure_notes
from ehl_schema.lint import lint
from ehl_schema.model import load_schema

ROWBOAT_NOTES_JSON = [
    {"type": "People", "folder": "People", "template": "# {Full Name}\n\n## Info\n", "extractionGuide": "Look for: name"},
    {"type": "Meetings", "folder": "Meetings", "template": "", "extractionGuide": "Look for: meeting title"},
    {"type": "Custom", "folder": "Custom", "template": "x", "extractionGuide": ""},
]


@pytest.fixture
def schema():
    return load_schema()


@pytest.fixture
def workdir(tmp_path):
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "notes.json").write_text(json.dumps(ROWBOAT_NOTES_JSON), encoding="utf-8")
    return tmp_path


def test_structure_notes_cover_company_domains_areas_and_rules(schema):
    notes = structure_notes(schema, "EHL")
    assert len(notes) == 1 + len(schema.domains) + len(schema.areas) + 1
    assert notes["Company"].startswith("---\nid: company\n")
    assert "# EHL" in notes["Company"]
    assert 'parent: "[[Domains/Market & sales]]"' in notes["Areas/Pipeline"]
    assert RULES_NOTE in notes


def test_build_on_empty_vault_lints_clean(schema, workdir):
    result = build(schema, workdir, "EHL")
    assert result == {"notes": len(structure_notes(schema, "EHL")), "notes_json": "updated"}
    assert lint(schema, workdir / "knowledge") == []


def test_build_is_idempotent(schema, workdir):
    build(schema, workdir, "EHL")
    before = (workdir / "config" / "notes.json").read_text(encoding="utf-8")
    assert build(schema, workdir, "EHL") == {"notes": 0, "notes_json": "unchanged"}
    after = (workdir / "config" / "notes.json").read_text(encoding="utf-8")
    assert before == after
    people = next(e for e in json.loads(after) if e["type"] == "People")
    assert people["extractionGuide"].count(RULES_MARK) == 1


def test_notes_json_keeps_rowboat_bodies_and_foreign_types(schema):
    entries = {e["type"]: e for e in notes_json(schema, ROWBOAT_NOTES_JSON)}
    people = entries["People"]
    assert people["template"].startswith("---\nid: {")
    assert "# {Full Name}" in people["template"]
    assert people["extractionGuide"].startswith("Look for: name")
    assert entries["Meetings"]["template"] == ""
    assert entries["Custom"] == ROWBOAT_NOTES_JSON[2]
    assert entries["Deals"]["folder"] == "Deals"
    assert 'customer: ["[[{Organizations/…}]]"]' in entries["Deals"]["template"]
    assert "Voice Memos" not in entries and "Areas" not in entries


def test_build_does_not_overwrite_a_human_note(schema, workdir):
    path = write_note(workdir / "knowledge", "Areas/Pipeline", {"id": "mine"}, "# My pipeline\n")
    before = path.read_text(encoding="utf-8")
    build(schema, workdir, "EHL")
    assert path.read_text(encoding="utf-8") == before


def test_build_without_notes_json(schema, tmp_path):
    (tmp_path / "knowledge").mkdir()
    assert build(schema, tmp_path, "EHL")["notes_json"] == "missing"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `market/.venv/Scripts/python -m pytest schema/tests/test_build.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ehl_schema.build'`.

- [ ] **Step 3: Implement `schema/ehl_schema/build.py`**

```python
"""Generate what the schema implies: Company/Domains/Areas notes, the rules note and Rowboat's notes.json."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .model import STRUCTURE_TYPES, Schema, TypeDef
from .notes import note_text, slug, split

log = logging.getLogger("ehl_schema.build")

MANAGED = "schema"
RULES_NOTE = "Agent Notes/Vault Schema"
RULES_MARK = "\n\nSchema rules ("
GENERIC_BODY = ("# {Title}\n\n## Summary\n{2-3 sentences.}\n\n## Key facts\n{Substantive facts only. Leave empty if "
                "none.}\n\n## Open items\n{Next steps only. Leave empty if none.}\n")


def _front(schema: Schema, **fields) -> dict:
    return {**fields, "managed_by": MANAGED, "schema_version": schema.version}


def structure_notes(schema: Schema, company: str) -> dict[str, str]:
    notes: dict[str, str] = {}
    domain_links = "\n".join(f"- [[{schema.domain_note(k)}]]" for k in schema.domains)
    notes["Company"] = note_text(
        _front(schema, id="company", type="Company", domain="company", level=0),
        f"# {company}\n\n## Info\n**Type:** Company (L0)\n\n## Domains\n{domain_links}\n")
    for key, title in schema.domains.items():
        areas = "\n".join(f"- [[{schema.area_note(a)}]]" for a, d in schema.areas.items() if d == key)
        notes[schema.domain_note(key)] = note_text(
            _front(schema, id=f"domain-{key}", type="Domains", domain=key, level=1, parent="[[Company]]"),
            f"# {title}\n\n## Info\n**Type:** Domain (L1)\n**Key:** {key}\n\n## Areas\n{areas}\n")
    for area, key in schema.areas.items():
        types = ", ".join(n for n, td in schema.types.items() if td.default_parent == area) or "none"
        notes[schema.area_note(area)] = note_text(
            _front(schema, id=f"area-{slug(area)}", type="Areas", domain=key, level=2,
                   parent=f"[[{schema.domain_note(key)}]]"),
            f"# {area}\n\n## Info\n**Type:** Area (L2)\n**Domain:** [[{schema.domain_note(key)}]]\n"
            f"**Note types placed here by default:** {types}\n")
    td = schema.types["Agent Notes"]
    notes[RULES_NOTE] = note_text(
        _front(schema, id="agent-notes-vault-schema", type="Agent Notes", domain=td.domain, level=td.level,
               parent=f"[[{schema.area_note(td.default_parent)}]]"),
        rules_body(schema))
    return notes


def rules_body(schema: Schema) -> str:
    lines = [f"# Vault schema (v{schema.version})", "",
             "Generated from schema/vault-schema.yaml by `ehl-schema build`. Do not edit; change the schema file.", "",
             "## Front matter", "",
             "Every note starts with flat YAML front matter. Required keys: id, type, domain, level, parent.",
             "- `id`: a stable slug; never change it. `type`: the folder name. `level`: from the table below.",
             '- `parent`: exactly one quoted link, for example `parent: "[[Areas/Pipeline]]"`.',
             '- Relations are lists of quoted links with the full path, for example `about: ["[[Areas/Pipeline]]"]`.',
             "- Never nest keys. Optional: status, visibility (team | restricted), env (prod | test), when (YYYY-MM-DD).",
             "", "## Domains and areas", "", "| Domain | Key | Areas |", "|---|---|---|"]
    for key, title in schema.domains.items():
        areas = ", ".join(a for a, d in schema.areas.items() if d == key)
        lines.append(f"| {title} | {key} | {areas} |")
    lines += ["", "## Note types", "",
              "| Type (folder) | Domain | Level | Parent (in order) | Default area | Required | Optional |",
              "|---|---|---|---|---|---|---|"]
    for name, td in schema.types.items():
        if name in STRUCTURE_TYPES:
            continue
        lines.append(f"| {name} | {td.domain} | {td.level} | {', '.join(td.parent)} | {td.default_parent or ''} | "
                     f"{', '.join(td.required) or '–'} | {', '.join(td.optional) or '–'} |")
    lines += ["", "## Relations", "", "| Key | Points to |", "|---|---|"]
    for name, rel in schema.relations.items():
        target = "a date" if rel.kind == "date" else ("any note" if rel.targets is None else ", ".join(rel.targets))
        lines.append(f"| {name} | {target} |")
    return "\n".join(lines) + "\n"


def write_structure(schema: Schema, vault: Path, company: str) -> int:
    written = 0
    for path, text in structure_notes(schema, company).items():
        file = vault / f"{path}.md"
        if file.exists():
            old = file.read_text(encoding="utf-8")
            if old == text:
                continue
            front, _, _ = split(old)
            if (front or {}).get("managed_by") != MANAGED:
                log.warning("%s exists and is not managed by the schema; left as it is", file)
                continue
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8", newline="\n")
        written += 1
    return written


def _parent_hint(td: TypeDef) -> str:
    if td.parent == ("Areas",):
        return f"Areas/{td.default_parent}"
    options = ", ".join(f"{p}/…" for p in td.parent if p != "Areas")
    return f"one of: {options}" + (f" (else Areas/{td.default_parent})" if td.default_parent else "")


def _skeleton(schema: Schema, td: TypeDef) -> str:
    lines = ["---", "id: {slug of the title}", f"type: {td.name}", f"domain: {td.domain}", f"level: {td.level}",
             f'parent: "[[{{{_parent_hint(td)}}}]]"']
    for name in td.required:
        rel = schema.relations[name]
        if rel.kind == "date":
            lines.append(f"{name}: {{YYYY-MM-DD}}")
        else:
            target = rel.targets[0] if rel.targets else "Folder"
            lines.append(f'{name}: ["[[{{{target}/…}}]]"]')
    lines += [f"schema_version: {schema.version}", "---", ""]
    return "\n".join(lines)


def _guide(schema: Schema, td: TypeDef) -> str:
    default = f" (else [[Areas/{td.default_parent}]])" if td.default_parent else ""
    return (f"v{schema.version}): flat YAML front matter. type: {td.name}; domain: {td.domain}; level: {td.level}; "
            f"id: a stable slug, never change it. parent: exactly one quoted link to a note of type "
            f"{', '.join(td.parent)}{default}. Required relations: {', '.join(td.required) or 'none'}. "
            f"Optional relations: {', '.join(td.optional) or 'none'}. Relation values are lists of quoted "
            f'full-path links like ["[[Organizations/Acme]]"]. Status: {", ".join(td.statuses) or "free text"}.')


def _strip_front(template: str) -> str:
    """The template body without a leading --- block. Text-based: template placeholders are not always YAML."""
    t = template.replace("\r\n", "\n")
    if t.startswith("---\n"):
        end = t.find("\n---\n", 3)
        if end != -1:
            return t[end + 5:]
    return t


def notes_json(schema: Schema, existing: list[dict]) -> list[dict]:
    by_type = {e["type"]: dict(e) for e in existing if isinstance(e, dict) and "type" in e}
    order = [e["type"] for e in existing if isinstance(e, dict) and "type" in e]
    for name, td in schema.types.items():
        if name in STRUCTURE_TYPES or (td.builtin and name not in by_type):
            continue
        entry = by_type.get(name, {"type": name, "folder": name, "template": "", "extractionGuide": ""})
        if name not in by_type:
            order.append(name)
        template = entry.get("template") or ""
        if not (td.builtin and not template.strip()):
            body = _strip_front(template)
            body = body if body.strip() else (td.template or GENERIC_BODY)
            entry["template"] = _skeleton(schema, td) + body
        guide = (entry.get("extractionGuide") or "").split(RULES_MARK)[0]
        entry["extractionGuide"] = guide + RULES_MARK + _guide(schema, td)
        by_type[name] = entry
    return [by_type[name] for name in order]


def build(schema: Schema, workdir: Path, company: str) -> dict:
    written = write_structure(schema, workdir / "knowledge", company)
    config = workdir / "config" / "notes.json"
    if not config.exists():
        log.warning("%s does not exist yet: start Rowboat once, then run build again", config)
        return {"notes": written, "notes_json": "missing"}
    old = config.read_text(encoding="utf-8")
    new = json.dumps(notes_json(schema, json.loads(old)), indent=2, ensure_ascii=False) + "\n"
    if new == old:
        return {"notes": written, "notes_json": "unchanged"}
    config.write_text(new, encoding="utf-8", newline="\n")
    return {"notes": written, "notes_json": "updated"}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `market/.venv/Scripts/python -m pytest schema/tests -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add schema/ehl_schema/build.py schema/tests/test_build.py
git commit -m "feat(schema): generate structure notes, rules note and notes.json" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Migration

**Files:**
- Create: `schema/ehl_schema/migrate.py`
- Test: `schema/tests/test_migrate.py`

**Interfaces:**
- Consumes:
  - Task 1: `Schema`, `STRUCTURE_TYPES`
  - Task 2: `add_keys`, `links`, `parent_target`, `read_vault`, `slug`
  - Task 3: `lint`, `errors`
  - Task 4: `build`
- Produces:
  - `Report(changes: dict[str, tuple[str, str]], unmapped: list[str], unresolved: list[str])`
  - `plan(schema, vault: Path) -> Report`
  - `apply(report, vault: Path) -> int`
  - `diff(report) -> str`

**How a parent is chosen:**
- **Candidates:** the notes this note links to, plus the notes that link to it. Each candidate must
  exist, must not be the note itself, must have a type allowed as a parent, and must not be on a lower
  level than the note.
- **Same type (hub rule):** a candidate of the note's own type is only taken if it has more distinct
  neighbours than the note.
- **No cycles:** a candidate that would create a cycle is skipped.
- **Ranking:** first by the position of its type in `parent`, then by more neighbours, then by path.
- **Fallback:** `Areas/<default_parent>`. If there is no default either, the note is reported as unresolved.
- **Processing order:** by level, then by more neighbours, then by path.

- [ ] **Step 1: Write the failing tests**

`schema/tests/test_migrate.py`:

```python
"""Checks for ehl_schema.migrate on a small vault shaped like the EHL vault."""
import pytest
from helpers import write_note

from ehl_schema.build import build
from ehl_schema.lint import errors, lint
from ehl_schema.migrate import apply, diff, plan
from ehl_schema.model import load_schema
from ehl_schema.notes import read_vault


@pytest.fixture
def schema():
    return load_schema()


@pytest.fixture
def vault(tmp_path, schema):
    v = tmp_path / "knowledge"
    build(schema, tmp_path, "EHL")
    write_note(v, "Brands/BMW", {"source": "dataset", "managed_by": "ehl-visu"}, "[[Models/5er G60]]\n")
    write_note(v, "Models/5er G60", {"source": "dataset"}, "[[Brands/BMW|BMW]] [[Components/Hood]] [[Feature Classes/Hood open close]]\n")
    write_note(v, "Components/Hood", {"part_id": "hood"}, "[[Models/5er G60]]\n")
    write_note(v, "Feature Classes/Hood open close", {"source": "dataset"}, "[[Models/5er G60]] [[Components/Hood]]\n")
    write_note(v, "Projects/G60", None, "[[Projects/G60 Roadmap]] [[Topics/Comfort]]\n")
    write_note(v, "Projects/G60 Roadmap", None, "[[Projects/G60]] [[Projects/G60]]\n")
    write_note(v, "Topics/Comfort", None, "[[Projects/G60]]\n")
    write_note(v, "Purchase Drivers/5 Series top 10", {"managed_by": "torque"},
               "[[Projects/G60]] [[Purchase Drivers/Quiet cabin]] [[Purchase Drivers/Range]]\n")
    write_note(v, "Purchase Drivers/Quiet cabin", {"managed_by": "torque"}, "[[Topics/Comfort]]\n")
    write_note(v, "Purchase Drivers/Range", {"managed_by": "torque"}, "")
    write_note(v, "Requirements/R-01 Fast charging", {"req_id": "R-01"}, "# R-01\n")
    return v


def parents(report):
    out = {}
    for path, (_, new) in report.changes.items():
        line = next(l for l in new.splitlines() if l.startswith("parent: "))
        out[path] = line.removeprefix('parent: "[[').removesuffix(']]"')
    return out


def test_plan_chooses_parents(schema, vault):
    got = parents(plan(schema, vault))
    assert got["Brands/BMW"] == "Areas/Brand"
    assert got["Models/5er G60"] == "Brands/BMW"
    assert got["Components/Hood"] == "Models/5er G60"
    assert got["Feature Classes/Hood open close"] == "Components/Hood"
    assert got["Projects/G60"] == "Areas/Client projects"
    assert got["Projects/G60 Roadmap"] == "Projects/G60"
    assert got["Topics/Comfort"] == "Areas/Topics"
    assert got["Purchase Drivers/5 Series top 10"] == "Projects/G60"
    assert got["Purchase Drivers/Quiet cabin"] == "Purchase Drivers/5 Series top 10"
    assert got["Purchase Drivers/Range"] == "Purchase Drivers/5 Series top 10"
    assert got["Requirements/R-01 Fast charging"] == "Areas/Requirements"


def test_existing_keys_stay_first_and_unchanged(schema, vault):
    _, new = plan(schema, vault).changes["Brands/BMW"]
    assert new.startswith("---\nsource: dataset\nmanaged_by: ehl-visu\nid: brands-bmw\ntype: Brands\n")


def test_dry_run_writes_nothing_and_shows_a_diff(schema, vault):
    before = (vault / "Brands" / "BMW.md").read_text(encoding="utf-8")
    report = plan(schema, vault)
    assert "+parent: \"[[Areas/Brand]]\"" in diff(report)
    assert (vault / "Brands" / "BMW.md").read_text(encoding="utf-8") == before


def test_apply_then_lint_has_no_errors(schema, vault):
    report = plan(schema, vault)
    assert apply(report, vault) == len(report.changes)
    assert errors(lint(schema, vault)) == []


def test_migrate_is_idempotent(schema, vault):
    apply(plan(schema, vault), vault)
    assert plan(schema, vault).changes == {}


def test_unknown_folders_are_reported_not_touched(schema, vault):
    write_note(vault, "Diary/2026", None, "private\n")
    report = plan(schema, vault)
    assert report.unmapped == ["Diary/2026"]
    assert "Diary/2026" not in report.changes


def test_ids_are_unique(schema, vault):
    write_note(vault, "Topics/Comfort!", None, "")
    ids = [l for _, (_, new) in plan(schema, vault).changes.items() for l in new.splitlines() if l.startswith("id: ")]
    assert len(ids) == len(set(ids))


def test_note_without_any_parent_option_is_unresolved(tmp_path):
    path = tmp_path / "s.yaml"
    path.write_text("""
schema_version: 1
domains: {sales: {title: Sales}}
areas: {Pipeline: sales}
relations: {owner: {targets: [People]}}
types:
  People: {domain: sales, level: 3, parent: [People]}
""", encoding="utf-8")
    schema = load_schema(path)
    vault = tmp_path / "knowledge"
    write_note(vault, "People/Alone", None, "")
    assert plan(schema, vault).unresolved == ["People/Alone"]
    assert read_vault(vault)[0]["People/Alone"].front is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `market/.venv/Scripts/python -m pytest schema/tests/test_migrate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ehl_schema.migrate'`.

- [ ] **Step 3: Implement `schema/ehl_schema/migrate.py`**

```python
"""Give existing notes the schema's front matter keys. Proposes changes; writes only through apply()."""
from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .model import STRUCTURE_TYPES, Schema, TypeDef
from .notes import Note, add_keys, links, parent_target, read_vault, slug

log = logging.getLogger("ehl_schema.migrate")


@dataclass
class Report:
    changes: dict[str, tuple[str, str]] = field(default_factory=dict)  # path -> (old text, new text)
    unmapped: list[str] = field(default_factory=list)   # notes in folders the schema does not know
    unresolved: list[str] = field(default_factory=list)  # no parent found and no default area


def _neighbours(notes: dict[str, Note]) -> dict[str, set[str]]:
    out = {path: set() for path in notes}
    for path, note in notes.items():
        for target in links(note.front_text + "\n" + note.body):
            if target in notes and target != path:
                out[path].add(target)
                out[target].add(path)
    return out


def _creates_cycle(child: str, candidate: str, parents: dict[str, str]) -> bool:
    node, steps = candidate, 0
    while node is not None and steps <= len(parents):
        if node == child:
            return True
        node = parents.get(node)
        steps += 1
    return False


def _choose_parent(schema: Schema, td: TypeDef, path: str, notes: dict, near: dict, parents: dict) -> str | None:
    best = None
    for candidate in near[path]:
        ctype = schema.type_of_path(candidate)
        if ctype not in td.parent or schema.types[ctype].level > td.level:
            continue
        if ctype == td.name and len(near[candidate]) <= len(near[path]):
            continue
        if _creates_cycle(path, candidate, parents):
            continue
        rank = (td.parent.index(ctype), -len(near[candidate]), candidate)
        if best is None or rank < best[0]:
            best = (rank, candidate)
    if best is not None:
        return best[1]
    return schema.area_note(td.default_parent) if td.default_parent else None


def _unique_id(base: str, used: set[str]) -> str:
    candidate, n = base, 1
    while candidate in used:
        n += 1
        candidate = f"{base}-{n}"
    used.add(candidate)
    return candidate


def plan(schema: Schema, vault: Path) -> Report:
    notes, _ = read_vault(vault)
    near = _neighbours(notes)
    parents = {p: t for p, n in notes.items() if (t := parent_target(n)) is not None}
    used_ids = {str(n.front["id"]) for n in notes.values() if n.front and n.front.get("id")}
    report = Report()
    todo = []
    for path, note in notes.items():
        tname = schema.type_of_path(path)
        if tname is None:
            report.unmapped.append(path)
        elif tname not in STRUCTURE_TYPES and note.error is None:
            todo.append((schema.types[tname].level, -len(near[path]), path))
    for _, _, path in sorted(todo):
        note, td = notes[path], schema.types[schema.type_of_path(path)]
        front = note.front or {}
        fields: dict = {}
        if not front.get("parent"):
            target = _choose_parent(schema, td, path, notes, near, parents)
            if target is None:
                report.unresolved.append(path)
                continue
            parents[path] = target
        if not front.get("id"):
            fields["id"] = _unique_id(slug(f"{td.name}-{path.partition('/')[2]}"), used_ids)
        fields.update({"type": td.name, "domain": td.domain, "level": td.level})
        if path in parents and not front.get("parent"):
            fields["parent"] = f"[[{parents[path]}]]"
        fields.update({"visibility": "team", "env": "prod", "schema_version": schema.version})
        missing = {k: v for k, v in fields.items() if k not in front}
        if missing:
            report.changes[path] = (note.raw, add_keys(note, missing))
    return report


def apply(report: Report, vault: Path) -> int:
    for path, (_, new) in report.changes.items():
        (vault / f"{path}.md").write_bytes(new.encode("utf-8"))
    return len(report.changes)


def diff(report: Report) -> str:
    parts = []
    for path, (old, new) in report.changes.items():
        parts.extend(difflib.unified_diff(old.replace("\r\n", "\n").splitlines(keepends=True),
                                          new.replace("\r\n", "\n").splitlines(keepends=True),
                                          f"a/{path}.md", f"b/{path}.md"))
    return "".join(parts)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `market/.venv/Scripts/python -m pytest schema/tests -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add schema/ehl_schema/migrate.py schema/tests/test_migrate.py
git commit -m "feat(schema): migrate existing notes onto the schema" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: CLI, installer and migrating the EHL vault

**Files:**
- Create: `schema/ehl_schema/cli.py`
- Modify: `scripts/install.py` (new `setup_schema`, a `--company` option, a call in `main` after `setup_vault`)
- Test: `schema/tests/test_cli.py`

**Interfaces:**
- Consumes:
  - Tasks 1–5: `load_schema`, `DEFAULT_SCHEMA`, `build`, `lint`, `errors`, `plan`, `apply`, `diff`
- Produces:
  - `main(argv: list[str] | None = None) -> int`. Exit codes: 0 ok, 1 lint errors, 2 no vault.
  - `python -m ehl_schema.cli {build,lint,migrate} --workdir DIR [--company NAME] [--write]`
  - In `scripts/install.py`: `setup_schema(py: Path, workdir: Path, company: str) -> None`

- [ ] **Step 1: Write the failing tests**

`schema/tests/test_cli.py`:

```python
"""Checks for the ehl-schema command line."""
import json

from helpers import write_note

from ehl_schema.cli import main


def test_no_vault_exits_2(tmp_path):
    assert main(["lint", "--workdir", str(tmp_path)]) == 2


def test_build_migrate_lint(tmp_path):
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "notes.json").write_text(json.dumps([]), encoding="utf-8")
    write_note(tmp_path / "knowledge", "Topics/Comfort", None, "# Comfort\n")
    assert main(["build", "--workdir", str(tmp_path), "--company", "EHL"]) == 0
    assert main(["lint", "--workdir", str(tmp_path)]) == 1          # Topics/Comfort has no front matter yet
    assert main(["migrate", "--workdir", str(tmp_path)]) == 0       # dry run
    assert main(["lint", "--workdir", str(tmp_path)]) == 1
    assert main(["migrate", "--workdir", str(tmp_path), "--write"]) == 0
    assert main(["lint", "--workdir", str(tmp_path)]) == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `market/.venv/Scripts/python -m pytest schema/tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ehl_schema.cli'`.

- [ ] **Step 3: Implement `schema/ehl_schema/cli.py`**

```python
"""Command line: python -m ehl_schema.cli build|lint|migrate --workdir <Rowboat data folder>."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .build import build
from .lint import errors, lint
from .migrate import apply, diff, plan
from .model import DEFAULT_SCHEMA, load_schema

log = logging.getLogger("ehl_schema")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(prog="ehl-schema", description="Vault schema: build, lint, migrate")
    ap.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="schema file (default: schema/vault-schema.yaml)")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, text in (("build", "write structure notes, rules note and notes.json"),
                       ("lint", "check every note"), ("migrate", "add missing front matter (dry run by default)")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--workdir", type=Path, required=True, help="Rowboat data folder, e.g. ~/.rowboat-ehl")
    sub.choices["build"].add_argument("--company", default="Company", help="title of the L0 note")
    sub.choices["migrate"].add_argument("--write", action="store_true", help="write the changes")
    args = ap.parse_args(argv)

    schema = load_schema(args.schema)
    workdir = args.workdir.expanduser()
    vault = workdir / "knowledge"
    if not vault.is_dir():
        log.error("no vault at %s", vault)
        return 2
    if args.command == "build":
        result = build(schema, workdir, args.company)
        log.info("build: %d structure note(s) written, notes.json %s", result["notes"], result["notes_json"])
        return 0
    if args.command == "lint":
        issues = lint(schema, vault)
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

- [ ] **Step 4: Run the tests to verify they pass**

Run: `market/.venv/Scripts/python -m pytest schema/tests -v`
Expected: all PASS.

- [ ] **Step 5: Wire the schema into the installer**

In `scripts/install.py`:

1. Add this function after `setup_vault`:

```python
def setup_schema(py: Path, workdir: Path, company: str) -> None:
    """Vault schema (schema/): one hierarchy for every note. Spec: docs/superpowers/specs/2026-10-12-vault-schema-design.md."""
    setup_pc.run([str(py), "-m", "pip", "install", "-q", "-e", str(ROOT / "schema")])
    cli = [str(py), "-m", "ehl_schema.cli"]
    setup_pc.run(cli + ["build", "--workdir", str(workdir), "--company", company])
    setup_pc.run(cli + ["migrate", "--workdir", str(workdir), "--write"])
    if setup_pc.run(cli + ["lint", "--workdir", str(workdir)], check=False).returncode != 0:
        log.warning("The vault does not follow the schema yet; see the lint output above")
```

2. Add this to the docstring list after step 4:

```
  4b. the vault schema (schema/): Company, Domains and Areas notes, notes.json rules, front matter on every note
```

3. Add the option after `--refresh`:

```python
    ap.add_argument("--company", default="EHL", help="name of the company note at the top of the vault hierarchy")
```

4. In `main`, after `setup_vault(py, workdir, args.refresh)`, add:

```python
        setup_schema(py, workdir, args.company)
```

- [ ] **Step 6: Run the installer's own tests**

Run: `market/.venv/Scripts/python -m pytest scripts/tests -q`
Expected: all PASS.

- [ ] **Step 7: Migrate the real EHL vault and check it**

Back up first. The vault is not under git:

```bash
cp -r ~/.rowboat-ehl/knowledge ~/.rowboat-ehl/knowledge.bak-$(date +%Y%m%d-%H%M)
```

Then preview the migration:

```bash
market/.venv/Scripts/python -m ehl_schema.cli build --workdir ~/.rowboat-ehl --company EHL
market/.venv/Scripts/python -m ehl_schema.cli migrate --workdir ~/.rowboat-ehl
```

Expected:
- `build` writes about 73 structure notes and reports `notes.json updated`.
- The dry run lists about 210 notes (Brands 1, Models 4, Components 56, Feature Classes 70,
  Requirements 21, Purchase Drivers about 24, Assumptions 8, Topics 22, Projects 7).
- No `unresolved` line.
- `unmapped` lines only for folders outside the schema. The EHL vault should have none.

Read 5 parents in the diff and check that they make sense:
- `Models/5er G60` → `Brands/BMW`
- `Components/Hood` → a model
- `Feature Classes/...` → a component
- a purchase driver → its `top 10` note
- `Projects/G60 Roadmap` → `Projects/G60`

Then write and lint:

```bash
market/.venv/Scripts/python -m ehl_schema.cli migrate --workdir ~/.rowboat-ehl --write
market/.venv/Scripts/python -m ehl_schema.cli lint --workdir ~/.rowboat-ehl
```

Expected: `lint: 0 error(s), N warning(s)`.

- Warnings may be `broken-link` from the WP1 notes, or `possible-duplicate`. List them in the commit body.
- An error means a bug in Tasks 2–5. Fix it with a failing test first; do not hand-edit the vault.
- Restart Rowboat and confirm Torque still loads, which shows that Torque's sync still finds `managed_by: torque`.

- [ ] **Step 8: Commit**

```bash
git add schema/ehl_schema/cli.py schema/tests/test_cli.py scripts/install.py
git commit -m "feat(schema): ehl-schema command line, run it from the installer" -m "Migrated ~/.rowboat-ehl: <N> notes, lint 0 errors, <M> warnings (<codes>)." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Torque's sync keeps the schema keys

**Files:**
- Modify: `demo/torque/sync.py` (`write_if_changed` at lines 88–96, plus two new functions above it)
- Test: `demo/tests/test_sync_frontmatter.py`

**Interfaces:**
- Consumes: nothing from `ehl_schema`. `sync.py` stays standard library only.
- Produces: `keep_foreign_keys(old: str, new: str) -> str`. `write_if_changed` calls it.

- [ ] **Step 1: Write the failing tests**

`demo/tests/test_sync_frontmatter.py`:

```python
"""Torque's sync must not drop front matter keys other tools added (e.g. the vault schema's parent)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "torque"))

import sync  # noqa: E402

OLD = ('---\nsource: torque\nmanaged_by: torque\nreviewed_on: 2026-10-11\nid: purchase-drivers-x\n'
       'parent: "[[Projects/G60]]"\nschema_version: 1\n---\n# X\nold body\n')
NEW = "---\nsource: torque\nmanaged_by: torque\nreviewed_on: 2026-10-12\n---\n# X\nnew body\n"


def test_keep_foreign_keys_appends_missing_keys():
    merged = sync.keep_foreign_keys(OLD, NEW)
    assert merged == ('---\nsource: torque\nmanaged_by: torque\nreviewed_on: 2026-10-12\nid: purchase-drivers-x\n'
                      'parent: "[[Projects/G60]]"\nschema_version: 1\n---\n# X\nnew body\n')


def test_keep_foreign_keys_without_front_matter_returns_new():
    assert sync.keep_foreign_keys("# no front matter\n", NEW) == NEW
    assert sync.keep_foreign_keys(OLD, "# plain\n") == "# plain\n"


def test_write_if_changed_keeps_schema_keys(tmp_path):
    path = tmp_path / "X.md"
    path.write_text(OLD, encoding="utf-8")
    assert sync.write_if_changed(path, NEW) is True
    text = path.read_text(encoding="utf-8")
    assert 'parent: "[[Projects/G60]]"' in text and "new body" in text
    assert sync.write_if_changed(path, NEW) is False


def test_write_if_changed_still_skips_unmanaged_notes(tmp_path):
    path = tmp_path / "X.md"
    path.write_text("---\nsource: me\n---\nmine\n", encoding="utf-8")
    assert sync.write_if_changed(path, NEW) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `market/.venv/Scripts/python -m pytest demo/tests/test_sync_frontmatter.py -v`
Expected: FAIL with `AttributeError: module 'sync' has no attribute 'keep_foreign_keys'`.

- [ ] **Step 3: Implement it in `demo/torque/sync.py`**

Add these functions directly above `def write_if_changed`:

```python
def _front_lines(text: str) -> tuple[list[str], str] | None:
    t = text.replace("\r\n", "\n")
    if not t.startswith("---\n"):
        return None
    end = t.find("\n---\n", 3)
    if end == -1:
        return None
    return [line for line in t[4:end].split("\n") if line.strip()], t[end + 5:]


def keep_foreign_keys(old: str, new: str) -> str:
    """Carry over front matter keys the old note has and the new text lacks (e.g. the vault schema's id and
    parent), so a rewrite never drops what other tools added. Only simple 'key: value' lines are carried."""
    o, n = _front_lines(old), _front_lines(new)
    if o is None or n is None:
        return new
    new_keys = {line.split(":", 1)[0].strip() for line in n[0] if ":" in line}
    extra = [line for line in o[0] if ":" in line and not line.startswith((" ", "-"))
             and line.split(":", 1)[0].strip() not in new_keys]
    if not extra:
        return new
    return "---\n" + "\n".join(n[0] + extra) + "\n---\n" + n[1]
```

Then, in `write_if_changed`, add the merge right after reading `old`:

```python
def write_if_changed(path: Path, text: str, managed_only: bool = True) -> bool:
    if path.exists():
        old = path.read_text(encoding="utf-8")
        text = keep_foreign_keys(old, text)
        if old == text or (managed_only and "managed_by: torque" not in old[:300]):
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return True
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `market/.venv/Scripts/python -m pytest demo/tests -v`
Expected: all PASS, including the existing `test_example_data.py` and `test_make_quotes.py`.

- [ ] **Step 5: Commit**

```bash
git add demo/torque/sync.py demo/tests/test_sync_frontmatter.py
git commit -m "fix(torque): sync keeps front matter keys other tools added" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: CI and documentation

**Files:**
- Create: `.github/workflows/schema.yml`
- Modify: `README.md` (repository table), `docs/superpowers/specs/2026-10-12-vault-schema-design.md` (record three decisions)

- [ ] **Step 1: Add the CI workflow**

`.github/workflows/schema.yml`:

```yaml
name: schema
on:
  pull_request:
    paths: ["schema/**", "demo/torque/sync.py", "demo/tests/**", ".github/workflows/schema.yml"]
  push:
    branches: [main]
    paths: ["schema/**", "demo/torque/sync.py"]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e "schema[dev]"
      - run: pytest schema/tests demo/tests/test_sync_frontmatter.py -q
```

- [ ] **Step 2: Document `schema/` in the README**

In `README.md`, in the table under `## Repository`, add this row after the `market/` row:

```markdown
| `schema/` | Vault schema: one hierarchy for all business data (`vault-schema.yaml`), and `ehl-schema build | lint | migrate` ([spec](docs/superpowers/specs/2026-10-12-vault-schema-design.md)) |
```

- [ ] **Step 3: Record the implementation decisions in the spec**

In `docs/superpowers/specs/2026-10-12-vault-schema-design.md`, append to section 10:

```markdown
3. **Parent level:** a parent may be on the same level as the note (`parent level ≤ note level`). This allows
   types to nest in themselves (a roadmap under its project, a driver under its top 10 note); the linter
   still rejects cycles. Migration takes a same-type parent only if it has more neighbours (hub rule).
4. **Sources are grouped by channel**, not by date: `Areas/Meetings`, `Areas/Mails`, `Areas/Chats`,
   `Areas/Voice memos`, `Areas/Agent notes`. Date buckets would create a new area every month.
5. **Body links that do not resolve are warnings**, not errors. Links in `parent` and in relations must
   resolve (errors).
```

- [ ] **Step 4: Run the full test suite**

Run: `market/.venv/Scripts/python -m pytest schema/tests demo/tests scripts/tests market/tests -q`
Expected: all PASS.

- [ ] **Step 5: Commit and push**

```bash
git add .github/workflows/schema.yml README.md docs/superpowers/specs/2026-10-12-vault-schema-design.md
git commit -m "docs(schema): CI for schema tests, README row, spec decisions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

Expected: the push succeeds, and the `schema` workflow runs on the PR.

---

## Known gaps (next sub-projects)

- **Notes created later are not migrated automatically:**
  - Torque's sync writes new purchase driver notes, which have no schema keys until `migrate` runs again.
  - Rowboat's own note agents write new `People/` and `Organizations/` notes. From now on their templates
    in `notes.json` include the front matter skeleton. Sub-project 3 makes the agents follow it reliably.
- **The VibeMind vault (`~/.rowboat`) is not touched.** Moving private notes out and migrating it is a
  manual step after this plan.
