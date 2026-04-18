"""WebSocket — bidirectional streaming with barge-in support.

Protocol:

* First client frame: ``{"type": "auth", "api_key": "..."}``.
* Subsequent client frames:
    * ``{"type": "chat", "message": "...", "session_id": "..."}``
    * ``{"type": "interrupt"}`` — barge-in / cancel the in-flight turn.
    * ``{"type": "approve", "id": "...", "decision": "approved_once" | ...}``
    * ``{"type": "ping"}``

* Server frames mirror :class:`OrchestratorEvent` plus an ``approval_request``
  frame for pending approvals and a ``pong`` for keep-alive.
"""

from __future__ import annotations

import asyncio
import contextlib
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from jarvis.core.permissions import ApprovalDecision
from jarvis.logging import get_logger
from jarvis.server.auth import websocket_api_key_ok

log = get_logger(__name__)
router = APIRouter()


@router.websocket("/v1/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    runtime = getattr(ws.app.state, "runtime", None)
    approvals = getattr(ws.app.state, "approvals", None)
    if runtime is None or approvals is None:
        await ws.send_json({"type": "error", "message": "runtime unavailable"})
        await ws.close(code=1011)
        return

    try:
        first = await asyncio.wait_for(ws.receive_json(), timeout=15)
    except (asyncio.TimeoutError, WebSocketDisconnect, json.JSONDecodeError):
        await ws.close(code=4001)
        return
    if (first or {}).get("type") != "auth" or not websocket_api_key_ok(first.get("api_key") or ""):
        await ws.send_json({"type": "error", "message": "auth failed"})
        await ws.close(code=4003)
        return
    await ws.send_json({"type": "ready"})

    active_task: asyncio.Task | None = None
    active_session: str | None = None

    async def relay_bus() -> None:
        async with await runtime.bus.subscribe("approvals") as sub:
            async for event in sub:
                try:
                    await ws.send_json({"type": event.type, **event.data})
                except Exception:
                    return

    async def relay_scheduler() -> None:
        async with await runtime.bus.subscribe("scheduler") as sub:
            async for event in sub:
                try:
                    await ws.send_json({"type": "scheduler_fired", **event.data})
                except Exception:
                    return

    async def relay_dispatch() -> None:
        async with await runtime.bus.subscribe("dispatch") as sub:
            async for event in sub:
                try:
                    await ws.send_json({"type": f"dispatch_{event.type}", **event.data})
                except Exception:
                    return

    bus_tasks = [
        asyncio.create_task(relay_bus(), name="ws-approvals"),
        asyncio.create_task(relay_scheduler(), name="ws-scheduler"),
        asyncio.create_task(relay_dispatch(), name="ws-dispatch"),
    ]

    try:
        while True:
            try:
                frame = await ws.receive_json()
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "invalid json"})
                continue

            kind = frame.get("type")
            if kind == "ping":
                await ws.send_json({"type": "pong", "ts": frame.get("ts")})
                continue

            if kind == "interrupt":
                if active_session is not None:
                    runtime.orchestrator.interrupt(active_session)
                    await ws.send_json({"type": "interrupted", "session_id": active_session})
                continue

            if kind == "approve":
                approval_id = frame.get("id")
                decision = frame.get("decision") or "denied"
                try:
                    resolved = await approvals.resolve(approval_id, ApprovalDecision(decision))
                except ValueError:
                    resolved = False
                await ws.send_json({"type": "approve_ack", "id": approval_id, "ok": resolved})
                continue

            if kind == "chat":
                if active_task is not None and not active_task.done():
                    await ws.send_json({"type": "error", "message": "turn already in progress"})
                    continue
                message = (frame.get("message") or "").strip()
                if not message:
                    await ws.send_json({"type": "error", "message": "empty message"})
                    continue
                session_id = frame.get("session_id") or (await runtime.memory.create_session()).id
                active_session = session_id
                await ws.send_json({"type": "session", "id": session_id})

                async def run_turn(sid: str, msg: str) -> None:
                    try:
                        async for event in runtime.orchestrator.run_stream(sid, msg):
                            await ws.send_json({"type": event.kind.value, **event.data})
                    except Exception as exc:  # pragma: no cover
                        await ws.send_json({"type": "error", "message": str(exc)})

                active_task = asyncio.create_task(run_turn(session_id, message))
                continue

            await ws.send_json({"type": "error", "message": f"unknown type: {kind!r}"})
    finally:
        for t in bus_tasks:
            t.cancel()
        if active_task is not None and not active_task.done():
            active_task.cancel()
            with contextlib.suppress(BaseException):
                await active_task
        with contextlib.suppress(Exception):
            await ws.close()
