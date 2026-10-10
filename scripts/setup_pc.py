"""One-command setup of a team PC for the EHL Rowboat demo (Windows and macOS).

Run by a Claude Code session (see SETUP.md):

    python scripts/setup_pc.py --wp 2            # team member, work package 2
    python scripts/setup_pc.py --wp 1 --no-start # set up, don't launch Rowboat
    python scripts/setup_pc.py --check           # only check prerequisites

What it does, idempotently (safe to re-run):
  1. checks git, gh (logged in), node 22/24, pnpm 10, python 3.12, docker
  2. clones Flissel/ehl-munich-2026 into the base dir, switches to the WP branch,
     adds the board worktree on branch `board`
  3. Rowboat: forks Flissel/rowboat into the user's account and clones the fork
     (the orchestrator clones Flissel/rowboat directly), sets `upstream`,
     local `ehl` tracks `upstream/ehl`
  4. builds Rowboat: apps/harbor (pnpm install + build), apps/x (pnpm install)
  5. starts the Rowboat desktop app in dev mode (sandboxed if ~/.rowboat exists)

Only the standard library is used, so it runs before anything is installed.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("setup_pc")

TEAM_REPO = "Flissel/ehl-munich-2026"
ROWBOAT_TEAM_FORK = "Flissel/rowboat"
ROWBOAT_BASE_BRANCH = "ehl"
ORCHESTRATOR = "Flissel"
WP_BRANCHES = {
    1: "feat/ehl-demo-content",
    2: "feat/ehl-bridge",
    3: "feat/ehl-search",
    4: "feat/ehl-agent-chat",
}
IS_WINDOWS = os.name == "nt"


class SetupError(Exception):
    """A step failed; the message says what to do."""


def run(cmd: list[str], cwd: Path | None = None, check: bool = True,
        capture: bool = False) -> subprocess.CompletedProcess:
    log.info("$ %s%s", " ".join(cmd), f"   (in {cwd})" if cwd else "")
    # On Windows npm/pnpm are .cmd shims and need the shell to resolve them.
    result = subprocess.run(cmd, cwd=cwd, text=True, shell=IS_WINDOWS,
                            capture_output=capture)
    if check and result.returncode != 0:
        detail = (result.stderr or "").strip()[-500:] if capture else ""
        raise SetupError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{detail}")
    return result


def output(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, text=True, capture_output=True, shell=IS_WINDOWS,
                              timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def major(version: str) -> int | None:
    match = re.search(r"(\d+)\.", version)
    return int(match.group(1)) if match else None


def check_prerequisites() -> list[str]:
    """Return a list of human-readable problems; empty means all good."""
    problems = []
    if not shutil.which("git"):
        problems.append("git missing - macOS: `xcode-select --install`, Windows: Git for Windows")
    if not shutil.which("gh"):
        problems.append("GitHub CLI missing - `brew install gh` / `winget install GitHub.cli`")
    elif subprocess.run(["gh", "auth", "status"], capture_output=True,
                        shell=IS_WINDOWS).returncode != 0:
        problems.append("GitHub CLI not logged in - run `gh auth login`")
    node_version = output(["node", "--version"]).lstrip("v")
    if not node_ok(node_version):
        problems.append(f"Node.js 22 LTS or 24.15+ needed (found: {node_version or 'none'}; "
                        "24.4 crashes `pnpm install` with 'invalid array length') - "
                        "nodejs.org, nvm/fnm, or `brew install node@22`")
    pnpm = major(output(["pnpm", "--version"]) + ".")
    if pnpm != 10:
        problems.append(f"pnpm 10 needed (found: {pnpm or 'none'}) - "
                        "`corepack enable && corepack prepare pnpm@10 --activate`")
    if not python312():
        problems.append("Python 3.12 missing - python.org or `brew install python@3.12`")
    if not shutil.which("docker") or subprocess.run(
            ["docker", "info"], capture_output=True, shell=IS_WINDOWS).returncode != 0:
        problems.append("Docker not running - start Docker Desktop (needed for Qdrant)")
    return problems


def node_ok(version: str) -> bool:
    """Node 22.x, or 24.15+ (Rowboat's own Windows build uses 24.15.0)."""
    parts = re.findall(r"\d+", version)
    if len(parts) < 2:
        return False
    major_v, minor_v = int(parts[0]), int(parts[1])
    return major_v == 22 or (major_v == 24 and minor_v >= 15)


def python312() -> str | None:
    for cmd in (["py", "-3.12", "--version"], ["python3.12", "--version"],
                ["python3", "--version"], ["python", "--version"]):
        if output(cmd).startswith("Python 3.12"):
            return cmd[0]
    return None


def gh_login() -> str:
    login = output(["gh", "api", "user", "--jq", ".login"])
    if not login:
        raise SetupError("could not read your GitHub login - run `gh auth login`")
    return login


def setup_team_repo(base: Path, wp: int | None) -> Path:
    repo = base / "ehl-munich-2026"
    if not (repo / ".git").exists():
        run(["gh", "repo", "clone", TEAM_REPO, str(repo)])
    run(["git", "fetch", "origin"], cwd=repo)
    if wp:
        branch = WP_BRANCHES[wp]
        current = output(["git", "-C", str(repo), "branch", "--show-current"])
        if current != branch:
            run(["git", "switch", branch], cwd=repo)
        run(["git", "pull", "--ff-only"], cwd=repo, check=False)
    board = base / "ehl-munich-2026-board"
    if not board.exists():
        run(["git", "worktree", "add", str(board), "board"], cwd=repo)
    return repo


def setup_rowboat(base: Path, login: str) -> Path:
    rowboat = base / "rowboat"
    if not (rowboat / ".git").exists():
        if login.lower() == ORCHESTRATOR.lower():
            run(["gh", "repo", "clone", ROWBOAT_TEAM_FORK, str(rowboat),
                 "--", "--branch", ROWBOAT_BASE_BRANCH])
        else:
            # Creates <login>/rowboat (all branches) if missing, clones it and sets `upstream`.
            run(["gh", "repo", "fork", ROWBOAT_TEAM_FORK, "--clone", "--remote"], cwd=base)
    remotes = output(["git", "-C", str(rowboat), "remote"]).split()
    if login.lower() != ORCHESTRATOR.lower() and "upstream" not in remotes:
        run(["git", "remote", "add", "upstream",
             f"https://github.com/{ROWBOAT_TEAM_FORK}.git"], cwd=rowboat)
    base_remote = "origin" if login.lower() == ORCHESTRATOR.lower() else "upstream"
    run(["git", "fetch", base_remote, ROWBOAT_BASE_BRANCH], cwd=rowboat)
    current = output(["git", "-C", str(rowboat), "branch", "--show-current"])
    if current != ROWBOAT_BASE_BRANCH:
        exists = output(["git", "-C", str(rowboat), "branch", "--list", ROWBOAT_BASE_BRANCH])
        if exists:
            run(["git", "switch", ROWBOAT_BASE_BRANCH], cwd=rowboat)
        else:
            run(["git", "switch", "-c", ROWBOAT_BASE_BRANCH,
                 f"{base_remote}/{ROWBOAT_BASE_BRANCH}"], cwd=rowboat)
    return rowboat


def build_rowboat(rowboat: Path) -> None:
    harbor = rowboat / "apps" / "harbor"
    run(["pnpm", "install", "--frozen-lockfile"], cwd=harbor)
    run(["pnpm", "-r", "build"], cwd=harbor)
    run(["pnpm", "install", "--frozen-lockfile"], cwd=rowboat / "apps" / "x")


def rowboat_workdir() -> Path:
    """Where the dev app keeps its data. A user who already runs Rowboat keeps ~/.rowboat
    untouched; the dev app then uses ~/.rowboat-ehl (`npm run dev:sandbox` is broken on
    Windows: it spawns `npm` without a shell)."""
    own = Path.home() / ".rowboat"
    return Path.home() / ".rowboat-ehl" if own.exists() else own


def start_rowboat(rowboat: Path) -> None:
    app = rowboat / "apps" / "x"
    workdir = rowboat_workdir()
    env = dict(os.environ)
    if workdir != Path.home() / ".rowboat":
        seed = Path.home() / ".rowboat" / "config"
        if seed.exists() and not (workdir / "config").exists():
            # Same idea as dev:sandbox --seed-config: reuse providers, minus server.json.
            shutil.copytree(seed, workdir / "config",
                            ignore=shutil.ignore_patterns("server.json"))
        env["ROWBOAT_WORKDIR"] = str(workdir)
    log.info("Rowboat data: %s  ->  vault: %s  (set EHL_VAULT to this)", workdir,
             workdir / "knowledge")
    log.info("Starting Rowboat (npm run dev); the window opens after the first build "
             "(a few minutes). Stop with Ctrl+C.")
    subprocess.run(["npm", "run", "dev"], cwd=app, env=env, shell=IS_WINDOWS)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--wp", type=int, choices=sorted(WP_BRANCHES),
                        help="your work package (1-4); omit for the orchestrator")
    parser.add_argument("--base", type=Path, default=Path.home() / "ehl",
                        help="folder for both repos (default: ~/ehl)")
    parser.add_argument("--check", action="store_true", help="only check prerequisites")
    parser.add_argument("--no-build", action="store_true", help="skip building Rowboat")
    parser.add_argument("--no-start", action="store_true", help="don't launch Rowboat")
    args = parser.parse_args()

    problems = check_prerequisites()
    if problems:
        log.error("Missing prerequisites:\n- %s", "\n- ".join(problems))
        return 2
    log.info("Prerequisites ok.")
    if args.check:
        return 0

    try:
        args.base.mkdir(parents=True, exist_ok=True)
        login = gh_login()
        repo = setup_team_repo(args.base, args.wp)
        rowboat = setup_rowboat(args.base, login)
        if not args.no_build:
            build_rowboat(rowboat)
        log.info("Done: %s (team repo), %s (Rowboat, branch %s).", repo, rowboat,
                 ROWBOAT_BASE_BRANCH)
        if not args.no_start:
            start_rowboat(rowboat)
    except SetupError as err:
        log.error("Setup stopped: %s", err)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
