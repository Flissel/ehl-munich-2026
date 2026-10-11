from __future__ import annotations

from typing import Any

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import Settings
from .service import RagService
from .voice import VoiceService


class SearchRequest(BaseModel):
    question: str
    top_k: int | None = Field(default=None, ge=1, le=25)
    filters: dict[str, str] | None = None


class TtsRequest(BaseModel):
    text: str = Field(max_length=8000)
    voice: str | None = None


class TranscribeRequest(BaseModel):
    audioBase64: str
    mimeType: str | None = None
    language: str | None = None


class ChatRequest(BaseModel):
    question: str
    top_k: int | None = Field(default=None, ge=1, le=25)
    filters: dict[str, str] | None = None


def create_app() -> FastAPI:
    app = FastAPI(title="EHL BMW RAG Backend")
    # Torque (a Rowboat app, served at torque.apps.localhost:3210) calls /search from the browser for Nordi.
    origins = os.getenv("RAG_CORS_ORIGINS", "http://torque.apps.localhost:3210").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins if o.strip()],
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
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

    voice = VoiceService(service.settings)

    # Voice for Nordi (Torque): Rowboat's voice API first, these with the backend's OpenAI key as fallback.
    @app.post("/voice/tts")
    def tts(request: TtsRequest) -> dict[str, str]:
        try:
            return voice.speak(request.text, request.voice)
        except ValueError as err:
            raise HTTPException(400, str(err)) from err

    @app.post("/voice/transcribe")
    def transcribe(request: TranscribeRequest) -> dict[str, str]:
        try:
            return voice.transcribe(request.audioBase64, request.mimeType, request.language)
        except ValueError as err:
            raise HTTPException(400, str(err)) from err

    @app.post("/chat")
    def chat(request: ChatRequest) -> dict[str, Any]:
        return service.answer(
            question=request.question,
            top_k=request.top_k,
            filters=request.filters,
        )

    return app


app = create_app()
