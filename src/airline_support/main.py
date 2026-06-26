from __future__ import annotations

import json
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from airline_support.agent import stream_agent_response
from airline_support.sessions import (
    append_message,
    create_session,
    list_sessions,
    read_messages,
    validate_session_id,
)
from airline_support.walkthrough import (
    PROMPT_TRACK_ID,
    walkthrough_status,
)


load_dotenv()

app = FastAPI(title="RELAI Airline Onboarding API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, alias="sessionId")
    message: str = Field(min_length=1, max_length=4000)


def sse_event(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/sessions")
def create_chat_session() -> dict[str, object]:
    return {"session": create_session()}


@app.get("/api/sessions")
def get_chat_sessions() -> dict[str, object]:
    return {"sessions": list_sessions()}


@app.get("/api/sessions/{session_id}")
def get_chat_session(session_id: str) -> dict[str, object]:
    try:
        validate_session_id(session_id)
        return {"id": session_id, "messages": read_messages(session_id)}
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="session not found") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/chat/stream")
async def stream_chat(request: ChatRequest) -> StreamingResponse:
    session = create_session() if request.session_id is None else None
    session_id = request.session_id or session.id
    try:
        validate_session_id(session_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    async def stream() -> AsyncIterator[str]:
        try:
            append_message(session_id, "user", request.message)
            messages = read_messages(session_id)
            chunks: list[str] = []
            yield sse_event("session", {"sessionId": session_id})
            async for delta in stream_agent_response(messages):
                chunks.append(delta)
                yield sse_event("token", {"delta": delta})
            assistant_text = "".join(chunks).strip()
            if assistant_text:
                append_message(session_id, "assistant", assistant_text)
            yield sse_event("done", {"sessionId": session_id, "message": assistant_text})
        except Exception as error:
            yield sse_event("error", {"message": str(error)})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/walkthrough/status")
def get_walkthrough_status(
    track_id: str = Query(default=PROMPT_TRACK_ID, alias="trackId"),
    env_name: str | None = Query(default=None, alias="envName"),
    prompt: str | None = Query(default=None),
    feedback: str | None = Query(default=None),
    session_id: str | None = Query(default=None, alias="sessionId"),
) -> dict[str, object]:
    return walkthrough_status(
        track_id=track_id,
        env_name=env_name,
        prompt=prompt,
        feedback=feedback,
        session_id=session_id,
    )
