"""Reminder, timer, and scheduled-prompt tools.

These tools are the hands that drive :mod:`jarvis.scheduler`. The scheduler
owns the persistence and the firing loop; the tools just translate the
model's natural-language requests into structured :class:`ScheduledJob`
rows.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from jarvis.scheduler.engine import JobKind, JobStatus, Scheduler, new_job
from jarvis.tools.base import Tool, ToolResult


class SetReminderTool(Tool):
    name = "set_reminder"
    description = (
        "Create a reminder that fires at a specific time or after a duration. "
        "Use 'in' phrasing for delays (e.g. 'in 10 minutes') or an ISO timestamp for absolute times."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Text to surface when the reminder fires."},
            "in_seconds": {"type": "integer", "minimum": 1, "description": "Relative delay in seconds."},
            "at_iso": {"type": "string", "description": "Absolute time as ISO 8601 (e.g. 2026-04-18T10:00:00)."},
            "title": {"type": "string", "default": "Reminder"},
        },
        "required": ["message"],
    }

    def __init__(self, scheduler: Scheduler) -> None:
        self.scheduler = scheduler

    async def run(
        self,
        *,
        message: str,
        in_seconds: int | None = None,
        at_iso: str | None = None,
        title: str = "Reminder",
        **_: Any,
    ) -> ToolResult:
        if in_seconds is None and not at_iso:
            parsed = _parse_relative(message)
            if parsed is not None:
                in_seconds = parsed
        ts: float | None
        if in_seconds is not None:
            ts = time.time() + max(1, int(in_seconds))
        elif at_iso:
            try:
                ts = _parse_iso(at_iso).timestamp()
            except ValueError as exc:
                return ToolResult(ok=False, error=f"invalid at_iso: {exc}")
        else:
            return ToolResult(ok=False, error="reminder needs in_seconds or at_iso")
        job = new_job(
            kind=JobKind.REMINDER,
            title=title,
            at_timestamp=ts,
            message=message,
        )
        await self.scheduler.create(job)
        return ToolResult(
            ok=True,
            output={"id": job.id, "fires_at": ts, "fires_in_seconds": int(ts - time.time()), "message": message},
        )


class SetTimerTool(Tool):
    name = "set_timer"
    description = "Start a one-shot timer. When it fires Jarvis will announce it."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "seconds": {"type": "integer", "minimum": 1},
            "label": {"type": "string", "default": "Timer"},
        },
        "required": ["seconds"],
    }

    def __init__(self, scheduler: Scheduler) -> None:
        self.scheduler = scheduler

    async def run(self, *, seconds: int, label: str = "Timer", **_: Any) -> ToolResult:
        seconds = max(1, int(seconds))
        ts = time.time() + seconds
        job = new_job(
            kind=JobKind.TIMER,
            title=label,
            at_timestamp=ts,
            message=f"{label} done.",
        )
        await self.scheduler.create(job)
        return ToolResult(ok=True, output={"id": job.id, "fires_at": ts, "seconds": seconds, "label": label})


class ScheduleRecurringTool(Tool):
    name = "schedule_recurring"
    description = "Create a recurring job using a cron expression (5 fields: min hour day month weekday)."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "cron": {"type": "string", "description": "5-field cron expression."},
            "title": {"type": "string"},
            "prompt": {"type": "string", "description": "If set, fires a prompt to Jarvis when due."},
            "message": {"type": "string", "description": "If set, a plain reminder message."},
        },
        "required": ["cron", "title"],
    }

    def __init__(self, scheduler: Scheduler) -> None:
        self.scheduler = scheduler

    async def run(
        self,
        *,
        cron: str,
        title: str,
        prompt: str | None = None,
        message: str | None = None,
        **_: Any,
    ) -> ToolResult:
        kind = JobKind.PROMPT if prompt else JobKind.REMINDER
        job = new_job(
            kind=kind,
            title=title,
            cron=cron,
            prompt=prompt,
            message=message or (prompt or title),
        )
        try:
            await self.scheduler.create(job)
        except ValueError as exc:
            return ToolResult(ok=False, error=str(exc))
        return ToolResult(ok=True, output={"id": job.id, "cron": cron, "kind": kind.value})


class ListRemindersTool(Tool):
    name = "list_reminders"
    description = "List active and upcoming scheduled jobs (reminders, timers, cron)."
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    def __init__(self, scheduler: Scheduler) -> None:
        self.scheduler = scheduler

    async def run(self, **_: Any) -> ToolResult:
        jobs = await self.scheduler.list_jobs()
        rows = [j.to_json() for j in jobs if j.status == JobStatus.ACTIVE]
        return ToolResult(ok=True, output={"count": len(rows), "jobs": rows})


class CancelReminderTool(Tool):
    name = "cancel_reminder"
    description = "Delete a scheduled job by id."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
    }

    def __init__(self, scheduler: Scheduler) -> None:
        self.scheduler = scheduler

    async def run(self, *, id: str, **_: Any) -> ToolResult:
        ok = await self.scheduler.delete(id)
        return ToolResult(ok=ok, output={"deleted": ok, "id": id}, error=None if ok else "not found")


# ------------------------------------------------------------------ helpers
_REL = re.compile(r"\bin\s+(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)\b", re.IGNORECASE)


def _parse_relative(text: str) -> int | None:
    m = _REL.search(text)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("s"):
        return n
    if unit.startswith("m"):
        return n * 60
    if unit.startswith("h"):
        return n * 3600
    if unit.startswith("d"):
        return n * 86400
    return None


def _parse_iso(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
