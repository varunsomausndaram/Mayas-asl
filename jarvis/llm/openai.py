"""OpenAI-compatible provider.

Works with OpenAI, Groq, Together, Fireworks, OpenRouter, or anything else
that speaks the ``/v1/chat/completions`` dialect. The Gemini API also has an
OpenAI-compatible endpoint which this provider can point at.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from jarvis.errors import LLMError, LLMUnavailable
from jarvis.llm.base import ChatMessage, ChatResult, LLMProvider, ToolSchema


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float = 180.0) -> None:
        if not api_key:
            raise LLMError("openai: OPENAI_API_KEY is empty")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        return bool(self.api_key)

    def _payload(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None,
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            body["tools"] = [t.to_openai() for t in tools]
        return body

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
            r = await self._client.post(
                f"{self.base_url}/chat/completions",
                json=self._payload(messages, tools, temperature, max_tokens, stream=False),
            )
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"openai network error: {exc}") from exc
        if r.status_code >= 400:
            raise LLMError(f"openai error {r.status_code}: {r.text[:500]}")

        data = r.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        return ChatResult(
            content=msg.get("content") or "",
            tool_calls=msg.get("tool_calls") or [],
            finish_reason=choice.get("finish_reason"),
            usage=data.get("usage") or {},
            provider=self.name,
            model=self.model,
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
        try:
            async with self._client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=self._payload(messages, tools, temperature, max_tokens, stream=True),
            ) as r:
                if r.status_code >= 400:
                    body_text = (await r.aread()).decode("utf-8", errors="replace")
                    raise LLMError(f"openai error {r.status_code}: {body_text[:500]}")
                async for line in r.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        obj = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    choice = (obj.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    chunk = delta.get("content")
                    if chunk:
                        yield chunk
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"openai network error: {exc}") from exc
