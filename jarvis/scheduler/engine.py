"""The scheduler loop itself.

Why not APScheduler? Because the dep-count budget is small and the feature
set we need is narrow: evaluate a few dozen jobs a minute, persist them to
SQLite, fire callbacks on the event loop, survive a restart, and support
pause/resume/delete from the UI. This implementation is ~200 lines and has
zero dependencies beyond the stdlib and aiosqlite.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import aiosqlite

from jarvis.logging import get_logger
from jarvis.scheduler.cron import CronTrigger, utcnow

log = get_logger(__name__)


class JobKind(str, Enum):
    PROMPT = "prompt"
    REMINDER = "reminder"
    TIMER = "timer"
    WEBHOOK = "webhook"


class JobStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ScheduledJob:
    id: str
    title: str
    kind: JobKind
    status: JobStatus = JobStatus.ACTIVE
    cron: str | None = None
    every_seconds: int | None = None
    at_timestamp: float | None = None
    prompt: str | None = None
    message: str | None = None
    webhook_url: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    last_run: float | None = None
    next_run: float | None = None
    run_count: int = 0
    created: float = field(default_factory=time.time)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> ScheduledJob:
        return cls(
            id=row["id"],
            title=row["title"],
            kind=JobKind(row["kind"]),
            status=JobStatus(row["status"]),
            cron=row["cron"],
            every_seconds=row["every_seconds"],
            at_timestamp=row["at_timestamp"],
            prompt=row["prompt"],
            message=row["message"],
            webhook_url=row["webhook_url"],
            payload=json.loads(row["payload"] or "{}"),
            last_run=row["last_run"],
            next_run=row["next_run"],
            run_count=row["run_count"],
            created=row["created"],
        )


_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    cron TEXT,
    every_seconds INTEGER,
    at_timestamp REAL,
    prompt TEXT,
    message TEXT,
    webhook_url TEXT,
    payload TEXT NOT NULL DEFAULT '{}',
    last_run REAL,
    next_run REAL,
    run_count INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_next_run
    ON scheduled_jobs(next_run)
    WHERE status = 'active';
"""


DispatchCallback = Callable[[ScheduledJob], Awaitable[None]]


