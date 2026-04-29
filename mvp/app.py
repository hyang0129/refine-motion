"""
FastAPI entrypoint for refine-motion mock v1.

Endpoints
---------
  GET  /                       static frontend
  GET  /health                 liveness probe
  POST /sessions               start a session against a target repo
  POST /sessions/{id}/turn     accept an audio blob, advance the dialogue
  GET  /sessions/{id}          session debug view

The HTTP surface is deliberately tiny: one endpoint to start, one to step.
All actual work is in adapters.py and refinement.py.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import refinement
from adapters import ClaudeError, transcribe

load_dotenv()

app = FastAPI(title="refine-motion mock v1", version="0.1")

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/health")
def health():
    return {"ok": True, "claude_cli": os.getenv("CLAUDE_CLI", "claude")}


@app.post("/sessions")
def post_session(payload: dict):
    """Start a new refinement session.

    Expects: {"owner": "...", "repo": "...", "issue_number": 42 | null}
    """
    owner = (payload.get("owner") or "").strip()
    repo = (payload.get("repo") or "").strip()
    issue_number = payload.get("issue_number")
    if not owner or not repo:
        raise HTTPException(400, "owner and repo are required")
    if issue_number is not None:
        try:
            issue_number = int(issue_number)
        except (ValueError, TypeError):
            raise HTTPException(400, "issue_number must be an integer if provided")

    try:
        sess, opener = refinement.start_session(owner, repo, issue_number)
    except Exception as e:  # bubble GitHub / network errors as 502
        raise HTTPException(502, f"failed to start session: {e}")

    return {"session_id": sess.id, "agent_text": opener, "status": sess.status}


@app.post("/sessions/{session_id}/turn")
async def post_turn(
    session_id: str,
    audio: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
):
    """Advance the dialogue. Accepts either an uploaded audio blob OR a text fallback.

    The text fallback exists so the loop can be exercised without a working mic
    (and so the system tests trivially without faster-whisper installed).
    """
    sess = refinement.get_session(session_id)
    if sess is None:
        raise HTTPException(404, "unknown session")
    if sess.status == "submitted":
        raise HTTPException(409, "session already submitted")

    if audio is not None:
        blob = await audio.read()
        if not blob:
            raise HTTPException(400, "empty audio upload")
        suffix = "." + (audio.filename or "audio.webm").rsplit(".", 1)[-1]
        try:
            user_text = transcribe(blob, suffix=suffix)
        except Exception as e:
            raise HTTPException(500, f"transcription failed: {e}")
    elif text is not None:
        user_text = text.strip()
    else:
        raise HTTPException(400, "provide either an audio file or a 'text' form field")

    if not user_text:
        raise HTTPException(400, "could not extract any text from input")

    try:
        result = refinement.take_turn(sess, user_text)
    except ClaudeError as e:
        raise HTTPException(500, f"claude -p failed: {e.message}")
    except Exception as e:
        raise HTTPException(502, f"turn failed: {e}")

    return JSONResponse(
        {
            "user_text": user_text,
            "agent_text": result["agent_text"],
            "status": result["status"],
            "contract": result.get("contract"),
            "issue_url": result.get("issue_url"),
        }
    )


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    sess = refinement.get_session(session_id)
    if sess is None:
        raise HTTPException(404, "unknown session")
    return {
        "id": sess.id,
        "owner": sess.owner,
        "repo": sess.repo,
        "issue_number": sess.issue_number,
        "status": sess.status,
        "contract": sess.contract,
        "issue_url": sess.issue_url,
        "transcript": sess.transcript,
    }


# Mount static last so API routes win on conflicts.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
