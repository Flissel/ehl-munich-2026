"""Checks for the generated demo notes in demo/example-data/."""
import json
import re
import sys
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO))

import dataset_to_notes as conv  # noqa: E402

NOTES = DEMO / "example-data"
FIXED_TARGETS = [
    "Topics/Newsletter", "Topics/Social Media", "Topics/Email", "Topics/Market Research",
    "Projects/F70", "Projects/G60", "Projects/G68", "Projects/G70",
]
LINK = re.compile(r"\[\[([^\]]+)\]\]")


def all_notes() -> dict[str, str]:
    return {p.relative_to(NOTES).with_suffix("").as_posix(): p.read_text(encoding="utf-8")
            for p in NOTES.glob("*/*.md")}


def test_fixed_link_targets_exist():
    names = all_notes()
    assert [t for t in FIXED_TARGETS if t not in names] == []


def test_frozen_link_targets_exist():
    """Every target frozen in demo/link-targets.json (M1) exists, except team notes (step 3)."""
    frozen = json.loads((DEMO / "link-targets.json").read_text(encoding="utf-8"))
    targets = [*frozen["products"], *frozen["roadmaps"], *frozen["channels"], *frozen["research"]]
    names = all_notes()
    assert [t for t in targets if t not in names] == []


def test_every_link_resolves():
    names = all_notes()
    broken = {(n, t) for n, text in names.items() for t in LINK.findall(text) if t not in names}
    assert broken == set()


def test_notes_follow_rowboat_template():
    for name, text in all_notes().items():
        assert text.startswith("---\n") and conv.MARKER in text, name
        assert f"\n# {name.split('/', 1)[1]}\n" in text, name
        for section in ("## Info", "## Connected to", "## Activity", "## Key facts", "## Open items"):
            assert section in text, (name, section)


def test_no_personal_data():
    email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    phone = re.compile(r"\+\d[\d ()/-]{7,}\d|\b0\d{2,4}[ /]\d{4,}\b")
    for name, text in all_notes().items():
        body = text.split("---", 2)[2]
        assert not email.search(body), name
        assert not phone.search(body), name


def test_committed_notes_match_the_converter(tmp_path):
    if not conv.DATASET.exists():
        pytest.skip("Dataset/ not available")
    expected = conv.build(conv.DATASET)
    assert set(expected) == {f"{n}.md" for n in all_notes()}
    for rel, text in expected.items():
        assert (NOTES / rel).read_text(encoding="utf-8") == text, rel


def test_write_never_touches_foreign_notes(tmp_path):
    foreign = tmp_path / "Projects" / "F70.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("# F70\nhand written\n", encoding="utf-8")
    stale = tmp_path / "Topics" / "Old.md"
    stale.parent.mkdir(parents=True)
    stale.write_text(f"---\n{conv.MARKER}\n---\n# Old\n", encoding="utf-8")
    conv.write({"Projects/F70.md": "new", "Topics/New.md": f"---\n{conv.MARKER}\n---\n# New\n"}, tmp_path)
    assert foreign.read_text(encoding="utf-8") == "# F70\nhand written\n"
    assert not stale.exists()
    assert (tmp_path / "Topics" / "New.md").exists()
