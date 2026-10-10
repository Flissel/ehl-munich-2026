#!/usr/bin/env python3
"""Create smaller Markdown chunks and a JSONL chunk manifest for RAG.

Input:
- outputs/markdown/

Outputs:
- outputs/markdown_chunked/
- outputs/chunks/chunks.jsonl

The Markdown chunks are meant for Rowboat's knowledge folder. The JSONL chunks
are meant for embeddings or any custom vector-store path.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIR = Path("outputs/markdown")
DEFAULT_MARKDOWN_OUTPUT_DIR = Path("outputs/markdown_chunked")
DEFAULT_CHUNKS_OUTPUT = Path("outputs/chunks/chunks.jsonl")
DEFAULT_MAX_CHARS = 14000


def clean_text(value: str) -> str:
    value = value.replace("\r", "\n")
    value = re.sub(r"\n{4,}", "\n\n\n", value)
    return value.strip()


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "unknown"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip()
    body = text[end + len("\n---") :].lstrip()
    meta = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"')
    return meta, body


def frontmatter(meta: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in meta.items():
        text = str(value).replace('"', '\\"')
        lines.append(f'{key}: "{text}"')
    lines.append("---")
    return "\n".join(lines)


def write_chunk_file(path: Path, meta: dict[str, Any], body: str) -> str:
    ensure_dir(path.parent)
    text = frontmatter(meta) + "\n\n" + clean_text(body) + "\n"
    path.write_text(text, encoding="utf-8")
    return text


def add_chunk(
    chunks: list[dict[str, Any]],
    chunk_id: str,
    chunk_file: Path,
    text: str,
    meta: dict[str, Any],
) -> None:
    chunks.append(
        {
            "chunk_id": chunk_id,
            "chunk_file": str(chunk_file),
            "text": text,
            "metadata": meta,
        }
    )


def split_large_blocks(blocks: list[str], max_chars: int) -> list[str]:
    groups: list[str] = []
    current: list[str] = []
    current_len = 0

    for block in blocks:
        block = clean_text(block)
        if not block:
            continue
        if len(block) > max_chars:
            if current:
                groups.append("\n\n".join(current))
                current = []
                current_len = 0
            groups.extend(split_oversized_text(block, max_chars=max_chars))
            continue
        projected = current_len + len(block) + 2
        if current and projected > max_chars:
            groups.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(block)
        current_len += len(block) + 2

    if current:
        groups.append("\n\n".join(current))
    return groups


def split_oversized_text(text: str, max_chars: int) -> list[str]:
    """Split a single very large section by paragraphs, then by hard windows."""
    parts: list[str] = []
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                parts.append("\n\n".join(current))
                current = []
                current_len = 0
            for idx in range(0, len(paragraph), max_chars):
                parts.append(paragraph[idx : idx + max_chars])
            continue

        projected = current_len + len(paragraph) + 2
        if current and projected > max_chars:
            parts.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += len(paragraph) + 2

    if current:
        parts.append("\n\n".join(current))
    return parts


def split_feedback_file(path: Path, output_root: Path, max_chars: int) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    source_meta, body = parse_frontmatter(text)
    vehicle = source_meta.get("vehicle_model") or path.stem.split("_")[0].upper()

    market_matches = list(re.finditer(r"^## Market: (.+)$", body, flags=re.MULTILINE))
    chunks: list[dict[str, Any]] = []
    if not market_matches:
        return split_generic_file(path, output_root, max_chars)

    for idx, match in enumerate(market_matches):
        market = match.group(1).strip()
        start = match.start()
        end = market_matches[idx + 1].start() if idx + 1 < len(market_matches) else len(body)
        market_section = body[start:end].strip()
        records = re.split(r"\n(?=### )", market_section)
        header = records[0].split("\n### ", 1)[0].strip()
        record_blocks = []
        for record in records:
            if record.startswith("## Market:"):
                parts = record.split("\n### ", 1)
                if len(parts) == 2:
                    record_blocks.append("### " + parts[1].strip())
            elif record.startswith("### "):
                record_blocks.append(record.strip())

        groups = split_large_blocks(record_blocks, max_chars=max_chars)
        if not groups:
            groups = [market_section]

        for part_number, group in enumerate(groups, start=1):
            chunk_id = f"{slugify(vehicle)}_{slugify(market)}_feedback_{part_number:03d}"
            out_path = (
                output_root
                / "feedback"
                / slugify(vehicle)
                / f"{slugify(vehicle)}_{slugify(market)}_feedback_part_{part_number:03d}.md"
            )
            meta = {
                "source_file": source_meta.get("source_file", path.name),
                "source_type": "customer_feedback",
                "vehicle_model": vehicle,
                "market": market,
                "chunk_id": chunk_id,
                "chunk_part": part_number,
            }
            chunk_body = f"# {vehicle} Feedback - Market: {market}\n\n{header}\n\n{group}"
            chunk_text = write_chunk_file(out_path, meta, chunk_body)
            add_chunk(chunks, chunk_id, out_path, chunk_text, meta)

    return chunks


def split_by_headings(body: str, heading_pattern: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(heading_pattern, body, flags=re.MULTILINE))
    if not matches:
        return [("Document", body)]
    sections = []
    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        sections.append((title, body[start:end].strip()))
    return sections


def split_generic_file(path: Path, output_root: Path, max_chars: int) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    source_meta, body = parse_frontmatter(text)
    rel_parent = path.parent.relative_to(DEFAULT_INPUT_DIR) if DEFAULT_INPUT_DIR in path.parents else path.parent.name
    rel_parent_path = Path(rel_parent) if not isinstance(rel_parent, Path) else rel_parent

    if "options/raw" in str(path):
        sections = split_by_headings(body, r"^## Page ([^-]+(?: - .+)?)$")
    elif "options/processed" in str(path):
        sections = split_by_headings(body, r"^## Feature Extract - (.+)$")
    else:
        sections = split_by_headings(body, r"^## (.+)$")

    chunks: list[dict[str, Any]] = []
    for section_number, (section_title, section_text) in enumerate(sections, start=1):
        groups = split_large_blocks([section_text], max_chars=max_chars)
        for part_number, group in enumerate(groups, start=1):
            chunk_id = f"{slugify(path.stem)}_{section_number:03d}_{part_number:03d}"
            out_path = (
                output_root
                / rel_parent_path
                / slugify(path.stem)
                / f"{slugify(path.stem)}_{section_number:03d}_{part_number:03d}.md"
            )
            meta = {
                "source_file": source_meta.get("source_file", path.name),
                "source_type": source_meta.get("source_type", "markdown"),
                "vehicle_model": source_meta.get("vehicle_model", ""),
                "section": section_title,
                "chunk_id": chunk_id,
                "chunk_part": part_number,
            }
            chunk_body = f"# {path.stem}\n\n## {section_title}\n\n{group}"
            chunk_text = write_chunk_file(out_path, meta, chunk_body)
            add_chunk(chunks, chunk_id, out_path, chunk_text, meta)

    return chunks


def run(input_dir: Path, markdown_output_dir: Path, chunks_output: Path, max_chars: int) -> list[dict[str, Any]]:
    all_chunks: list[dict[str, Any]] = []
    for path in sorted(input_dir.rglob("*.md")):
        if path.parent.name == "feedback":
            all_chunks.extend(split_feedback_file(path, markdown_output_dir, max_chars))
        else:
            all_chunks.extend(split_generic_file(path, markdown_output_dir, max_chars))

    ensure_dir(chunks_output.parent)
    with chunks_output.open("w", encoding="utf-8") as handle:
        for chunk in all_chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    return all_chunks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk generated Markdown for Rowboat/RAG.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--markdown-output-dir", type=Path, default=DEFAULT_MARKDOWN_OUTPUT_DIR)
    parser.add_argument("--chunks-output", type=Path, default=DEFAULT_CHUNKS_OUTPUT)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = run(args.input_dir, args.markdown_output_dir, args.chunks_output, args.max_chars)
    print(f"Wrote {len(chunks)} chunks")
    print(f"Markdown chunks: {args.markdown_output_dir}")
    print(f"JSONL chunks: {args.chunks_output}")


if __name__ == "__main__":
    main()
