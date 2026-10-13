# VibeMind desktop update: the new Rowboat in vibemind-os

**Date:** 2026-10-13 · **Status:** draft for review · **Part 2 of 2** (part 1:
`2026-10-13-vault-folder-rules-design.md`)

## 1. Goal

VibeMind runs our current Rowboat desktop app (upstream `72e9d8c` + vault schema hierarchy + 2D/3D brain graph +
vault map) from source in dev mode on its own vault `~/.rowboat`, with VibeMind's own desktop additions (plugin
settings, video links) carried over. Future updates are one script run, not a hand port.

**Success criteria**

- `vibemind-os/spaces/rowboat/rowboat/apps/x` and `apps/harbor` are the exact trees of a recorded `Flissel/rowboat` commit; a script
  produced it and `UPSTREAM.md` names the commit.
- `start_desktop.py` starts Rowboat in dev mode on `~/.rowboat` with the vault map refresh; the 3D graph shows the
  VibeMind hierarchy.
- The plugin tab in Settings works as before (lists the catalog, previews, installs) against the same web app.
- The web app `apps/rowboat`, `packages/openai-plugin-runtime` and every file outside `apps/x`, `apps/harbor` and
  `spaces/rowboat/schema` stay byte-identical; the web app's `test:plugins` stays green.

## 2. Findings that shaped this design

| Finding | Consequence |
|---|---|
| The copy in `vibemind-os/spaces/rowboat/rowboat` was taken from upstream around `86cc2aaf` (2026-03-30). Its core is the web app `apps/rowboat` with VibeMind's plugin/OAuth/OpenFang work; upstream later deleted `apps/rowboat` | The web app has no newer upstream: it stays as it is |
| Commit `ec98a0c6` (2026-06-16, "commit working-tree changes") deleted `apps/x/apps/main` and `apps/x/packages`; the desktop app cannot be built from vibemind-os since then | The update restores a complete, buildable `apps/x` |
| VibeMind's own desktop changes: plugin settings (`3b282629` and follow-ups, Aug/Sep 2026: `lib/rowboat-plugin-api.ts`, `lib/rowboat-plugin-session.ts`, `hooks/usePlugins.ts`, `components/settings/plugin-settings.tsx` + 2 tests, tab in `settings-dialog.tsx`, script `test:plugins`), video links (`extensions/video-link.tsx` registered in `markdown-editor.tsx`), a tolerant file read in the graph build, `DialogTitle`/`DialogDescription` in Settings. All other differences are older upstream code (meeting/transcript) | Port exactly these; drop the rest |
| `apps/rowboat/test/plugins/catalog-pin-guard.test.ts` reads `apps/x/apps/renderer/src/lib/rowboat-plugin-api.ts` | That file keeps its path and its catalog pin |
| The plugin session reads `{signedIn, accessToken, config: {appUrl, …}}` from IPC `account:getRowboat`. At `72e9d8c` that channel returns `{signedIn, accessToken}`; service URLs come from `rowboat:getConfig` | The session must read both channels, or the plugin tab always says "unavailable" |
| `apps/x` links packages of `apps/harbor` (`@rowboat/spaces-protocol`, `@rowboat/harbor` via `link:../../../harbor/...`); building runs `pnpm install` + `pnpm -r build` in `apps/harbor` first. The VibeMind copy has no `apps/harbor` | The sync copies `apps/harbor` too; `--install` builds it |
| The renderer at `72e9d8c` already has zod, vitest, jsdom and testing-library | No new dependencies |
| The vibemind-os checkout on the PC is on a detached HEAD with 184 uncommitted changes of other sessions; Vibemind_V1 uses a WORKBOARD claim protocol and several sessions commit to `master` | Work in a separate git worktree on branch `feat/rowboat-desktop-update`; claim on the board first; never touch the main checkout |

## 3. Decisions

- **D1 The fork is the source.** VibeMind's desktop changes live as commits on branch `vibemind` in
  `Flissel/rowboat`, on top of `ehl-schema-graph`. vibemind-os only holds a pinned copy. (Best practice for a
  downstream fork: patches in the fork, consumer pins an exact revision, the copy is never edited by hand.)
- **D2 Only `apps/x` and `apps/harbor` are replaced.** The web app and the plugin runtime stay; upstream has nothing newer for them.
- **D3 The schema comes from the EHL repo the same way.** `schema/` (package, `vault-schema.yaml`, `profiles/`) is
  copied from a pinned `Flissel/ehl-munich-2026` commit to `vibemind-os/spaces/rowboat/schema/`. Changes to the
  schema or the VibeMind profile go to the EHL repo first.
- **D4 Dev mode only.** No installer build, no signing. The installed Rowboat app stays as it is.
- **D5 Separate branch in vibemind-os.** `feat/rowboat-desktop-update` from `origin/master` (Flissel/vibemind-os), worked in its own worktree; the user decides
  the merge.

## 4. Fork branch `vibemind` (Flissel/rowboat)

Base `ehl-schema-graph`. One commit per item; every new or changed file gets a first-line notice
`// Modified for VibeMind (Flissel/rowboat vibemind): <what>` (Apache-2.0 §4b).

