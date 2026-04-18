"""Construct a fully-wired :class:`Orchestrator` from :class:`Settings`.

Callers use this in preference to instantiating :class:`Orchestrator`
directly: it handles the dance of hooking the scheduler's dispatch back
into the orchestrator, loading the user profile, and seeding the
permission broker with previously-approved fingerprints.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from jarvis.config import Settings
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.permissions import (
    ApprovalDecision,
    PermissionBroker,
    RiskAssessment,
    RiskLevel,
)
from jarvis.core.persona import Persona
from jarvis.core.profile import UserProfileStore
from jarvis.dispatch.claude_code import ClaudeCodeDispatcher
from jarvis.events import EventBus, get_bus
from jarvis.llm.router import build_provider
from jarvis.memory.store import MemoryStore
from jarvis.scheduler.engine import JobKind, ScheduledJob, Scheduler
from jarvis.security.audit import AuditLog
from jarvis.tools.registry import build_registry

ApprovalRequester = Callable[[RiskAssessment], Awaitable[ApprovalDecision]]


@dataclass
class JarvisRuntime:
    """The full set of stateful objects Jarvis needs to serve a request."""

    settings: Settings
    orchestrator: Orchestrator
    memory: MemoryStore
    profile_store: UserProfileStore
    persona: Persona
    permissions: PermissionBroker
    audit: AuditLog
    scheduler: Scheduler
    dispatcher: ClaudeCodeDispatcher
    bus: EventBus

    async def start(self) -> None:
        await self.memory.init()
        await self.audit.init()
        await self.scheduler.start()

    async def stop(self) -> None:
        await self.scheduler.stop()
        await self.orchestrator.close()


async def build_runtime(
    settings: Settings,
    *,
    approval_requester: ApprovalRequester | None = None,
    persona: Persona | None = None,
    auto_approve_below: RiskLevel = RiskLevel.MEDIUM,
) -> JarvisRuntime:
    """Assemble all components and return a :class:`JarvisRuntime`."""
    settings.ensure_dirs()
    bus = get_bus()

    memory = MemoryStore(settings.db_path)
    await memory.init()

    profile_store = UserProfileStore(settings.data_dir / "profile.json")
    profile = await profile_store.load()

    if persona is None:
        persona = Persona(
            address=profile.preferred_address,
            humor_level=profile.humor_level,
            verbosity=profile.verbosity,
            voice_speech_rate=profile.speech_rate,
        )

    audit = AuditLog(settings.data_dir / "audit.sqlite3")
    await audit.init()

    permissions = PermissionBroker(
        auto_approve_below=auto_approve_below,
        requester=approval_requester,
        always_approved=set(profile.always_approved),
        persist_callback=profile_store.add_always_approved,
    )

    scheduler = Scheduler(settings.data_dir / "scheduler.sqlite3")
    await scheduler.init()

    registry, dispatcher, sched = build_registry(
        settings,
        scheduler=scheduler,
        bus=bus,
    )

    llm = build_provider(settings)

    orch = Orchestrator(
        settings=settings,
        llm=llm,
        registry=registry,
        memory=memory,
        profile_store=profile_store,
        persona=persona,
        permissions=permissions,
        audit=audit,
        bus=bus,
    )

    # Scheduler dispatches fire a prompt back through Jarvis or publish an
    # event for the UI to surface as a notification.
    async def dispatch(job: ScheduledJob) -> None:
        if job.kind == JobKind.PROMPT and job.prompt:
            session_id = job.payload.get("session_id") or f"scheduled-{job.id[:8]}"
            try:
                await orch.run(session_id, job.prompt)
            except Exception:  # pragma: no cover
                pass
        payload = {
            "job_id": job.id,
            "title": job.title,
            "kind": job.kind.value,
            "message": job.message or job.prompt or job.title,
        }
        await bus.publish_event("scheduler.fired", payload) if hasattr(
            bus, "publish_event"
        ) else await _publish(bus, payload)

    scheduler.dispatch = dispatch

    return JarvisRuntime(
        settings=settings,
        orchestrator=orch,
        memory=memory,
        profile_store=profile_store,
        persona=persona,
        permissions=permissions,
        audit=audit,
        scheduler=scheduler,
        dispatcher=dispatcher,
        bus=bus,
    )


async def _publish(bus: EventBus, payload: dict) -> None:
    from jarvis.events import Event

    await bus.publish(Event(topic="scheduler", type="fired", data=payload))
