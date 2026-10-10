from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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


def load_project_env(repo_root: Path | None = None) -> None:
    root = repo_root or Path.cwd()
    load_env_file(root / ".env")
    load_env_file(root / "search" / ".env")


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    embedding_model: str
    chat_model: str
    qdrant_url: str
    qdrant_collection: str
    chunks_path: Path
    top_k: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_project_env()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing. Add it to search/.env or the environment.")

        return cls(
            openai_api_key=api_key,
            embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
            qdrant_url=os.getenv("QDRANT_URL", "http://127.0.0.1:6333"),
            qdrant_collection=os.getenv("QDRANT_COLLECTION", "ehl_notes"),
            chunks_path=Path(os.getenv("EHL_CHUNKS_PATH", "outputs/chunks/chunks.jsonl")),
            top_k=int(os.getenv("RAG_TOP_K", "8")),
        )
