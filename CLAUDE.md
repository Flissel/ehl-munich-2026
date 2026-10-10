# CLAUDE.md – EHL Munich 2026: Rowboat Live Demo

Read this at the start of every session in this repo. Several Claude Code sessions (one per team
member, on different PCs) work in parallel. **Fresh PC? Do `SETUP.md` first.**

## Roles

- **Orchestrator: Flissel.** Owns `main` (here) and `ehl` (in the Rowboat fork), reviews and merges
  every pull request. Sessions never merge PRs themselves and never push to `main` or `ehl`.
- **WP sessions:** one per team member and work package; work on their WP branch, open PRs.

## Project in one paragraph

Rowboat Desktop is the product we demo (Oct 11, 6-min pitch). We run it **from source in dev mode**
(fork `Flissel/rowboat`, branch `ehl`) so we can adapt it. Sales-Claw (companies) and Marketing
(newsletters, images) are data sources and worker agents. A bridge writes their data as Markdown
notes into Rowboat's vault so its knowledge graph shows the cluster; a local Qdrant index adds
semantic search via MCP; chat tools let the Rowboat agent talk to the Sales and Marketing agents.
Products are the machines F70, G60, G68, G70 from `Dataset/`.
Full design: `docs/superpowers/specs/2026-10-10-rowboat-ehl-space-design.md` (on every `feat/ehl-*`
branch). **§12 lists the shared contracts – do not change them on your own.**

## Repos and branches

| Repo | Branch | Rules |
|---|---|---|
| `Flissel/ehl-munich-2026` | `main` | protected: PR + orchestrator review only |
| | `feat/ehl-*` (one per WP) | your work; push freely; PR into `main` |
| | `board` | **WORKBOARD.md lives here**; every session pushes board updates directly |
| `Flissel/rowboat` (team fork of `rowboatlabs/rowboat`) | `ehl` | protected; our Rowboat base, pinned to upstream `72e9d8c`. Nobody but the orchestrator pushes here |
| `<your-login>/rowboat` (**your own fork of `Flissel/rowboat`**) | `ehl/<wp>-<topic>` | your Rowboat changes; PR from your fork into `Flissel/rowboat:ehl` |

**Rowboat remotes in your clone:** `origin` = your fork (you push here), `upstream` = `Flissel/rowboat`
(you only fetch from here). Never add `rowboatlabs/rowboat` as a push target.

## Work packages

| WP | Branch | Folder | Spec (on that branch) |
|---|---|---|---|
| WP1 Demo content, Rowboat setup, rehearsal | `feat/ehl-demo-content` | `demo/` | `docs/superpowers/specs/2026-10-10-ehl-wp1-demo-content-design.md` |
| WP2 Bridge | `feat/ehl-bridge` | `bridge/` | `docs/superpowers/specs/2026-10-10-ehl-wp2-bridge-design.md` |
| WP3 Semantic search | `feat/ehl-search` | `search/` | `docs/superpowers/specs/2026-10-10-ehl-wp3-search-design.md` |
| WP4 Agent chat tools | `feat/ehl-agent-chat` | `agents-mcp/` | `docs/superpowers/specs/2026-10-10-ehl-wp4-agent-chat-design.md` |

Your WP is the one whose branch you are on. If you are on `main` or unsure, ask the user which WP.
Any WP may change Rowboat itself if its package needs it – in **your own fork**, on
`ehl/<wp>-<topic>` branched from `upstream/ehl`, then a PR into `Flissel/rowboat:ehl`.

## Your PC vs. the demo PC (spec D11)

Every team member runs Rowboat (dev mode, from the fork) on their own PC to test in their own graph:
repo notes via WP1's installer, fake companies via `bridge --fake`, local Qdrant + `ehl-search`.
Until WP1/WP2 deliver these, use a test vault (`EHL_VAULT` pointing to a temp folder). The
Sales/Marketing agents (`ehl-agents`) and real company data exist **only on the demo PC**. Never
commit real company notes or a real vault to git.

## Session start (do this first, every time)

