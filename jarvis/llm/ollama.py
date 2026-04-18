"""Ollama provider — talks to a local Ollama server (Gemma, Llama, etc.).

Uses Ollama's chat API, which understands ``tools`` in the OpenAI dialect
from 0.3 onward. If the model doesn't speak tool calling natively, we fall
back to a structured-JSON protocol in :mod:`jarvis.core.orchestrator`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from jarvis.errors import LLMError, LLMUnavailable
from jarvis.llm.base import ChatMessage, ChatResult, LLMProvider, ToolSchema


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        try:
            r = await self._client.get(f"{self.base_url}/api/tags", timeout=5.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    # ---------------------------------------------------------------- helpers
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
            "stream": stream,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if tools:
            body["tools"] = [t.to_openai() for t in tools]
        return body

    # ------------------------------------------------------------------- chat
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
                f"{self.base_url}/api/chat",
                json=self._payload(messages, tools, temperature, max_tokens, stream=False),
            )
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"ollama unreachable at {self.base_url}: {exc}") from exc
        if r.status_code >= 400:
            raise LLMError(f"ollama error {r.status_code}: {r.text[:500]}")

        data = r.json()
        msg = data.get("message") or {}
        content = msg.get("content") or ""
        tool_calls_raw = msg.get("tool_calls") or []
        tool_calls = _normalise_tool_calls(tool_calls_raw)

        return ChatResult(
            content=content,
            tool_calls=tool_calls,
            finish_reason=data.get("done_reason") or ("stop" if data.get("done") else None),
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
            provider=self.name,
            model=self.model,
        )

    # ----------------------------------------------------------------- stream
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
                f"{self.base_url}/api/chat",
                json=self._payload(messages, tools, temperature, max_tokens, stream=True),
            ) as r:
                if r.status_code >= 400:
                    body = (await r.aread()).decode("utf-8", errors="replace")
                    raise LLMError(f"ollama error {r.status_code}: {body[:500]}")
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = obj.get("message") or {}
                    chunk = msg.get("content") or ""
                    if chunk:
                        yield chunk
                    if obj.get("done"):
                        break
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"ollama unreachable at {self.base_url}: {exc}") from exc


def _normalise_tool_calls(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Ollama's tool-call payload into the OpenAI shape we use."""
    out = []
    for i, tc in enumerate(raw):
        fn = tc.get("function") or {}
        args = fn.get("arguments")
        if isinstance(args, dict):
            args_str = json.dumps(args)
        elif isinstance(args, str):
            args_str = args
        else:
            args_str = "{}"
        out.append(
            {
                "id": tc.get("id") or f"call_{i}",
                "type": "function",
                "function": {"name": fn.get("name", ""), "arguments": args_str},
            }
        )
    return out
