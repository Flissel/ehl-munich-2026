#!/usr/bin/env python3
"""Embed chunks and upsert them into Qdrant."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_backend.chunks import load_chunks
from rag_backend.config import Settings
from rag_backend.embeddings import OpenAIEmbedder
from rag_backend.vector_store import QdrantVectorStore


def batched(items: list[dict], batch_size: int) -> list[list[dict]]:
    return [items[idx : idx + batch_size] for idx in range(0, len(items), batch_size)]


def run(chunks_path: Path, batch_size: int) -> int:
    settings = Settings.from_env()
    chunks = load_chunks(chunks_path)
    embedder = OpenAIEmbedder(settings)
    store = QdrantVectorStore(settings)

    total = 0
    for batch in batched(chunks, batch_size):
        vectors = embedder.embed_texts([item["text"] for item in batch])
        store.upsert_chunks(batch, vectors)
        total += len(batch)
        print(f"Upserted {total}/{len(chunks)} chunks")
    return total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest chunk JSONL into Qdrant.")
    parser.add_argument("--chunks-path", type=Path, default=Path("outputs/chunks/chunks.jsonl"))
    parser.add_argument("--batch-size", type=int, default=32)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    total = run(chunks_path=args.chunks_path, batch_size=args.batch_size)
    print(f"Ingested {total} chunks into Qdrant")


if __name__ == "__main__":
    main()
