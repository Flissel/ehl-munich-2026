from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .config import Settings
from .service import RagService


class SearchRequest(BaseModel):
    question: str
    top_k: int | None = Field(default=None, ge=1, le=25)
    filters: dict[str, str] | None = None


class ChatRequest(BaseModel):
    question: str
    top_k: int | None = Field(default=None, ge=1, le=25)
    filters: dict[str, str] | None = None


def create_app() -> FastAPI:
    app = FastAPI(title="EHL BMW RAG Backend")
    service = RagService(Settings.from_env())

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/search")
    def search(request: SearchRequest) -> dict[str, Any]:
        hits = service.retrieve(
            question=request.question,
            top_k=request.top_k,
            filters=request.filters,
        )
        return {"results": [service._source_from_hit(hit) | {"text": hit["payload"].get("text", "")} for hit in hits]}

    @app.post("/chat")
    def chat(request: ChatRequest) -> dict[str, Any]:
        return service.answer(
            question=request.question,
            top_k=request.top_k,
            filters=request.filters,
        )

    return app


app = create_app()
