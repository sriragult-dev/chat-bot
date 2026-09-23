"""DataMentor API - a Gemini-backed chat bot for data science and startup guidance."""

import json
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from app import gemini
from app.config import settings
from app.memory import store
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    HistoryResponse,
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="DataMentor API",
    description=(
        "A Gemini-powered chat bot that answers data science questions and gives "
        "practical guidance to startups."
    ),
    version="1.0.0",
)

# Open CORS: this is a local development project served from the same origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_session(session_id: str | None) -> str:
    return session_id or str(uuid.uuid4())


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Liveness check. Does not call Gemini."""
    return HealthResponse(
        status="ok",
        model=settings.gemini_model,
        active_sessions=store.count(),
    )


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
def chat(request: ChatRequest) -> ChatResponse:
    """Ask a question and get the complete answer in one response."""
    session_id = _resolve_session(request.session_id)
    history = store.get_history(session_id)

    try:
        reply = gemini.ask(history, request.message)
    except gemini.GeminiError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini API error: {exc}")

    store.append(session_id, "user", request.message)
    store.append(session_id, "model", reply)
    return ChatResponse(session_id=session_id, reply=reply)


@app.post("/chat/stream", tags=["chat"])
def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Same as /chat, but streams the answer as server-sent events.

    Events carry `{"session_id": ..., "delta": ...}` and the stream ends with a
    `[DONE]` payload. The turn is only written to memory once the answer is
    complete, so an aborted stream leaves no partial history behind.
    """
    session_id = _resolve_session(request.session_id)
    history = store.get_history(session_id)

    def event_source():
        chunks: list[str] = []
        try:
            for chunk in gemini.ask_stream(history, request.message):
                chunks.append(chunk)
                payload = {"session_id": session_id, "delta": chunk}
                yield f"data: {json.dumps(payload)}\n\n"
        except gemini.GeminiError as exc:
            error = {"session_id": session_id, "error": f"Gemini API error: {exc}"}
            yield f"data: {json.dumps(error)}\n\n"
            yield "data: [DONE]\n\n"
            return

        reply = "".join(chunks).strip()
        if reply:
            store.append(session_id, "user", request.message)
            store.append(session_id, "model", reply)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/history/{session_id}", response_model=HistoryResponse, tags=["session"])
def history(session_id: str) -> HistoryResponse:
    """Show what the bot currently remembers for a session."""
    return HistoryResponse(session_id=session_id, turns=store.get_history(session_id))


@app.delete("/session/{session_id}", tags=["session"])
def reset_session(session_id: str) -> dict:
    """Clear a session's memory and start a fresh conversation."""
    return {"session_id": session_id, "cleared": store.reset(session_id)}
