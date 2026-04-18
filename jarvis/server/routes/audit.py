"""Audit-log viewer endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from jarvis.server.auth import require_api_key
from jarvis.server.deps import get_runtime

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/v1/audit")
async def audit(request: Request, kind: str | None = None, limit: int = 100) -> dict:
    runtime = get_runtime(request)
    records = await runtime.audit.recent(kind=kind, limit=max(1, min(limit, 1000)))
    return {"records": [r.to_json() for r in records]}
