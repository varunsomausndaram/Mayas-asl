"""REST chat endpoints and session management."""

from __future__ import annotations

import asyncio
from typing import Any

import orjson
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from jarvis.server.auth import require_api_key
from jarvis.server.deps import get_runtime

router = APIRouter(dependencies=[Depends(require_api_key)])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None
    tools: list[str] | None = None


class NewSessionRequest(BaseModel):
    title: str = "New session"


@router.post("/v1/sessions")
async def create_session(body: NewSessionRequest, request: Request) -> dict:
    runtime = get_runtime(request)
    session = await runtime.memory.create_session(title=body.title)
    return session.model_dump()


@router.get("/v1/sessions")
async def list_sessions(request: Request, limit: int = 50) -> dict:
    runtime = get_runtime(request)
    sessions = await runtime.memory.list_sessions(limit=limit)
    return {"sessions": [s.model_dump() for s in sessions]}


@router.get("/v1/sessions/{session_id}/messages")
async def list_messages(session_id: str, request: Request, limit: int = 200) -> dict:
    runtime = get_runtime(request)
    session = await runtime.memory.get_session(session_id)
    if session is None:
        raise HTTPException(404, "session not found")
    msgs = await runtime.memory.list_messages(session_id, limit=limit)
    return {"session": session.model_dump(), "messages": [m.model_dump() for m in msgs]}


@router.delete("/v1/sessions/{session_id}")
async def delete_session(session_id: str, request: Request) -> dict:
    runtime = get_runtime(request)
    ok = await runtime.memory.delete_session(session_id)
    return {"deleted": ok}


@router.post("/v1/chat")
async def chat(body: ChatRequest, request: Request) -> dict:
    runtime = get_runtime(request)
    session_id = body.session_id or (await runtime.memory.create_session()).id
    turn = await runtime.orchestrator.run(session_id, body.message, tool_filter=body.tools)
    return {
        "session_id": session_id,
        "reply": turn.assistant.content,
        "tool_messages": [m.model_dump() for m in turn.tool_messages],
        "usage": turn.usage,
        "aborted": turn.aborted,
    }


@router.post("/v1/chat/stream")
async def chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
    runtime = get_runtime(request)
    session_id = body.session_id or (await runtime.memory.create_session()).id

    async def gen() -> Any:
        yield _sse({"kind": "session", "data": {"id": session_id}})
        try:
            async for event in runtime.orchestrator.run_stream(
                session_id, body.message, tool_filter=body.tools
            ):
                yield _sse(event.to_json())
        except asyncio.CancelledError:
            yield _sse({"kind": "done", "data": {"aborted": True, "reason": "client_disconnect"}})
            raise

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.post("/v1/chat/{session_id}/interrupt")
async def interrupt(session_id: str, request: Request) -> dict:
    runtime = get_runtime(request)
    runtime.orchestrator.interrupt(session_id)
    return {"interrupted": session_id}


def _sse(event: dict) -> bytes:
    return b"data: " + orjson.dumps(event) + b"\n\n"
