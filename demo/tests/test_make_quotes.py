"""Checks for demo/torque/make_quotes.py (customer comment texts for Torque's data/quotes.json)."""
import sys
from pathlib import Path

import pytest

TORQUE = Path(__file__).resolve().parents[1] / "torque"
sys.path.insert(0, str(TORQUE))

import make_quotes as mq  # noqa: E402

PLACEHOLDER = "Comment G70-3713, text only in the local copy"

BMW = {
    "themes": {
        "R-01": {"quotes": [
            {"id": "G70-3713", "t": PLACEHOLDER, "dv": "G70", "s": "B"},
            {"id": "G60-1316", "t": "Comment G60-1316, text only in the local copy", "dv": "G60", "s": "B"},
        ], "mq": {"US": [{"id": "F70-9", "t": "Comment F70-9, text only in the local copy", "c": "US", "s": "A"}]}},
    },
    "says": [{"id": "G70-1", "t": "already has a text", "s": "A"}],
}


def test_finds_every_placeholder_with_its_path():
    found = mq.placeholders(BMW)
    assert ("G70-3713", ["themes", "R-01", "quotes", 0, "t"]) in found
    assert ("F70-9", ["themes", "R-01", "mq", "US", 0, "t"]) in found
    assert len(found) == 3  # the quote that already has a text is left alone


def test_patches_use_masked_text_and_skip_unknown_ids():
    texts = {"G70-3713": "Call me at mail@example.com", "F70-9": "Great seats"}
    patches, missing = mq.patches(BMW, texts, mask=lambda t: t.replace("mail@example.com", "[EMAIL]"))
    assert patches == [
        [["themes", "R-01", "quotes", 0, "t"], "Call me at [EMAIL]"],
        [["themes", "R-01", "mq", "US", 0, "t"], "Great seats"],
    ]
    assert missing == ["G60-1316"]


def test_same_comment_id_in_two_places_gets_the_same_text():
    bmw = {"a": [{"id": "G60-5", "t": "Comment G60-5, text only in the local copy"}],
           "b": [{"id": "G60-5", "t": "Comment G60-5, text only in the local copy"}]}
    patches, missing = mq.patches(bmw, {"G60-5": "Seats too firm"}, mask=lambda t: t)
    assert [p[1] for p in patches] == ["Seats too firm", "Seats too firm"]
    assert missing == []


def test_reads_comment_texts_from_the_feedback_workbooks(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ID", "Country", "Customer Feedback", "Feedback Type"])
    ws.append(["G70-3713", "US", "Love the seats", "Likes"])  # the Dataset's IDs carry the series
    ws.append(["G70-3713", "US", "Love the seats", "Wants"])  # one comment, two classification rows
    ws.append(["G70-0042", "DE", None, "Defect"])
    ws.append([7, "DE", "Bare number", "Likes"])  # a bare number gets the series from the file name
    wb.save(tmp_path / "G70_feedback_hackathon.xlsx")
    assert mq.load_texts(tmp_path) == {"G70-3713": "Love the seats", "G70-7": "Bare number"}
