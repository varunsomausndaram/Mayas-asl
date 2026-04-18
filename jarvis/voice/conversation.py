"""Interrupt-aware voice conversation manager.

A :class:`VoiceSession` wraps a running dialog: Jarvis speaks, the user may
cut in, and the session preserves enough state to resume, rewind, or
pivot. The manager is UI-agnostic — the CLI's voice mode and the PWA both
drive the same state machine over different I/O transports.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


@dataclass
class Utterance:
    """Something Jarvis has said or started to say during the session."""

    index: int
    text: str
    started: float
    ended: float | None = None
    chunks_played: int = 0
    interrupted: bool = False
    resumed_from: int | None = None


@dataclass
class VoiceSession:
    """Mutable conversation state. Thread-safe via an internal asyncio lock."""

    session_id: str
    state: VoiceState = VoiceState.IDLE
    utterances: list[Utterance] = field(default_factory=list)
    last_user_text: str = ""
    last_interrupt_at: float = 0.0
    barge_in_event: asyncio.Event = field(default_factory=asyncio.Event)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _listeners: list[Callable[[dict[str, Any]], None]] = field(default_factory=list)

    # -------------------------------------------------------------- lifecycle
    async def begin_user_turn(self, text: str) -> None:
        async with self._lock:
            self.last_user_text = text
            self.state = VoiceState.THINKING
            self.barge_in_event.clear()
        self._broadcast({"type": "user_turn", "text": text})

    async def begin_speaking(self, text: str) -> Utterance:
        async with self._lock:
            utterance = Utterance(index=len(self.utterances), text=text, started=time.time())
            self.utterances.append(utterance)
            self.state = VoiceState.SPEAKING
        self._broadcast({"type": "speaking_start", "index": utterance.index, "text": text})
        return utterance

    async def record_chunk_played(self, index: int, chunks: int) -> None:
        async with self._lock:
            if 0 <= index < len(self.utterances):
                self.utterances[index].chunks_played = chunks
        self._broadcast({"type": "speaking_progress", "index": index, "chunks": chunks})

    async def end_speaking(self, index: int, *, interrupted: bool = False) -> None:
        async with self._lock:
            if 0 <= index < len(self.utterances):
                u = self.utterances[index]
                u.ended = time.time()
                u.interrupted = interrupted
            self.state = VoiceState.INTERRUPTED if interrupted else VoiceState.IDLE
        self._broadcast(
            {"type": "speaking_end", "index": index, "interrupted": interrupted}
        )

    async def interrupt(self) -> int | None:
        """Signal that the user has barged in. Returns the active utterance index."""
        async with self._lock:
            self.barge_in_event.set()
            self.last_interrupt_at = time.time()
            active = None
            if self.utterances and self.utterances[-1].ended is None:
                active = self.utterances[-1].index
            self.state = VoiceState.INTERRUPTED
        self._broadcast({"type": "interrupt", "active": active})
        return active

    async def listening(self) -> None:
        async with self._lock:
            self.state = VoiceState.LISTENING
        self._broadcast({"type": "listening"})

    # ---------------------------------------------------------------- helpers
    def last_interrupted_utterance(self) -> Utterance | None:
        for u in reversed(self.utterances):
            if u.interrupted:
                return u
        return None

    def resume_plan(self) -> Utterance | None:
        """Return the utterance that should be resumed if the user asks."""
        return self.last_interrupted_utterance()

    def subscribe(self, listener: Callable[[dict[str, Any]], None]) -> None:
        self._listeners.append(listener)

    def _broadcast(self, event: dict[str, Any]) -> None:
        event.setdefault("ts", time.time())
        event.setdefault("session", self.session_id)
        event.setdefault("state", self.state.value)
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:  # pragma: no cover
                pass
