# Brain Graph Hierarchy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rowboat's brain graph shows the vault hierarchy (`level`, `parent`, `domain`, typed relations) as
a force layout pulled onto one ring per level, while vaults without that front matter keep today's graph.

**Architecture:**
- **Logic:** a new pure module `apps/renderer/src/lib/graph-hierarchy.ts` holds all of it:
  - parse the front matter,
  - classify the edges,
  - compute the initial ring positions,
  - compute the two extra forces.
- **Wiring:** `App.tsx` `buildGraph` and `graph-view.tsx` only wire the module in.
- **Where the work happens:** in the Rowboat clone `C:/Users/User/Desktop/rowboat` on a new branch
  `ehl/schema-graph`. The docs in this repo change in the last task.

**Tech Stack:** TypeScript, React, Vite, vitest (jsdom), pnpm.

**Spec:** `docs/superpowers/specs/2026-10-12-brain-graph-hierarchy-design.md` (in this repo)

## Global Constraints

- **Repo and branch:** Rowboat repo `C:/Users/User/Desktop/rowboat`. Branch `ehl/schema-graph`, created from
  `ehl` (= upstream `72e9d8c`). Push to `origin` = `Flissel/rowboat`. PR into `ehl`. Never push to `ehl` directly.
- **Run from:** all renderer commands run in `C:/Users/User/Desktop/rowboat/apps/x/apps/renderer`.
  - Tests: `pnpm exec vitest run <file>`
  - Types: `pnpm exec tsc -b`
  - Lint: `pnpm exec eslint <files>`
- **TypeScript:** strict. No `any`; use `unknown` and narrow. No `console.log` in committed code.
- **Optional fields only:** new fields on `GraphNode`/`GraphEdge` are optional. A vault without `level` front
  matter must run exactly today's code paths (hierarchy mode off).
- **Apache-2.0 §4(b):** every modified upstream file gets a one-line notice at the top:
  `// Modified for EHL (Flissel/rowboat ehl/schema-graph): hierarchical brain graph.`
  The new file carries its own header.
- **Commits:** conventional commits ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  In this environment, prefix `git commit` with `ENTIRE_TEST_TTY=0` (Entire hook, see CLAUDE.md).
- **Node IDs:** graph node ids are knowledge paths like `knowledge/Areas/Pipeline.md`. Wiki targets like
  `Areas/Pipeline` become node ids through `toKnowledgePath` from `@/lib/wiki-links`.

## Review Focus

