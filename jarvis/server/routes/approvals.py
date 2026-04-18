"""Approval REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from jarvis.core.permissions import ApprovalDecision
from jarvis.server.auth import require_api_key

router = APIRouter(dependencies=[Depends(require_api_key)])


class ApprovalBody(BaseModel):
    decision: str  # approved_once | approved_session | approved_always | denied


@router.get("/v1/approvals/pending")
async def pending(request: Request) -> dict:
    registry = request.app.state.approvals
    return {"pending": registry.snapshot()}


@router.post("/v1/approvals/{approval_id}")
async def resolve(approval_id: str, body: ApprovalBody, request: Request) -> dict:
    registry = request.app.state.approvals
    try:
        decision = ApprovalDecision(body.decision)
    except ValueError as exc:
        raise HTTPException(400, f"invalid decision: {body.decision!r}") from exc
    ok = await registry.resolve(approval_id, decision)
    if not ok:
        raise HTTPException(404, "approval not found or already resolved")
    return {"ok": True}
