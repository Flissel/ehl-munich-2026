# VibeMind Desktop Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give vibemind-os a buildable, current Rowboat desktop app (upstream `72e9d8c` + schema hierarchy + 3D graph +
VibeMind's plugin settings and video links), copied reproducibly from the fork, started in dev mode on `~/.rowboat`.

**Architecture:** VibeMind's desktop changes are ported as commits on a new fork branch `vibemind` (on top of
`ehl-schema-graph`). In vibemind-os a stdlib script (`sync_desktop.py`) replaces `apps/x`, `apps/harbor` and
`spaces/rowboat/schema` with pinned trees and writes `UPSTREAM.md`; a second script (`start_desktop.py`) installs and
starts the app plus the vault-map refresh. All vibemind-os work happens in a separate worktree on
`feat/rowboat-desktop-update`.

**Tech Stack:** TypeScript/React/vitest (Rowboat renderer, pnpm), Python stdlib + pytest (vibemind-os scripts; the
VibeMind venv is Python 3.11, so no 3.12-only syntax in the scripts), git.

**Spec:** `docs/superpowers/specs/2026-10-13-vibemind-desktop-update-design.md` (EHL repo, branch `feat/vibemind-desktop-update`)

## Global Constraints

- Repos and branches:
  - Fork: `C:\Users\User\Desktop\rowboat`, new branch `vibemind` from `ehl-schema-graph`.
  - vibemind-os: worktree `C:\Users\User\ClaudeWork\wt-rowboat-desktop` on new branch `feat/rowboat-desktop-update` from `origin/master` (remote `origin` = `Flissel/vibemind-os`). **Never touch the main checkout** `C:\Users\User\Desktop\Vibemind_V1\vibemind-os` (detached HEAD, 184 uncommitted changes of other sessions).
- Source of VibeMind's files: `git -C C:/Users/User/Desktop/Vibemind_V1/vibemind-os show origin/master:<path>` (committed version, never the dirty working tree).
- New files in the fork start with `// VibeMind addition (Flissel/rowboat vibemind): <what>`; changed upstream files get `// Modified for VibeMind (Flissel/rowboat vibemind): <what>` as first line unless the file already has an EHL notice line (then add the VibeMind line below it). Apache-2.0 §4b.
- Commits: conventional commits, `ENTIRE_TEST_TTY=0` before `git commit`, message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Stop and ask the user** before: pushing anything to a `master` branch (board claim), stopping a running Rowboat, merging.
- No `build`/`migrate` on `~/.rowboat`; no existing note is edited.
- TypeScript strict, no `any`, no `console.log` in new code; Python: `logging`, no `print`.
- Renderer tests: `cd <apps/x>/apps/renderer && npx vitest run <files>`; typecheck `npx tsc -b`.
- vibemind-os script tests: `C:/Users/User/Desktop/Vibemind_V1/.venv/Scripts/python.exe -m pytest -q spaces/rowboat/tests/<file> -p no:cacheprovider` run from the worktree root.

## Review Focus

1. **A video link vanishes when a note is saved** (`blockToMarkdown` returns `''` for unknown nodes). Expect: `[title](src)` round-trips (test in Task 2).
2. **Plugin tab always "unavailable"** because `account:getRowboat` no longer carries `config`, or because the strict key check rejects the larger `RowboatApiConfig`. Expect: signed in + config → ok; signed out → `signed_out` without reading config; config `null` → `plugin_session_unavailable` (tests in Task 1).
3. **The sync deletes `node_modules`/`.venv`** or touches the web app `apps/rowboat`. Expect: ignored folders survive, files outside the targets are byte-identical (tests in Task 4).
4. **CRLF checkouts on Windows look like hand edits** and block every later sync. Expect: line endings are normalised in the comparison (test in Task 4).
5. **`start_desktop.py` leaves Rowboat running as an orphan** when the venv or `node_modules` is missing. Expect: nothing starts, exit 2 (test in Task 5).

---

## File Structure

| File | Responsibility |
|---|---|
| Fork `apps/x/apps/renderer/src/lib/rowboat-plugin-api.ts` (+ `.test.ts`) | VibeMind plugin web-app client (copied unchanged) |
| Fork `apps/x/apps/renderer/src/lib/rowboat-plugin-session.ts` | Session from IPC; `acquire()` adapted to the two-channel IPC |
| Fork `apps/x/apps/renderer/src/hooks/usePlugins.ts` | Plugin state hook (copied unchanged) |
| Fork `apps/x/apps/renderer/src/components/settings/plugin-settings.tsx` (+ `.test.tsx`) | Plugins tab UI (copied; session tests updated) |
| Fork `apps/x/apps/renderer/src/components/settings-dialog.tsx` | Tab "Plugins", nav `role="tablist"`/`role="tab"` |
| Fork `apps/x/apps/renderer/src/extensions/video-link.tsx` (+ `.test.ts`) | Video link node (copied) |
| Fork `apps/x/apps/renderer/src/components/markdown-editor.tsx` | Register the extension, `case 'videoLink'`, export `blockToMarkdown` |
| Fork `apps/x/apps/renderer/src/lib/graph-hierarchy.ts` | `graphFileData()` tolerant read helper |
| Fork `apps/x/apps/renderer/src/App.tsx` | Use `graphFileData()` |
| Fork `apps/x/apps/renderer/package.json` | Script `test:plugins` |
| vibemind-os `spaces/rowboat/scripts/sync_desktop.py` | Pinned copy of `apps/x`, `apps/harbor`, `schema/`; guards; `UPSTREAM.md` |
| vibemind-os `spaces/rowboat/scripts/start_desktop.py` | `--install` and start (Rowboat + map refresh) |
| vibemind-os `spaces/rowboat/tests/test_sync_desktop.py`, `test_start_desktop.py` | Tests |
| vibemind-os `spaces/rowboat/rowboat/UPSTREAM.md` | Generated by the sync |

---

### Task 1: Plugin settings in the fork

**Files:**
- Create (copied): `apps/x/apps/renderer/src/lib/rowboat-plugin-api.ts`, `lib/rowboat-plugin-api.test.ts`, `lib/rowboat-plugin-session.ts`, `hooks/usePlugins.ts`, `components/settings/plugin-settings.tsx`, `components/settings/plugin-settings.test.tsx`
- Modify: `apps/x/apps/renderer/src/components/settings-dialog.tsx`, `apps/x/apps/renderer/package.json`

