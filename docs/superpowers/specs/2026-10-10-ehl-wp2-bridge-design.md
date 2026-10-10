# WP2 – Bridge: Sales and Marketing → Rowboat Notes

**Branch:** `feat/ehl-bridge` · **Folder:** `bridge/` · **Parent spec:** `2026-10-10-rowboat-ehl-space-design.md` (§5.1, §5.2, §12 contracts)
**Status:** Draft awaiting approval

## 1. Goal

Every 60 s, read companies from Sales-Claw and campaigns/content from Marketing (read-only) and
write them as Rowboat notes into the vault, so the graph grows live.

**Done when:** a contact created in Sales-Claw shows up in its company's note under
`Organizations/` within ~60 s, linked to owner, products and channels; Marketing campaigns appear
under `Content/`; no file without `managed_by: ehl-bridge` is ever touched.

## 2. Modules

| Module | Responsibility |
|---|---|
| `sources/sales.py` | Leads, companies, pipeline stages, owner via sales-mcp (read-only). Group leads by company. Skip leads marked private. Drop email/phone. |
| `sources/marketing.py` | Campaigns and content of all tenants via the Marketing API (`127.0.0.1:5510`) |
| `model.py` | `Organization`, `Content`, `Activity` |
| `linking.py` | Company → product links from WP1's keyword list; company → owner from Sales; content → channel/product |
| `render.py` | Pure: model → Markdown (parent spec §5.1 template + frontmatter) |
| `vault.py` | Write only own files (`managed_by: ehl-bridge`), only on content-hash change; safe filenames; atomic write (temp file + rename) |
| `run.py` | Loop every `INTERVAL_S` (default 60); `--once` for tests |

## 3. First task: sales-mcp access (time-boxed 45 min)

`:8765/mcp` returns 404. Find the mount path and whether auth is required, and confirm one
read-only call (e.g. list contacts). Fallback: read-only access via the existing sales-claw
configuration. Record the result here.

## 4. Configuration

`.env` (template `.env.example`): `EHL_VAULT`, `SALES_MCP_URL`, `MARKETING_API_URL`,
`MARKETING_API_KEY`, `INTERVAL_S`, `PRODUCT_KEYWORDS` (path to WP1's list).

## 5. Error handling

Source unreachable → its notes untouched, warning logged, retry next run. Malformed record →
skipped and logged. 401/403 → clear error, process exits non-zero.

## 6. Tests (pytest)

- render: umlauts, empty lists, links, no email/phone in output.
- vault: never overwrites a file without `managed_by`; unchanged content → no write; atomic write.
- sales source: private leads skipped; leads grouped by company (fake MCP responses).
- run `--once` with fake sources into a temp vault → expected file set.

## 7. Dependencies

Needs WP1's frozen link targets and product keywords (parent §12). Until then, use the example
names from the parent spec.
