"""Install everything the EHL demo needs on a fresh PC (Windows and macOS), then optionally start it.

    python scripts/install.py --check            # only check the system tools
    python scripts/install.py                    # set everything up (except the 3D cars, see below)
    python scripts/install.py --cars "<folder>"  # ... and install the three 3D cars from their zips
    python scripts/install.py --start            # start Rowboat, the RAG backend and both syncs

What it does, idempotently (safe to re-run):
  1. checks Git, Python 3.12, Node 22 / 24.15+, pnpm 10 and Docker (Docker only for the RAG)
  2. clones Rowboat (team fork Flissel/rowboat, branch `ehl` = upstream commit 72e9d8c, unmodified)
     next to this repo and installs its packages (pnpm)
  3. market/.venv: the market MCP server, the research pipeline (research/data/processed) and the
     demo scripts; demo/torque/data/quotes.json (customer comment texts) from Dataset/
  4. the Rowboat knowledge vault: product and topic notes (demo/example-data), brand, model, part,
     assumption and requirement notes; existing notes are never overwritten
  5. Torque as a Rowboat app (<workdir>/apps/torque) and `ehl-market` in <workdir>/config/mcp.json
  6. heat map data for the Concept 3D view (--cars replaces the committed cars with new zips)
  7. RAG: Qdrant (Docker), search/.venv, OPENAI_API_KEY into search/.env, the Qdrant index

The three 3D cars ship with the repo (demo/torque/dist/visu/models/, CC BY-NC-SA 4.0); --cars only
replaces them. Manual: set a model provider with your own key in Rowboat (Settings). For a team member's dev PC with forks
and work-package branches use scripts/setup_pc.py instead (SETUP.md).

Only the standard library is used, so it runs before anything is installed.
"""
from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import setup_pc  # noqa: E402  (shared helpers: run, output, node_ok, python312, build_rowboat, rowboat_workdir)

log = logging.getLogger("install")

ROOT = Path(__file__).resolve().parents[1]
ROWBOAT_URL = "https://github.com/Flissel/rowboat.git"
ROWBOAT_BRANCH = "ehl"
ROWBOAT_COMMIT = "72e9d8c"
RAG_PORT = 8100
IS_WINDOWS = os.name == "nt"
# car id -> (zip name, download page). Keep in sync with demo/visu/prepare_local.py CARS.
CARS = {
    "bmw-x1-2020": ("2020_bmw_x1_xdrive_18d.zip",
                    "https://sketchfab.com/3d-models/2020-bmw-x1-xdrive-18d-4ca3a2247af44e51919074565ed93486"),
    "bmw-x5-2019": ("2019_bmw_x5_xdrive30d.zip",
                    "https://sketchfab.com/3d-models/2019-bmw-x5-xdrive30d-850fb32f984c4630969840fc61f44902"),
    "bmw-x7-2019": ("2019_bmw_x7_xdrive40i.zip",
                    "https://sketchfab.com/3d-models/2019-bmw-x7-xdrive40i-a4b1edf1ec614f06b5d4db7208fe9650"),
}
MODELS = ROOT / "demo" / "torque" / "dist" / "visu" / "models"


class InstallError(Exception):
    """A step failed; the message says what to do."""


# --- pure helpers (tested in scripts/tests/test_install.py) ---------------------------------------

def venv_python(venv: Path, windows: bool = IS_WINDOWS) -> Path:
    return venv / "Scripts" / "python.exe" if windows else venv / "bin" / "python"