**Interfaces:**
- Produces: tab id `"plugins"` in `ConfigTab`; `ConnectedPluginSettings` rendered for it; `rowboatPluginApiAccess` reading `account:getRowboat` → `{signedIn, accessToken}` and `rowboat:getConfig` → `{appUrl, …} | null`.

- [ ] **Step 1: Branch and copy the files**

```bash
cd C:/Users/User/Desktop/rowboat
git switch -c vibemind ehl-schema-graph
R=apps/x/apps/renderer/src
V=C:/Users/User/Desktop/Vibemind_V1/vibemind-os
for f in lib/rowboat-plugin-api.ts lib/rowboat-plugin-api.test.ts lib/rowboat-plugin-session.ts hooks/usePlugins.ts components/settings/plugin-settings.tsx components/settings/plugin-settings.test.tsx; do
  git -C $V show origin/master:spaces/rowboat/rowboat/apps/x/apps/renderer/src/$f > $R/$f
done
git status --short
```

Expected: six new files listed.

Prepend to each of the four non-test files the line
`// VibeMind addition (Flissel/rowboat vibemind): plugin settings (vibemind-os 3b282629 and follow-ups).`
Do **not** change `DESKTOP_PLUGIN_CATALOG_PIN` or anything else in `rowboat-plugin-api.ts`: the web app's
`catalog-pin-guard.test.ts` reads this file.

- [ ] **Step 2: Update the session tests to the new IPC (they become the failing tests)**

In `components/settings/plugin-settings.test.tsx`, inside `describe('rowboatPluginApiAccess', …)`, replace the
`Object.defineProperty(window, 'ipc', …)` block of the first test with:

```ts
    Object.defineProperty(window, 'ipc', { configurable: true, value: {
      invoke: vi.fn(async (channel: string) => channel === 'account:getRowboat'
        ? { signedIn: true, accessToken: token }
        : { appUrl: 'https://rowboat.example/', websocketApiUrl: 'wss://rowboat.example/',
            supabaseUrl: 'https://supabase.example/', billing: { plans: [] } }),
      on: vi.fn(() => () => undefined),
    } });
```

Append two tests at the end of that `describe`:

```ts
  it('returns signed_out without reading the service config', async () => {
    const invoke = vi.fn(async (channel: string) => channel === 'account:getRowboat'
      ? { signedIn: false, accessToken: null } : null);
    Object.defineProperty(window, 'ipc', { configurable: true, value: { invoke, on: vi.fn(() => () => undefined) } });
    await expect(rowboatPluginApiAccess.listCatalog(digest)).resolves.toEqual({ kind: 'signed_out' });
    expect(invoke).not.toHaveBeenCalledWith('rowboat:getConfig', null);
  });

  it('is unavailable when signed in but the service config is missing', async () => {
    Object.defineProperty(window, 'ipc', { configurable: true, value: {
      invoke: vi.fn(async (channel: string) => channel === 'account:getRowboat'
        ? { signedIn: true, accessToken: 'token-a' } : null),
      on: vi.fn(() => () => undefined),
    } });
    await expect(rowboatPluginApiAccess.listCatalog(digest)).rejects.toThrow('plugin_session_unavailable');
  });
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd apps/x/apps/renderer && npx vitest run src/components/settings/plugin-settings.test.tsx src/lib/rowboat-plugin-api.test.ts`
Expected: FAIL — the session tests (old `acquire()` expects `config` inside the account) and the
"integrates an accessible Plugins tab" test (no tab yet). `rowboat-plugin-api.test.ts` passes.

- [ ] **Step 4: Adapt `acquire()` in `rowboat-plugin-session.ts`**

Below the `record` function add:

```ts
function plainObject(value: unknown): object {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) throw new Error('plugin_session_unavailable');
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) throw new Error('plugin_session_unavailable');
  return value;
}
```

Replace the whole `async function acquire() { … }` with:

```ts
// Rowboat at 72e9d8c: account:getRowboat carries only the sign-in state; the service URLs come from
// rowboat:getConfig (a larger object, so only appUrl is checked there).
async function acquire() {
  let rawAccount: unknown;
  try { rawAccount = await window.ipc.invoke('account:getRowboat', null); }
  catch { throw new Error('plugin_session_unavailable'); }
  let accessToken: string;
  try {
    const account = record(rawAccount, ['signedIn', 'accessToken']);
    const signedIn = ownData(account, 'signedIn');
    const token = ownData(account, 'accessToken');
    if (signedIn === false && token === null) return null;
    if (signedIn !== true || typeof token !== 'string' || token.length < 1 || token.length > TOKEN_LIMIT || /[,\s\0]/.test(token)) throw new Error();
    accessToken = token;
  } catch { throw new Error('plugin_session_unavailable'); }
  let rawConfig: unknown;
  try { rawConfig = await window.ipc.invoke('rowboat:getConfig', null); }
  catch { throw new Error('plugin_session_unavailable'); }
  try {
    const appUrl = ownData(plainObject(rawConfig), 'appUrl');
    if (typeof appUrl !== 'string') throw new Error();
    const origin = canonicalPluginOrigin(appUrl);
    return Object.freeze({ baseUrl: appUrl, accessToken, origin });
  } catch { throw new Error('plugin_session_unavailable'); }
}
```

- [ ] **Step 5: Add the Plugins tab to `settings-dialog.tsx`**

1. First line: `// Modified for VibeMind (Flissel/rowboat vibemind): Plugins tab, accessible tab navigation.`
2. Import: `import { ConnectedPluginSettings } from "@/components/settings/plugin-settings"` next to the other `@/components/settings/` imports.
3. `ConfigTab`: add `"plugins"` after `"connections"`.
4. In `tabs`, after the `connections` entry:

```ts
  {
    id: "plugins",
    label: "Plugins",
    icon: Plug,
    description: "View and install server-authorized OpenAI plugins",
  },
```

5. `NAV_SECTIONS` first group: `ids: ["account", "connections", "plugins", "mobile", "phone"]`.
6. In the effect that loads file-backed tabs, add `|| tab === "plugins"` to the early-return condition
   (`if (tab === "appearance" || tab === "shortcuts" || …) return`).
