"""Voice subsystem: speech recognition, speech synthesis, wake word, barge-in.

The subsystem degrades gracefully: if the optional ``faster-whisper`` or
``pyttsx3`` dependencies are missing, the components raise a clear error at
first use rather than at import. That means the rest of Jarvis (server, CLI,
orchestrator, PWA) runs identically on a host without audio libraries.
"""

from jarvis.voice.conversation import VoiceSession
from jarvis.voice.stt import SpeechRecognizer, TranscriptionResult
from jarvis.voice.tts import SpeakChunk, Speaker

__all__ = [
    "SpeechRecognizer",
    "TranscriptionResult",
    "Speaker",
    "SpeakChunk",
    "VoiceSession",
]
