"""Checks for the ehl-schema command line."""
import json

from helpers import write_note

from ehl_schema.cli import main


def test_no_vault_exits_2(tmp_path):
    assert main(["lint", "--workdir", str(tmp_path)]) == 2


def test_build_migrate_lint(tmp_path):
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "notes.json").write_text(json.dumps([]), encoding="utf-8")
    write_note(tmp_path / "knowledge", "Topics/Comfort", None, "# Comfort\n")
    assert main(["build", "--workdir", str(tmp_path), "--company", "EHL"]) == 0
    assert main(["lint", "--workdir", str(tmp_path)]) == 1          # Topics/Comfort has no front matter yet
    assert main(["migrate", "--workdir", str(tmp_path)]) == 0       # dry run
    assert main(["lint", "--workdir", str(tmp_path)]) == 1
    assert main(["migrate", "--workdir", str(tmp_path), "--write"]) == 0
    assert main(["lint", "--workdir", str(tmp_path)]) == 0