class Scheduler:
    """Persistent scheduler with a single background task."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        dispatch: DispatchCallback | None = None,
        tick_seconds: float = 5.0,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.dispatch = dispatch
        self.tick_seconds = tick_seconds
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._initialised = False

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()
        self._initialised = True

    async def start(self) -> None:
        if not self._initialised:
            await self.init()
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="jarvis.scheduler")
        log.info("scheduler.started")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        log.info("scheduler.stopped")

    # --------------------------------------------------------------- schedule
    async def create(self, job: ScheduledJob) -> ScheduledJob:
        self._validate(job)
        if job.next_run is None:
            job.next_run = self._first_run(job)
        if not self._initialised:
            await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO scheduled_jobs(id, title, kind, status, cron, every_seconds, at_timestamp, "
                "prompt, message, webhook_url, payload, last_run, next_run, run_count, created) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    job.id,
                    job.title,
                    job.kind.value,
                    job.status.value,
                    job.cron,
                    job.every_seconds,
                    job.at_timestamp,
                    job.prompt,
                    job.message,
                    job.webhook_url,
                    json.dumps(job.payload),
                    job.last_run,
                    job.next_run,
                    job.run_count,
                    job.created,
                ),
            )
            await db.commit()
        log.info("scheduler.job_created", id=job.id, kind=job.kind.value, next_run=job.next_run)
        return job

    async def list_jobs(self) -> list[ScheduledJob]:
        if not self._initialised:
            await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM scheduled_jobs ORDER BY created DESC"
            ) as cur:
                rows = await cur.fetchall()
        return [ScheduledJob.from_row(r) for r in rows]

    async def get(self, job_id: str) -> ScheduledJob | None:
        if not self._initialised:
            await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM scheduled_jobs WHERE id = ?", (job_id,)) as cur:
                row = await cur.fetchone()
        return ScheduledJob.from_row(row) if row else None

    async def update_status(self, job_id: str, status: JobStatus) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "UPDATE scheduled_jobs SET status = ? WHERE id = ?",
                (status.value, job_id),
            )
            await db.commit()
            return cur.rowcount > 0

    async def delete(self, job_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("DELETE FROM scheduled_jobs WHERE id = ?", (job_id,))
            await db.commit()
            return cur.rowcount > 0

    # -------------------------------------------------------- internal engine
    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception:  # pragma: no cover
                log.exception("scheduler.tick_failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.tick_seconds)
            except asyncio.TimeoutError:
                continue

    async def _tick(self) -> None:
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM scheduled_jobs WHERE status = 'active' AND next_run IS NOT NULL "
                "AND next_run <= ? ORDER BY next_run ASC",
                (now,),
            ) as cur:
                rows = await cur.fetchall()
        jobs = [ScheduledJob.from_row(r) for r in rows]
        for job in jobs:
            await self._fire(job)

    async def _fire(self, job: ScheduledJob) -> None:
        log.info("scheduler.firing", id=job.id, kind=job.kind.value)
        if self.dispatch is not None:
            try:
                await self.dispatch(job)
            except Exception:  # pragma: no cover
                log.exception("scheduler.dispatch_failed", id=job.id)
        job.last_run = time.time()
        job.run_count += 1
        job.next_run = self._next_run(job)
        new_status = job.status
        if job.next_run is None:
            new_status = JobStatus.COMPLETED
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE scheduled_jobs SET last_run = ?, next_run = ?, run_count = ?, status = ? WHERE id = ?",
                (job.last_run, job.next_run, job.run_count, new_status.value, job.id),
            )
            await db.commit()

    # -------------------------------------------------------------- triggers
    def _validate(self, job: ScheduledJob) -> None:
        triggers = [t for t in (job.cron, job.every_seconds, job.at_timestamp) if t is not None]
        if len(triggers) != 1:
            raise ValueError("job must declare exactly one of cron / every_seconds / at_timestamp")
        if job.cron:
            CronTrigger.parse(job.cron)
        if job.kind == JobKind.PROMPT and not job.prompt:
            raise ValueError("prompt jobs require 'prompt' text")
        if job.kind == JobKind.REMINDER and not (job.message or job.prompt):
            raise ValueError("reminder jobs require 'message' text")
        if job.kind == JobKind.WEBHOOK and not job.webhook_url:
            raise ValueError("webhook jobs require 'webhook_url'")

    def _first_run(self, job: ScheduledJob) -> float | None:
        now = utcnow()
        if job.cron:
            nxt = CronTrigger.parse(job.cron).next_after(now + timedelta(seconds=1))
            return nxt.timestamp() if nxt else None
        if job.every_seconds:
            return (now + timedelta(seconds=job.every_seconds)).timestamp()
        if job.at_timestamp:
            return float(job.at_timestamp)
        return None

    def _next_run(self, job: ScheduledJob) -> float | None:
        now = utcnow()
        if job.cron:
            nxt = CronTrigger.parse(job.cron).next_after(now + timedelta(seconds=1))
            return nxt.timestamp() if nxt else None
        if job.every_seconds:
            return (now + timedelta(seconds=job.every_seconds)).timestamp()
        if job.at_timestamp:
            # one-shot: no next run
            return None
        return None


def new_job(
    kind: JobKind,
    title: str,
    *,
    cron: str | None = None,
    every_seconds: int | None = None,
    at_timestamp: float | None = None,
    prompt: str | None = None,
    message: str | None = None,
    webhook_url: str | None = None,
    payload: dict[str, Any] | None = None,
) -> ScheduledJob:
    """Convenience constructor used by the tool layer and the HTTP API."""
    return ScheduledJob(
        id=uuid.uuid4().hex,
        title=title,
        kind=kind,
        cron=cron,
        every_seconds=every_seconds,
        at_timestamp=at_timestamp,
        prompt=prompt,
        message=message,
        webhook_url=webhook_url,
        payload=payload or {},
    )
