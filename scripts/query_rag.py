#!/usr/bin/env python3
"""Ask the local RAG backend from the command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_backend.service import RagService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query the EHL BMW RAG backend.")
    parser.add_argument("question")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--vehicle-model", default="")
    parser.add_argument("--market", default="")
    parser.add_argument("--source-type", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    filters = {
        "vehicle_model": args.vehicle_model,
        "market": args.market,
        "source_type": args.source_type,
    }
    filters = {key: value for key, value in filters.items() if value}
    result = RagService().answer(args.question, top_k=args.top_k, filters=filters or None)
    print(result["answer"])
    print("\nSources:")
    for source in result["sources"]:
        print(f"- {source['chunk_id']} ({source['score']:.3f}) {source['chunk_file']}")


if __name__ == "__main__":
    main()
