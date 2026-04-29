# refine-motion · mock v1

Bare-bones local web app that satisfies [#1](../../issues/1):
voice → AI refinement → GitHub issue. No code, no PRs, no commits.

## Run

```bash
cd mvp
make install    # creates .venv, installs deps, copies .env.example → .env
$EDITOR .env    # set GITHUB_TOKEN
make up         # uvicorn on http://127.0.0.1:8000
```

Open `http://127.0.0.1:8000`, type `owner` + `repo`, hit **Start session**, hold the
push-to-talk button to speak. Agent replies via your browser's speech synthesis.

## Prereqs

- Python 3.11+
- The Claude CLI installed and authenticated: `claude` on `$PATH`
  (the backend shells out via `claude -p`)
- A GitHub PAT with `repo` (or `public_repo`) scope
- Modern browser with `MediaRecorder` and `SpeechSynthesis` (Chrome / Safari / Firefox)

## What's in here

```
app.py            FastAPI: 3 endpoints (/sessions, /sessions/{id}/turn, /sessions/{id})
refinement.py     Dialogue state machine + prompt templates
adapters.py       STT (faster-whisper), LLM (subprocess → claude -p), GitHub REST
static/           Single-page UI: index.html · app.js · style.css
```

That's it. No DB, no auth, no deploy. Sessions live in memory; restart wipes them.

## Constraint compliance

| Constraint                          | How                                                              |
| ----------------------------------- | ---------------------------------------------------------------- |
| GitHub is the only write surface    | `adapters.create_issue` / `update_issue` are the only write calls |
| Web app only                        | Static frontend served from `static/`; desktop browser           |
| Turnkey via env keys                | `make install` → set `GITHUB_TOKEN` → `make up`. Free defaults.  |
| `claude -p` is the LLM adapter      | `adapters.claude_print` shells out via `subprocess`              |

## Concessions / known limitations

- **Voice is push-to-talk.** No barge-in, no full duplex.
- **Codebase grounding is shallow.** Top-level file list + first matching
  `CLAUDE.md` / `CONSTITUTION*.md` excerpt. No tree-sitter, no embeddings.
- **In-memory sessions.** Server restart drops state. By design (walking-meeting tool).
- **No retries / no backoff** on `claude -p` failures. They surface as 500s.
- **Text fallback** included for when the mic is broken — not a substitute for the
  voice path; reach for it only when debugging.

## Architectural notes (sticky vs incidental)

These observations come from building the mock; promote any that survive a
second build into the constitution / `CLAUDE.md`.

**Likely sticky:**

- *The LLM owns both "what to ask" and "is the contract ready."* Treating
  refinement as a single LLM-driven loop (rather than a fixed Q-list) keeps
  the dialogue short on simple intents and long on complex ones — matches
  Law 1's "30-second refinement is the goal" framing.
- *Confirmation is a separate LLM call.* Disambiguating "yes" from a
  correction reliably needs context. A regex would lock in too soon.
- *Subprocess adapter for the LLM.* Decouples the product from any specific
  vendor SDK; future swaps (a self-hosted model, a different CLI) are
  zero-touch outside `adapters.py`.

**Likely incidental:**

- FastAPI / faster-whisper / `requests` choices — all swappable.
- The static-frontend split — could become a real SPA, doesn't change the contract.
- In-memory session store — fine for v1, will need persistence at any
  multi-session-per-user volume.

## Cleanup

Per the issue: after this produces signal, **delete the implementation**.
Keep the findings above as draft conventions / architecture notes.