1. **A vault without schema front matter (the user's `~/.rowboat`).**
   - Hierarchy mode stays off, so cluster pull, spring length, initial circle and edge opacity 0.4 are as today.
   - Test: Task 3 `buildHierarchyGraph … plain links stay kind link`, and the manual check in Task 4.
2. **Notes whose parent is outside the graph.** `Meetings/` notes are excluded from the graph, and a parent
   can be a missing note.
   - `parentId` must be undefined then, so no force toward a missing position.
   - Test: Task 3 `parentId only when the parent is a node`.
3. **Parent cycles or a parent with a higher level in hand-edited notes.**
   - `initialHierarchyPositions` must terminate.
   - Test: Task 2 `initial positions survive a parent cycle`.
4. **Links with alias, heading or `.xlsx` attachment in front matter values** (`[[Brands/BMW|BMW]]`,
   `[[Data/BMW Dataset.xlsx]]`).
   - Test: Task 1 `strips alias and heading`, `relation to an attachment`.
5. **CRLF and BOM files written on Windows.**
   - Test: Task 1 `accepts CRLF and a BOM`.

## File Structure

| File | Responsibility |
|---|---|
| `apps/x/apps/renderer/src/lib/graph-hierarchy.ts` (create) | `parseHierarchy`, `buildHierarchyGraph`, `initialHierarchyPositions`, `hierarchyForces`, `DEFAULT_FORCES` |
| `apps/x/apps/renderer/src/lib/graph-hierarchy.test.ts` (create) | vitest for the module |
| `apps/x/apps/renderer/src/components/graph-view.tsx` (modify) | Optional node/edge fields; hierarchy mode (initial positions, forces, parent spring length, rings, edge styles) |
| `apps/x/apps/renderer/src/App.tsx` (modify) | `buildGraph` uses `buildHierarchyGraph`; nodes get `level`, `parentId`, `domain`; group by `domain` |
| this repo: `docs/why-rowboat.md`, `README.md`, `NOTICE`, `docs/walkthrough.md` (modify) | "unmodified" → "one small, named patch" |

---

### Task 1: `parseHierarchy`

**Files:**
- Create: `apps/x/apps/renderer/src/lib/graph-hierarchy.ts`
- Test: `apps/x/apps/renderer/src/lib/graph-hierarchy.test.ts`

**Interfaces:**
- Produces:
  - `type Relation = { name: string; target: string }`
  - `type Hierarchy = { level?: number; parent?: string; domain?: string; relations: Relation[] }`
  - `linkTarget(raw: string): string`
  - `parseHierarchy(content: string): Hierarchy`
  - Targets are wiki paths without alias or heading, e.g. `Areas/Pipeline`.

- [ ] **Step 1: Create the branch**

```bash
cd C:/Users/User/Desktop/rowboat
git fetch origin
git switch -c ehl/schema-graph origin/ehl
```

- [ ] **Step 2: Write the failing tests**

`apps/x/apps/renderer/src/lib/graph-hierarchy.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { parseHierarchy } from './graph-hierarchy'

const note = (front: string, body = '# Title\n') => `---\n${front}\n---\n${body}`

describe('parseHierarchy', () => {
  it('reads level, parent and domain', () => {
    const h = parseHierarchy(note('id: deal-x\nlevel: 3\ndomain: sales\nparent: "[[Areas/Pipeline]]"'))
    expect(h).toEqual({ level: 3, parent: 'Areas/Pipeline', domain: 'sales', relations: [] })
  })

  it('accepts an unquoted parent and a quoted domain', () => {
    const h = parseHierarchy(note('parent: [[Areas/Pipeline]]\ndomain: "sales"'))
    expect(h.parent).toBe('Areas/Pipeline')
    expect(h.domain).toBe('sales')
  })

  it('strips alias and heading', () => {
    const h = parseHierarchy(note('parent: "[[Brands/BMW|BMW]]"\nabout: ["[[Models/5er G60#Sales]]"]'))
    expect(h.parent).toBe('Brands/BMW')
    expect(h.relations).toEqual([{ name: 'about', target: 'Models/5er G60' }])
  })

  it('turns link lists into relations and ignores other keys', () => {
    const h = parseHierarchy(note(
      'customer: ["[[Organizations/Acme]]", "[[Organizations/Beta]]"]\nowner: ["[[People/Felix Baumann]]"]\n' +
      'status: active\nsource: sales-claw\nwhen: 2026-10-20'))
    expect(h.relations).toEqual([
      { name: 'customer', target: 'Organizations/Acme' },
      { name: 'customer', target: 'Organizations/Beta' },
      { name: 'owner', target: 'People/Felix Baumann' },
    ])
  })

  it('relation to an attachment', () => {
    const h = parseHierarchy(note('evidence: ["[[Data/BMW Dataset.xlsx|data]]"]'))
    expect(h.relations).toEqual([{ name: 'evidence', target: 'Data/BMW Dataset.xlsx' }])
  })

  it('accepts CRLF and a BOM', () => {
    const h = parseHierarchy('\ufeff---\r\nlevel: 2\r\nparent: "[[Domains/Market & sales]]"\r\n---\r\n# A\r\n')
    expect(h.level).toBe(2)
    expect(h.parent).toBe('Domains/Market & sales')
  })

  it('a note without front matter has no hierarchy', () => {
    expect(parseHierarchy('# Just a note with [[Topics/Comfort]]\n')).toEqual({ relations: [] })
  })

  it('ignores a non-numeric level and links in the body', () => {
    const h = parseHierarchy(note('level: three', 'See [[Topics/Comfort]].\n'))
    expect(h).toEqual({ relations: [] })
  })
})
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pnpm exec vitest run src/lib/graph-hierarchy.test.ts`
Expected: FAIL. The import `./graph-hierarchy` cannot be resolved.

- [ ] **Step 4: Implement the parser**

`apps/x/apps/renderer/src/lib/graph-hierarchy.ts`:

```ts
// EHL addition (Flissel/rowboat ehl/schema-graph): hierarchical brain graph. Reads the vault schema's flat
// front matter (level, parent, domain, typed relations) and lays notes out on one ring per level.
// Spec: Flissel/ehl-munich-2026 docs/superpowers/specs/2026-10-12-brain-graph-hierarchy-design.md
import { splitFrontmatter } from './frontmatter'

export type Relation = { name: string; target: string }
export type Hierarchy = { level?: number; parent?: string; domain?: string; relations: Relation[] }

const LINK = /\[\[([^[\]]+)\]\]/g
const KEY_LINE = /^([A-Za-z_]\w*):\s*(.*)$/

export function linkTarget(raw: string): string {
  return raw.split('|')[0].split('#')[0].trim()
}

function linksIn(value: string): string[] {
  return Array.from(value.matchAll(LINK), (m) => linkTarget(m[1])).filter((t) => t.length > 0)
}

function unquote(value: string): string {
  return value.trim().replace(/^["']|["']$/g, '').trim()
}

export function parseHierarchy(content: string): Hierarchy {
  const text = content.replace(/^\ufeff/, '').replace(/\r\n/g, '\n')
  const { raw } = splitFrontmatter(text)
  const result: Hierarchy = { relations: [] }
  if (!raw) return result
  for (const line of raw.split('\n')) {
    const match = line.match(KEY_LINE)
    if (!match) continue
    const [, key, value] = match
    if (key === 'level') {
      const level = Number(unquote(value))
      if (Number.isInteger(level)) result.level = level
    } else if (key === 'domain') {
      const domain = unquote(value)
      if (domain) result.domain = domain
    } else if (key === 'parent') {
      const [target] = linksIn(value)
      if (target) result.parent = target
    } else {
      for (const target of linksIn(value)) result.relations.push({ name: key, target })
    }
  }
  return result
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pnpm exec vitest run src/lib/graph-hierarchy.test.ts`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/x/apps/renderer/src/lib/graph-hierarchy.ts apps/x/apps/renderer/src/lib/graph-hierarchy.test.ts
ENTIRE_TEST_TTY=0 git commit -m "feat(graph): parse the vault schema's hierarchy from front matter" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Ring forces and initial positions

**Files:**
- Modify: `apps/x/apps/renderer/src/lib/graph-hierarchy.ts` (append)
- Test: `apps/x/apps/renderer/src/lib/graph-hierarchy.test.ts` (append)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `type ForceParams = { ringSpacing: number; ringStrength: number; angleStrength: number }`
  - `DEFAULT_FORCES: ForceParams` = `{ ringSpacing: 140, ringStrength: 0.02, angleStrength: 0.015 }`
  - `type LevelNode = { id: string; level?: number; parentId?: string }`
  - `hierarchyForces(nodes: LevelNode[], positions: Map<string, {x: number; y: number}>, params?: ForceParams): Map<string, {x: number; y: number}>`
  - `initialHierarchyPositions(nodes: LevelNode[], ringSpacing?: number): Map<string, {x: number; y: number}>`

- [ ] **Step 1: Write the failing tests**

Append to `graph-hierarchy.test.ts`. Change the import line at the top to:

```ts
import { DEFAULT_FORCES, hierarchyForces, initialHierarchyPositions, parseHierarchy } from './graph-hierarchy'
```

and append:

```ts
describe('hierarchyForces', () => {
  const ring = DEFAULT_FORCES.ringSpacing

  it('pulls a node outside its ring inward and a node inside outward', () => {
    const nodes = [{ id: 'out', level: 1 }, { id: 'in', level: 2 }]
    const positions = new Map([['out', { x: ring * 2, y: 0 }], ['in', { x: ring, y: 0 }]])
    const forces = hierarchyForces(nodes, positions)
    expect(forces.get('out')!.x).toBeLessThan(0)
    expect(forces.get('in')!.x).toBeGreaterThan(0)
  })

  it('pulls level 0 to the centre', () => {
    const forces = hierarchyForces([{ id: 'c', level: 0 }], new Map([['c', { x: 30, y: -40 }]]))
    expect(forces.get('c')!.x).toBeLessThan(0)
    expect(forces.get('c')!.y).toBeGreaterThan(0)
  })

  it('pulls a child tangentially toward its parent angle', () => {
    const nodes = [{ id: 'p', level: 1 }, { id: 'c', level: 2, parentId: 'p' }]
    const positions = new Map([['p', { x: 0, y: ring }], ['c', { x: ring * 2, y: 0 }]])
    const force = hierarchyForces(nodes, positions).get('c')!
    expect(force.y).toBeGreaterThan(0)
  })

  it('gives no force to a node without a level', () => {
    const forces = hierarchyForces([{ id: 'x' }], new Map([['x', { x: 10, y: 10 }]]))
    expect(forces.has('x')).toBe(false)
  })
})

describe('initialHierarchyPositions', () => {
  const ring = DEFAULT_FORCES.ringSpacing

  it('puts every node on its ring and children in their parent sector', () => {
    const nodes = [
      { id: 'company', level: 0 },
      { id: 'd1', level: 1, parentId: 'company' },
      { id: 'd2', level: 1, parentId: 'company' },
      { id: 'a1', level: 2, parentId: 'd1' },
      { id: 'a2', level: 2, parentId: 'd2' },
    ]
    const pos = initialHierarchyPositions(nodes)
    expect(Math.hypot(pos.get('company')!.x, pos.get('company')!.y)).toBe(0)
    for (const id of ['d1', 'd2']) expect(Math.hypot(pos.get(id)!.x, pos.get(id)!.y)).toBeCloseTo(ring)
    for (const id of ['a1', 'a2']) expect(Math.hypot(pos.get(id)!.x, pos.get(id)!.y)).toBeCloseTo(ring * 2)
    const angle = (id: string) => Math.atan2(pos.get(id)!.y, pos.get(id)!.x)
    expect(angle('a1')).toBeCloseTo(angle('d1'))
    expect(angle('a2')).toBeCloseTo(angle('d2'))
  })

  it('skips nodes without a level', () => {
    expect(initialHierarchyPositions([{ id: 'x' }]).size).toBe(0)
  })

  it('initial positions survive a parent cycle', () => {
    const nodes = [{ id: 'a', level: 3, parentId: 'b' }, { id: 'b', level: 3, parentId: 'a' }]
    expect(initialHierarchyPositions(nodes).size).toBe(2)
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pnpm exec vitest run src/lib/graph-hierarchy.test.ts`
Expected: FAIL. `DEFAULT_FORCES`, `hierarchyForces` and `initialHierarchyPositions` are not exported.

- [ ] **Step 3: Implement it**

Append to `graph-hierarchy.ts`:

```ts
export type ForceParams = { ringSpacing: number; ringStrength: number; angleStrength: number }
export const DEFAULT_FORCES: ForceParams = { ringSpacing: 140, ringStrength: 0.02, angleStrength: 0.015 }
export type LevelNode = { id: string; level?: number; parentId?: string }
type Point = { x: number; y: number }

/** Extra force per node with a level: toward its ring (radius level × spacing around 0,0) and, along the
 * ring, toward its parent's angle. Nodes without a level get no entry. */
export function hierarchyForces(
  nodes: LevelNode[],
  positions: Map<string, Point>,
  params: ForceParams = DEFAULT_FORCES,
): Map<string, Point> {
  const forces = new Map<string, Point>()
  for (const node of nodes) {
    if (node.level === undefined) continue
    const pos = positions.get(node.id)
    if (!pos) continue
    const force = { x: 0, y: 0 }
    const radius = Math.hypot(pos.x, pos.y)
    const target = node.level * params.ringSpacing
    if (radius > 1e-6) {
      const pull = (target - radius) * params.ringStrength
      force.x += (pos.x / radius) * pull
      force.y += (pos.y / radius) * pull
    } else if (target > 0) {
      force.x += target * params.ringStrength
    }
    const parent = node.parentId ? positions.get(node.parentId) : undefined
    if (parent && radius > 1e-6 && Math.hypot(parent.x, parent.y) > 1e-6) {
      const own = Math.atan2(pos.y, pos.x)
      const wanted = Math.atan2(parent.y, parent.x)
      const delta = Math.atan2(Math.sin(wanted - own), Math.cos(wanted - own))
      const push = delta * radius * params.angleStrength
      force.x += -Math.sin(own) * push
      force.y += Math.cos(own) * push
    }
    forces.set(node.id, force)
  }
  return forces
}

/** Start positions: every node with a level on its ring, each subtree inside its parent's angular sector
 * (sector size ∝ subtree size). Roots share the full circle. Cycles are cut. */
export function initialHierarchyPositions(
  nodes: LevelNode[],
  ringSpacing: number = DEFAULT_FORCES.ringSpacing,
): Map<string, Point> {
  const leveled = nodes.filter((n) => n.level !== undefined).sort((a, b) => a.id.localeCompare(b.id))
  const byId = new Map(leveled.map((n) => [n.id, n]))
  const children = new Map<string, string[]>()
  const roots: string[] = []
  for (const node of leveled) {
    if (node.parentId && byId.has(node.parentId)) {
      const list = children.get(node.parentId) ?? []
      list.push(node.id)
      children.set(node.parentId, list)
    } else {
      roots.push(node.id)
    }
  }
  const sizes = new Map<string, number>()
  const sizeOf = (id: string, seen: Set<string>): number => {
    const known = sizes.get(id)
    if (known !== undefined) return known
    if (seen.has(id)) return 1
    seen.add(id)
    const size = 1 + (children.get(id) ?? []).reduce((sum, child) => sum + sizeOf(child, seen), 0)
    sizes.set(id, size)
    return size
  }
  const out = new Map<string, Point>()
  const place = (ids: string[], start: number, span: number) => {
    const fresh = ids.filter((id) => !out.has(id))
    const total = fresh.reduce((sum, id) => sum + sizeOf(id, new Set()), 0)
    let angle = start
    for (const id of fresh) {
      const share = (span * sizeOf(id, new Set())) / total
      const mid = angle + share / 2
      const radius = (byId.get(id)?.level ?? 0) * ringSpacing
      out.set(id, { x: radius * Math.cos(mid), y: radius * Math.sin(mid) })
      place(children.get(id) ?? [], angle, share)
      angle += share
    }
  }
  place(roots, 0, Math.PI * 2)
  for (const node of leveled) {
    if (!out.has(node.id)) place([node.id], 0, Math.PI * 2)
  }
  return out
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pnpm exec vitest run src/lib/graph-hierarchy.test.ts`
Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/x/apps/renderer/src/lib/graph-hierarchy.ts apps/x/apps/renderer/src/lib/graph-hierarchy.test.ts
ENTIRE_TEST_TTY=0 git commit -m "feat(graph): ring forces and initial ring positions for the hierarchy" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Typed edges and node info, wired into `buildGraph`

**Files:**
- Modify: `apps/x/apps/renderer/src/lib/graph-hierarchy.ts` (append)
- Modify: `apps/x/apps/renderer/src/components/graph-view.tsx:1-25` (types and the §4(b) notice)
- Modify: `apps/x/apps/renderer/src/App.tsx` (the §4(b) notice on line 1; `buildGraph` ~7055–7135)
- Test: `apps/x/apps/renderer/src/lib/graph-hierarchy.test.ts` (append)

**Interfaces:**
- Consumes: Task 1 `parseHierarchy`.
- Produces:
  - `type EdgeKind = 'parent' | 'relation' | 'link'`
  - `type HierarchyEdge = { source: string; target: string; kind: EdgeKind; relation?: string }`
  - `type NodeInfo = { level?: number; parentId?: string; domain?: string }`
  - `buildHierarchyGraph(contents: {path: string; data: string}[], nodeSet: Set<string>, toNodeId: (wikiTarget: string) => string | null): { edges: HierarchyEdge[]; info: Map<string, NodeInfo> }`
  - In `graph-view.tsx`:
    - `GraphNode` gains `level?: number; parentId?: string; domain?: string`
    - `GraphEdge` gains `kind?: 'parent' | 'relation' | 'link'; relation?: string`

- [ ] **Step 1: Write the failing tests**

Change the import in `graph-hierarchy.test.ts` to:

```ts
import { DEFAULT_FORCES, buildHierarchyGraph, hierarchyForces, initialHierarchyPositions, parseHierarchy } from './graph-hierarchy'
```

and append:

```ts
describe('buildHierarchyGraph', () => {
  const toNodeId = (wiki: string) => `knowledge/${wiki.split('|')[0].split('#')[0].trim()}.md`
  const node = (path: string, front: string, body = '') => ({
    path: `knowledge/${path}.md`,
    data: front ? `---\n${front}\n---\n${body}` : body,
  })

  it('classifies parent, relation and link edges, strongest kind wins', () => {
    const contents = [
      node('Areas/Pipeline', 'level: 2\ndomain: sales'),
      node('Organizations/Acme', 'level: 3\ndomain: register'),
      node('Deals/X', 'level: 3\ndomain: sales\nparent: "[[Areas/Pipeline]]"\ncustomer: ["[[Organizations/Acme]]"]',
           'See [[Areas/Pipeline]] and [[Organizations/Acme]].\n'),
    ]
    const nodeSet = new Set(contents.map((c) => c.path))
    const { edges, info } = buildHierarchyGraph(contents, nodeSet, toNodeId)
    expect(edges).toEqual([
      { source: 'knowledge/Deals/X.md', target: 'knowledge/Areas/Pipeline.md', kind: 'parent' },
      { source: 'knowledge/Deals/X.md', target: 'knowledge/Organizations/Acme.md', kind: 'relation', relation: 'customer' },
    ])
    expect(info.get('knowledge/Deals/X.md')).toEqual({ level: 3, parentId: 'knowledge/Areas/Pipeline.md', domain: 'sales' })
  })

  it('plain links stay kind link', () => {
    const contents = [node('Topics/A', '', '[[Topics/B]]\n'), node('Topics/B', '', '')]
    const { edges, info } = buildHierarchyGraph(contents, new Set(contents.map((c) => c.path)), toNodeId)
    expect(edges).toEqual([{ source: 'knowledge/Topics/A.md', target: 'knowledge/Topics/B.md', kind: 'link' }])
    expect(info.get('knowledge/Topics/A.md')).toEqual({ level: undefined, parentId: undefined, domain: undefined })
  })

  it('parentId only when the parent is a node', () => {
    const contents = [node('Meetings/M', 'level: 4\nparent: "[[Areas/Meetings]]"')]
    const { edges, info } = buildHierarchyGraph(contents, new Set(contents.map((c) => c.path)), toNodeId)
    expect(edges).toEqual([])
    expect(info.get('knowledge/Meetings/M.md')?.parentId).toBeUndefined()
  })

  it('ignores self links and unresolvable targets', () => {
    const contents = [node('Topics/A', 'about: ["[[Topics/A]]"]', '[[Nowhere/X]]\n')]
    const toNull = (wiki: string) => (wiki.startsWith('Nowhere') ? null : toNodeId(wiki))
    expect(buildHierarchyGraph(contents, new Set(contents.map((c) => c.path)), toNull).edges).toEqual([])
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pnpm exec vitest run src/lib/graph-hierarchy.test.ts`
Expected: FAIL. `buildHierarchyGraph` is not exported.

- [ ] **Step 3: Implement `buildHierarchyGraph`**

Append to `graph-hierarchy.ts`:

```ts
export type EdgeKind = 'parent' | 'relation' | 'link'
export type HierarchyEdge = { source: string; target: string; kind: EdgeKind; relation?: string }
export type NodeInfo = { level?: number; parentId?: string; domain?: string }

const RANK: Record<EdgeKind, number> = { link: 0, relation: 1, parent: 2 }

/** Typed edges (one per unordered pair, strongest kind wins) and hierarchy info per node. */
export function buildHierarchyGraph(
  contents: { path: string; data: string }[],
  nodeSet: Set<string>,
  toNodeId: (wikiTarget: string) => string | null,
): { edges: HierarchyEdge[]; info: Map<string, NodeInfo> } {
  const edges = new Map<string, HierarchyEdge>()
  const info = new Map<string, NodeInfo>()
  const add = (source: string, rawTarget: string, kind: EdgeKind, relation?: string) => {
    const target = toNodeId(rawTarget)
    if (!target || target === source || !nodeSet.has(target)) return
    const key = source < target ? `${source}|${target}` : `${target}|${source}`
    const existing = edges.get(key)
    if (existing && RANK[existing.kind] >= RANK[kind]) return
    edges.set(key, relation ? { source, target, kind, relation } : { source, target, kind })
  }
  for (const { path, data } of contents) {
    const hierarchy = parseHierarchy(data)
    const parentId = hierarchy.parent ? toNodeId(hierarchy.parent) : null
    info.set(path, {
      level: hierarchy.level,
      parentId: parentId && nodeSet.has(parentId) ? parentId : undefined,
      domain: hierarchy.domain,
    })
    if (hierarchy.parent) add(path, hierarchy.parent, 'parent')
    for (const relation of hierarchy.relations) add(path, relation.target, 'relation', relation.name)
    for (const match of data.matchAll(LINK)) add(path, match[1], 'link')
  }
  return { edges: Array.from(edges.values()), info }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pnpm exec vitest run src/lib/graph-hierarchy.test.ts`
Expected: 19 passed.

- [ ] **Step 5: Extend the graph types**

In `apps/x/apps/renderer/src/components/graph-view.tsx`, add the notice as a new first line:

```ts
// Modified for EHL (Flissel/rowboat ehl/schema-graph): hierarchical brain graph.
```

Then replace the two type declarations:

```ts
export type GraphNode = {
  id: string
  label: string
  degree: number
  radius: number
  group: string
  color: string
  stroke: string
  level?: number
  parentId?: string
  domain?: string
}

export type GraphEdge = {
  source: string
  target: string
  kind?: 'parent' | 'relation' | 'link'
  relation?: string
}
```

- [ ] **Step 6: Wire it into `buildGraph` in `App.tsx`**

1. Add the notice as a new first line of `apps/x/apps/renderer/src/App.tsx`:

```ts
// Modified for EHL (Flissel/rowboat ehl/schema-graph): hierarchical brain graph.
```

2. Add the import next to the other `@/lib` imports:

```ts
import { buildHierarchyGraph } from '@/lib/graph-hierarchy'
```

3. In `buildGraph`, delete the line `const edgeKeys = new Set<string>()`. Replace the whole loop
   `for (const { path, data } of contents) { for (const match of data.matchAll(wikiLinkRegex)) { … } }` with:

```ts
      const { edges: typedEdges, info: hierarchyInfo } = buildHierarchyGraph(contents, nodeSet, toKnowledgePath)
      edges.push(...typedEdges)
```

4. In `const nodes = graphFilePaths.map((path) => { … })`, replace
   `const { group, depth } = getNodeGroup(path)` with:

```ts
        const hierarchy = hierarchyInfo.get(path)
        const folderGroup = getNodeGroup(path)
        const group = hierarchy?.domain ?? folderGroup.group
        const depth = folderGroup.depth
```

5. In the same map, add these fields to the returned object, after `stroke: colors.stroke,`:

```ts
          level: hierarchy?.level,
          parentId: hierarchy?.parentId,
          domain: hierarchy?.domain,
```

If `wikiLinkRegex` (App.tsx:148) is now unused, `tsc`/`eslint` will say so. In that case, check
`grep -n wikiLinkRegex src/App.tsx`: delete the declaration only if no other use remains.

- [ ] **Step 7: Typecheck, lint and test**

Run: `pnpm exec tsc -b`
Expected: exit 0.

Run: `pnpm exec eslint src/lib/graph-hierarchy.ts src/lib/graph-hierarchy.test.ts src/components/graph-view.tsx src/App.tsx`
Expected: no errors. Pre-existing warnings in `App.tsx` are allowed; compare with `git stash` if unsure.

Run: `pnpm exec vitest run src/lib/graph-hierarchy.test.ts`
Expected: 19 passed.

- [ ] **Step 8: Commit**

```bash
git add apps/x/apps/renderer/src/lib/graph-hierarchy.ts apps/x/apps/renderer/src/lib/graph-hierarchy.test.ts apps/x/apps/renderer/src/components/graph-view.tsx apps/x/apps/renderer/src/App.tsx
ENTIRE_TEST_TTY=0 git commit -m "feat(graph): typed edges and hierarchy info in the brain graph data" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Hierarchy mode in the graph view

**Files:**
- Modify: `apps/x/apps/renderer/src/components/graph-view.tsx`:
  - the imports,
  - the `groupCenters` area (~100),
  - the positions effect (~178–300),
  - the SVG edges (~535–580).

**Interfaces:**
- Consumes: `DEFAULT_FORCES`, `hierarchyForces`, `initialHierarchyPositions` (Task 2); `GraphNode.level/parentId`, `GraphEdge.kind/relation` (Task 3).

This task changes rendering. The pure logic is already tested; the gate here is the typecheck, the renderer
suite and the manual check in the running app.

- [ ] **Step 1: Import the module**

Below `import { Input } from '@/components/ui/input'`:

```ts
import { DEFAULT_FORCES, hierarchyForces, initialHierarchyPositions } from '@/lib/graph-hierarchy'
```

- [ ] **Step 2: Hierarchy mode and ring radii**

Directly after the `groupCenters` `useMemo`:

```ts
  const hierarchyMode = useMemo(() => nodes.some((node) => node.level !== undefined), [nodes])
  const ringRadii = useMemo(() => {
    if (!hierarchyMode) return []
    const levels = new Set(nodes.map((node) => node.level).filter((level): level is number => level !== undefined && level > 0))
    return Array.from(levels).sort((a, b) => a - b).map((level) => level * DEFAULT_FORCES.ringSpacing)
  }, [nodes, hierarchyMode])
```

- [ ] **Step 3: Initial positions**

In the positions `useEffect`:

1. After `const radius = Math.max(110, Math.min(220, count * 9))`, add:

```ts
    const ringStart = hierarchyMode ? initialHierarchyPositions(nodes) : new Map<string, { x: number; y: number }>()
```

2. In `nodes.forEach((node, index) => { … })`, replace the block that sets a new position
   (`const angle = …; nextPositions.set(node.id, { x: radius * Math.cos(angle), … })`) with:

```ts
      const start = ringStart.get(node.id)
      const angle = (index / count) * Math.PI * 2
      nextPositions.set(node.id, {
        x: start ? start.x : radius * Math.cos(angle),
        y: start ? start.y : radius * Math.sin(angle),
        vx: 0,
        vy: 0,
      })
```

- [ ] **Step 4: Parent spring length**

In the `edgeList.forEach((edge) => { … })` spring block, replace `const delta = distance - SPRING_LENGTH` with:

```ts
        const springLength = hierarchyMode && edge.kind === 'parent' ? DEFAULT_FORCES.ringSpacing : SPRING_LENGTH
        const delta = distance - springLength
```

- [ ] **Step 5: Ring forces instead of the group pull for leveled nodes**

1. At the top of `simulate`, after `const ids = nodes.map((node) => node.id)`, add:

```ts
      const leveled = hierarchyMode ? new Set(nodes.filter((node) => node.level !== undefined).map((node) => node.id)) : null
```

2. In the group-centre loop (`const group = nodeGroupMap.get(id) ?? 'root'`), add as its first statement
   after `if (!pos || !force) return`:

```ts
        if (leveled?.has(id)) return
```

3. After that loop, add:

```ts
      if (hierarchyMode) {
        hierarchyForces(nodes, positions).forEach((extra, id) => {
          const force = forces.get(id)
          if (!force) return
          force.x += extra.x
          force.y += extra.y
        })
      }
```

4. Add `hierarchyMode` to the effect's dependency array: `[nodes, edgeList, groupCenters, nodeGroupMap, hierarchyMode]`.

- [ ] **Step 6: Rings and edge styles**

1. Inside `<g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>`, before `{edgeList.map(`, add:

```tsx
          {ringRadii.map((r) => (
            <circle key={`ring-${r}`} cx={0} cy={0} r={r} fill="none" stroke="#888" strokeOpacity={0.12} strokeWidth={1} />
          ))}
```

2. In the edge map, replace `let strokeOpacity = 0.4` with:

```ts
            let strokeOpacity = edge.kind === 'link' ? 0.12 : edge.kind === 'relation' ? 0.45 : edge.kind === 'parent' ? 0.5 : 0.4
```

3. Replace the returned `<path … />` element with:

```tsx
              <path
                key={`${edge.source}-${edge.target}-${index}`}
                d={pathD}
                fill="none"
                stroke={stroke}
                strokeOpacity={strokeOpacity}
                strokeWidth={strokeWidth}
                strokeDasharray={edge.kind === 'relation' ? '4 3' : undefined}
                style={{ transition: 'stroke 0.2s, stroke-opacity 0.2s, stroke-width 0.2s' }}
              >
                {edge.relation ? <title>{edge.relation}</title> : null}
              </path>
```

- [ ] **Step 7: Typecheck, lint and run the renderer suite**

Run: `pnpm exec tsc -b`
Expected: exit 0.

Run: `pnpm exec eslint src/components/graph-view.tsx src/lib/graph-hierarchy.ts`
Expected: no errors.

Run: `pnpm exec vitest run > %TEMP%/renderer-tests.txt 2>&1`, then read the tail.
Expected: all test files pass. Name any failure in the ledger. Compare against `git stash` to tell
pre-existing failures from new ones.

- [ ] **Step 8: Manual check in the running app**

1. Rowboat runs in dev mode with `ROWBOAT_WORKDIR=~/.rowboat-ehl` (started by `python scripts/install.py --start`
   in the EHL repo). Vite reloads the renderer by itself. If not, restart that command.
2. Open Brain → Graph. Expected:
   - the Company note in the centre,
   - 15 domains on the first ring,
   - areas on the second ring in their domain's sector,
   - notes on their level's ring near their parent,
   - faint rings,
   - dashed relation edges with the name on hover,
   - faint body links,
   - a legend with domains.
3. Take a screenshot for the PR.
4. Fallback check: start a second dev instance against a vault without schema keys, or ask the user to
   look at `~/.rowboat` in their normal Rowboat. Expected: the old cluster layout.

- [ ] **Step 9: Commit**

```bash
git add apps/x/apps/renderer/src/components/graph-view.tsx
ENTIRE_TEST_TTY=0 git commit -m "feat(graph): radial-force hierarchy layout, rings and typed edge styles" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Pull request and documentation

**Files:**
- Rowboat repo: push `ehl/schema-graph`, open the PR into `ehl`.
- This repo (`C:/Users/User/Desktop/ehl-munich-2026`, branch `feat/vault-schema`): `docs/why-rowboat.md`,
  `README.md`, `NOTICE`, `docs/walkthrough.md`.

- [ ] **Step 1: Push and open the PR in the fork**

```bash
cd C:/Users/User/Desktop/rowboat
ENTIRE_TEST_TTY=0 git push -u origin ehl/schema-graph
gh pr create --repo Flissel/rowboat --base ehl --head ehl/schema-graph --title "feat(graph): hierarchical brain graph from the vault schema" --body "<summary, tests run, screenshot, link to the spec in Flissel/ehl-munich-2026>

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

Expected: a PR URL. Note its number N. Do not merge; the orchestrator decides.

- [ ] **Step 2: Update the docs in the EHL repo**

1. `docs/why-rowboat.md`:
   - Line 5: replace `and how we connect to it without changing a line of its code.` with
     `and how we connect to it, almost entirely without changing its code.`
   - Rename the section `## Integrated, not forked` to `## Integrated, with one small patch`.
   - Replace its first paragraph with:

```markdown
The team fork [`Flissel/rowboat`](https://github.com/Flissel/rowboat), branch `ehl`, starts at upstream
commit **`72e9d8c`** (9 Oct 2026). It carries **one small, named patch**: the hierarchical brain graph
([Flissel/rowboat#N](https://github.com/Flissel/rowboat/pull/N)). The patch adds `src/lib/graph-hierarchy.ts`
and changes `graph-view.tsx` and `buildGraph` in `App.tsx` in the desktop renderer. It reads the vault
schema's front matter and lays notes out on one ring per level. Without that front matter, the graph is
upstream's. Everything else connects through Rowboat's documented extension points:
```

   - Replace the bullets "We can upgrade.", "Clear authorship." and "Simple licence compliance." with:

```markdown
- **We can upgrade.** A newer Rowboat needs a new pin and a rebase of one small patch in three files.
- **Clear authorship.** Everything the team wrote sits in this repository, plus that one patch in the fork,
  so the jury can see exactly what is ours.
- **Licence compliance.** The changed files carry a notice that we modified them (Apache 2.0 §4(b)). We keep
  Rowboat's licence and credit, list it in [NOTICE](../NOTICE), and do not use its name to suggest
  endorsement (§6).
```

2. `README.md`:
   - Line 45: `(unmodified, upstream commit `72e9d8c`)` → `(upstream commit `72e9d8c` plus one patch: the hierarchical brain graph)`.
   - Line 136: `- Rowboat: Apache-2.0, used unmodified.` → `- Rowboat: Apache-2.0, with one marked patch (hierarchical brain graph).`
3. `NOTICE`: replace `Used unmodified at upstream commit 72e9d8c (team fork Flissel/rowboat, branch `ehl`). This project`
   with:

```
  Used at upstream commit 72e9d8c (team fork Flissel/rowboat, branch `ehl`) with one patch, the
  hierarchical brain graph (Flissel/rowboat PR #N); the changed files say so in their header. This project
```

4. `docs/walkthrough.md` line 6: `(unmodified, commit `72e9d8c`)` → `(commit `72e9d8c`, plus our brain-graph patch)`.

- [ ] **Step 3: Commit and push the docs**

```bash
cd C:/Users/User/Desktop/ehl-munich-2026
git add docs/why-rowboat.md README.md NOTICE docs/walkthrough.md
ENTIRE_TEST_TTY=0 git commit -m "docs: Rowboat now carries one patch, the hierarchical brain graph" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
ENTIRE_TEST_TTY=0 git push
```

Expected: the push succeeds. If it is rejected with "missing necessary objects", retry once; that happened
twice in this repo.
