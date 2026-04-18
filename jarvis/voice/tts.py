"""Text-to-speech with barge-in support.

We use :mod:`pyttsx3` on the server for reliable cross-platform playback,
but the browser-side PWA can also call the Web Speech API's
``speechSynthesis`` directly. The :class:`Speaker` here drives local audio
(CLI voice mode, tray app). The server's ``/voice/tts`` endpoint returns a
short-lived WAV for clients that want server-side voice.

Barge-in is implemented by chunking utterances at sentence boundaries and
checking an ``interrupt`` event between chunks. If the caller sets the
event, the current chunk finishes speaking and playback stops there —
leaving a clean resumption point that the conversation manager can reuse.
"""

from __future__ import annotations

import asyncio
import re
import threading
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from jarvis.logging import get_logger

log = get_logger(__name__)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|(?<=[:;])\s+|\n+")


@dataclass
class SpeakChunk:
    """One logical unit of speech. The ``index`` lets callers resume."""

    index: int
    text: str
    total: int


def split_for_speech(text: str) -> list[str]:
    """Split a response into short chunks so barge-in loses little context."""
    cleaned = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)  # drop code blocks
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    pieces = [p.strip() for p in _SENTENCE_SPLIT.split(cleaned) if p.strip()]
    # Further cap very long pieces to ~200 chars to keep interrupt latency low.
    capped: list[str] = []
    for piece in pieces:
        if len(piece) <= 220:
            capped.append(piece)
            continue
        words = piece.split(" ")
        buf: list[str] = []
        size = 0
        for w in words:
            if size + len(w) + 1 > 220 and buf:
                capped.append(" ".join(buf))
                buf, size = [w], len(w)
            else:
                buf.append(w)
                size += len(w) + 1
        if buf:
            capped.append(" ".join(buf))
    return capped


class Speaker:
    """Speak text aloud with stop / resume support.

    The speaker runs :mod:`pyttsx3` in a dedicated thread because the engine
    is blocking and not asyncio-friendly. The async API (``speak``,
    ``stop``) marshals commands into that thread.
    """

    def __init__(self, *, rate: int = 180, voice: str = "") -> None:
        self.rate = rate
        self.voice = voice
        self._engine = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def _engine_or_raise(self):
        if self._engine is not None:
            return self._engine
        try:
            import pyttsx3
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "pyttsx3 is not installed. Install the voice extra: "
                "pip install 'jarvis-assistant[voice]'"
            ) from exc
        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        if self.voice:
            engine.setProperty("voice", self.voice)
        self._engine = engine
        return engine

    async def speak(
        self,
        text: str,
        *,
        interrupt: asyncio.Event | None = None,
        on_chunk: Callable[[SpeakChunk], None] | None = None,
    ) -> int:
        """Speak ``text`` aloud, chunk by chunk. Returns the index reached.

        If ``interrupt`` is provided and becomes set, the speaker stops at
        the next chunk boundary and returns the index of the last chunk
        successfully played. That index can be passed to :meth:`resume` to
        pick up where we left off.
        """
        chunks = split_for_speech(text)
        if not chunks:
            return 0
        played = 0
        for i, chunk_text in enumerate(chunks):
            if interrupt is not None and interrupt.is_set():
                break
            if on_chunk is not None:
                on_chunk(SpeakChunk(index=i, text=chunk_text, total=len(chunks)))
            await asyncio.to_thread(self._say, chunk_text)
            played = i + 1
            if interrupt is not None and interrupt.is_set():
                break
        return played

    async def resume(
        self,
        text: str,
        from_index: int,
        *,
        interrupt: asyncio.Event | None = None,
        on_chunk: Callable[[SpeakChunk], None] | None = None,
    ) -> int:
        """Continue speaking a previously-interrupted utterance."""
        chunks = split_for_speech(text)
        remaining = chunks[from_index:]
        if not remaining:
            return from_index
        joined = " ".join(remaining)
        return from_index + await self.speak(joined, interrupt=interrupt, on_chunk=on_chunk)

    def stop(self) -> None:
        """Stop the current utterance immediately."""
        with self._lock:
            if self._engine is not None:
                try:
                    self._engine.stop()
                except Exception:
                    pass

    def synth_to_wav(self, text: str, path: str) -> str:
        """Render ``text`` to a WAV file at ``path``. Returns the path."""
        engine = self._engine_or_raise()
        engine.save_to_file(text, path)
        engine.runAndWait()
        return path

    # -------------------------------------------------------------- internal
    def _say(self, text: str) -> None:
        with self._lock:
            engine = self._engine_or_raise()
            engine.say(text)
            engine.runAndWait()


async def stream_chunks(text: str) -> AsyncIterator[SpeakChunk]:
    """Yield :class:`SpeakChunk` units without any audio engine attached."""
    pieces = split_for_speech(text)
    for i, piece in enumerate(pieces):
        yield SpeakChunk(index=i, text=piece, total=len(pieces))
