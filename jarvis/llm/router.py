"""Provider selection with automatic fallback.

The router constructs whichever provider is configured as primary. If a call
fails with :class:`LLMUnavailable`, it transparently retries against the
configured fallback. This gives Jarvis a "use local Gemma when Ollama is up,
otherwise call Claude" story out of the box.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from jarvis.config import Settings
from jarvis.errors import ConfigurationError, LLMError, LLMUnavailable
from jarvis.llm.anthropic import AnthropicProvider
from jarvis.llm.base import ChatMessage, ChatResult, LLMProvider, ToolSchema
from jarvis.llm.echo import EchoProvider
from jarvis.llm.ollama import OllamaProvider
from jarvis.llm.openai import OpenAIProvider
from jarvis.logging import get_logger

log = get_logger(__name__)


def _construct(name: str, settings: Settings) -> LLMProvider:
    name = (name or "").lower()
    if name == "ollama":
        return OllamaProvider(settings.ollama_base_url, settings.ollama_model)
    if name == "anthropic":
        if not settings.anthropic_api_key:
            raise ConfigurationError("anthropic selected but ANTHROPIC_API_KEY is empty")
        return AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model)
    if name == "openai":
        if not settings.openai_api_key:
            raise ConfigurationError("openai selected but OPENAI_API_KEY is empty")
        return OpenAIProvider(
            settings.openai_api_key, settings.openai_base_url, settings.openai_model
        )
    if name == "echo":
        return EchoProvider()
    raise ConfigurationError(f"unknown llm provider: {name!r}")


class RoutedProvider(LLMProvider):
    """Primary provider with optional fallback on :class:`LLMUnavailable`."""

    name = "routed"

    def __init__(self, primary: LLMProvider, fallback: LLMProvider | None = None) -> None:
        self.primary = primary
        self.fallback = fallback
        self.model = primary.model

    async def close(self) -> None:
        await self.primary.close()
        if self.fallback is not None:
            await self.fallback.close()

    async def health(self) -> bool:
        if await self.primary.health():
            return True
        if self.fallback is not None:
            return await self.fallback.health()
        return False

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> ChatResult:
        try:
            return await self.primary.chat(
                messages, tools=tools, temperature=temperature, max_tokens=max_tokens, **kwargs
            )
        except LLMUnavailable as exc:
            if self.fallback is None:
                raise
            log.warning("llm.primary_unavailable", error=str(exc), falling_back=self.fallback.name)
            return await self.fallback.chat(
                messages, tools=tools, temperature=temperature, max_tokens=max_tokens, **kwargs
            )

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        primary_failed = False
        try:
            async for chunk in self.primary.stream(
                messages, tools=tools, temperature=temperature, max_tokens=max_tokens, **kwargs
            ):
                yield chunk
            return
        except LLMUnavailable as exc:
            if self.fallback is None:
                raise
            primary_failed = True
            log.warning(
                "llm.primary_stream_unavailable", error=str(exc), falling_back=self.fallback.name
            )
        except LLMError:
            raise

        if primary_failed:
            async for chunk in self.fallback.stream(  # type: ignore[union-attr]
                messages, tools=tools, temperature=temperature, max_tokens=max_tokens, **kwargs
            ):
                yield chunk


def build_provider(settings: Settings) -> LLMProvider:
    """Construct the default provider, with fallback if configured."""
    primary = _construct(settings.llm_provider, settings)
    fallback: LLMProvider | None = None
    if settings.llm_fallback and settings.llm_fallback != settings.llm_provider:
        try:
            fallback = _construct(settings.llm_fallback, settings)
        except ConfigurationError as exc:
            log.warning("llm.fallback_disabled", reason=str(exc))
            fallback = None
    if fallback is None:
        return primary
    return RoutedProvider(primary, fallback)
