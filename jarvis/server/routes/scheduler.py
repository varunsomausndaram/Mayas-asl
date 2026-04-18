"""Scheduler REST endpoints — list, create, delete jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from jarvis.scheduler.engine import JobKind, JobStatus, new_job
from jarvis.server.auth import require_api_key
from jarvis.server.deps import get_runtime

router = APIRouter(dependencies=[Depends(require_api_key)])


class JobCreate(BaseModel):
    kind: str = Field(description="prompt | reminder | timer | webhook")
    title: str
    cron: str | None = None
    every_seconds: int | None = Field(default=None, ge=1)
    at_timestamp: float | None = None
    prompt: str | None = None
    message: str | None = None
    webhook_url: str | None = None
    payload: dict | None = None


@router.get("/v1/scheduler/jobs")
async def list_jobs(request: Request) -> dict:
    runtime = get_runtime(request)
    jobs = await runtime.scheduler.list_jobs()
    return {"jobs": [j.to_json() for j in jobs]}


@router.post("/v1/scheduler/jobs")
async def create_job(body: JobCreate, request: Request) -> dict:
    runtime = get_runtime(request)
    try:
        kind = JobKind(body.kind)
    except ValueError as exc:
        raise HTTPException(400, f"invalid kind: {body.kind!r}") from exc
    job = new_job(
        kind=kind,
        title=body.title,
        cron=body.cron,
        every_seconds=body.every_seconds,
        at_timestamp=body.at_timestamp,
        prompt=body.prompt,
        message=body.message,
        webhook_url=body.webhook_url,
        payload=body.payload,
    )
    try:
        await runtime.scheduler.create(job)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return job.to_json()


@router.delete("/v1/scheduler/jobs/{job_id}")
async def delete_job(job_id: str, request: Request) -> dict:
    runtime = get_runtime(request)
    ok = await runtime.scheduler.delete(job_id)
    if not ok:
        raise HTTPException(404, "job not found")
    return {"ok": True}


@router.post("/v1/scheduler/jobs/{job_id}/pause")
async def pause_job(job_id: str, request: Request) -> dict:
    runtime = get_runtime(request)
    ok = await runtime.scheduler.update_status(job_id, JobStatus.PAUSED)
    if not ok:
        raise HTTPException(404, "job not found")
    return {"ok": True}


@router.post("/v1/scheduler/jobs/{job_id}/resume")
async def resume_job(job_id: str, request: Request) -> dict:
    runtime = get_runtime(request)
    ok = await runtime.scheduler.update_status(job_id, JobStatus.ACTIVE)
    if not ok:
        raise HTTPException(404, "job not found")
    return {"ok": True}
