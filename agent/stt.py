"""STT adapter — Whisper (local) by default, swap for Deepgram/cloud as needed."""

from __future__ import annotations

import io
import asyncio
import tempfile
from pathlib import Path


async def transcribe(audio_bytes: bytes) -> str:
    """Return transcript string from raw audio bytes (WAV or MP3)."""
    return await asyncio.to_thread(_whisper_transcribe, audio_bytes)


def _whisper_transcribe(audio_bytes: bytes) -> str:
    import whisper  # lazy import — model load is slow

    model = _get_model()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        result = model.transcribe(tmp_path)
        return result["text"].strip()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


_model_cache: "whisper.Whisper | None" = None  # type: ignore[name-defined]


def _get_model():
    global _model_cache
    if _model_cache is None:
        import whisper
        _model_cache = whisper.load_model("base")
    return _model_cache
