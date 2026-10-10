# SETUP – get a team PC ready (for Claude Code)

Written so a Claude Code session can follow it step by step. Tell your session:
**"Read SETUP.md in Flissel/ehl-munich-2026 and set up this PC for WP<n>."**
Works on macOS and Windows (Git Bash or PowerShell). Ask the user before installing anything.

## 0. Who am I?

Ask the user for their **WP** (1–4, see the table in `CLAUDE.md`) and their GitHub login. The user
needs write access to `Flissel/ehl-munich-2026` (ask Flissel if missing). For Rowboat the user works
in **their own fork** of `Flissel/rowboat` (created in step 2) – no write access to `Flissel/rowboat`
is needed.

## 1. Prerequisites (check, install only what is missing)

| Tool | Version | Check | Install hint |
|---|---|---|---|
| git | any recent | `git --version` | macOS: `xcode-select --install` · Windows: Git for Windows |
| GitHub CLI | any recent | `gh --version`, then `gh auth status` | `brew install gh` · `winget install GitHub.cli`; then `gh auth login` |
| Node.js | **22 or 24** | `node --version` | nvm / fnm, or nodejs.org LTS |
| pnpm | **10** | `pnpm --version` | `corepack enable && corepack prepare pnpm@10 --activate` |
| Python | **3.12** | `python3 --version` / `py -3.12 --version` | python.org or `brew install python@3.12` |
| Docker | Desktop running | `docker info` | Docker Desktop (needed for Qdrant) |
| Claude Code plugin | superpowers | `/plugin` list | install `superpowers` from the official marketplace via `/plugin` |

Entire CLI is optional; without it the repo's Claude hooks do nothing.

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
- Already have the official Rowboat app installed? Use `npm run dev:sandbox -- --seed-config`
  instead; it runs in `~/.rowboat-dev/<id>`, so point `EHL_VAULT` at that instance's `knowledge/`.
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