| Item | Change |
|---|---|
| Plugin settings | Add the four source files and two tests unchanged, same paths. Add tab `plugins` ("Plugins", icon `Plug`) to `settings-dialog.tsx` and render `ConnectedPluginSettings` for it. Add script `test:plugins` to the renderer `package.json` |
| Plugin session | `acquire()` reads `account:getRowboat` (`{signedIn, accessToken}`) and `rowboat:getConfig` (service URLs incl. `appUrl`); the strict shape checks stay, per channel. Signed out → `null` as before; anything malformed → `plugin_session_unavailable` |
| Video links | Add `extensions/video-link.tsx`; register `VideoLinkExtension` in `markdown-editor.tsx` next to the other block extensions; add `case 'videoLink'` to `blockToMarkdown` (writes `[title](src)`), because the editor at `72e9d8c` serializes unknown nodes to an empty string and a saved note would lose its video link |
| Tolerant read | In `App.tsx` `buildGraph`, `data: typeof result?.data === 'string' ? result.data : ''` |
| Settings dialog a11y | `DialogTitle` / `DialogDescription` only if the dialog at `72e9d8c` lacks them |

## 5. Sync into vibemind-os

`spaces/rowboat/scripts/sync_desktop.py` (standard library only, Windows and macOS):

```
python spaces/rowboat/scripts/sync_desktop.py \
  --fork <clone of Flissel/rowboat> --fork-ref <commit> \
  --ehl <clone of Flissel/ehl-munich-2026> --ehl-ref <commit>
```

1. **Guard against hand edits:** if `spaces/rowboat/rowboat/UPSTREAM.md` exists, the current `apps/x`, `apps/harbor` and
   `spaces/rowboat/schema` must equal the trees of the commits it names (ignoring `node_modules`, `.venv`,
   `__pycache__`, `dist`). Otherwise stop and list the differing files.
2. Export `apps/x` and `apps/harbor` from `--fork-ref` and `schema` from `--ehl-ref` with `git archive` into a temp folder.
3. Replace `spaces/rowboat/rowboat/apps/x`, `apps/harbor` and `spaces/rowboat/schema` with them (ignored folders such as
   `node_modules` and `.venv` are kept so no reinstall is forced).
4. **Guard against collateral changes:** `git status` of the vibemind-os worktree may show changes only under the
   three target folders and `UPSTREAM.md`; otherwise stop.
5. Check that `apps/x/apps/renderer/src/lib/rowboat-plugin-api.ts` exists.
6. Write `spaces/rowboat/rowboat/UPSTREAM.md`: fork URL, branch, commit; upstream base `72e9d8c`; EHL repo commit
   for `schema/`; the list of VibeMind patches (from `git log ehl-schema-graph..<ref>` of the fork); the rule
   "never edit by hand; change the fork or the EHL repo, then run this script".

## 6. Start

`spaces/rowboat/scripts/start_desktop.py`:

- `--install`: `pnpm install` + `pnpm -r build` in `apps/harbor`, then `pnpm install` in `apps/x`; create `spaces/rowboat/schema/.venv` and `pip install -e` the schema.
- Start: check that `apps/x/node_modules` and the schema venv exist **before** starting anything (clear message
  otherwise); run `ehl_schema.cli map --workdir ~/.rowboat --profile vibemind` once; then start `npm run dev` in
  `apps/x` with `ROWBOAT_WORKDIR=~/.rowboat` and `map --watch 60`; Ctrl+C stops both.
- Never runs `build` or `migrate`; never edits an existing note.
- `--workdir` overrides `~/.rowboat`.

## 7. Error handling

| Case | Behaviour |
|---|---|
| `apps/x`, `apps/harbor` or `schema` hand-edited since the last sync | Sync stops, lists the files; nothing is replaced |
| A change outside the targets would result | Sync stops before writing `UPSTREAM.md`; the worktree shows what happened |
| `--fork-ref` / `--ehl-ref` unknown | Sync stops before touching anything |
| Plugin web app unreachable or signed out | Plugin tab shows its existing "unavailable" / "signed out" states |
| Missing `node_modules` or schema venv on start | Start stops with "run start_desktop.py --install first"; no orphan processes |

## 8. Tests

- **Fork:** the two ported plugin test files; a new test for `acquire()` combining both IPC channels (signed in,
  signed out, malformed config); a test that `VideoLinkExtension` is in the editor's extension list (or the
  editor module exports it); graph tests (30) and `tsc -b` stay green.
- **vibemind-os** (`spaces/rowboat/tests/`, pytest, temporary git repos): sync replaces only the targets; stops on
  hand edits; stops on collateral changes; keeps `node_modules`; writes `UPSTREAM.md`; start command lists contain
  no `build`/`migrate`, carry `--profile vibemind`, and nothing starts without venv/`node_modules`.
- **Real run:** sync on the feature branch; `pnpm install`; renderer tests; the web app's `test:plugins`; start on
  `~/.rowboat`; the user checks the plugin tab and the 3D graph.

## 9. Out of scope

- An installable app; changes to the web app or OpenFang; a PR to rowboatlabs; the curator writing schema
  fields; wiring the start into the VibeMind launcher.