7. Nav: `<nav className="flex flex-col">` → `<nav className="flex flex-col" role="tablist" aria-label="Settings tabs">`;
   each tab `<button` gets `role="tab"` and `aria-selected={activeTab === tab.id}`.
8. Render branch: before `) : activeTab === "connections" ? (` insert
   `) : activeTab === "plugins" ? (\n                <ConnectedPluginSettings />`.

In `apps/x/apps/renderer/package.json` add to `scripts`:
`"test:plugins": "vitest run --environment jsdom src/lib/rowboat-plugin-api.test.ts src/components/settings/plugin-settings.test.tsx"`.

- [ ] **Step 6: Run the tests and the typecheck**

Run: `npx vitest run src/components/settings/plugin-settings.test.tsx src/lib/rowboat-plugin-api.test.ts && npx tsc -b`
Expected: all PASS, tsc clean. If "integrates an accessible Plugins tab" fails because the 72e9d8c dialog calls
other IPC channels that the test's single mock answers wrongly, change that test's mock to answer per channel
(`null` for unknown channels) and ledger it as a ruling; do not weaken the assertion.

- [ ] **Step 7: Commit**

```bash
git add apps/x/apps/renderer/src apps/x/apps/renderer/package.json
ENTIRE_TEST_TTY=0 git commit -m "feat(vibemind): plugin settings tab, session on the 72e9d8c IPC

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Video links and the tolerant graph read

**Files:**
- Create (copied): `apps/x/apps/renderer/src/extensions/video-link.tsx`
- Create: `apps/x/apps/renderer/src/extensions/video-link.test.ts`
- Modify: `apps/x/apps/renderer/src/components/markdown-editor.tsx` (import, extensions list near line 786, `blockToMarkdown` at line 142)
- Modify: `apps/x/apps/renderer/src/lib/graph-hierarchy.ts`, `graph-hierarchy.test.ts`, `App.tsx` (`buildGraph` file read)

**Interfaces:**
- Produces: `export function blockToMarkdown(node: JsonNode): string` (now exported) with `case 'videoLink'`;
  `export function graphFileData(result: unknown): string` in `graph-hierarchy.ts`.

- [ ] **Step 1: Copy the extension**

```bash
cd C:/Users/User/Desktop/rowboat
git -C C:/Users/User/Desktop/Vibemind_V1/vibemind-os show origin/master:spaces/rowboat/rowboat/apps/x/apps/renderer/src/extensions/video-link.tsx > apps/x/apps/renderer/src/extensions/video-link.tsx
```

Prepend `// VibeMind addition (Flissel/rowboat vibemind): video links as inline players (vibemind-os f6695d46).`

- [ ] **Step 2: Write the failing tests**

Create `apps/x/apps/renderer/src/extensions/video-link.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { blockToMarkdown } from '@/components/markdown-editor'
import { VideoLinkExtension } from './video-link'

describe('video links', () => {
  it('is a block node named videoLink', () => {
    expect(VideoLinkExtension.name).toBe('videoLink')
  })

  it('survives saving as a markdown link', () => {
    expect(blockToMarkdown({ type: 'videoLink', attrs: { src: 'http://localhost:8977/demo.mp4', title: 'Demo' } }))
      .toBe('[Demo](http://localhost:8977/demo.mp4)')
  })

  it('gets a default title when it has none', () => {
    expect(blockToMarkdown({ type: 'videoLink', attrs: { src: 'http://x/a.webm', title: '' } }))
      .toBe('[▶ Video abspielen](http://x/a.webm)')
  })
})
```

Append to `src/lib/graph-hierarchy.test.ts` (add `graphFileData` to its import):

```ts
describe('graphFileData', () => {
  it('returns the text of a read result and an empty string for anything else', () => {
    expect(graphFileData({ data: '# a' })).toBe('# a')
    expect(graphFileData({ data: 42 })).toBe('')
    expect(graphFileData(null)).toBe('')
    expect(graphFileData(undefined)).toBe('')
  })
})
```

- [ ] **Step 3: Run them to verify they fail**

Run: `npx vitest run src/extensions/video-link.test.ts src/lib/graph-hierarchy.test.ts`
Expected: FAIL (`blockToMarkdown` / `graphFileData` not exported). If importing `markdown-editor` itself fails in
jsdom for an unrelated reason, ledger it and move `blockToMarkdown` + its helpers' use unchanged (do not copy them):
export it anyway and test through it; never duplicate the serializer.

- [ ] **Step 4: Implement**

`markdown-editor.tsx`:
1. First line (or below an existing notice): `// Modified for VibeMind (Flissel/rowboat vibemind): video link blocks.`
2. `import { VideoLinkExtension } from '@/extensions/video-link'` next to `TranscriptBlockExtension`'s import.
3. Add `VideoLinkExtension,` after `MermaidBlockExtension,` in the extensions list.
4. `function blockToMarkdown(` → `export function blockToMarkdown(`.
5. Before `default:` in its switch:

```ts
    case 'videoLink': {
      const src = (node.attrs?.src as string) || ''
      const title = (node.attrs?.title as string) || '▶ Video abspielen'
      return src ? `[${title}](${src})` : ''
    }
```

`graph-hierarchy.ts` (after `vaultMapNodeId`):

```ts
/** Text of a workspace:readFile result; anything unexpected reads as an empty note (VibeMind: vibemind-os 2f0f2974). */
export function graphFileData(result: unknown): string {
  if (typeof result !== 'object' || result === null) return ''
  const data = (result as { data?: unknown }).data
  return typeof data === 'string' ? data : ''
}
```

`App.tsx` `buildGraph`: `return { path, data: result.data as string }` → `return { path, data: graphFileData(result) }`
and add `graphFileData` to the `@/lib/graph-hierarchy` import.

- [ ] **Step 5: Run tests and typecheck**

Run: `npx vitest run src/extensions/video-link.test.ts src/lib/graph-hierarchy.test.ts src/components/settings/plugin-settings.test.tsx src/lib/rowboat-plugin-api.test.ts && npx tsc -b`
Expected: all PASS, tsc clean.

