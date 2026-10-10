#!/usr/bin/env python3
"""Embed chunk JSONL with OpenAI and save a local vector-store JSONL.

Input:
- outputs/chunks/chunks.jsonl

Output:
- outputs/embeddings/openai_embeddings.jsonl

This is a lightweight backup/custom RAG store. Rowboat can still read the
chunked Markdown files directly from its knowledge folder.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_CHUNKS_INPUT = Path("outputs/chunks/chunks.jsonl")
DEFAULT_EMBEDDINGS_OUTPUT = Path("outputs/embeddings/openai_embeddings.jsonl")
DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_BATCH_SIZE = 64


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


def load_chunks(path: Path) -> list[dict[str, Any]]:
    chunks = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks


def existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                ids.add(json.loads(line)["chunk_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return ids


def embed_batch(texts: list[str], model: str, api_key: str, timeout: int = 120) -> list[list[float]]:
    payload = {
        "model": model,
        "input": texts,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
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
        raise RuntimeError(f"OpenAI embeddings request failed ({exc.code}): {detail}") from exc

    vectors = [item["embedding"] for item in sorted(data["data"], key=lambda item: item["index"])]
    if len(vectors) != len(texts):
        raise RuntimeError("Embedding count did not match input count.")
    return vectors


def batched(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [items[idx : idx + batch_size] for idx in range(0, len(items), batch_size)]


def run(chunks_input: Path, embeddings_output: Path, model: str, batch_size: int) -> int:
    api_key = load_openai_key(Path.cwd())
    if not api_key:
        raise SystemExit("OPENAI_API_KEY was not found in environment, .env, or search/.env.")

    chunks = load_chunks(chunks_input)
    done = existing_ids(embeddings_output)
    pending = [chunk for chunk in chunks if chunk["chunk_id"] not in done]

    embeddings_output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with embeddings_output.open("a", encoding="utf-8") as handle:
        for batch in batched(pending, batch_size):
            vectors = embed_batch([item["text"] for item in batch], model=model, api_key=api_key)
            for item, vector in zip(batch, vectors):
                record = {
                    "chunk_id": item["chunk_id"],
                    "chunk_file": item["chunk_file"],
                    "metadata": item["metadata"],
                    "embedding_model": model,
                    "embedding": vector,
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1
            handle.flush()
            print(f"Embedded {written}/{len(pending)} pending chunks")
            time.sleep(0.2)

    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed Markdown chunks with OpenAI.")
    parser.add_argument("--chunks-input", type=Path, default=DEFAULT_CHUNKS_INPUT)
    parser.add_argument("--embeddings-output", type=Path, default=DEFAULT_EMBEDDINGS_OUTPUT)
    parser.add_argument("--model", default=os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_MODEL))
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    written = run(args.chunks_input, args.embeddings_output, args.model, args.batch_size)
    print(f"Wrote {written} new embeddings to {args.embeddings_output}")


if __name__ == "__main__":
    main()
