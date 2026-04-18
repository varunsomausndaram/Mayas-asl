"""Deterministic ``echo`` provider used by tests and offline smoke runs.

It returns the last user message back verbatim, optionally prefixed. It does
not call the network, so the full Jarvis stack can be exercised in CI without
any external dependency.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from jarvis.llm.base import ChatMessage, ChatResult, LLMProvider, ToolSchema


class EchoProvider(LLMProvider):
    name = "echo"
    model = "echo-1"

    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix

    def _last_user(self, messages: list[ChatMessage]) -> str:
        for m in reversed(messages):
            if m.role == "user":
                return m.content
        return ""

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> ChatResult:
        text = f"{self.prefix}{self._last_user(messages)}"
        return ChatResult(content=text, provider=self.name, model=self.model, finish_reason="stop")

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        text = f"{self.prefix}{self._last_user(messages)}"
        # Yield in small chunks so tests can observe streaming.
        for i in range(0, len(text), 8):
            yield text[i : i + 8]
