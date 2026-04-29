"""
Adapters for the three external surfaces refine-motion mock v1 talks to:

  - STT: faster-whisper (local, free).
  - LLM: shells out to `claude -p`. No direct Anthropic SDK by design.
  - GitHub: PAT + REST. Issue create/update only — no other writes.

Everything here is a thin wrapper. State lives in refinement.py; this file
just translates between the world and Python types.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# STT — faster-whisper
# ---------------------------------------------------------------------------

_whisper_model = None


def _get_whisper():
    """Lazy-load the whisper model on first use; reused across requests."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        size = os.getenv("WHISPER_MODEL", "base.en")
        _whisper_model = WhisperModel(size, device="cpu", compute_type="int8")
    return _whisper_model


def transcribe(audio_bytes: bytes, suffix: str = ".webm") -> str:
    """Transcribe an audio blob to text. Returns the joined transcript."""
    model = _get_whisper()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        segments, _info = model.transcribe(tmp_path, language="en")
        text = " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
    return text


# ---------------------------------------------------------------------------
# LLM — `claude -p`
# ---------------------------------------------------------------------------


@dataclass
class ClaudeError(Exception):
    """Raised when `claude -p` fails or returns unparseable output."""

    message: str
    raw_output: str = ""

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.message}\n--- raw ---\n{self.raw_output[:2000]}"


def claude_print(prompt: str, timeout: int = 180) -> str:
    """Invoke `claude -p` via stdin; return raw stdout."""
    cli = os.getenv("CLAUDE_CLI", "claude")
    try:
        result = subprocess.run(
            [cli, "-p"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as e:
        raise ClaudeError(
            f"`{cli}` not found on PATH. Set CLAUDE_CLI in .env or install Claude CLI."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise ClaudeError(f"`{cli} -p` timed out after {timeout}s") from e

    if result.returncode != 0:
        raise ClaudeError(
            f"`{cli} -p` exited {result.returncode}: {result.stderr.strip()}",
            raw_output=result.stdout,
        )
    return result.stdout


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def claude_json(prompt: str) -> dict[str, Any]:
    """Run claude -p and parse the first JSON object out of its output.

    The prompt itself is responsible for instructing the model to return JSON.
    We tolerate either a bare JSON object or a fenced code block.
    """
    raw = claude_print(prompt)
    # First try fenced block
    m = _JSON_FENCE.search(raw)
    candidate = m.group(1) if m else raw

    # If still not parseable, try greedy braces match
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        first = candidate.find("{")
        last = candidate.rfind("}")
        if first != -1 and last != -1 and last > first:
            try:
                return json.loads(candidate[first : last + 1])
            except json.JSONDecodeError as e:
                raise ClaudeError(f"could not parse JSON from claude output: {e}", raw)
        raise ClaudeError("no JSON object found in claude output", raw)


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"


def _gh_headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set in environment / .env")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def list_repo_files(owner: str, repo: str, max_paths: int = 200) -> list[str]:
    """Cheap codebase grounding: a flat list of paths from the default branch tree.

    Bare-bones — no ranking, no semantic search. Enough to give the LLM a sense
    of layout. Trims to max_paths to keep the prompt small.
    """
    repo_info = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}", headers=_gh_headers(), timeout=20
    )
    repo_info.raise_for_status()
    default_branch = repo_info.json().get("default_branch", "main")

    tree_resp = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{default_branch}",
        headers=_gh_headers(),
        params={"recursive": "1"},
        timeout=20,
    )
    tree_resp.raise_for_status()
    tree = tree_resp.json().get("tree", [])
    paths = [item["path"] for item in tree if item.get("type") == "blob"]
    return paths[:max_paths]


def get_file_excerpt(
    owner: str, repo: str, path: str, max_chars: int = 4000
) -> str | None:
    """Fetch a file's text content (utf-8). Returns None if missing or binary."""
    resp = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
        headers=_gh_headers(),
        timeout=20,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    import base64

    data = resp.json()
    if data.get("encoding") != "base64":
        return None
    try:
        text = base64.b64decode(data["content"]).decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text[:max_chars]


def get_issue(owner: str, repo: str, number: int) -> dict[str, Any]:
    resp = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/issues/{number}",
        headers=_gh_headers(),
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def create_issue(owner: str, repo: str, title: str, body: str) -> dict[str, Any]:
    resp = requests.post(
        f"{GITHUB_API}/repos/{owner}/{repo}/issues",
        headers=_gh_headers(),
        json={"title": title, "body": body},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def update_issue(
    owner: str, repo: str, number: int, *, title: str | None = None, body: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    resp = requests.patch(
        f"{GITHUB_API}/repos/{owner}/{repo}/issues/{number}",
        headers=_gh_headers(),
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
