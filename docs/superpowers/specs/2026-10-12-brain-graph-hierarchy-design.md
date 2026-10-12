# Rowboat brain graph: hierarchical layout (sub-project 2, step A)

**Date:** 2026-10-12 · **Status:** draft for review
**Depends on:** the vault schema, `docs/superpowers/specs/2026-10-12-vault-schema-design.md` (sub-project 1).
**Changes:** the Rowboat fork `Flissel/rowboat`, branch `ehl` (upstream `72e9d8c`), through a PR from
`ehl/schema-graph`.

## 1. Goal

Rowboat's brain graph shows the vault hierarchy that sub-project 1 wrote into every note's front matter
(`level`, `parent`, `domain`, typed relations). The graph keeps its floating, draggable force layout.

Notes are pulled onto **one ring per level** around the company note in the centre. Each subtree stays in
its parent's angular sector.

**Success criteria**

- On the EHL vault (`~/.rowboat-ehl`, 288 notes):
  - The company note sits in the centre and the 15 domains form the first ring.
  - Every area sits on the second ring, in its domain's sector.
  - Every note sits on the ring of its level, near its parent.
- Parent edges, relation edges and body links look different from each other.
- Colours and the legend follow `domain`.
- A vault without `level`/`parent` front matter looks and behaves exactly as today.
- New logic sits in a pure, unit-tested module. The vitest suite of the renderer stays green.

## 2. Current code (Rowboat `72e9d8c`)

| Place | Today |
|---|---|
| `apps/renderer/src/App.tsx` `buildGraph` (~7040–7150) | Reads every note except `Meetings/`. Finds `[[links]]` in the whole text with one regex and stores them as undirected, untyped edges. Groups nodes by the first path segment and colours them by group index. |
| `apps/renderer/src/components/graph-view.tsx` | `GraphNode {id, label, degree, radius, group, color, stroke}`, `GraphEdge {source, target}`. Own simulation (~200–300): 240 steps of repulsion, edge springs (`SPRING_LENGTH 80`), a pull to group centres placed on a circle, damping. World origin (0,0) is the view centre. SVG lines for edges (~535), circles and labels for nodes. The legend comes from groups. |
| `apps/renderer/src/lib/frontmatter.ts` | `splitFrontmatter(content)` and `extractAllFrontmatterValues(raw)`. The latter returns flow lists like `["[[A]]"]` as raw strings and quoted values with their quotes. |

## 3. Design

### 3.1 New pure module `apps/renderer/src/lib/graph-hierarchy.ts`

```ts
export type Relation = { name: string; target: string }        // target: vault path without ".md"
export type Hierarchy = { level?: number; parent?: string; domain?: string; relations: Relation[] }

export function parseHierarchy(content: string): Hierarchy
export function hierarchyForces(
  nodes: { id: string; level?: number; parentId?: string }[],
  positions: Map<string, { x: number; y: number }>,
  params?: { ringSpacing?: number; ringStrength?: number; angleStrength?: number },
): Map<string, { x: number; y: number }>
```

**`parseHierarchy`**
- Uses `splitFrontmatter`.
- Reads the flat keys `level` (integer), `parent` and `domain`. `parent` is one link, quoted or not, with
  `|alias` and `#heading` stripped. `domain` is a string.
- Every other key whose value is a list of links becomes relations, e.g. `customer: ["[[Organizations/Acme]]"]`.
- Not relations: `parent`, and keys whose values are not links.
- Accepts CRLF.
- A note without front matter gives `{ relations: [] }`.

**`hierarchyForces`** returns an extra force per node:
- **Ring force:** pulls a node with `level` radially toward radius `level × ringSpacing` around (0, 0).
  - Default `ringSpacing` 140, strength 0.02.
  - Level 0 is pulled to the centre.
- **Parent-angle force:** pulls a node with a positioned parent tangentially toward the parent's angle, at
  the node's own radius. Default strength 0.015.
- **No `level`:** the node gets no force.

### 3.2 `App.tsx`, `buildGraph`

- **Parse every note once.** For each note in `contents`, call `parseHierarchy(data)`.
- **Nodes** get `level`, `parentId` and `domain`. `parentId` is set only if the target is a node of the graph.
- **Edges** get `kind: 'parent' | 'relation' | 'link'` and an optional `relation` name.
  - The parent link gives a `parent` edge; relations give `relation` edges; other `[[links]]` give `link`
    edges.
  - One edge per unordered pair, as today. The strongest kind wins: parent > relation > link.
- **Group and colour:** when the node has a `domain`, group = `domain`. Otherwise today's first-folder group
  is used. The palette and depth shading are unchanged.

### 3.3 `graph-view.tsx`

- **Types:**
  - `GraphNode` gets optional `level?: number`, `parentId?: string`, `domain?: string`.
  - `GraphEdge` gets optional `kind?: 'parent' | 'relation' | 'link'` and `relation?: string`.
  - All fields are optional, so other callers keep compiling.
- **Hierarchy mode** is on when at least one node has a `level`.
  - **Initial positions:** a node with `level` starts on its ring. Its angle is spread over its parent's
    sector (siblings evenly), or over the full circle for level ≤ 1.
  - **Each step:** nodes with `level` get `hierarchyForces` instead of the group-centre pull. Repulsion,
    edge springs, damping and dragging stay.
  - **Edge springs:** the spring length is `ringSpacing` for `parent` edges and today's 80 for others.
  - **Rings:** faint background circles at each used level radius.
- **Edge style:**

| Kind | Opacity | Dash |
|---|---|---|
| `parent` | 0.5 | solid |
| `relation` | 0.45 | dash `4 3`; `<title>` shows the relation name |
| `link` | 0.12 | solid |

  Hover, search and group highlighting keep today's rules on top of this.
- **Legend** shows domains (group labels) as today.
- **Off:** when hierarchy mode is off, the code paths are exactly the current ones.

## 4. Testing

- **`apps/renderer/src/lib/graph-hierarchy.test.ts` (vitest):**
  - `parseHierarchy`:
    - quoted and unquoted parent
    - alias and heading stripped
    - flow lists → relations
    - non-link keys ignored
    - CRLF
    - no front matter
    - level parsed as a number
  - `hierarchyForces`:
    - a node outside its ring gets a force toward the centre, a node inside gets one outward
    - a child at a different angle than its parent gets a tangential force toward the parent's side
    - a node without a level gets no force
    - level 0 is pulled toward (0, 0)
- **Renderer suite:** `pnpm --filter @x/renderer test` (or the package's `vitest run`) stays green.
- **Manual check:**
  - Run Rowboat in dev mode with `ROWBOAT_WORKDIR=~/.rowboat-ehl`.
  - Open Brain → Graph. Check the success criteria in §1 with a screenshot.
  - Switch to a vault without schema front matter (`~/.rowboat`) and check that the old layout is unchanged.

## 5. Delivery

- **Branch:** `ehl/schema-graph` in `C:/Users/User/Desktop/rowboat` (remote `origin` = `Flissel/rowboat`), from `ehl`.
- **PR:** into `Flissel/rowboat:ehl`.
- **Docs:** this repo's `docs/why-rowboat.md` says "unmodified". It changes to "one small, named patch: the
  hierarchical brain graph (`Flissel/rowboat` PR #…)" in the same delivery. The README licence line and
  NOTICE change the same way: one file group modified, Apache 2.0 §4(b) notice in the changed files' header
  comment.

## 6. Out of scope

- 3D / octree view (step B).
- Editing parents in the graph.
- Agent changes (sub-project 3).
- Business-data bridges (sub-project 4).
- Showing `Meetings/` in the graph (still excluded, as today).
