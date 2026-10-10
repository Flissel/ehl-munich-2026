# CLAUDE.md – EHL Munich 2026: Rowboat Live Demo

Read this at the start of every session in this repo. It tells you which work package you are on,
where the shared state lives, and how to keep it up to date. Several Claude Code sessions (one per
team member) work in parallel; **`WORKBOARD.md` on `main` is the single source of truth.**

## Project in one paragraph

Rowboat Desktop is the product we demo (Oct 11, 6-min pitch). Sales-Claw (companies) and Marketing
(newsletters, images) are data sources and worker agents. A bridge writes their data as Markdown
notes into Rowboat's vault so its knowledge graph shows the cluster; a local Qdrant index adds
semantic search via MCP; chat tools let the Rowboat agent talk to the Sales and Marketing agents.
Full design: `docs/superpowers/specs/2026-10-10-rowboat-ehl-space-design.md` (on every `feat/ehl-*`
branch). **§12 of that spec lists the shared contracts – do not change them on your own.**

## Work packages

| WP | Branch | Folder | Spec (on that branch) |
|---|---|---|---|
| WP1 Demo content, Rowboat setup, rehearsal | `feat/ehl-demo-content` | `demo/` | `docs/superpowers/specs/2026-10-10-ehl-wp1-demo-content-design.md` |
| WP2 Bridge | `feat/ehl-bridge` | `bridge/` | `docs/superpowers/specs/2026-10-10-ehl-wp2-bridge-design.md` |
| WP3 Semantic search | `feat/ehl-search` | `search/` | `docs/superpowers/specs/2026-10-10-ehl-wp3-search-design.md` |
| WP4 Agent chat tools | `feat/ehl-agent-chat` | `agents-mcp/` | `docs/superpowers/specs/2026-10-10-ehl-wp4-agent-chat-design.md` |

Your WP is the one whose branch you are on. If you are on `main` or unsure, ask the user which WP.

## Your PC vs. the demo PC (spec D11)

Every team member runs Rowboat Desktop on their own PC to test in their own graph: repo notes via
`demo/install.ps1`, fake companies via `bridge --fake`, local Qdrant + `ehl-search`. Until WP1/WP2
deliver these, use a test vault (`EHL_VAULT` pointing to a temp folder). The Sales/Marketing agents
(`ehl-agents`) and real company data exist **only on the demo PC** (`install.ps1 -Demo`). Never commit
real company notes or a real vault to git.

## Session start (do this first, every time)

1. `git fetch origin` and read the live board: `git show origin/main:WORKBOARD.md`.
2. Find your WP row. If another session holds an **active claim** on it (updated < 2 h ago),
   do not take it over – ask the user.
3. **Claim** it on the board (see "Updating the board"): your name/session, status, timestamp.
4. Merge the latest `main` into your branch (`git merge origin/main`) so you have the current
   CLAUDE.md, board and `Dataset/`.
5. Read the parent spec (§12 contracts!) and your WP spec. Check the board's **Handoffs** and
   **Open questions** for anything addressed to your WP.
6. No plan yet? Write it with the `superpowers:writing-plans` skill to
   `docs/superpowers/plans/2026-10-10-ehl-wpN-<name>-plan.md` on your branch, commit, push,
   and link it in your board row. Each WP has its own plan; do not plan other WPs.
7. Execute the plan. Start with the time-boxed "first task" from your WP spec.

## Updating the board

Update `WORKBOARD.md` when you claim, finish a plan step group, hit a blocker, hand something to
another WP, or end the session. Keep entries short (one line each).

Use a separate worktree for `main` so you never switch your WP branch:

```bash
git worktree add ../ehl-munich-2026-board main   # once per machine; skip if it exists
cd ../ehl-munich-2026-board
git pull --rebase origin main
# edit WORKBOARD.md: your row + one line at the top of the Log
git add WORKBOARD.md
git commit -m "chore(board): WPn <what changed>"
git push origin main     # rejected? git pull --rebase origin main, re-check your edit, push again
```

**Rules for `main`:** the only thing sessions commit directly to `main` is `WORKBOARD.md`
(and this file, when the user asks). Never `--force`. Everything else goes to your WP branch.

## Working rules

- Touch only your WP folder (and your WP spec/plan). Need something from another WP? Add a line
  under **Handoffs** on the board instead of editing their folder.
- Contract changes (spec §12): add a line under **Contract change requests**, wait for the affected
  WP owners to agree, then the user updates the parent spec.
- Python 3.12, own `pyproject.toml` per folder, pytest, `logging` (no `print`), secrets only in
  `.env` (gitignored) with a `.env.example`.
- Privacy: no customer individuals, emails or phone numbers in the vault or Qdrant; private leads
  are skipped (spec D8).
- Never send, approve or schedule anything in Sales-Claw or Marketing from our code (spec D7).
- Machine-wide changes (mini PC `vibemind-offload-1`, OpenClaw config, Docker stacks, secrets):
  claim first in `C:\Users\User\Desktop\secondbrain\00_Meta\002_Koordination_Live.md` and commit
  the claim.
- Conventional commits (`feat:`, `fix:`, `docs:`, `chore(board):`), feature branches, push your WP
  branch regularly. Never delete branches or force-push without asking.
- Verify before claiming done (tests, a quick repro); say so if you could not verify.

## Known quirk: Entire hook hangs

On some machines Entire's `prepare-commit-msg` hook hangs commits (it is not skipped by
`--no-verify`). If a commit hangs, stop it and ask the user whether to commit with
`git -c core.hooksPath=/dev/null commit …` (the commit then has no Entire checkpoint link).
