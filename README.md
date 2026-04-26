# refine-motion

Voice-first issue refinement for mobile. Engineers speak their intent; an AI agent navigates the codebase, surfaces the decisions that require human taste, and drives a back-and-forth dialogue until the issue is detailed enough for an autonomous coding system to implement.

## How it works

1. **Engineer opens a session** — points the app at a repo and names the issue.
2. **Agent reads the codebase** — scans the relevant files to understand context.
3. **Voice dialogue** — the agent asks one focused question at a time (STT → Claude → TTS). Questions target areas where the engineer's taste matters most: naming, UX flow, error strategy, data-model shape.
4. **Spec emerges** — answers accumulate into a structured issue spec (title, context, acceptance criteria, out-of-scope).
5. **Handoff** — the finished spec is handed to an agentic coding system to implement.

## Stack (planned)

| Layer | Choice |
|---|---|
| Mobile client | PWA (voice API, runs in Safari/Chrome) |
| STT | Whisper (local) or Deepgram |
| Refinement agent | Claude (`claude-sonnet-4-6`) via Anthropic API |
| TTS | Workspace `tts_server` |
| Backend | FastAPI (Python 3.11) |

## Design principles

- **One question per turn.** Voice UX breaks down under multi-part questions.
- **Codebase-grounded.** Every question is informed by what's actually in the repo — no generic checklists.
- **Taste-first.** The agent skips things it can infer; it only asks when the engineer's judgment changes the outcome.
- **Output is agentic-ready.** The session ends when the spec is unambiguous enough for an AI coding agent to implement without follow-up.
