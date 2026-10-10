import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import fill_data  # noqa: E402

PAGE = Path(__file__).with_name("index.html")
TEAM = re.compile(r'<script id="data-team" type="application/json">(.*?)</script>', re.S)


def test_inject_replaces_only_real_block():
    html = PAGE.read_text(encoding="utf-8")
    out = fill_data.inject(html, {"probe": "</script> stays escaped"})
    assert TEAM.search(out).group(1) == TEAM.search(html).group(1)
    real = re.search(r'<script id="data-real" type="application/json">(.*?)</script>', out, re.S).group(1)
    assert json.loads(real) == {"probe": "</script> stays escaped"}


def test_inject_needs_the_block():
    with pytest.raises(ValueError):
        fill_data.inject("<p>no block</p>", {})


@pytest.mark.skipif(not (fill_data.ROOT / "Dataset").exists(), reason="Dataset/ not present")
def test_build_has_only_aggregates():
    data = fill_data.build(fill_data.ROOT / "Dataset")
    assert {p["code"] for p in data["products"]} == {"F70", "G60", "G68", "G70"}
    longest = max(len(s) for s in re.findall(r'"([^"]*)"', json.dumps(data, ensure_ascii=False)))
    assert longest < 100, "a long string suggests customer text leaked into the page"
