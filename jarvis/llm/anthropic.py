"""Anthropic Claude provider.

We talk to Anthropic's Messages API directly over HTTPX so the dependency on
the ``anthropic`` package is optional. Tool use is translated from the
OpenAI-style ``tool_calls`` we standardise on into Anthropic's
``tool_use`` / ``tool_result`` blocks, and back.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from jarvis.errors import LLMError, LLMUnavailable
from jarvis.llm.base import ChatMessage, ChatResult, LLMProvider, ToolSchema

_API = "https://api.anthropic.com/v1/messages"
_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float = 180.0) -> None:
        if not api_key:
            raise LLMError("anthropic: ANTHROPIC_API_KEY is empty")
        self.api_key = api_key
        self.model = model
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "x-api-key": api_key,
                "anthropic-version": _VERSION,
                "content-type": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        return bool(self.api_key)

    # ----------------------------------------------------------------- helpers
    def _to_anthropic(
        self,
        messages: list[ChatMessage],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        system_parts: list[str] = []
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                if m.content:
                    system_parts.append(m.content)
                continue
            if m.role == "tool":
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_call_id or "",
                                "content": m.content,
                            }
                        ],
                    }
                )
                continue
            if m.role == "assistant" and m.tool_calls:
                blocks: list[dict[str, Any]] = []
                if m.content:
                    blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    fn = tc.get("function") or {}
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id") or "",
                            "name": fn.get("name") or "",
                            "input": args,
                        }
                    )
                out.append({"role": "assistant", "content": blocks})
                continue
            out.append({"role": m.role, "content": m.content})
        system = "\n\n".join(system_parts) if system_parts else None
        return system, out

    # -------------------------------------------------------------------- chat
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> ChatResult:
        system, msgs = self._to_anthropic(messages)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [t.to_anthropic() for t in tools]

        try:
            r = await self._client.post(_API, json=body)
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"anthropic network error: {exc}") from exc
        if r.status_code >= 400:
            raise LLMError(f"anthropic error {r.status_code}: {r.text[:500]}")

        data = r.json()
        content_parts = data.get("content") or []
        text_chunks: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for i, part in enumerate(content_parts):
            if part.get("type") == "text":
                text_chunks.append(part.get("text", ""))
            elif part.get("type") == "tool_use":
                tool_calls.append(
                    {
                        "id": part.get("id") or f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": part.get("name") or "",
                            "arguments": json.dumps(part.get("input") or {}),
                        },
                    }
                )
        return ChatResult(
            content="".join(text_chunks),
            tool_calls=tool_calls,
            finish_reason=data.get("stop_reason"),
            usage=(data.get("usage") or {}),
            provider=self.name,
            model=self.model,
        )

    # ------------------------------------------------------------------ stream
    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        system, msgs = self._to_anthropic(messages)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [t.to_anthropic() for t in tools]

        try:
            async with self._client.stream("POST", _API, json=body) as r:
                if r.status_code >= 400:
                    body_text = (await r.aread()).decode("utf-8", errors="replace")
                    raise LLMError(f"anthropic error {r.status_code}: {body_text[:500]}")
                async for line in r.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        evt = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if evt.get("type") == "content_block_delta":
                        delta = evt.get("delta") or {}
                        text = delta.get("text")
                        if text:
                            yield text
                    elif evt.get("type") == "message_stop":
                        break
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"anthropic network error: {exc}") from exc
