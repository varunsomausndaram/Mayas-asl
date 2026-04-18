"""In-process pub/sub used to stream orchestrator progress to clients.

An :class:`EventBus` accepts topic-scoped subscriptions. Publishers are the
orchestrator and tools; subscribers are HTTP/WebSocket handlers that relay
events to the UI. The bus is non-blocking: slow subscribers drop frames
rather than stalling the orchestrator.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Event:
    """A single pub/sub payload.

    Attributes:
        topic: Hierarchical name such as ``session.<id>.token``.
        type: Short machine tag, e.g. ``token``, ``tool_call``, ``done``.
        data: Arbitrary JSON-serialisable payload.
        ts: UNIX timestamp (seconds) assigned at construction.
        id: Monotonically unique identifier — helpful for client-side dedup.
    """

    topic: str
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_json(self) -> dict[str, Any]:
        return {"id": self.id, "ts": self.ts, "topic": self.topic, "type": self.type, "data": self.data}


class EventBus:
    """Tiny topic-prefixed event bus.

    Subscribers receive events whose topic *starts with* the subscription
    prefix. Queues are bounded so a stalled subscriber cannot push the
    process into swap; overflow events are dropped with a warning event.
    """

    def __init__(self, queue_size: int = 256) -> None:
        self._subs: dict[str, list[tuple[str, asyncio.Queue[Event]]]] = {}
        self._lock = asyncio.Lock()
        self._queue_size = queue_size

    async def publish(self, event: Event) -> None:
        async with self._lock:
            dead: list[tuple[str, asyncio.Queue[Event]]] = []
            for prefix, queues in self._subs.items():
                if not event.topic.startswith(prefix):
                    continue
                for entry in queues:
                    _, q = entry
                    try:
                        q.put_nowait(event)
                    except asyncio.QueueFull:
                        # Drop the oldest item and insert the new one so the
                        # subscriber still makes forward progress.
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        try:
                            q.put_nowait(event)
                        except asyncio.QueueFull:
                            dead.append(entry)
            for entry in dead:
                for queues in self._subs.values():
                    if entry in queues:
                        queues.remove(entry)

    async def subscribe(self, topic_prefix: str) -> Subscription:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._queue_size)
        sub_id = uuid.uuid4().hex
        async with self._lock:
            self._subs.setdefault(topic_prefix, []).append((sub_id, q))
        return Subscription(bus=self, prefix=topic_prefix, sub_id=sub_id, queue=q)

    async def _unsubscribe(self, prefix: str, sub_id: str) -> None:
        async with self._lock:
            queues = self._subs.get(prefix)
            if not queues:
                return
            self._subs[prefix] = [s for s in queues if s[0] != sub_id]
            if not self._subs[prefix]:
                self._subs.pop(prefix, None)


@dataclass
class Subscription:
    """A handle returned by :meth:`EventBus.subscribe`.

    Use as an async iterator, or call :meth:`close` when done. The
    subscription is also an async context manager for the common case.
    """

    bus: EventBus
    prefix: str
    sub_id: str
    queue: asyncio.Queue[Event]
    _closed: bool = False

    async def __aenter__(self) -> Subscription:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    def __aiter__(self) -> AsyncIterator[Event]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[Event]:
        while not self._closed:
            try:
                yield await self.queue.get()
            except asyncio.CancelledError:
                break

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self.bus._unsubscribe(self.prefix, self.sub_id)


_bus: EventBus | None = None


def get_bus() -> EventBus:
    """Return the process-global bus, creating it on first use."""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
