"""Common LLM provider interface.

All providers implement :class:`LLMProvider`. The interface is intentionally
minimal so we can point at anything from a local Ollama server running Gemma
to Anthropic's cloud API without leaking provider-specific shapes into the
orchestrator.

The ``chat`` method returns a :class:`ChatResult`. The ``stream`` method
yields raw token strings. Tool-calling is modelled in the OpenAI dialect
(``tool_calls`` as a list of ``{id, type, function: {name, arguments}}``)
because that is the most widely implemented shape; providers that speak a
different dialect translate internally.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSchema:
    """A JSON-schema description of a tool the model may call."""

    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


@dataclass
class ChatMessage:
    """Neutral chat message. Accepts OpenAI-style ``tool_calls``."""

    role: str  # system | user | assistant | tool
    content: str = ""
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChatMessage:
        return cls(
            role=d.get("role", "user"),
            content=d.get("content", "") or "",
            tool_calls=d.get("tool_calls"),
            tool_call_id=d.get("tool_call_id"),
            name=d.get("name"),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            out["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            out["tool_call_id"] = self.tool_call_id
        if self.name:
            out["name"] = self.name
        return out


@dataclass
class ChatResult:
    """What a provider returns for a non-streaming call."""

    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    provider: str = ""
    model: str = ""


class LLMProvider(ABC):
    """Abstract base class for every LLM backend."""

    name: str = "base"
    model: str = ""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> ChatResult:
        """Blocking chat completion."""

    @abstractmethod
    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Yield text deltas. Tool calls are surfaced via :meth:`chat`."""

    async def health(self) -> bool:  # pragma: no cover - overridden by providers
        return True

    async def close(self) -> None:  # pragma: no cover
        return None
