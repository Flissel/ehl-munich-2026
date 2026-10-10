# SETUP – get a team PC ready (for Claude Code)

## For humans: paste this into Claude Code

> Set up this PC for the EHL hackathon, work package **WP<n>**: read
> https://github.com/Flissel/ehl-munich-2026/blob/main/SETUP.md and follow the "Quick path".

That's all. Claude Code installs what is missing (after asking you), clones everything, builds
Rowboat and opens the Rowboat desktop app in dev mode.

## Quick path (for Claude Code)

1. Ask the user for their WP (1–4, table in `CLAUDE.md`). Make sure `git`, `gh` and Python 3.12 exist
   and `gh auth status` is logged in (help the user with `gh auth login` if not).
2. Clone the team repo and run the setup script:

   ```bash
   gh repo clone Flissel/ehl-munich-2026 ~/ehl/ehl-munich-2026
   python3.12 ~/ehl/ehl-munich-2026/scripts/setup_pc.py --wp <n>   # Windows: py -3.12 …
   ```

3. Exit code `2` = prerequisites missing: the script lists them with install hints. Ask the user,
   install them (table in section 1), re-run. Exit code `1` = a step failed: read the message, fix,
   re-run (the script is idempotent).
4. When the script starts Rowboat it keeps running (dev server). Run it in the background or a
   separate terminal; the Rowboat window opens after the first build. In Rowboat, set a model
   provider with the user's **own** API key.
5. Report the verify checklist (section 5), then continue with "Session start" in `CLAUDE.md`.

The sections below are the manual equivalent – use them if the script fails.

Works on macOS and Windows (Git Bash or PowerShell). Ask the user before installing anything.

## 0. Who am I?

Ask the user for their **WP** (1–4, see the table in `CLAUDE.md`) and their GitHub login. The user
needs write access to `Flissel/ehl-munich-2026` (ask Flissel if missing). For Rowboat the user works
in **their own fork** of `Flissel/rowboat` (created in step 2) – no write access to `Flissel/rowboat`
is needed.

## 1. Requirements and prerequisites

**Machine and accounts** (check before starting):

| Requirement | Detail |
|---|---|
| OS | macOS (Apple Silicon or Intel) or Windows 10/11 x64 |
| Disk | ~5 GB free (Rowboat installs ~2,300 npm packages + Electron; Qdrant + embedding model) |
| RAM | 8 GB minimum, 16 GB recommended (Rowboat dev build + Docker) |
| Network | Fast enough for ~1 GB of downloads on first setup |
| GitHub | Account with write access to `Flissel/ehl-munich-2026` (ask Flissel); fork rights for `Flissel/rowboat` (any account) |
| LLM provider | Your **own** API key for Rowboat's model provider (set in Rowboat's settings, never committed) |
| Claude Code | Installed and logged in; plugin `superpowers` from the official marketplace (`/plugin`) |

**Tools** (`python3.12 scripts/setup_pc.py --check` checks them all):

| Tool | Version | Check | Install hint |
|---|---|---|---|
| git | any recent | `git --version` | macOS: `xcode-select --install` · Windows: Git for Windows |
| GitHub CLI | any recent | `gh --version`, then `gh auth status` | `brew install gh` · `winget install GitHub.cli`; then `gh auth login` |
| Node.js | **22 LTS or 24.15+** (not 24.0–24.14: 24.4 crashes `pnpm install` with "invalid array length") | `node --version` | nodejs.org, nvm/fnm, `brew install node@22` · `winget install OpenJS.NodeJS.LTS` |
| pnpm | **10** | `pnpm --version` | `corepack enable && corepack prepare pnpm@10 --activate` |
| Python | **3.12** | `python3.12 --version` / `py -3.12 --version` | python.org or `brew install python@3.12` |
| Docker | Desktop running | `docker info` | Docker Desktop (needed for Qdrant) |

Entire CLI is optional; without it the repo's Claude hooks do nothing.

