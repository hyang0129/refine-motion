"""Voice I/O endpoints.

POST /voice/{session_id}/turn   — upload audio → get audio reply
WS   /voice/{session_id}/stream — real-time bidirectional (future)
"""

import io

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from agent.stt import transcribe
from agent.tts import synthesize
from server.routers.sessions import _sessions

router = APIRouter()


@router.post("/{session_id}/turn")
async def voice_turn(session_id: str, audio: UploadFile) -> StreamingResponse:
    """Accept a WAV/MP3 clip, return the agent's reply as audio."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "session not found")

    raw = await audio.read()
    user_text = await transcribe(raw)
    reply_text = await session.handle_turn(user_text)
    reply_audio = await synthesize(reply_text)

    return StreamingResponse(
        io.BytesIO(reply_audio),
        media_type="audio/mpeg",
        headers={"X-Transcript": reply_text},
    )