- [ ] **Step 6: Commit**

```bash
git add apps/x/apps/renderer/src
ENTIRE_TEST_TTY=0 git commit -m "feat(vibemind): video links that survive saving, tolerant graph file read

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: vibemind-os worktree and board claim

**Files:** none in the repo yet (worktree + Vibemind_V1 `WORKBOARD.md`).

- [ ] **Step 1: Create the worktree**

```bash
cd C:/Users/User/Desktop/Vibemind_V1/vibemind-os
git fetch origin master
git worktree add C:/Users/User/ClaudeWork/wt-rowboat-desktop -b feat/rowboat-desktop-update origin/master
git -C C:/Users/User/ClaudeWork/wt-rowboat-desktop status --short | head
```

Expected: worktree created, clean status.

- [ ] **Step 2: Prepare the board claim, then ask**

Read `C:/Users/User/Desktop/Vibemind_V1/WORKBOARD.md` (and `git -C C:/Users/User/Desktop/Vibemind_V1 log -1 origin/master`).
Draft one row under **In Arbeit**:
`| cc-rowboat-desktop-update | 2026-10-13 | Rowboat-Desktop in vibemind-os erneuern: spaces/rowboat/rowboat/apps/x + apps/harbor + spaces/rowboat/schema per Sync aus Flissel/rowboat vibemind bzw. Flissel/ehl-munich-2026; neue Skripte spaces/rowboat/scripts/sync_desktop.py, start_desktop.py. Branch feat/rowboat-desktop-update (Worktree C:/Users/User/ClaudeWork/wt-rowboat-desktop). Web-App apps/rowboat und Plugin-Runtime unberuehrt. |`
**Stop and ask the user** whether to commit and push this claim to Vibemind_V1 `master` (shared branch). Only on yes:
do it in a separate Vibemind_V1 worktree on master (the Vibemind_V1 checkout is on `codex/vibemind-ops-baseline`),
commit `docs: workboard claim rowboat-desktop-update`, push. On no: continue and note "claim not posted" in the ledger.

---

### Task 4: `sync_desktop.py`

**Files (in the worktree):**
- Create: `spaces/rowboat/scripts/sync_desktop.py`
- Create: `spaces/rowboat/tests/test_sync_desktop.py`

**Interfaces:**
- Produces: `sync(space: Path, repo: Path, fork: Path, fork_ref: str, ehl: Path, ehl_ref: str, upstream_base: str = UPSTREAM_BASE) -> dict[str, str]`
  (returns `{"fork": sha, "ehl": sha}`), `SyncError`, `files_of(root) -> dict[str, bytes]`, `changed_paths(repo) -> set[str]`,
  `replace(dest, source)`, `read_pins(upstream_md: Path) -> dict[str, str]`; CLI `--fork --fork-ref --ehl --ehl-ref`.

- [ ] **Step 1: Write the failing tests**

Create `spaces/rowboat/tests/test_sync_desktop.py`:

```python
"""Checks for spaces/rowboat/scripts/sync_desktop.py (temporary git repos only)."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_desktop  # noqa: E402
from sync_desktop import SyncError, read_pins, sync  # noqa: E402

PIN = "apps/x/apps/renderer/src/lib/rowboat-plugin-api.ts"


def commit_files(repo: Path, files: dict[str, str], message: str = "c") -> str:
    for rel, text in files.items():
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True)
    run("add", "-A")
    run("-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
        "commit", "-q", "-m", message)
    return run("rev-parse", "HEAD").stdout.strip()


def new_repo(path: Path, files: dict[str, str]) -> tuple[Path, str]:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path, commit_files(path, files)


@pytest.fixture
def world(tmp_path):
    fork, fork_sha = new_repo(tmp_path / "fork", {
        "apps/x/package.json": "x1\n", PIN: "pin\n", "apps/harbor/package.json": "h1\n", "README.md": "fork\n"})
    ehl, ehl_sha = new_repo(tmp_path / "ehl", {
        "schema/pyproject.toml": "s1\n", "schema/profiles/vibemind.yaml": "company: VibeMind\n", "market/x.py": "bmw\n"})
    vos, _ = new_repo(tmp_path / "vos", {
        ".gitignore": "node_modules/\n.venv/\n",
        "spaces/rowboat/rowboat/apps/x/apps/renderer/old.ts": "old\n",
        "spaces/rowboat/rowboat/apps/rowboat/web.ts": "web\n",
        "README.md": "vos\n"})
    keep = vos / "spaces/rowboat/rowboat/apps/x/node_modules/keep.txt"
    keep.parent.mkdir(parents=True)
    keep.write_text("installed", encoding="utf-8")
    return {"fork": fork, "fork_sha": fork_sha, "ehl": ehl, "ehl_sha": ehl_sha, "vos": vos,
            "space": vos / "spaces/rowboat", "keep": keep}


def run_sync(w, fork_ref=None, ehl_ref=None):
    return sync(w["space"], w["vos"], w["fork"], fork_ref or w["fork_sha"], w["ehl"], ehl_ref or w["ehl_sha"])


def test_first_sync_replaces_only_the_targets(world):
    shas = run_sync(world)
    app = world["space"] / "rowboat/apps/x"
    assert (app / "package.json").read_text(encoding="utf-8") == "x1\n"
    assert not (app / "apps/renderer/old.ts").exists()
    assert (world["space"] / "rowboat/apps/harbor/package.json").is_file()
    assert (world["space"] / "schema/profiles/vibemind.yaml").is_file()
    assert not (world["space"] / "schema/market").exists() and not (world["space"] / "market").exists()
    assert (world["space"] / "rowboat/apps/rowboat/web.ts").read_text(encoding="utf-8") == "web\n"
    assert world["keep"].read_text(encoding="utf-8") == "installed"
    pins = read_pins(world["space"] / "rowboat/UPSTREAM.md")
    assert pins == {"Fork": shas["fork"], "EHL": shas["ehl"]} == {"Fork": world["fork_sha"], "EHL": world["ehl_sha"]}


def test_unchanged_copy_syncs_to_a_new_commit(world):
    run_sync(world)
    new_sha = commit_files(world["fork"], {"apps/x/package.json": "x2\n"})
    run_sync(world, fork_ref=new_sha)
    assert (world["space"] / "rowboat/apps/x/package.json").read_text(encoding="utf-8") == "x2\n"
    assert read_pins(world["space"] / "rowboat/UPSTREAM.md")["Fork"] == new_sha


def test_crlf_checkout_is_not_a_hand_edit(world):
    run_sync(world)
    f = world["space"] / "rowboat/apps/x/package.json"
    f.write_bytes(b"x1\r\n")
    new_sha = commit_files(world["fork"], {"apps/x/package.json": "x3\n"})
    run_sync(world, fork_ref=new_sha)
    assert f.read_text(encoding="utf-8") == "x3\n"


def test_hand_edit_stops_the_next_sync(world):
    run_sync(world)
    edited = world["space"] / "rowboat/apps/x/package.json"
    edited.write_text("edited here\n", encoding="utf-8", newline="\n")
    new_sha = commit_files(world["fork"], {"apps/x/package.json": "x2\n"})
    with pytest.raises(SyncError, match="rowboat/apps/x/package.json"):
        run_sync(world, fork_ref=new_sha)
    assert edited.read_text(encoding="utf-8") == "edited here\n"


def test_missing_pin_file_stops_before_replacing(world):
    subprocess.run(["git", "-C", str(world["fork"]), "rm", "-q", PIN], check=True)
    sha = commit_files(world["fork"], {}, "drop pin")
    with pytest.raises(SyncError, match="rowboat-plugin-api.ts"):
        run_sync(world, fork_ref=sha)
    assert (world["space"] / "rowboat/apps/x/apps/renderer/old.ts").exists()


def test_unknown_ref_stops_before_touching(world):
    with pytest.raises(SyncError):
        run_sync(world, fork_ref="no-such-ref")
    assert (world["space"] / "rowboat/apps/x/apps/renderer/old.ts").exists()
    assert not (world["space"] / "rowboat/UPSTREAM.md").exists()


def test_changes_outside_the_targets_stop_the_sync(world, monkeypatch):
    real_replace = sync_desktop.replace

    def leaky(dest, source):
        real_replace(dest, source)
        (world["vos"] / "README.md").write_text("collateral\n", encoding="utf-8")

    monkeypatch.setattr(sync_desktop, "replace", leaky)
    with pytest.raises(SyncError, match="README.md"):
        run_sync(world)
    assert not (world["space"] / "rowboat/UPSTREAM.md").exists()
```

- [ ] **Step 2: Run them to verify they fail**

Run (worktree root): `C:/Users/User/Desktop/Vibemind_V1/.venv/Scripts/python.exe -m pytest -q spaces/rowboat/tests/test_sync_desktop.py -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'sync_desktop'`.

- [ ] **Step 3: Write `sync_desktop.py`**

```python
"""Replace the pinned copies of the Rowboat desktop app and the vault schema in this space.

    python spaces/rowboat/scripts/sync_desktop.py --fork <clone of Flissel/rowboat> --fork-ref <commit> \\
        --ehl <clone of Flissel/ehl-munich-2026> --ehl-ref <commit>

