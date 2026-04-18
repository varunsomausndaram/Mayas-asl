"""Voice endpoints: server-side transcription and TTS synthesis.

These endpoints are optional — the PWA normally uses the browser's own
Web Speech APIs for latency reasons. But for the CLI and for phones that
lack on-device models, the server provides fallbacks here.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from jarvis.server.auth import require_api_key
from jarvis.server.deps import get_runtime
from jarvis.voice.stt import SpeechRecognizer, atranscribe
from jarvis.voice.tts import Speaker

router = APIRouter(dependencies=[Depends(require_api_key)])


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


_recognizer: SpeechRecognizer | None = None
_speaker: Speaker | None = None


def _lazy_recognizer(request: Request) -> SpeechRecognizer:
    global _recognizer
    if _recognizer is None:
        runtime = get_runtime(request)
        _recognizer = SpeechRecognizer(model=runtime.settings.whisper_model)
    return _recognizer


def _lazy_speaker(request: Request) -> Speaker:
    global _speaker
    if _speaker is None:
        runtime = get_runtime(request)
        _speaker = Speaker(rate=runtime.settings.tts_rate, voice=runtime.settings.tts_voice)
    return _speaker


@router.post("/v1/voice/transcribe")
async def transcribe(
    request: Request,
    file: UploadFile = File(...),
    language: str | None = Form(default=None),
) -> dict:
    runtime = get_runtime(request)
    if not runtime.settings.voice_enabled:
        raise HTTPException(400, "voice is disabled in settings")
    audio = await file.read()
    if not audio:
        raise HTTPException(400, "empty audio payload")
    try:
        recognizer = _lazy_recognizer(request)
        result = await atranscribe(recognizer, audio, language=language)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"text": result.text, "language": result.language, "duration": result.duration}


@router.post("/v1/voice/speak")
async def speak(body: SpeakRequest, request: Request) -> FileResponse:
    runtime = get_runtime(request)
    if not runtime.settings.voice_enabled:
        raise HTTPException(400, "voice is disabled in settings")
    try:
        speaker = _lazy_speaker(request)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    out = Path(tempfile.mkstemp(suffix=".wav", prefix="jarvis-tts-")[1])
    try:
        speaker.synth_to_wav(body.text, str(out))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return FileResponse(str(out), media_type="audio/wav", filename="speak.wav")