1. `git fetch origin` and read the live board: `git show origin/board:WORKBOARD.md`.
2. Find your WP row. If another session holds an **active claim** on it (updated < 2 h ago),
   do not take it over – ask the user.
3. **Claim** it on the board (see "Updating the board"): your name, status, timestamp.
4. Merge the latest `main` into your WP branch (`git merge origin/main`).
5. Read the parent spec (§12 contracts!) and your WP spec. Check the board's **Handoffs** and
   **Open questions** for anything addressed to your WP.
6. No plan yet? Write it with the `superpowers:writing-plans` skill to
   `docs/superpowers/plans/2026-10-10-ehl-wpN-<name>-plan.md` on your branch, commit, push,
   link it in your board row, and **open a draft PR** into `main` so the orchestrator can follow.
7. Execute the plan. Start with the time-boxed "first task" from your WP spec.

## Updating the board

Update `WORKBOARD.md` when you claim, finish a plan step group, hit a blocker, hand something to
another WP, open a PR, or end the session. Keep entries short (one line each).

Use a separate worktree for the `board` branch so you never switch your WP branch:

```bash
git worktree add ../ehl-munich-2026-board board   # once per PC; skip if it exists
cd ../ehl-munich-2026-board
git pull --rebase origin board
# edit WORKBOARD.md: your row + one line at the top of the Log
git add WORKBOARD.md
git commit -m "chore(board): WPn <what changed>"
git push origin board    # rejected? git pull --rebase origin board, re-check your edit, push again
```

Only `WORKBOARD.md` is committed on `board`. Never `--force`.

## Pull requests

- Open a PR from your WP branch into `main`:
  `gh pr create --base main --draft --title "WPn: <what>" --body "<summary, tests run, open points>"`.
- Rowboat changes: keep your branch current (`git fetch upstream && git rebase upstream/ehl`), push to
  your fork (`git push -u origin ehl/<wp>-<topic>`), then
  `gh pr create --repo Flissel/rowboat --base ehl --head <your-login>:ehl/<wp>-<topic> --draft --title "WPn: <what>"`.
- Mark it ready (`gh pr ready`) when tests pass; put the PR link in your board row.
- Keep PRs small and per WP; the orchestrator reviews and merges. Address review comments on your
  branch; do not merge `main` into another WP's branch.

## Working rules

- Touch only your WP folder (and your WP spec/plan). Need something from another WP? Add a line
  under **Handoffs** on the board instead of editing their folder.
- Contract changes (spec §12): add a line under **Contract change requests** on the board; the
  orchestrator decides and updates the parent spec.
- Python 3.12, own `pyproject.toml` per folder, pytest, `logging` (no `print`), secrets only in
  `.env` (gitignored) with a `.env.example`. Scripts must run on **Windows and macOS**.
- Data (orchestrator decision 2026-10-11): `Dataset/` is **dummy data**. It and everything derived
  from it (comments incl. names, `outputs/` chunks, notes) may be committed. OpenAI embeddings are
  allowed (also committed under `outputs/`). **Real** data stays out of git (public repo): real
  Sales-Claw contacts/companies, team members' private data, Rowboat vaults (`~/.rowboat*`); private
  leads are skipped (spec D8).
- Never send, approve or schedule anything in Sales-Claw or Marketing from our code (spec D7).
- Machine-wide changes on the orchestrator's machines (mini PC `vibemind-offload-1`, OpenClaw config,
  Docker stacks, secrets): ask the orchestrator first.
- Conventional commits (`feat:`, `fix:`, `docs:`, `chore(board):`). Never delete branches or
  force-push.
- Verify before claiming done (tests, a quick repro); say so if you could not verify.

## Known quirk: Entire hook hangs

Where the Entire CLI is installed, its `prepare-commit-msg` hook can hang commits (not skipped by
`--no-verify`). If a commit hangs, stop it and ask the user whether to commit with
`git -c core.hooksPath=/dev/null commit …` (the commit then has no Entire checkpoint link).
Without Entire installed, the repo's `.claude/settings.json` hooks are no-ops.
