"""Helpers for the schema tests: write notes and small valid vaults."""
from pathlib import Path

from ehl_schema.notes import note_text


def write_note(vault: Path, path: str, front: dict | None, body: str = "") -> Path:
    file = vault / f"{path}.md"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(note_text(front, body) if front is not None else body, encoding="utf-8", newline="\n")
    return file


def structure(schema, key: str, area: str) -> dict:
    """front matter of the domain note and the area note a test needs."""
    return {
        schema.domain_note(key): {"id": f"domain-{key}", "type": "Domains", "domain": key, "level": 1,
                                  "parent": "[[Company]]"},
        schema.area_note(area): {"id": f"area-{area.lower()}", "type": "Areas", "domain": key, "level": 2,
                                 "parent": f"[[{schema.domain_note(key)}]]"},
    }


def valid_vault(tmp_path: Path, schema) -> Path:
    vault = tmp_path / "knowledge"
    write_note(vault, "Company", {"id": "company", "type": "Company", "domain": "company", "level": 0})
    notes = {**structure(schema, "sales", "Pipeline"), **structure(schema, "register", "Companies")}
    notes[schema.area_note("Contacts")] = {"id": "area-contacts", "type": "Areas", "domain": "register",
                                           "level": 2, "parent": f"[[{schema.domain_note('register')}]]"}
    for path, front in notes.items():
        write_note(vault, path, front)
    write_note(vault, "Organizations/Acme", {"id": "org-acme", "type": "Organizations", "domain": "register",
                                             "level": 3, "parent": "[[Areas/Companies]]"})
    write_note(vault, "People/Felix Baumann", {"id": "person-felix", "type": "People", "domain": "register",
                                               "level": 3, "parent": "[[Areas/Contacts]]",
                                               "works_at": ["[[Organizations/Acme]]"]})
    write_note(vault, "Deals/Acme deal", {"id": "deal-acme", "type": "Deals", "domain": "sales", "level": 3,
                                          "parent": "[[Areas/Pipeline]]", "status": "proposal",
                                          "customer": ["[[Organizations/Acme]]"],
                                          "owner": ["[[People/Felix Baumann]]"], "when": "2026-10-20"},
               "# Acme deal\n\nWith [[Organizations/Acme|Acme]].\n")
    return vault
