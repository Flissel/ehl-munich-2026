from __future__ import annotations

from typing import Any

from openai import OpenAI

from .config import Settings
from .embeddings import OpenAIEmbedder
from .vector_store import QdrantVectorStore


SYSTEM_PROMPT = """You are a concise BMW data assistant for a hackathon RAG system.

Use only the provided context chunks. If the context is insufficient, say what is missing.
Answer the user's question directly in simple language.
Use plain text with short bullet points when a list is useful.
Do not use Markdown headings like ## or ###.
Do not add extra sections such as requirements, recommendations, or uncertainty unless the user explicitly asks for them.
Do not show chunk IDs or source IDs in the main answer unless the user asks for sources.
"""


class RagService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.embedder = OpenAIEmbedder(self.settings)
        self.vector_store = QdrantVectorStore(self.settings)
        self.client = OpenAI(api_key=self.settings.openai_api_key)

    def retrieve(
        self,
        question: str,
        top_k: int | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        query_vector = self.embedder.embed_query(question)
        return self.vector_store.search(
            query_vector=query_vector,
            limit=top_k or self.settings.top_k,
            filters=filters,
        )

    def answer(
        self,
        question: str,
        top_k: int | None = None,
        filters: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        hits = self.retrieve(question=question, top_k=top_k, filters=filters)
        context = self._format_context(hits)
        response = self.client.responses.create(
            model=self.settings.chat_model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Question:\n{question}\n\n"
                        f"Context chunks:\n{context}\n\n"
                        "Answer only what the user asked, using the context only. Do not include source IDs in the main answer."
                    ),
                },
            ],
            temperature=0.2,
        )
        evidence = [self._source_from_hit(hit) for hit in hits]
        return {
            "answer": response.output_text,
            "evidence": evidence,
            "sources": evidence,
        }

    def _format_context(self, hits: list[dict[str, Any]]) -> str:
        blocks = []
        for idx, hit in enumerate(hits, start=1):
            payload = hit["payload"]
            blocks.append(
                "\n".join(
                    [
                        f"[{idx}] chunk_id: {payload.get('chunk_id', '')}",
                        f"source_type: {payload.get('source_type', '')}",
                        f"vehicle_model: {payload.get('vehicle_model', '')}",
                        f"market: {payload.get('market', '')}",
                        f"section: {payload.get('section', '')}",
                        f"chunk_file: {payload.get('chunk_file', '')}",
                        "text:",
                        payload.get("text", ""),
                    ]
                )
            )
        return "\n\n---\n\n".join(blocks)

    def _source_from_hit(self, hit: dict[str, Any]) -> dict[str, Any]:
        payload = hit["payload"]
        return {
            "score": hit["score"],
            "chunk_id": payload.get("chunk_id"),
            "chunk_file": payload.get("chunk_file"),
            "source_file": payload.get("source_file"),
            "source_type": payload.get("source_type"),
            "vehicle_model": payload.get("vehicle_model"),
            "market": payload.get("market"),
            "section": payload.get("section"),
        }