apps/x and apps/harbor come from the fork, schema/ from the EHL repo. Never edit these copies by hand: change the
fork or the EHL repo, then run this script. It stops when a copy was edited since the last sync and when anything
outside the copies would change. Spec: Flissel/ehl-munich-2026
docs/superpowers/specs/2026-10-13-vibemind-desktop-update-design.md
"""
from __future__ import annotations

import argparse
import io
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("sync_desktop")

SPACE = Path(__file__).resolve().parents[1]
FORK_URL = "https://github.com/Flissel/rowboat"
EHL_URL = "https://github.com/Flissel/ehl-munich-2026"
UPSTREAM_BASE = "72e9d8c"
IGNORED = ("node_modules", ".venv", "__pycache__", "dist", ".vite", ".pytest_cache")
PIN_FILE = "apps/renderer/src/lib/rowboat-plugin-api.ts"   # inside apps/x; read by apps/rowboat's catalog-pin-guard test
PIN_LINE = re.compile(r"^- (Fork|EHL) commit: `([0-9a-f]{40})`$", re.M)


class SyncError(Exception):
    """The sync stopped; the step that failed says why."""


@dataclass(frozen=True)
class Target:
    source: str   # "fork" or "ehl"
    subdir: str   # folder inside the source repo
    dest: Path    # folder in this space


def targets(space: Path) -> list[Target]:
    return [Target("fork", "apps/x", space / "rowboat" / "apps" / "x"),
            Target("fork", "apps/harbor", space / "rowboat" / "apps" / "harbor"),
            Target("ehl", "schema", space / "schema")]


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise SyncError(f"git {' '.join(args)} in {repo}: {proc.stderr.strip()}")
    return proc.stdout


def resolve(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").strip()


def _ignored(name: str) -> bool:
    return name in IGNORED or name.endswith(".egg-info")


def _walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _ignored(d)]
        yield Path(dirpath), dirnames, filenames


def files_of(root: Path) -> dict[str, bytes]:
    """Every file under root (relative posix path -> content with LF newlines); ignored folders left out."""
    out: dict[str, bytes] = {}
    if not root.is_dir():
        return out
    for dirpath, _, filenames in _walk(root):
        for name in filenames:
            file = dirpath / name
            out[file.relative_to(root).as_posix()] = file.read_bytes().replace(b"\r\n", b"\n")
    return out


def export(repo: Path, ref: str, subdir: str, dest: Path) -> Path:
    proc = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", ref, subdir], capture_output=True)
    if proc.returncode != 0:
        raise SyncError(f"git archive {ref} {subdir} in {repo}: {proc.stderr.decode(errors='replace').strip()}")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, filter="data")
        else:  # Python < 3.11.4: archive comes from our own git repo
            tar.extractall(dest)
    return dest / subdir


def differences(expected: dict[str, bytes], actual: dict[str, bytes]) -> list[str]:
    return sorted(p for p in expected.keys() | actual.keys() if expected.get(p) != actual.get(p))


def replace(dest: Path, source: Path) -> None:
    """dest becomes a copy of source; ignored folders inside dest (node_modules, .venv, …) are kept."""
    if dest.is_dir():
        dirs: list[Path] = []
        for dirpath, _, filenames in _walk(dest):
            dirs.append(dirpath)
            for name in filenames:
                (dirpath / name).unlink()
        for d in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
            if d != dest and not any(d.iterdir()):
                d.rmdir()
    shutil.copytree(source, dest, dirs_exist_ok=True)


def changed_paths(repo: Path) -> set[str]:
    out = git(repo, "status", "--porcelain", "-z", "-uall", "--no-renames")
    return {entry[3:] for entry in out.split("\0") if entry}


def read_pins(upstream_md: Path) -> dict[str, str]:
    return dict(PIN_LINE.findall(upstream_md.read_text(encoding="utf-8")))


def patches(fork: Path, sha: str, base: str) -> list[str]:
    try:
        base_sha = resolve(fork, base)
    except SyncError:
        return [f"(upstream base {base} is not in this fork clone)"]
    return [line for line in git(fork, "log", "--format=%h %s", f"{base_sha}..{sha}").splitlines() if line]


def upstream_text(fork_sha: str, ehl_sha: str, base: str, patch_lines: list[str]) -> str:
    lines = ["# Pinned upstream code – do not edit by hand", "",
             "`apps/x` and `apps/harbor` (Rowboat desktop app) and `../schema` (vault schema) are copies made by",
             "`spaces/rowboat/scripts/sync_desktop.py`. Change the fork or the EHL repo, then run the script again;",
             "it refuses to run when these copies were edited here.", "",
             f"- Fork: {FORK_URL} (branch `vibemind`)",
             f"- Fork commit: `{fork_sha}`",
             f"- Upstream base: rowboatlabs/rowboat `{base}`",
             f"- EHL repo: {EHL_URL} (`schema/`)",
             f"- EHL commit: `{ehl_sha}`", "",
             "## Patches on top of upstream (EHL hierarchy graph, VibeMind)", ""]
    lines += [f"- {p}" for p in patch_lines] or ["- (none)"]
    return "\n".join(lines) + "\n"


def sync(space: Path, repo: Path, fork: Path, fork_ref: str, ehl: Path, ehl_ref: str,
         upstream_base: str = UPSTREAM_BASE) -> dict[str, str]:
    sources = {"fork": fork, "ehl": ehl}
    shas = {"fork": resolve(fork, fork_ref), "ehl": resolve(ehl, ehl_ref)}
    upstream_md = space / "rowboat" / "UPSTREAM.md"
    tgts = targets(space)
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        if upstream_md.exists():
            pins = read_pins(upstream_md)
            old = {"fork": pins.get("Fork"), "ehl": pins.get("EHL")}
            if None in old.values():
                raise SyncError(f"{upstream_md} names no fork or EHL commit")
            edited: list[str] = []
            for i, t in enumerate(tgts):
                pinned = export(sources[t.source], old[t.source], t.subdir, tmpdir / f"old{i}")
                prefix = t.dest.relative_to(space).as_posix()
                edited += [f"{prefix}/{p}" for p in differences(files_of(pinned), files_of(t.dest))]
            if edited:
                raise SyncError("edited by hand since the last sync (change the fork or the EHL repo instead):\n  "
                                + "\n  ".join(edited[:50]))
        new = {t: export(sources[t.source], shas[t.source], t.subdir, tmpdir / f"new{i}") for i, t in enumerate(tgts)}
        if not (new[tgts[0]] / PIN_FILE).is_file():
            raise SyncError(f"apps/x/{PIN_FILE} is missing at fork commit {shas['fork']}; the web app's pin test needs it")
        before = changed_paths(repo)
        for t in tgts:
            replace(t.dest, new[t])
        allowed = [t.dest.relative_to(repo).as_posix() + "/" for t in tgts]
        outside = sorted(p for p in changed_paths(repo) - before if not any(p.startswith(a) for a in allowed))
        if outside:
            raise SyncError("changes outside the pinned copies (check the worktree):\n  " + "\n  ".join(outside))
    upstream_md.write_text(upstream_text(shas["fork"], shas["ehl"], upstream_base,
                                         patches(fork, shas["fork"], upstream_base)), encoding="utf-8", newline="\n")
    return shas


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fork", type=Path, required=True, help="local clone of Flissel/rowboat")
    ap.add_argument("--fork-ref", required=True, help="commit or branch of the fork, e.g. vibemind")
    ap.add_argument("--ehl", type=Path, required=True, help="local clone of Flissel/ehl-munich-2026")
    ap.add_argument("--ehl-ref", required=True, help="commit or branch of the EHL repo")
    args = ap.parse_args(argv)
    repo = Path(git(SPACE, "rev-parse", "--show-toplevel").strip())
    try:
        shas = sync(SPACE, repo, args.fork, args.fork_ref, args.ehl, args.ehl_ref)
    except SyncError as err:
        log.error("sync stopped: %s", err)
        return 1
    log.info("synced apps/x + apps/harbor from %s and schema from %s; see spaces/rowboat/rowboat/UPSTREAM.md",
             shas["fork"][:9], shas["ehl"][:9])
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Python 3.11 note: `list[str] | None` in annotations works because of `from __future__ import annotations`.

- [ ] **Step 4: Run the tests**

Run: `C:/Users/User/Desktop/Vibemind_V1/.venv/Scripts/python.exe -m pytest -q spaces/rowboat/tests/test_sync_desktop.py -p no:cacheprovider`
Expected: 7 passed.

- [ ] **Step 5: Commit (in the worktree)**

```bash
cd C:/Users/User/ClaudeWork/wt-rowboat-desktop
git add spaces/rowboat/scripts/sync_desktop.py spaces/rowboat/tests/test_sync_desktop.py
ENTIRE_TEST_TTY=0 git commit -m "feat(rowboat): sync_desktop.py pins apps/x, apps/harbor and the vault schema

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `start_desktop.py`

**Files (in the worktree):**
- Create: `spaces/rowboat/scripts/start_desktop.py`
- Create: `spaces/rowboat/tests/test_start_desktop.py`

**Interfaces:**
- Produces: `Layout(app, harbor, schema, venv)`, `layout(space) -> Layout`, `venv_python(venv, windows) -> Path`,
  `install_steps(lay, windows) -> list[tuple[list[str], Path]]`, `missing(lay, windows) -> list[str]`,
  `map_command(py, workdir, watch=0) -> list[str]`, `jobs(lay, workdir, windows) -> list[tuple[str, list[str], Path]]`,
  `start(lay, workdir, windows) -> int`, CLI `--install`, `--workdir`.

- [ ] **Step 1: Write the failing tests**

Create `spaces/rowboat/tests/test_start_desktop.py`:

```python
"""Checks for spaces/rowboat/scripts/start_desktop.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import start_desktop  # noqa: E402
from start_desktop import install_steps, jobs, layout, map_command, missing  # noqa: E402


