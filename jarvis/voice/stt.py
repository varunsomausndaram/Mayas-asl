"""Speech-to-text backed by ``faster-whisper``.

Two entry points:

* :meth:`SpeechRecognizer.transcribe_bytes` — one-shot transcription of a
  complete WAV/PCM payload. Used by the web UI, which records a clip and
  posts it.
* :meth:`SpeechRecognizer.stream` — iterate over PCM chunks and yield
  partial / final transcripts. Used by the CLI voice mode for push-to-talk.

The recognizer is optional: constructing one on a host without the
``faster-whisper`` extra will still work but the first transcription raises
a clear :class:`RuntimeError` asking the operator to install ``[voice]``.
"""

from __future__ import annotations

import io
import wave
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass

from jarvis.logging import get_logger

log = get_logger(__name__)


@dataclass
class TranscriptionResult:
    text: str
    language: str = ""
    duration: float = 0.0
    partial: bool = False


class SpeechRecognizer:
    """Lazy wrapper around ``faster-whisper`` with a minimal API."""

    def __init__(self, model: str = "base", *, device: str = "auto", compute_type: str = "int8") -> None:
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self._whisper = None

    # ------------------------------------------------------------------ setup
    def _load(self):
        if self._whisper is not None:
            return self._whisper
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - depends on env
            raise RuntimeError(
                "faster-whisper is not installed. Install the voice extra: "
                "pip install 'jarvis-assistant[voice]'"
            ) from exc
        log.info("stt.loading", model=self.model_name, device=self.device)
        self._whisper = WhisperModel(self.model_name, device=self.device, compute_type=self.compute_type)
        return self._whisper

    # ------------------------------------------------------------------- API
    def transcribe_bytes(self, audio: bytes, *, language: str | None = None) -> TranscriptionResult:
        """Transcribe a WAV byte string. PCM16 16 kHz mono is what the UI sends."""
        if not audio:
            return TranscriptionResult(text="")
        model = self._load()
        buf = io.BytesIO(audio)
        segments, info = model.transcribe(
            buf,
            language=language,
            vad_filter=True,
            beam_size=1,
            condition_on_previous_text=False,
        )
        text = "".join(seg.text for seg in segments).strip()
        return TranscriptionResult(text=text, language=info.language, duration=info.duration)

    def stream(self, pcm_chunks: Iterable[bytes], *, sample_rate: int = 16000) -> TranscriptionResult:
        """Accumulate PCM chunks and run one transcription at the end.

        faster-whisper is not an online STT — we buffer, convert to WAV, then
        decode. Good enough for push-to-talk; for fully streaming captions we
        partition on VAD silences in :class:`VoiceSession`.
        """
        buffer = bytearray()
        for chunk in pcm_chunks:
            if chunk:
                buffer.extend(chunk)
        wav = _pcm_to_wav(bytes(buffer), sample_rate)
        return self.transcribe_bytes(wav)


def _pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return out.getvalue()


async def atranscribe(
    recognizer: SpeechRecognizer, audio: bytes, *, language: str | None = None
) -> TranscriptionResult:
    """Run transcription in a worker thread so we don't block the event loop."""
    import asyncio

    return await asyncio.to_thread(recognizer.transcribe_bytes, audio, language=language)


async def astream(
    recognizer: SpeechRecognizer, chunks: Iterable[bytes], *, sample_rate: int = 16000
) -> AsyncIterator[TranscriptionResult]:
    """Async generator wrapper around :meth:`SpeechRecognizer.stream`."""
    import asyncio

    result = await asyncio.to_thread(recognizer.stream, chunks, sample_rate=sample_rate)
    yield result
