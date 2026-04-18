"""Scheduler — cron jobs, one-shot timers, reminders.

The scheduler is a lightweight asyncio loop that persists its catalog to
SQLite so jobs survive restarts. Every job has a kind (``prompt``,
``reminder``, ``timer``, ``webhook``) and a trigger (``cron`` expression,
``every`` duration, or ``at`` RFC-3339 timestamp). Triggered prompt jobs
are handed back to the orchestrator via a dispatch callback.
"""

from jarvis.scheduler.cron import CronField, CronTrigger
from jarvis.scheduler.engine import JobKind, JobStatus, ScheduledJob, Scheduler

__all__ = [
    "Scheduler",
    "ScheduledJob",
    "JobKind",
    "JobStatus",
    "CronTrigger",
    "CronField",
]