def add_mcp_server(config: Path, name: str, entry: dict) -> None:
    """Add or replace one server in Rowboat's mcp.json, keeping every other server."""
    data = json.loads(config.read_text(encoding="utf-8")) if config.exists() else {}
    data.setdefault("mcpServers", {})[name] = entry
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def find_openai_key(root: Path, env: Mapping[str, str]) -> str | None:
    """OPENAI_API_KEY from the environment, else search/.env, else .env (as src/rag_backend reads it)."""
    if env.get("OPENAI_API_KEY", "").strip():
        return env["OPENAI_API_KEY"].strip()
    for path in (root / "search" / ".env", root / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "OPENAI_API_KEY" and value.strip().strip("'\""):
                return value.strip().strip("'\"")
    return None


def copy_example_notes(src: Path, vault: Path) -> int:
    """Copy the product and topic notes (demo/example-data) into the vault; never overwrite a note."""
    copied = 0
    for note in sorted(src.rglob("*.md")):
        dest = vault / note.relative_to(src)
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(note, dest)
        copied += 1
    return copied


def missing_cars(models: Path) -> list[str]:
    return [car for car in CARS if not (models / car / "scene.gltf").is_file()]


# --- steps ----------------------------------------------------------------------------------------

def check_tools(need_docker: bool, need_build: bool) -> list[str]:
    problems = []
    if not shutil.which("git"):
        problems.append("Git missing - Windows: `winget install Git.Git`, macOS: `xcode-select --install`")
    if not setup_pc.python312():
        problems.append("Python 3.12 missing - `winget install Python.Python.3.12` / `brew install python@3.12`")
    node = setup_pc.output(["node", "--version"]).lstrip("v")
    if not node:
        problems.append("Node.js missing - `winget install OpenJS.NodeJS.LTS` / `brew install node@22`")
    elif need_build and not setup_pc.node_ok(node):  # 24.0-24.14 crash `pnpm install`; running is fine
        problems.append(f"Node.js 22 or 24.15+ needed to build Rowboat (found: {node}) - "
                        "`winget install OpenJS.NodeJS.LTS` / `brew install node@22`, or --no-build "
                        "if Rowboat is already built")
    if need_build and setup_pc.major(setup_pc.output(["pnpm", "--version"]) + ".") != 10:
        problems.append("pnpm 10 needed - `corepack enable && corepack prepare pnpm@10 --activate`")
    if need_docker and (not shutil.which("docker") or subprocess.run(
            ["docker", "info"], capture_output=True, shell=IS_WINDOWS).returncode != 0):
        problems.append("Docker not running - install/start Docker Desktop (Qdrant for the RAG), "
                        "or pass --skip-rag")
    return problems


def python312_cmd() -> list[str]:
    exe = setup_pc.python312()
    if not exe:
        raise InstallError("Python 3.12 not found")
    return [exe, "-3.12"] if exe == "py" else [exe]


def setup_rowboat(dest: Path, build: bool) -> Path:
    if not (dest / ".git").exists():
        setup_pc.run(["git", "clone", "--branch", ROWBOAT_BRANCH, ROWBOAT_URL, str(dest)])
    head = setup_pc.output(["git", "-C", str(dest), "rev-parse", "--short", "HEAD"])
    if not head.startswith(ROWBOAT_COMMIT):
        log.warning("Rowboat at %s is on %s, the demo was built on %s", dest, head, ROWBOAT_COMMIT)
    if build:
        setup_pc.build_rowboat(dest)
    return dest


def make_venv(venv: Path) -> Path:
    py = venv_python(venv)
    if not py.exists():
        setup_pc.run([*python312_cmd(), "-m", "venv", str(venv)])
        setup_pc.run([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"])
    return py


def setup_market(refresh: bool) -> Path:
    """market/.venv: market MCP server + research pipeline + demo scripts (openpyxl, pandas)."""
    py = make_venv(ROOT / "market" / ".venv")
    setup_pc.run([str(py), "-m", "pip", "install", "-q", "-e", str(ROOT / "market"),
                  "scikit-learn", "pyyaml", "pytest"])
    processed = ROOT / "research" / "data" / "processed"
    if refresh or not any(processed.glob("*")):
        setup_pc.run([str(py), str(ROOT / "research" / "scripts" / "prepare_data.py"),
                      "--raw", str(ROOT / "Dataset"), "--out", str(processed)], cwd=ROOT / "research")
    setup_pc.run([str(py), str(ROOT / "demo" / "torque" / "make_quotes.py")])
    return py


def setup_vault(py: Path, workdir: Path, refresh: bool) -> None:
    vault = workdir / "knowledge"
    vault.mkdir(parents=True, exist_ok=True)
    copied = copy_example_notes(ROOT / "demo" / "example-data", vault)
    log.info("%d product and topic notes copied to %s (Projects/, Topics/)", copied, vault)
    cmd =[str(py), str(ROOT / "demo" / "visu" / "vault.py"), "notes", "--vault", str(vault)]
    setup_pc.run(cmd + (["--refresh"] if refresh else []))
    if not (workdir / "config" / "notes.json").exists():
        log.warning("Rowboat has not created %s yet: start Rowboat once, then run "
                    "`python scripts/install.py --no-build --skip-rag` again to register the note types",
                    workdir / "config" / "notes.json")


def link_torque(workdir: Path) -> None:
    target, link = ROOT / "demo" / "torque", workdir / "apps" / "torque"
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists():
        if link.resolve() != target.resolve():
            log.warning("%s exists and points to %s, not to %s - left as it is", link, link.resolve(), target)
        return
    if IS_WINDOWS:  # a junction needs no admin rights or developer mode
        setup_pc.run(["cmd", "/c", "mklink", "/J", str(link), str(target)])
    else:
        link.symlink_to(target, target_is_directory=True)
    log.info("Torque linked: %s -> %s", link, target)


def register_market(py: Path, workdir: Path) -> None:
    add_mcp_server(workdir / "config" / "mcp.json", "ehl-market", {
        "command": str(py), "args": ["-m", "ehl_market.server"],
        "env": {"EHL_MARKET_HOME": str(ROOT / "market"), "EHL_RESEARCH_HOME": str(ROOT / "research")}})
    log.info("ehl-market registered in %s", workdir / "config" / "mcp.json")


def setup_3d(py: Path, cars: Path | None) -> None:
    cmd = [str(py), str(ROOT / "demo" / "visu" / "prepare_local.py")]
    setup_pc.run(cmd + (["--cars", str(cars)] if cars else []), cwd=ROOT / "demo" / "visu")
    missing = missing_cars(MODELS)
    if missing:
        lines = [f"  {car}: {CARS[car][1]}  ->  save as {CARS[car][0]}" for car in missing]
        log.warning("3D cars not installed yet (Concept 3D stays empty). Download glTF from Sketchfab "
                    "(free account, CC-BY-NC-SA-4.0, Ddiaz Design) into one folder:\n%s\n"
                    "then: python scripts/install.py --no-build --skip-rag --cars \"<folder>\"", "\n".join(lines))


def setup_rag(interactive: bool) -> None:
    setup_pc.run(["docker", "compose", "-f", str(ROOT / "docker-compose.qdrant.yml"), "up", "-d"], cwd=ROOT)
    py = make_venv(ROOT / "search" / ".venv")
    setup_pc.run([str(py), "-m", "pip", "install", "-q", "-r", str(ROOT / "requirements.txt")])
    key = find_openai_key(ROOT, os.environ)
    if not key and interactive:
        key = getpass.getpass("OPENAI_API_KEY for the RAG (embeddings; Enter to skip): ").strip() or None
        if key:
            env_file = ROOT / "search" / ".env"
            with env_file.open("a", encoding="utf-8") as fh:
                fh.write(f"OPENAI_API_KEY={key}\n")
            log.info("Key written to %s (gitignored)", env_file)
    if not key:
        log.warning("No OPENAI_API_KEY: the Qdrant index is not built; Nordi answers from Torque's data only. "
                    "Add the key to search/.env and run the installer again.")
        return
    setup_pc.run([str(py), str(ROOT / "scripts" / "ingest_qdrant.py"),
                  "--chunks-path", str(ROOT / "outputs" / "chunks" / "chunks.jsonl")], cwd=ROOT)


def start(rowboat: Path, workdir: Path) -> int:
    """Start Rowboat, the RAG backend and both syncs; Ctrl+C stops all of them."""
    market_py, search_py = venv_python(ROOT / "market" / ".venv"), venv_python(ROOT / "search" / ".venv")
    vault = str(workdir / "knowledge")
    env = {**os.environ, "ROWBOAT_WORKDIR": str(workdir), "EHL_VAULT": vault}
    jobs = [("Rowboat", ["npm", "run", "dev"], rowboat / "apps" / "x"),
            ("vault sync", [str(market_py), str(ROOT / "demo" / "visu" / "vault.py"), "sync", "--watch",
                            "--vault", vault], ROOT),
            ("Torque sync", [str(market_py), str(ROOT / "demo" / "torque" / "sync.py"), "--watch",
                             "--vault", vault], ROOT)]
    if search_py.exists():
        jobs.append(("RAG", [str(search_py), "-m", "uvicorn", "app:app", "--port", str(RAG_PORT)], ROOT))
    procs = []
    for name, cmd, cwd in jobs:
        log.info("starting %s: %s", name, " ".join(cmd))
        procs.append(subprocess.Popen(cmd, cwd=cwd, env=env, shell=IS_WINDOWS and cmd[0] == "npm"))
    log.info("Rowboat opens after its first build (a few minutes): Apps -> Torque. Ctrl+C stops everything.")
    try:
        procs[0].wait()
    except KeyboardInterrupt:
        pass
    finally:
        for proc in procs:
            stop(proc)
    return 0


def stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if IS_WINDOWS:  # npm runs through cmd.exe; /T also ends its child processes
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.terminate()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="only check the system tools")
    ap.add_argument("--start", action="store_true", help="start the demo (after setting it up)")
    ap.add_argument("--cars", type=Path, help="folder with the three Sketchfab car zips")
    ap.add_argument("--rowboat", type=Path, default=ROOT.parent / "rowboat",
                    help="Rowboat checkout (default: next to this repo)")
    ap.add_argument("--workdir", type=Path, help="Rowboat data folder (default: ~/.rowboat, or "
                    "~/.rowboat-ehl if you already use Rowboat)")
    ap.add_argument("--no-build", action="store_true", help="skip pnpm install of Rowboat")
    ap.add_argument("--skip-rag", action="store_true", help="no Docker/Qdrant/OpenAI (Nordi without RAG)")
    ap.add_argument("--refresh", action="store_true", help="rewrite generated data and managed notes")
    args = ap.parse_args()
    workdir = (args.workdir or setup_pc.rowboat_workdir()).expanduser()

    problems = check_tools(need_docker=not args.skip_rag and not args.start,
                           need_build=not args.no_build and not args.start)
    if problems:
        log.error("Missing prerequisites:\n- %s", "\n- ".join(problems))
        return 2
    log.info("Prerequisites ok. Rowboat data folder: %s", workdir)
    if args.check:
        return 0
    if args.start:
        return start(args.rowboat, workdir)

    try:
        setup_rowboat(args.rowboat, build=not args.no_build)
        py = setup_market(args.refresh)
        setup_vault(py, workdir, args.refresh)
        link_torque(workdir)
        register_market(py, workdir)
        setup_3d(py, args.cars)
        if not args.skip_rag:
            setup_rag(interactive=sys.stdin.isatty())
    except (InstallError, setup_pc.SetupError) as err:
        log.error("Install stopped: %s", err)
        return 1
    log.info("Done. Next: python scripts/install.py --start, then in Rowboat set a model provider "
             "(Settings) and open Apps -> Torque.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
