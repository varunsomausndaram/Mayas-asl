"""User profile — the long-term memory Jarvis uses to learn your personality.

The profile stores (a) structured preferences (preferred name, humor level,
timezone, spoken rate, standing tool approvals) and (b) a rolling list of
free-form "notes" the orchestrator can append when it learns a durable fact
about the user. Notes older than a configurable horizon are summarised by
the LLM at next idle so the store doesn't grow without bound.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os


@dataclass
class UserProfile:
    name: str = ""
    preferred_address: str = "sir"
    timezone: str = "UTC"
    humor_level: int = 2
    verbosity: str = "concise"
    speech_rate: int = 180
    always_approved: list[str] = field(default_factory=list)
    notes: list[dict[str, Any]] = field(default_factory=list)
    inside_jokes: list[str] = field(default_factory=list)
    last_session: float = 0.0

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "preferred_address": self.preferred_address,
            "timezone": self.timezone,
            "humor_level": self.humor_level,
            "verbosity": self.verbosity,
            "speech_rate": self.speech_rate,
            "always_approved": list(self.always_approved),
            "notes": list(self.notes),
            "inside_jokes": list(self.inside_jokes),
            "last_session": self.last_session,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> UserProfile:
        return cls(
            name=data.get("name", ""),
            preferred_address=data.get("preferred_address", "sir"),
            timezone=data.get("timezone", "UTC"),
            humor_level=int(data.get("humor_level", 2)),
            verbosity=data.get("verbosity", "concise"),
            speech_rate=int(data.get("speech_rate", 180)),
            always_approved=list(data.get("always_approved", [])),
            notes=list(data.get("notes", [])),
            inside_jokes=list(data.get("inside_jokes", [])),
            last_session=float(data.get("last_session", 0.0)),
        )

    def render_notes(self, limit: int = 30) -> str:
        """Render the profile into the compact text Jarvis feeds the model."""
        bits: list[str] = []
        if self.name:
            bits.append(f"Name: {self.name}")
        bits.append(f"Preferred address: {self.preferred_address}")
        if self.timezone and self.timezone != "UTC":
            bits.append(f"Timezone: {self.timezone}")
        bits.append(f"Humor level: {self.humor_level}/3")
        bits.append(f"Verbosity preference: {self.verbosity}")
        if self.inside_jokes:
            bits.append("Inside jokes: " + " ; ".join(self.inside_jokes[-6:]))
        if self.notes:
            bits.append("Remembered notes:")
            for note in self.notes[-limit:]:
                bits.append(f"  - {note.get('text', '')}")
        return "\n".join(bits)


class UserProfileStore:
    """Async, file-backed profile store. One profile per deployment."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: UserProfile | None = None

    async def load(self) -> UserProfile:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            self._cache = UserProfile()
            await self.save()
            return self._cache
        async with aiofiles.open(self.path, encoding="utf-8") as f:
            raw = await f.read()
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError:
            data = {}
        self._cache = UserProfile.from_json(data)
        return self._cache

    async def save(self) -> None:
        if self._cache is None:
            return
        tmp = self.path.with_suffix(".json.tmp")
        async with aiofiles.open(tmp, "w", encoding="utf-8") as f:
            await f.write(json.dumps(self._cache.to_json(), indent=2))
        try:
            await aiofiles.os.replace(tmp, self.path)
        except AttributeError:
            tmp.replace(self.path)

    async def update(self, **kwargs: Any) -> UserProfile:
        profile = await self.load()
        for k, v in kwargs.items():
            if hasattr(profile, k):
                setattr(profile, k, v)
        await self.save()
        return profile

    async def add_note(self, text: str, *, tag: str = "observation") -> None:
        profile = await self.load()
        profile.notes.append({"ts": time.time(), "tag": tag, "text": text.strip()})
        if len(profile.notes) > 500:
            profile.notes = profile.notes[-500:]
        await self.save()

    async def add_inside_joke(self, text: str) -> None:
        profile = await self.load()
        text = text.strip()
        if text and text not in profile.inside_jokes:
            profile.inside_jokes.append(text)
            if len(profile.inside_jokes) > 40:
                profile.inside_jokes = profile.inside_jokes[-40:]
            await self.save()

    async def add_always_approved(self, fingerprint: str) -> None:
        profile = await self.load()
        if fingerprint not in profile.always_approved:
            profile.always_approved.append(fingerprint)
            await self.save()

    async def stamp_session(self) -> None:
        profile = await self.load()
        profile.last_session = time.time()
        await self.save()
