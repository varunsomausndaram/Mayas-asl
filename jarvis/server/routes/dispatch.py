"""Claude Code dispatch endpoints."""

from __future__ import annotations

from typing import Any

import orjson
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from jarvis.server.auth import require_api_key
from jarvis.server.deps import get_runtime

router = APIRouter(dependencies=[Depends(require_api_key)])


class DispatchBody(BaseModel):
    prompt: str = Field(min_length=1)
    repo_url: str | None = None
    workspace: str | None = None


@router.post("/v1/dispatch")
async def dispatch(body: DispatchBody, request: Request) -> dict:
    runtime = get_runtime(request)
    job = await runtime.dispatcher.dispatch(
        body.prompt, repo_url=body.repo_url, workspace=body.workspace
    )
    return job.to_json()


@router.get("/v1/dispatch/jobs")
async def list_jobs(request: Request) -> dict:
    runtime = get_runtime(request)
    return {"jobs": [j.to_json() for j in runtime.dispatcher.jobs()]}


@router.get("/v1/dispatch/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> dict:
    runtime = get_runtime(request)
    job = runtime.dispatcher.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job.to_json()


@router.post("/v1/dispatch/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, request: Request) -> dict:
    runtime = get_runtime(request)
    cancelled = await runtime.dispatcher.cancel(job_id)
    return {"cancelled": cancelled}


@router.get("/v1/dispatch/jobs/{job_id}/stream")
async def stream_job(job_id: str, request: Request) -> StreamingResponse:
    runtime = get_runtime(request)
    job = runtime.dispatcher.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")

    async def gen() -> Any:
        async for event in runtime.dispatcher.stream(job_id):
            yield b"data: " + orjson.dumps(event.to_json()) + b"\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
