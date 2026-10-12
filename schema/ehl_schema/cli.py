"""Command line: python -m ehl_schema.cli build|lint|migrate --workdir <Rowboat data folder>."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .build import build
from .lint import errors, lint
from .migrate import apply, diff, plan
from .model import DEFAULT_SCHEMA, load_schema

log = logging.getLogger("ehl_schema")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(prog="ehl-schema", description="Vault schema: build, lint, migrate")
    ap.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="schema file (default: schema/vault-schema.yaml)")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, text in (("build", "write structure notes, rules note and notes.json"),
                       ("lint", "check every note"), ("migrate", "add missing front matter (dry run by default)")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--workdir", type=Path, required=True, help="Rowboat data folder, e.g. ~/.rowboat-ehl")
    sub.choices["build"].add_argument("--company", default="Company", help="title of the L0 note")
    sub.choices["migrate"].add_argument("--write", action="store_true", help="write the changes")
    args = ap.parse_args(argv)

    schema = load_schema(args.schema)
    workdir = args.workdir.expanduser()
    vault = workdir / "knowledge"
    if not vault.is_dir():
        log.error("no vault at %s", vault)
        return 2
    if args.command == "build":
        result = build(schema, workdir, args.company)
        log.info("build: %d structure note(s) written, notes.json %s", result["notes"], result["notes_json"])
        return 0
    if args.command == "lint":
        issues = lint(schema, vault)
        for issue in issues:
            log.info("%s %s [%s] %s", issue.severity.upper(), issue.path, issue.code, issue.message)
        n_errors = len(errors(issues))
        log.info("lint: %d error(s), %d warning(s)", n_errors, len(issues) - n_errors)
        return 1 if n_errors else 0
    report = plan(schema, vault)
    if args.write:
        log.info("migrate: wrote %d note(s)", apply(report, vault))
    else:
        if report.changes:
            log.info("%s", diff(report))
        log.info("migrate (dry run): %d note(s) would change; add --write to apply", len(report.changes))
    for path in report.unmapped:
        log.warning("unmapped (folder not in the schema): %s", path)
    for path in report.unresolved:
        log.warning("unresolved (no parent found, no default area): %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