def test_install_builds_harbor_first_then_app_then_schema(tmp_path):
    lay = layout(tmp_path)
    steps = install_steps(lay, windows=True)
    assert [(cmd[:2], cwd) for cmd, cwd in steps[:3]] == [
        (["pnpm", "install"], lay.harbor), (["pnpm", "-r"], lay.harbor), (["pnpm", "install"], lay.app)]
    assert steps[3][0][:4] == ["py", "-3.12", "-m", "venv"]
    assert steps[4][0][-2:] == ["-e", str(lay.schema)]


def test_map_never_builds_or_migrates_and_uses_the_profile(tmp_path):
    cmd = map_command(Path("py"), tmp_path, watch=60)
    assert cmd[1:4] == ["-m", "ehl_schema.cli", "map"]
    assert cmd[cmd.index("--profile") + 1] == "vibemind"
    assert cmd[-2:] == ["--watch", "60"]
    every = [c for _, c, _ in jobs(layout(tmp_path), tmp_path, windows=False)] + [cmd]
    assert not any(word in c for c in every for word in ("build", "migrate"))


def test_rowboat_gets_the_workdir_and_runs_in_apps_x(tmp_path):
    lay = layout(tmp_path)
    (name, cmd, cwd), (map_name, _, _) = jobs(lay, tmp_path / ".rowboat", windows=False)
    assert (name, cmd, cwd, map_name) == ("Rowboat", ["npm", "run", "dev"], lay.app, "vault map")


