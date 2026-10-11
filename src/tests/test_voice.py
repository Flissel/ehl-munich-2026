"""Checks for src/rag_backend/voice.py (Nordi's speech fallback) with a fake OpenAI client, no network."""
import base64
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_backend import voice as voice_mod  # noqa: E402


class FakeAudio:
    def __init__(self) -> None:
        self.speech_kw: dict = {}
        self.transcribe_kw: dict = {}
        self.speech = SimpleNamespace(create=self._speech)
        self.transcriptions = SimpleNamespace(create=self._transcribe)

    def _speech(self, **kw):
        self.speech_kw = kw
        return SimpleNamespace(read=lambda: b"mp3-bytes")

    def _transcribe(self, **kw):
        self.transcribe_kw = kw
        return SimpleNamespace(text="  Why is R-01 ranked first?  ")


@pytest.fixture
def svc(monkeypatch):
    audio = FakeAudio()
    monkeypatch.setattr(voice_mod, "OpenAI", lambda api_key: SimpleNamespace(audio=audio))
    return voice_mod.VoiceService(SimpleNamespace(openai_api_key="test")), audio


def test_speak_returns_base64_mp3_and_caps_text(svc):
    s, audio = svc
    out = s.speak("x" * (voice_mod.MAX_TTS_CHARS + 50))
    assert base64.b64decode(out["audioBase64"]) == b"mp3-bytes"
    assert out["mimeType"] == "audio/mpeg"
    assert len(audio.speech_kw["input"]) == voice_mod.MAX_TTS_CHARS
    assert audio.speech_kw["voice"] == s.tts_voice


def test_speak_rejects_empty_text(svc):
    s, _ = svc
    with pytest.raises(ValueError):
        s.speak("   ")


def test_transcribe_names_file_after_mime_type(svc):
    s, audio = svc
    out = s.transcribe(base64.b64encode(b"ogg-audio").decode(), "audio/ogg;codecs=opus", "en")
    assert out == {"transcript": "Why is R-01 ranked first?"}
    assert audio.transcribe_kw["file"].name == "speech.ogg"
    assert audio.transcribe_kw["language"] == "en"


@pytest.mark.parametrize("payload", ["", "not base64!", base64.b64encode(b"0" * (voice_mod.MAX_AUDIO_BYTES + 1)).decode()])
def test_transcribe_rejects_bad_audio(svc, payload):
    # All of these must become ValueError, which the API turns into a 400 instead of a 500
    s, _ = svc
    with pytest.raises(ValueError):
        s.transcribe(payload)
