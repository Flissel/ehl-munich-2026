"""Voice for Nordi (Torque's copilot): speech to text and text to speech with the OpenAI key of the RAG backend.

Torque tries Rowboat's own voice API first (needs ElevenLabs/Deepgram or a Rowboat account); this is the fallback
every team PC with the RAG backend has (2026-10-11). Models via env: OPENAI_TTS_MODEL, OPENAI_TTS_VOICE,
OPENAI_STT_MODEL.
"""
from __future__ import annotations

import base64
import io
import os

from openai import OpenAI

from .config import Settings

MAX_TTS_CHARS = 4000
MAX_AUDIO_BYTES = 10 * 1024 * 1024
EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3", "audio/wav": "wav",
       "audio/x-wav": "wav"}


class VoiceService:
    def __init__(self, settings: Settings) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.tts_model = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
        self.tts_voice = os.getenv("OPENAI_TTS_VOICE", "coral")
        self.stt_model = os.getenv("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe")

    def speak(self, text: str, voice: str | None = None) -> dict[str, str]:
        text = text.strip()[:MAX_TTS_CHARS]
        if not text:
            raise ValueError("text is empty")
        res = self.client.audio.speech.create(model=self.tts_model, voice=voice or self.tts_voice, input=text,
                                              response_format="mp3",
                                              instructions="Speak as a calm, clear product analyst. Natural pace.")
        return {"audioBase64": base64.b64encode(res.read()).decode(), "mimeType": "audio/mpeg"}

    def transcribe(self, audio_base64: str, mime_type: str | None = None, language: str | None = None) -> dict[str, str]:
        audio = base64.b64decode(audio_base64)
        if not audio:
            raise ValueError("audio is empty")
        if len(audio) > MAX_AUDIO_BYTES:
            raise ValueError("audio is larger than 10 MB")
        base = (mime_type or "audio/webm").split(";")[0].strip()
        buf = io.BytesIO(audio)
        buf.name = f"speech.{EXT.get(base, 'webm')}"
        kw = {"language": language} if language else {}
        res = self.client.audio.transcriptions.create(model=self.stt_model, file=buf, **kw)
        return {"transcript": (res.text or "").strip()}
