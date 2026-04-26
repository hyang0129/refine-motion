# refine-motion

Voice-first issue refinement platform for mobile. Architects and engineers speak
their intent; a refinement agent navigates the target codebase, surfaces taste-dependent
decisions, and drives a back-and-forth dialogue until the issue is implementation-ready.

## Architecture

```
Mobile PWA (mic → speaker)
    │  WebSocket / REST
FastAPI server  (server/)
    ├── STT   — Whisper (local) or Deepgram (cloud)
    ├── Agent — Claude via Anthropic SDK  (agent/)
    │             reads target repo, asks clarifying Qs
    └── TTS   — calls workspace tts_server (port 8880)
```

## Python

- Version: 3.11
- Venv: `refine-motion/.venv/`
- Activate: `source .venv/bin/activate`
- Install: `pip install -e ".[dev]"`

## Key Commands

```bash
# Start backend
uvicorn server.main:app --reload --port 8900

# Run tests
pytest tests/
```

## Repo-Specific Rules

1. The **target repo** being refined is supplied at session start (a path or GitHub URL).
   The agent may READ that repo but must NEVER write to it.
2. STT and TTS are swappable; hide them behind `agent/stt.py` and `agent/tts.py` adapters.
3. The agent's question list is derived from codebase analysis — never hardcoded.
4. Session state lives in-memory; persistence is out of scope for v0.
5. Claude model: `claude-sonnet-4-6` for the refinement agent.