**Known issues (tested 2026-10-10 on Windows):**
- `npm run dev:sandbox` fails on Windows (`spawn npm ENOENT`, upstream bug). Use `npm run dev` with
  `ROWBOAT_WORKDIR` instead (the setup script does this).
- If you already use Rowboat (`~/.rowboat` exists), the script runs the dev app in `~/.rowboat-ehl`
  so your own data is untouched; your vault is then `~/.rowboat-ehl/knowledge` (set `EHL_VAULT`).

## 2. Clone side by side

Pick a base folder (e.g. `~/ehl`). Clone this repo, then **fork** `Flissel/rowboat` into your own
account and clone your fork next to it:

```bash
mkdir -p ~/ehl && cd ~/ehl
gh repo clone Flissel/ehl-munich-2026
gh repo fork Flissel/rowboat --clone        # creates <your-login>/rowboat incl. branch ehl
cd rowboat
git remote -v                               # origin = <your-login>/rowboat, upstream = Flissel/rowboat
git fetch upstream ehl
git switch -c ehl upstream/ehl              # local ehl tracks the team base
```

Result: `~/ehl/ehl-munich-2026` and `~/ehl/rowboat` (your fork, on `ehl`, `upstream` = `Flissel/rowboat`).
Already have a fork? Clone it instead, then `git remote add upstream https://github.com/Flissel/rowboat.git`.
Never push to `upstream`; push your branches to `origin` and open PRs (see `CLAUDE.md`).

## 3. Your WP branch and the board worktree

```bash
cd ~/ehl/ehl-munich-2026
git switch feat/ehl-<wp-branch>                 # see CLAUDE.md table
git worktree add ../ehl-munich-2026-board board
```

## 4. Rowboat in dev mode (from the fork)

```bash
cd ~/ehl/rowboat/apps/harbor
pnpm install --frozen-lockfile && pnpm -r build  # apps/x links Harbor packages
cd ../x
pnpm install --frozen-lockfile
npm run dev                                       # Electron app + renderer (ports 3220/3210/5173)
```

- First start: configure a model provider in Rowboat's settings with **your own** API key. Never
  commit keys.
- Vault: `~/.rowboat/knowledge/` (set `EHL_VAULT` to it once you work with real notes; until then use
  a temp folder as test vault).
- Already use Rowboat (`~/.rowboat` exists)? Keep your data separate: copy `~/.rowboat/config` to
  `~/.rowboat-ehl/config` (without `server.json`) and start with
  `ROWBOAT_WORKDIR=~/.rowboat-ehl npm run dev` (PowerShell: `$env:ROWBOAT_WORKDIR="$HOME\.rowboat-ehl"`).
  Your vault is then `~/.rowboat-ehl/knowledge`. Don't use `npm run dev:sandbox` on Windows (broken).
- Changing Rowboat: `git fetch upstream && git switch -c ehl/<wp>-<topic> upstream/ehl` in
  `~/ehl/rowboat`, commit, `git push -u origin ehl/<wp>-<topic>`, then a PR from your fork into
  `Flissel/rowboat:ehl` (command in `CLAUDE.md` → Pull requests).

## 5. Verify

- [ ] `gh auth status` ok, both repos cloned, WP branch checked out, board worktree on `board`
- [ ] `~/ehl/rowboat`: `origin` = your own fork, `upstream` = `Flissel/rowboat`, local `ehl` tracks `upstream/ehl`
- [ ] Rowboat dev window opens and shows the (empty or test) vault
- [ ] `docker info` ok
- [ ] `git show origin/board:WORKBOARD.md` prints the board

Report the checklist result to the user, then continue with **"Session start"** in `CLAUDE.md`.

## 6. Later, when WP1/WP2 deliver

- WP1's installer copies the repo notes (products F70/G60/G68/G70, topics, team) into your vault and
  registers `ehl-search` in Rowboat's `mcp.json`.
- `bridge --fake` (WP2) fills your vault with fake companies.
- `ehl-agents` (Sales/Marketing chat) is **only** set up on the demo PC.
