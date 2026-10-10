#!/usr/bin/env python3
"""Preprocess BMW option-list PDFs into raw and LLM-processed Markdown.

Outputs:
- outputs/markdown/options/raw/<vehicle>_options_raw.md
- outputs/markdown/options/processed/<vehicle>_options_features.md

The raw Markdown preserves page-level traceability. The processed Markdown asks an
LLM to reorganize the raw text into feature/category sections for better RAG use.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover - only hit on missing setup
    raise SystemExit("Missing dependency: pypdf. Install it with `pip install pypdf`.") from exc


DEFAULT_DATASET_DIR = Path("dataset")
DEFAULT_OUTPUT_DIR = Path("outputs/markdown/options")
DEFAULT_MODEL = "gpt-4o-mini"

SECTION_KEYWORDS = [
    ("Contents", ["INHALT"]),
    ("Vehicle Prices & Models", ["FAHRZEUGPREISE", "FAHRZEUGPREISE & MODELLE"]),
    (
        "Standard Equipment",
        ["AUSGEWÄHLTE SERIENAUSSTATTUNGEN", "AUSGEWÄHL TE SERIENAUSSTATTUNGEN"],
    ),
    ("M Sport Packages", ["M SPORTPAKET PRO", "M SPORTPAKET", "M SPORT DESIGN"]),
    ("Optional Equipment", ["SONDERAUSSTATTUNGEN"]),
    ("Wheels & Tires", ["RÄDER UND REIFEN", "RADER UND REIFEN"]),
    ("Exterior Colors", ["FARBWELT EXTERIEUR"]),
    ("Interior Colors", ["FARBWELT INTERIEUR"]),
    ("Technical Values", ["TECHNISCHE WERTE", "TECHNISCHE MAßZEICHNUNG"]),
]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def yaml_value(value: Any) -> str:
    text = clean_text(value).replace('"', '\\"')
    return f'"{text}"'


def frontmatter(**fields: Any) -> str:
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {yaml_value(value)}")
    lines.append("---")
    return "\n".join(lines)


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "unknown"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def infer_vehicle_model(path: Path, title: str) -> str:
    stem = path.stem.upper()
    if stem.startswith("F70"):
        return "F70"
    if stem.startswith("G60"):
        return "G60"
    if stem.startswith("G70"):
        return "G70"
    if "1ER" in title.upper():
        return "F70"
    if "5ER" in title.upper():
        return "G60"
    if "7ER" in title.upper():
        return "G70"
    return path.stem


def detect_section(text: str, previous_section: str) -> str:
    upper = text.upper()
    first_part = upper[:1200]
    for section, keywords in SECTION_KEYWORDS:
        if any(keyword in first_part for keyword in keywords):
            return section
    return previous_section or "Unclassified"


def extract_option_pdf(path: Path) -> dict[str, Any]:
    reader = PdfReader(str(path))
    title = clean_text((reader.metadata or {}).get("/Title", ""))
    vehicle_model = infer_vehicle_model(path, title)
    pages = []
    current_section = ""

    for page_number, page in enumerate(reader.pages, start=1):
        text = clean_text(page.extract_text() or "")
        current_section = detect_section(text, current_section)
        pages.append(
            {
                "page": page_number,
                "section": current_section,
                "text": text,
            }
        )

    return {
        "source_file": path.name,
        "title": title,
        "vehicle_model": vehicle_model,
        "page_count": len(reader.pages),
        "pages": pages,
    }


def raw_markdown(extracted: dict[str, Any]) -> str:
    lines = [
        frontmatter(
            source_file=extracted["source_file"],
            source_type="option_list_raw",
            vehicle_model=extracted["vehicle_model"],
            language="de",
            page_count=extracted["page_count"],
            created_from="scripts/preprocess_options.py",
        ),
        "",
        f"# {extracted['vehicle_model']} Option List - Raw Extract",
        "",
        f"Source file: `{extracted['source_file']}`",
        f"PDF title: {extracted['title'] or 'unknown'}",
        f"Pages: {extracted['page_count']}",
        "",
    ]

    for page in extracted["pages"]:
        lines.extend(
            [
                f"## Page {page['page']} - {page['section']}",
                "",
                page["text"] or "No extractable text found on this page.",
                "",
            ]
        )

    return "\n".join(lines)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def load_openai_key(repo_root: Path) -> str:
    for env_path in [repo_root / ".env", repo_root / "search" / ".env"]:
        load_env_file(env_path)
    return os.getenv("OPENAI_API_KEY", "").strip()


def call_openai(prompt: str, model: str, api_key: str, timeout: int = 120) -> str:
    payload = {
        "model": model,
        "input": prompt,
        "temperature": 0.1,
        "max_output_tokens": 12000,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenAI API request failed ({exc.code}): {detail}") from exc

    output_text = data.get("output_text")
    if output_text:
        return output_text.strip()

    parts = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])
    if not parts:
        raise RuntimeError("OpenAI API response did not contain text output.")
    return "\n".join(parts).strip()


def page_groups(pages: list[dict[str, Any]], pages_per_group: int) -> list[list[dict[str, Any]]]:
    return [pages[idx : idx + pages_per_group] for idx in range(0, len(pages), pages_per_group)]


def build_feature_prompt(
    extracted: dict[str, Any], pages: list[dict[str, Any]], chunk_label: str
) -> str:
    page_blocks = []
    for page in pages:
        if not page["text"]:
            continue
        page_blocks.append(
            f"### Page {page['page']} | Detected section: {page['section']}\n{page['text']}"
        )
    source_text = "\n\n".join(page_blocks)

    return f"""You are converting a BMW German option-list PDF extract into clean Markdown for a RAG system.

