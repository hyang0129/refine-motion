"""Core refinement session — owns conversation history and drives the agent."""

from dataclasses import dataclass, field

import anthropic

from agent.codebase import CodebaseIndex

MODEL = "claude-sonnet-4-6"

SYSTEM = """\
You are a senior software architect conducting a voice-first issue refinement session.

Your job:
1. Analyse the target codebase snapshot provided.
2. Ask the engineer ONE focused question per turn — prioritise decisions where their
   aesthetic judgment or domain knowledge matters most (naming, UX flow, error
   strategy, data-model shape, etc.).
3. Synthesise answers into a growing, structured issue spec (title, context, acceptance
   criteria, open questions, out-of-scope).
4. When the spec is detailed enough for an autonomous coding agent to implement without
   ambiguity, reply with the JSON sentinel {"ready": true, "spec": {...}} and stop asking.

Rules:
- Keep replies SHORT — they will be converted to speech. One question max per turn.
- Never ask about things already answered or inferable from the codebase.
- Do not suggest implementation details unless the engineer asks.
"""


@dataclass
class RefinementSession:
    session_id: str
    repo_path: str
    issue_title: str

    history: list[dict] = field(default_factory=list)
    spec: dict = field(default_factory=dict)
    ready: bool = False

    _client: anthropic.AsyncAnthropic = field(
        default_factory=anthropic.AsyncAnthropic, init=False, repr=False
    )
    _index: CodebaseIndex | None = field(default=None, init=False, repr=False)

    async def _get_index(self) -> CodebaseIndex:
        if self._index is None:
            self._index = await CodebaseIndex.build(self.repo_path)
        return self._index

    async def handle_turn(self, user_text: str) -> str:
        index = await self._get_index()

        # First turn: seed the conversation with the codebase snapshot + issue title
        if not self.history:
            seed = (
                f"Issue title: {self.issue_title}\n\n"
                f"Codebase snapshot:\n{index.summary()}"
            )
            self.history.append({"role": "user", "content": seed})

        self.history.append({"role": "user", "content": user_text})

        response = await self._client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=SYSTEM,
            messages=self.history,
        )

        reply = response.content[0].text
        self.history.append({"role": "assistant", "content": reply})

        # Detect readiness sentinel
        if '"ready": true' in reply:
            self.ready = True
            import json, re  # noqa: E401
            m = re.search(r'\{.*\}', reply, re.DOTALL)
            if m:
                try:
                    payload = json.loads(m.group())
                    self.spec = payload.get("spec", {})
                    return "The issue spec is complete. I'll read it back to you now. " + \
                           str(self.spec)
                except json.JSONDecodeError:
                    pass

        return reply
