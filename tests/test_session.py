"""Smoke tests for RefinementSession — no LLM calls, mocked."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from agent.session import RefinementSession


@pytest.fixture
def session(tmp_path):
    # Write a minimal fake repo
    (tmp_path / "main.py").write_text("def hello(): pass\n")
    return RefinementSession(
        session_id="test-123",
        repo_path=str(tmp_path),
        issue_title="Add greeting endpoint",
    )


@pytest.mark.asyncio
async def test_first_turn_seeds_history(session):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="What format should the greeting take?")]

    with patch.object(session._client.messages, "create", new=AsyncMock(return_value=mock_response)):
        reply = await session.handle_turn("I want to add a /greet route")

    assert reply == "What format should the greeting take?"
    # history: seed + user turn + assistant
    assert len(session.history) == 3


@pytest.mark.asyncio
async def test_ready_sentinel_detected(session):
    sentinel = '{"ready": true, "spec": {"title": "Add /greet", "criteria": ["returns JSON"]}}'
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=sentinel)]

    with patch.object(session._client.messages, "create", new=AsyncMock(return_value=mock_response)):
        await session.handle_turn("That covers it")

    assert session.ready is True
    assert session.spec["title"] == "Add /greet"