Task:
- Create feature/category Markdown for vehicle {extracted['vehicle_model']}.
- Preserve source traceability with page numbers.
- Do not invent features, availability, prices, packages, or variants.
- If availability, variant, package, or price is unclear, write "unclear".
- Keep German feature names when useful, but add short English category headings.
- Focus on product-requirement evidence: equipment, comfort, infotainment, driver assistance, exterior/interior, range/charging, packages, and technical customer-facing values.
- Extract all useful customer-facing features from this page group.
- Do not stop after only one or two examples per category. Prefer concise records over long prose.
- Exclude legal footnotes unless they clarify availability.

Required output format:

## Feature Extract - {chunk_label}

### <Category>

#### <Feature name>
- Availability: standard / optional / package / unclear
- Package: <package name or unclear>
- Variant/model: <variant/model or unclear>
- Price: <price or unclear>
- Source pages: <page numbers>
- Evidence: "<short source phrase, not long quote>"

Repeat for relevant features. Keep the output concise but useful for retrieval.

PDF extract for {chunk_label}:

{source_text}
"""


def processed_markdown(
    extracted: dict[str, Any], model: str, api_key: str, pages_per_group: int
) -> str:
    lines = [
        frontmatter(
            source_file=extracted["source_file"],
            source_type="option_list_features",
            vehicle_model=extracted["vehicle_model"],
            language="de",
            created_from="scripts/preprocess_options.py + OpenAI LLM",
        ),
        "",
        f"# {extracted['vehicle_model']} Option List - Feature Extract",
        "",
        "## Summary",
        (
            "Feature-oriented extract from the raw option-list Markdown. "
            "Each feature keeps source-page references for traceability."
        ),
        "",
        "## Feature Categories",
        "",
    ]

    for pages in page_groups(extracted["pages"], pages_per_group):
        first_page = pages[0]["page"]
        last_page = pages[-1]["page"]
        chunk_label = f"Pages {first_page}-{last_page}"
        prompt = build_feature_prompt(extracted, pages, chunk_label)
        lines.append(call_openai(prompt, model=model, api_key=api_key))
        lines.append("")
        time.sleep(0.5)

    return "\n".join(lines)


def run(
    dataset_dir: Path,
    output_dir: Path,
    skip_llm: bool,
    model: str,
    pages_per_llm_call: int,
) -> list[Path]:
    repo_root = Path.cwd()
    api_key = "" if skip_llm else load_openai_key(repo_root)
    option_files = sorted(dataset_dir.glob("*_OptionList.PDF"))
    if not option_files:
        option_files = sorted(dataset_dir.glob("*_OptionList.pdf"))

    written: list[Path] = []
    for pdf_path in option_files:
        extracted = extract_option_pdf(pdf_path)
        vehicle_slug = slugify(extracted["vehicle_model"])

        raw_path = output_dir / "raw" / f"{vehicle_slug}_options_raw.md"
        write_text(raw_path, raw_markdown(extracted))
        written.append(raw_path)

        if skip_llm:
            continue
        if not api_key:
            raise SystemExit(
                "OPENAI_API_KEY was not found in the environment, .env, or search/.env. "
                "Raw option Markdown was created; rerun without --skip-llm after adding the key."
            )

        processed_path = output_dir / "processed" / f"{vehicle_slug}_options_features.md"
        feature_md = processed_markdown(
            extracted,
            model=model,
            api_key=api_key,
            pages_per_group=pages_per_llm_call,
        )
        write_text(processed_path, feature_md)
        written.append(processed_path)

    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert BMW option-list PDFs to raw and LLM-processed Markdown."
    )
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--skip-llm", action="store_true", help="Only create raw Markdown.")
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        help=f"OpenAI model for processed feature Markdown. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--pages-per-llm-call",
        type=int,
        default=4,
        help="How many PDF pages to send to each LLM extraction call.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    written = run(
        args.dataset_dir,
        args.output_dir,
        args.skip_llm,
        args.model,
        args.pages_per_llm_call,
    )
    print(f"Wrote {len(written)} Markdown files:")
    for path in written:
        print(f"- {path}")


if __name__ == "__main__":
    main()
