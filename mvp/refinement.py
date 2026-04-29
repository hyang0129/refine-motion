"""
Refinement state machine.

Sessions live entirely in process memory — restart the server, sessions die.
That's the MVP scope: a walking-meeting tool, not a continuous-workday system
(see Corollary 1+2.1 in the constitution).

Two states:
  - "active": agent is asking questions, architect is answering. Each turn,
    the LLM either emits the next question or declares the contract ready.
  - "awaiting_confirmation": the contract has been read back; the next user
    turn is interpreted as confirm or correct.

Successful confirmation moves the session to "submitted" and writes the issue.
"""

from __future__ import annotations

import secrets
import textwrap
from dataclasses import dataclass, field
from typing import Any, Literal

from adapters import (
    claude_json,
    create_issue,
    get_file_excerpt,
    get_issue,
    list_repo_files,
    update_issue,
)

Status = Literal["active", "awaiting_confirmation", "submitted"]


@dataclass
class Session:
    id: str
    owner: str
    repo: str
    issue_number: int | None  # set when refining an existing issue
    file_paths: list[str]
    claude_md: str | None
    existing_issue: dict[str, Any] | None
    transcript: list[dict[str, str]] = field(default_factory=list)
    contract: dict[str, Any] | None = None
    status: Status = "active"
    issue_url: str | None = None


_sessions: dict[str, Session] = {}


def _new_id() -> str:
    return secrets.token_urlsafe(8)


# ---------------------------------------------------------------------------
# Public ops
# ---------------------------------------------------------------------------


def start_session(owner: str, repo: str, issue_number: int | None) -> tuple[Session, str]:
    """Create a session and return (session, opening prompt for the architect)."""
    file_paths = list_repo_files(owner, repo)

    # Try to fetch CLAUDE.md or CONSTITUTION.md as a quick conventions excerpt.
    claude_md = None
    for candidate in ("CLAUDE.md", "CONSTITUTION.mini.md", "CONSTITUTION.md"):
        excerpt = get_file_excerpt(owner, repo, candidate, max_chars=3000)
        if excerpt:
            claude_md = excerpt
            break

    existing_issue = None
    if issue_number is not None:
        existing_issue = get_issue(owner, repo, issue_number)

    sess = Session(
        id=_new_id(),
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        file_paths=file_paths,
        claude_md=claude_md,
        existing_issue=existing_issue,
    )
    _sessions[sess.id] = sess

    if existing_issue:
        opener = (
            f"I've loaded issue #{issue_number} on {owner}/{repo}: "
            f"\"{existing_issue['title']}\". What would you like to refine about it?"
        )
    else:
        opener = (
            f"Okay, I'm looking at {owner}/{repo}. "
            "What do you want to do — describe it in your own words."
        )
    sess.transcript.append({"role": "agent", "text": opener})
    return sess, opener


def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def take_turn(sess: Session, user_text: str) -> dict[str, Any]:
    """Process one architect turn. Returns a dict suitable for the JSON response."""
    sess.transcript.append({"role": "user", "text": user_text})

    if sess.status == "awaiting_confirmation":
        decision = _decide_confirmation(sess, user_text)
        if decision["decision"] == "confirm":
            return _submit(sess)
        # Correction: append a correction note and resume refinement.
        sess.status = "active"
        sess.transcript.append(
            {"role": "agent", "text": f"(noted correction: {decision.get('correction_note', '')})"}
        )
        # Fall through into active-mode refinement using the correction note as
        # the latest signal.
        user_text = decision.get("correction_note") or user_text

    return _refine_step(sess, user_text)


# ---------------------------------------------------------------------------
# Internal — LLM dialogue
# ---------------------------------------------------------------------------


def _format_transcript(transcript: list[dict[str, str]], limit: int = 12) -> str:
    tail = transcript[-limit:]
    return "\n".join(f"{t['role'].upper()}: {t['text']}" for t in tail)


def _refine_step(sess: Session, latest_user_text: str) -> dict[str, Any]:
    prompt = _build_refinement_prompt(sess, latest_user_text)
    result = claude_json(prompt)

    if result.get("ready"):
        sess.contract = {
            "title": result.get("title", "Untitled"),
            "job_statement": result.get("job_statement", ""),
            "behavioral_intent": result.get("behavioral_intent", []),
        }
        sess.status = "awaiting_confirmation"
        readback = _format_readback(sess.contract)
        sess.transcript.append({"role": "agent", "text": readback})
        return {
            "status": sess.status,
            "agent_text": readback,
            "contract": sess.contract,
        }

    next_q = result.get("next_question", "Could you tell me more about that?")
    sess.transcript.append({"role": "agent", "text": next_q})
    return {
        "status": sess.status,
        "agent_text": next_q,
        "contract": None,
    }


