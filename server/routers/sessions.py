"""Session lifecycle endpoints.

A session ties together: a target repo path, the running conversation history,
and the derived issue spec.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from agent.session import RefinementSession

router = APIRouter()

# In-memory store — v0 only
_sessions: dict[str, RefinementSession] = {}


class CreateSessionRequest(BaseModel):
    repo_path: str  # absolute path or GitHub URL of the target codebase
    issue_title: str


class SessionSummary(BaseModel):
    session_id: str
    repo_path: str
    issue_title: str
    turn_count: int
    ready: bool  # True when agent judges the spec is implementation-ready


@router.post("/", response_model=SessionSummary, status_code=201)
async def create_session(body: CreateSessionRequest) -> SessionSummary:
    sid = str(uuid.uuid4())
    session = RefinementSession(
        session_id=sid,
        repo_path=body.repo_path,
        issue_title=body.issue_title,
    )
    _sessions[sid] = session
    return _to_summary(session)


@router.get("/{session_id}", response_model=SessionSummary)
async def get_session(session_id: str) -> SessionSummary:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "session not found")
    return _to_summary(session)


@router.get("/{session_id}/spec")
async def get_spec(session_id: str) -> dict:
    """Return the current structured issue spec."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "session not found")
    return session.spec


def _to_summary(s: RefinementSession) -> SessionSummary:
    return SessionSummary(
        session_id=s.session_id,
        repo_path=s.repo_path,
        issue_title=s.issue_title,
        turn_count=len(s.history),
        ready=s.ready,
    )
