"""Checks for ehl_schema.lint."""
import pytest
from helpers import valid_vault, write_note

from ehl_schema.lint import errors, lint
from ehl_schema.model import load_schema


@pytest.fixture
def schema():
    return load_schema()


def codes(issues, path=None):
    return {i.code for i in issues if path is None or i.path == path}


def deal(**changes):
    front = {"id": "deal-x", "type": "Deals", "domain": "sales", "level": 3, "parent": "[[Areas/Pipeline]]",
             "customer": ["[[Organizations/Acme]]"], "owner": ["[[People/Felix Baumann]]"]}
    front.update(changes)
    return {k: v for k, v in front.items() if v is not None}


def test_valid_vault_has_no_issues(tmp_path, schema):
    assert lint(schema, valid_vault(tmp_path, schema)) == []


def test_unknown_folder_and_missing_front_matter(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Random/Thing", {"id": "x"})
    write_note(vault, "Topics/Loose", None, "# Loose\n")
    issues = lint(schema, vault)
    assert codes(issues, "Random/Thing") == {"unknown-type"}
    assert codes(issues, "Topics/Loose") == {"no-front-matter"}


def test_bad_yaml(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    (vault / "Topics").mkdir()
    (vault / "Topics" / "Bad.md").write_text("---\nid: [x\n---\n", encoding="utf-8")
    assert codes(lint(schema, vault), "Topics/Bad") == {"bad-yaml"}


def test_wrong_type_domain_level(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Deals/X", deal(type="Leads", domain="legal", level=4))
    assert codes(lint(schema, vault), "Deals/X") >= {"type-mismatch", "domain-mismatch", "level-mismatch"}


def test_missing_key_and_nested_value(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Deals/X", deal(parent=None))
    (vault / "Deals" / "Y.md").write_text(
        '---\nid: deal-y\ntype: Deals\ndomain: sales\nlevel: 3\nparent: "[[Areas/Pipeline]]"\n'
        'owner:\n  name: Felix\n---\n', encoding="utf-8")
    issues = lint(schema, vault)
    assert "missing-key" in codes(issues, "Deals/X")
    assert "nested" in codes(issues, "Deals/Y")


def test_parent_rules(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Deals/A", deal(id="a", parent="[[People/Felix Baumann]]"))
    write_note(vault, "Deals/B", deal(id="b", parent="[[Areas/Nowhere]]"))
    write_note(vault, "Deals/C", deal(id="c", parent="Areas/Pipeline"))
    issues = lint(schema, vault)
    assert "parent-type" in codes(issues, "Deals/A")
    assert "parent-missing" in codes(issues, "Deals/B")
    assert "parent-format" in codes(issues, "Deals/C")


def test_cycle(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    base = {"type": "Projects", "domain": "delivery", "level": 3}
    write_note(vault, "Projects/A", {**base, "id": "pa", "parent": "[[Projects/B]]"})
    write_note(vault, "Projects/B", {**base, "id": "pb", "parent": "[[Projects/A]]"})
    assert "cycle" in codes(lint(schema, vault))


def test_relations(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Deals/A", deal(id="a", customer=None))
    write_note(vault, "Deals/B", deal(id="b", customer=["[[People/Felix Baumann]]"]))
    write_note(vault, "Deals/C", deal(id="c", customer="[[Organizations/Acme]]"))
    write_note(vault, "Deals/D", deal(id="d", customer=["[[Organizations/Nobody]]"]))
    write_note(vault, "Deals/E", deal(id="e", when="next week"))
    issues = lint(schema, vault)
    assert "required-relation" in codes(issues, "Deals/A")
    assert "relation-target" in codes(issues, "Deals/B")
    assert "relation-format" in codes(issues, "Deals/C")
    assert "relation-missing" in codes(issues, "Deals/D")
    assert "relation-format" in codes(issues, "Deals/E")


def test_duplicate_id_and_status(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Deals/Copy", deal(id="deal-acme", status="maybe"))
    issues = lint(schema, vault)
    assert "duplicate-id" in codes(issues, "Deals/Copy")
    assert any(i.code == "status-value" and i.severity == "warning" for i in issues)


def test_broken_body_link_is_a_warning(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "Deals/X", deal(), "See [[Topics/Nope]].\n")
    issues = lint(schema, vault)
    assert codes(issues, "Deals/X") == {"broken-link"}
    assert errors(issues) == []


def test_alias_and_attachment_links_resolve(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    (vault / "Data").mkdir()
    (vault / "Data" / "BMW Dataset.xlsx").write_bytes(b"x")
    write_note(vault, "Deals/X", deal(), "[[Organizations/Acme|Acme]] [[Data/BMW Dataset.xlsx|data]] [[Deals/Acme deal#Top]]\n")
    assert codes(lint(schema, vault), "Deals/X") == set()


def test_possible_duplicate_people(tmp_path, schema):
    vault = valid_vault(tmp_path, schema)
    write_note(vault, "People/Felix-Baumann", {"id": "p2", "type": "People", "domain": "register", "level": 3,
                                               "parent": "[[Areas/Contacts]]"})
    issues = lint(schema, vault)
    assert {i.path for i in issues if i.code == "possible-duplicate"} == {"People/Felix Baumann",
                                                                          "People/Felix-Baumann"}
