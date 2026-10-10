# WP3 – Semantic Search: Qdrant, Indexer and `ehl-search` MCP

**Branch:** `feat/ehl-search` · **Folder:** `search/` · **Parent spec:** `2026-10-10-rowboat-ehl-space-design.md` (§5.3, §12 contracts)
**Status:** Draft awaiting approval

## 1. Goal

Keep a local Qdrant index of all vault notes up to date and let the Rowboat agent search it by
meaning through an MCP tool. This is a separable add-on: the demo works without it.

**Done when:** `semantic_search("logistics companies interested in route planning")` via MCP
returns the matching `Organizations/` notes within 2 s; a changed note is re-indexed within 10 s;
a deleted note disappears from results.

## 2. Components

| Item | Responsibility |
|---|---|
| `search/docker-compose.yml` | Qdrant on `127.0.0.1:6333`, volume for data |
| `search/indexer.py` | Full pass on start, then watch `EHL_VAULT` (watchdog); parse frontmatter + `# Title` + `## Info` + body; embed with fastembed (multilingual model, local); upsert into collection `ehl_notes`; delete on file removal |
| `search/server.py` | MCP server `ehl-search` (stdio): `semantic_search(query, folder?, limit=5)` → `[{path, title, score, snippet}]` |
| `search/notes.py` | Shared note parser (pure) |

Point id = stable hash of the vault-relative path. Payload: `path`, `folder`, `title`, `source`,
`relationship`, outgoing `links`.

## 3. First task: model choice (time-boxed 30 min)

Pick a fastembed multilingual model that handles German, check download size and speed on the demo
PC, record it here.

## 4. Error handling

Qdrant down → tool returns a clear error message (the agent falls back to grep). Unparseable note →
indexed as plain text, warning logged. Embedding model missing → indexer exits with a clear message.

## 5. Tests (pytest)

- notes parser: frontmatter, title, Info fields, links, umlauts.
- indexer against a temp vault + Qdrant test collection: add, change, delete.
- server: `semantic_search` returns the expected note for 3 fixed queries; `folder` filter works.

## 6. Dependencies

None to start (use a fixture vault). Final check against WP1 example data + WP2 output in the dress rehearsal.
