"""FastAPI entry point for refine-motion."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.routers import sessions, voice

app = FastAPI(title="refine-motion", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for prod
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(voice.router, prefix="/voice", tags=["voice"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