def test_missing_lists_everything_that_is_not_installed(tmp_path):
    assert len(missing(layout(tmp_path), windows=True)) == 3


def test_nothing_starts_when_something_is_missing(tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(start_desktop.subprocess, "Popen", lambda *a, **k: started.append(a))
    monkeypatch.setattr(start_desktop.subprocess, "run", lambda *a, **k: started.append(a))
    assert start_desktop.start(layout(tmp_path), tmp_path, windows=True) == 2
    assert started == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `C:/Users/User/Desktop/Vibemind_V1/.venv/Scripts/python.exe -m pytest -q spaces/rowboat/tests/test_start_desktop.py -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'start_desktop'`.

- [ ] **Step 3: Write `start_desktop.py`**

```python
"""Start the Rowboat desktop app of this space in dev mode on the VibeMind vault (~/.rowboat).

    python spaces/rowboat/scripts/start_desktop.py --install   # once: build harbor, install the app, schema venv
    python spaces/rowboat/scripts/start_desktop.py             # Rowboat + vault-map refresh; Ctrl+C stops both

The vault map (config/vault-map.json) places VibeMind's notes in the schema hierarchy for the 3D brain graph.
It never edits a note: no `build`, no `migrate`. Spec: Flissel/ehl-munich-2026
docs/superpowers/specs/2026-10-13-vibemind-desktop-update-design.md
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("start_desktop")

SPACE = Path(__file__).resolve().parents[1]
IS_WINDOWS = os.name == "nt"
PROFILE = "vibemind"
MAP_SECONDS = 60


@dataclass(frozen=True)
class Layout:
    app: Path
    harbor: Path
    schema: Path
    venv: Path


def layout(space: Path = SPACE) -> Layout:
    return Layout(space / "rowboat" / "apps" / "x", space / "rowboat" / "apps" / "harbor",
                  space / "schema", space / "schema" / ".venv")


def venv_python(venv: Path, windows: bool = IS_WINDOWS) -> Path:
    return venv / "Scripts" / "python.exe" if windows else venv / "bin" / "python"


def python312(windows: bool = IS_WINDOWS) -> list[str]:
    return ["py", "-3.12"] if windows else ["python3.12"]


def install_steps(lay: Layout, windows: bool = IS_WINDOWS) -> list[tuple[list[str], Path]]:
    return [(["pnpm", "install", "--frozen-lockfile"], lay.harbor),
            (["pnpm", "-r", "build"], lay.harbor),
            (["pnpm", "install", "--frozen-lockfile"], lay.app),
            ([*python312(windows), "-m", "venv", str(lay.venv)], lay.schema),
            ([str(venv_python(lay.venv, windows)), "-m", "pip", "install", "-q", "-e", str(lay.schema)], lay.schema)]


def missing(lay: Layout, windows: bool = IS_WINDOWS) -> list[str]:
    out = []
    if not (lay.harbor / "node_modules").is_dir():
        out.append(f"{lay.harbor / 'node_modules'} (harbor packages)")
    if not (lay.app / "node_modules").is_dir():
        out.append(f"{lay.app / 'node_modules'} (Rowboat packages)")
    if not venv_python(lay.venv, windows).is_file():
        out.append(f"{lay.venv} (vault schema)")
    return out


def map_command(py: Path, workdir: Path, watch: int = 0) -> list[str]:
    cmd = [str(py), "-m", "ehl_schema.cli", "map", "--workdir", str(workdir), "--profile", PROFILE]
    return cmd + (["--watch", str(watch)] if watch else [])


def jobs(lay: Layout, workdir: Path, windows: bool = IS_WINDOWS) -> list[tuple[str, list[str], Path]]:
    py = venv_python(lay.venv, windows)
    return [("Rowboat", ["npm", "run", "dev"], lay.app),
            ("vault map", map_command(py, workdir, MAP_SECONDS), lay.schema)]


def _shell(cmd: list[str], windows: bool) -> bool:
    return windows and cmd[0] in ("npm", "pnpm")  # .cmd launchers on Windows


def stop(proc: subprocess.Popen, windows: bool = IS_WINDOWS) -> None:
    if proc.poll() is not None:
        return
    if windows:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.terminate()


def install(lay: Layout, windows: bool = IS_WINDOWS) -> int:
    for cmd, cwd in install_steps(lay, windows):
        log.info("running in %s: %s", cwd, " ".join(cmd))
        if subprocess.run(cmd, cwd=cwd, shell=_shell(cmd, windows)).returncode != 0:
            log.error("install step failed: %s", " ".join(cmd))
            return 1
    return 0


def start(lay: Layout, workdir: Path, windows: bool = IS_WINDOWS) -> int:
    gaps = missing(lay, windows)
    if gaps:
        log.error("not installed yet - run start_desktop.py --install first. Missing:\n- %s", "\n- ".join(gaps))
        return 2
    if subprocess.run(map_command(venv_python(lay.venv, windows), workdir), cwd=lay.schema).returncode != 0:
        log.warning("vault map failed once; Rowboat starts anyway, the refresh retries every %d s", MAP_SECONDS)
    env = {**os.environ, "ROWBOAT_WORKDIR": str(workdir)}
    procs = []
    for name, cmd, cwd in jobs(lay, workdir, windows):
        log.info("starting %s: %s", name, " ".join(cmd))
        procs.append(subprocess.Popen(cmd, cwd=cwd, env=env, shell=_shell(cmd, windows)))
    log.info("Rowboat opens after its first build (a few minutes). Ctrl+C stops everything.")
    try:
        procs[0].wait()
    except KeyboardInterrupt:
        pass
    finally:
        for proc in procs:
            stop(proc, windows)
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--install", action="store_true", help="build harbor, install Rowboat and the schema venv")
    ap.add_argument("--workdir", type=Path, default=Path.home() / ".rowboat", help="Rowboat data folder")
    args = ap.parse_args(argv)
    lay = layout()
    if args.install:
        return install(lay)
    return start(lay, args.workdir.expanduser())


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests**

Run: `C:/Users/User/Desktop/Vibemind_V1/.venv/Scripts/python.exe -m pytest -q spaces/rowboat/tests/test_start_desktop.py spaces/rowboat/tests/test_sync_desktop.py -p no:cacheprovider`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add spaces/rowboat/scripts/start_desktop.py spaces/rowboat/tests/test_start_desktop.py
ENTIRE_TEST_TTY=0 git commit -m "feat(rowboat): start_desktop.py starts the desktop app on ~/.rowboat with the vault map refresh

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Real sync, install and tests

- [ ] **Step 1: Sync from the local clones**

```bash
cd C:/Users/User/ClaudeWork/wt-rowboat-desktop
C:/Users/User/Desktop/Vibemind_V1/.venv/Scripts/python.exe spaces/rowboat/scripts/sync_desktop.py \
  --fork C:/Users/User/Desktop/rowboat --fork-ref vibemind \
  --ehl C:/Users/User/Desktop/ehl-munich-2026 --ehl-ref feat/vault-schema
git status --short | cut -c4- | cut -d/ -f1-5 | sort | uniq -c
```

Expected: "synced …"; changes only under `spaces/rowboat/rowboat/apps/x`, `spaces/rowboat/rowboat/apps/harbor`,
`spaces/rowboat/schema` and `spaces/rowboat/rowboat/UPSTREAM.md`. `git diff --stat -- spaces/rowboat/rowboat/apps/rowboat spaces/rowboat/rowboat/packages` is empty.

- [ ] **Step 2: Install and run the tests in the synced copy**

```bash
C:/Users/User/Desktop/Vibemind_V1/.venv/Scripts/python.exe spaces/rowboat/scripts/start_desktop.py --install
cd spaces/rowboat/rowboat/apps/x/apps/renderer
npx vitest run src/lib/graph-hierarchy.test.ts src/extensions/video-link.test.ts src/components/settings/plugin-settings.test.tsx src/lib/rowboat-plugin-api.test.ts
npx tsc -b
cd ../../../rowboat && npm run test:plugins
```

Expected: install ok; renderer tests pass; tsc clean; the web app's `test:plugins` passes (if `apps/rowboat` has
no `node_modules`, install it with its own package manager first, `npm ci`, and ledger that). The schema tests:
`spaces/rowboat/schema/.venv/Scripts/python.exe -m pytest -q spaces/rowboat/schema` (needs `pytest` in that venv:
`pip install pytest` there) → 95 passed.

- [ ] **Step 3: Commit the sync**

```bash
cd C:/Users/User/ClaudeWork/wt-rowboat-desktop
git add spaces/rowboat/rowboat/apps/x spaces/rowboat/rowboat/apps/harbor spaces/rowboat/schema spaces/rowboat/rowboat/UPSTREAM.md
ENTIRE_TEST_TTY=0 git commit -m "chore(rowboat): desktop app from Flissel/rowboat vibemind@<short sha>, schema from ehl-munich-2026@<short sha>

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(Fill in the two short SHAs from `UPSTREAM.md`.)

---

### Task 7: Real start, check, docs

- [ ] **Step 1: Ask before stopping the running Rowboat**

A Rowboat dev instance (from the EHL repo, on `~/.rowboat`) is probably running. **Ask the user** before stopping it.

- [ ] **Step 2: Start from vibemind-os**

Run in the background: `C:/Users/User/Desktop/Vibemind_V1/.venv/Scripts/python.exe spaces/rowboat/scripts/start_desktop.py`
Wait for the Electron process; ask the user to check **Settings → Plugins** (tab present; signed in → catalog or a
clear "unavailable"; signed out → "signed out") and **Brain → Graph** (3D VibeMind hierarchy).

- [ ] **Step 3: Docs**

Add a short section to `spaces/rowboat/README.md` (create it if missing): "Desktop app" with the two
`start_desktop.py` commands, the `sync_desktop.py` command and "never edit `rowboat/apps/x`, `rowboat/apps/harbor`
or `schema/` by hand – see `rowboat/UPSTREAM.md`". Commit `docs(rowboat): desktop app start and sync`.

- [ ] **Step 4: Push the branches (ask first)**

Ask the user, then push `vibemind` to `Flissel/rowboat` and `feat/rowboat-desktop-update` to `origin`
(`Flissel/vibemind-os`). Update the board row (if the claim was posted) to "ausgeliefert auf Branch …, Merge offen".