def _decide_confirmation(sess: Session, user_text: str) -> dict[str, Any]:
    prompt = _build_confirmation_prompt(sess, user_text)
    return claude_json(prompt)


def _submit(sess: Session) -> dict[str, Any]:
    contract = sess.contract or {}
    body = _format_issue_body(contract)
    title = contract.get("title", "Refined issue")

    if sess.issue_number is not None:
        issue = update_issue(sess.owner, sess.repo, sess.issue_number, title=title, body=body)
    else:
        issue = create_issue(sess.owner, sess.repo, title, body)

    sess.status = "submitted"
    sess.issue_url = issue["html_url"]
    closing = f"Submitted: {sess.issue_url}"
    sess.transcript.append({"role": "agent", "text": closing})
    return {
        "status": sess.status,
        "agent_text": closing,
        "contract": sess.contract,
        "issue_url": sess.issue_url,
    }


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_REFINE_TEMPLATE = """\
You are the refinement agent for refine-motion. The architect speaks intent;
you ask one focused question per turn until the contract is unambiguous.

Repo: {owner}/{repo}
Top-level files (truncated):
{file_list}

{conventions_block}

{existing_issue_block}

Conversation so far:
{transcript}

Architect's latest turn: "{latest_user_text}"

Decide: ask one more question, or declare the contract ready.

A contract is ready when you can write:
  - A clear job statement: "When [situation], I want to [motivation], so I can [outcome]"
  - 3-7 behavioral-intent bullets describing what should be true after the change

Hard rules:
  - One question per turn. Never compound.
  - Ground questions in the repo when possible (reference specific files / patterns).
  - Taste-first: skip what you can infer; ask only when the architect's
    judgment changes the outcome.
  - Stop refining as soon as the contract is unambiguous. A 30-second
    refinement that ends "yes, that's what I meant" is the goal.

Output STRICT JSON, no commentary, no fences:

If not ready:
{{"ready": false, "next_question": "<one focused question>"}}

If ready:
{{"ready": true,
  "title": "<short issue title>",
  "job_statement": "When ..., I want to ..., so I can ...",
  "behavioral_intent": ["...", "...", "..."]}}
"""


_CONFIRM_TEMPLATE = """\
The architect was just read this contract:

Title: {title}

Job statement:
{job_statement}

Behavioral intent:
{bullets}

Architect's spoken response: "{user_text}"

Decide:
  - "confirm" if the architect approves (e.g. "yes", "ship it", "looks good")
  - "correct" if they want to change something (capture the correction)

Output STRICT JSON, no fences:
{{"decision": "confirm"}}
or
{{"decision": "correct", "correction_note": "<what to change>"}}
"""


def _build_refinement_prompt(sess: Session, latest_user_text: str) -> str:
    file_list = "\n".join(f"  - {p}" for p in sess.file_paths[:80])
    conventions_block = (
        f"Repo conventions / constitution (excerpt):\n{sess.claude_md}\n"
        if sess.claude_md
        else "(no CLAUDE.md or constitution found in repo)\n"
    )
    if sess.existing_issue:
        existing_issue_block = textwrap.dedent(
            f"""\
            Refining existing issue #{sess.existing_issue['number']}:
            Title: {sess.existing_issue['title']}
            Body:
            {sess.existing_issue.get('body') or '(empty)'}
            """
        )
    else:
        existing_issue_block = "Mode: creating a new issue."

    return _REFINE_TEMPLATE.format(
        owner=sess.owner,
        repo=sess.repo,
        file_list=file_list,
        conventions_block=conventions_block,
        existing_issue_block=existing_issue_block,
        transcript=_format_transcript(sess.transcript),
        latest_user_text=latest_user_text,
    )


def _build_confirmation_prompt(sess: Session, user_text: str) -> str:
    contract = sess.contract or {}
    bullets = "\n".join(f"  - {b}" for b in contract.get("behavioral_intent", []))
    return _CONFIRM_TEMPLATE.format(
        title=contract.get("title", ""),
        job_statement=contract.get("job_statement", ""),
        bullets=bullets,
        user_text=user_text,
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def _format_readback(contract: dict[str, Any]) -> str:
    bullets = "; ".join(contract.get("behavioral_intent", []))
    return (
        f"Here's the contract. Title: {contract.get('title', '')}. "
        f"Job statement: {contract.get('job_statement', '')}. "
        f"Behavioral intent: {bullets}. Does that capture what you meant?"
    )


def _format_issue_body(contract: dict[str, Any]) -> str:
    lines = [
        "## Job statement",
        "",
        contract.get("job_statement", "").strip(),
        "",
        "## Behavioral intent",
        "",
    ]
    for b in contract.get("behavioral_intent", []):
        lines.append(f"- {b}")
    lines += ["", "---", "", "_Refined via refine-motion mock v1._"]
    return "\n".join(lines)
