"""TTS adapter — delegates to the workspace tts_server (port 8880).

Falls back to a simple pyttsx3-based local synth if the server is unreachable.
"""

from __future__ import annotations

import asyncio
import os

import httpx

TTS_SERVER_URL = os.getenv("TTS_SERVER_URL", "http://localhost:8880")


async def synthesize(text: str) -> bytes:
    """Return MP3 bytes for the given text."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{TTS_SERVER_URL}/tts",
                json={"text": text, "voice": "default"},
            )
            r.raise_for_status()
            return r.content
    except Exception:
        return await asyncio.to_thread(_local_synth, text)


def _local_synth(text: str) -> bytes:
    """Minimal fallback: pyttsx3 → WAV bytes (no external dependency on tts_server)."""
    import io
    import tempfile
    from pathlib import Path

    try:
        import pyttsx3
        engine = pyttsx3.init()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name
        engine.save_to_file(text, tmp)
        engine.runAndWait()
        data = Path(tmp).read_bytes()
        Path(tmp).unlink(missing_ok=True)
        return data
    except Exception:
        # Last resort: return empty bytes — caller still has the text header
        return b""
