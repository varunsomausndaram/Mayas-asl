"""Pending-approval registry backing the HTTP approval flow.

When the orchestrator encounters a risky tool call it suspends the call and
hands a pending :class:`RiskAssessment` to the server through the approval
requester callback built here. The server pushes the assessment to any
connected UI (WebSocket or long-polling REST) and waits for the user to
resolve it through ``POST /v1/approvals/{id}``.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from jarvis.core.permissions import ApprovalDecision, RiskAssessment
from jarvis.events import Event, EventBus


@dataclass
class PendingApproval:
    id: str
    assessment: RiskAssessment
    future: asyncio.Future

    def to_json(self) -> dict[str, Any]:
        return {"id": self.id, "assessment": self.assessment.to_json()}


class ApprovalRegistry:
    """In-memory registry of approvals awaiting a human decision."""

    def __init__(self, bus: EventBus | None = None, *, timeout_seconds: float = 120.0) -> None:
        self._pending: dict[str, PendingApproval] = {}
        self._lock = asyncio.Lock()
        self._bus = bus
        self.timeout_seconds = timeout_seconds

    def attach_bus(self, bus: EventBus) -> None:
        self._bus = bus

    def snapshot(self) -> list[dict[str, Any]]:
        return [p.to_json() for p in self._pending.values()]

    async def request(self, assessment: RiskAssessment) -> ApprovalDecision:
        """Return the decision the user makes for ``assessment``.

        Times out to :attr:`ApprovalDecision.DENIED` if no-one responds in
        ``timeout_seconds`` — safety-first default.
        """
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        pending = PendingApproval(id=uuid.uuid4().hex, assessment=assessment, future=fut)
        async with self._lock:
            self._pending[pending.id] = pending
        if self._bus is not None:
            await self._bus.publish(
                Event(
                    topic="approvals",
                    type="pending",
                    data=pending.to_json(),
                )
            )
        try:
            return await asyncio.wait_for(fut, timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            return ApprovalDecision.DENIED
        finally:
            async with self._lock:
                self._pending.pop(pending.id, None)

    async def resolve(self, approval_id: str, decision: ApprovalDecision) -> bool:
        async with self._lock:
            pending = self._pending.get(approval_id)
        if pending is None:
            return False
        if not pending.future.done():
            pending.future.set_result(decision)
        await self._bus.publish(
            Event(
                topic="approvals",
                type="resolved",
                data={"id": approval_id, "decision": decision.value},
            )
        )
        return True
