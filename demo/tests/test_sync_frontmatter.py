"""Torque's sync must not drop front matter keys other tools added (e.g. the vault schema's parent)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "torque"))

import sync  # noqa: E402

OLD = ('---\nsource: torque\nmanaged_by: torque\nreviewed_on: 2026-10-11\nid: purchase-drivers-x\n'
       'parent: "[[Projects/G60]]"\nschema_version: 1\n---\n# X\nold body\n')
NEW = "---\nsource: torque\nmanaged_by: torque\nreviewed_on: 2026-10-12\n---\n# X\nnew body\n"


def test_keep_foreign_keys_appends_missing_keys():
    merged = sync.keep_foreign_keys(OLD, NEW)
    assert merged == ('---\nsource: torque\nmanaged_by: torque\nreviewed_on: 2026-10-12\nid: purchase-drivers-x\n'
                      'parent: "[[Projects/G60]]"\nschema_version: 1\n---\n# X\nnew body\n')


def test_keep_foreign_keys_without_front_matter_returns_new():
    assert sync.keep_foreign_keys("# no front matter\n", NEW) == NEW
    assert sync.keep_foreign_keys(OLD, "# plain\n") == "# plain\n"


def test_write_if_changed_keeps_schema_keys(tmp_path):
    path = tmp_path / "X.md"
    path.write_text(OLD, encoding="utf-8")
    assert sync.write_if_changed(path, NEW) is True
    text = path.read_text(encoding="utf-8")
    assert 'parent: "[[Projects/G60]]"' in text and "new body" in text
    assert sync.write_if_changed(path, NEW) is False


def test_write_if_changed_still_skips_unmanaged_notes(tmp_path):
    path = tmp_path / "X.md"
    path.write_text("---\nsource: me\n---\nmine\n", encoding="utf-8")
    assert sync.write_if_changed(path, NEW) is False
