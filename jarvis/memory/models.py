"""Plain-data models used by the memory layer.

These are Pydantic models rather than ORM rows because everything is small
and JSON-friendly; the SQLite store in :mod:`jarvis.memory.store` handles
serialisation. Keep the surface narrow — the whole point is auditability.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]


def _new_id() -> str:
    return uuid.uuid4().hex


class Message(BaseModel):
    """A single turn in a conversation.

    ``tool_calls`` and ``tool_call_id`` are optional so the same model can
    represent a plain chat message, a tool invocation, or a tool result.
    """

    id: str = Field(default_factory=_new_id)
    session_id: str
    role: Role
    content: str = ""
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    ts: float = Field(default_factory=time.time)
    meta: dict[str, Any] = Field(default_factory=dict)

    def to_chat_dict(self) -> dict[str, Any]:
        """Render to the OpenAI-style chat dict the LLM providers consume."""
        out: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            out["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            out["tool_call_id"] = self.tool_call_id
        if self.name:
            out["name"] = self.name
        return out


class Session(BaseModel):
    """A conversation, keyed by a stable ID handed back to clients."""

    id: str = Field(default_factory=_new_id)
    title: str = "New session"
    created: float = Field(default_factory=time.time)
    updated: float = Field(default_factory=time.time)
    meta: dict[str, Any] = Field(default_factory=dict)
