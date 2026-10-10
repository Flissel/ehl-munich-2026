from __future__ import annotations

import hashlib
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models

from .config import Settings


def stable_point_id(chunk_id: str) -> str:
    digest = hashlib.sha256(chunk_id.encode("utf-8")).digest()
    return str(uuid.UUID(bytes=digest[:16]))


class QdrantVectorStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = QdrantClient(url=settings.qdrant_url)

    def ensure_collection(self, vector_size: int) -> None:
        collections = self.client.get_collections().collections
        if any(item.name == self.settings.qdrant_collection for item in collections):
            return
        self.client.create_collection(
            collection_name=self.settings.qdrant_collection,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    def upsert_chunks(self, chunks: list[dict[str, Any]], vectors: list[list[float]]) -> None:
        if not chunks:
            return
        self.ensure_collection(vector_size=len(vectors[0]))
        points = []
        for chunk, vector in zip(chunks, vectors):
            points.append(
                models.PointStruct(
                    id=stable_point_id(chunk["chunk_id"]),
                    vector=vector,
                    payload={
                        "chunk_id": chunk["chunk_id"],
                        "chunk_file": chunk["chunk_file"],
                        "text": chunk["text"],
                        **chunk.get("metadata", {}),
                    },
                )
            )
        self.client.upsert(collection_name=self.settings.qdrant_collection, points=points)

    def search(
        self,
        query_vector: list[float],
        limit: int,
        filters: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        query_filter = None
        if filters:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(key=key, match=models.MatchValue(value=value))
                    for key, value in filters.items()
                    if value
                ]
            )
        response = self.client.query_points(
            collection_name=self.settings.qdrant_collection,
            query=query_vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        hits = response.points
        return [
            {
                "score": hit.score,
                "payload": hit.payload or {},
            }
            for hit in hits
        ]
