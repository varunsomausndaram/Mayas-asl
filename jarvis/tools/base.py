"""Tool base classes, registry, and execution plumbing."""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from jarvis.errors import ToolError, ToolNotAllowed
from jarvis.llm.base import ToolSchema
from jarvis.logging import get_logger

log = get_logger(__name__)


@dataclass
class ToolResult:
    """Value returned by a :meth:`Tool.run` invocation."""

    ok: bool
    output: Any = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_text(self) -> str:
        """Render to a string suitable for a ``tool`` message sent back to the LLM."""
        if not self.ok:
            return json.dumps({"ok": False, "error": self.error or "tool failed"})
        if isinstance(self.output, (dict, list)):
            return json.dumps({"ok": True, "output": self.output}, default=str)
        return json.dumps({"ok": True, "output": str(self.output)})


class Tool(ABC):
    """Abstract base class every tool extends.

    A tool has a machine name (``name``), a human description, a JSON-schema
    for its arguments, and an async ``run`` method. Keep side effects
    contained — a tool that dispatches a Claude Code session should return
    quickly and stream its progress via the event bus.
    """

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=self.parameters)

    @abstractmethod
    async def run(self, **kwargs: Any) -> ToolResult: ...


class ToolRegistry:
    """Holds the tools available to the orchestrator for a given call.

    The registry enforces the allowlist from settings. A tool present in the
    registry but not in the allowlist cannot be executed — it is also hidden
    from the LLM's schema list so the model can't hallucinate its use.
    """

    def __init__(self, allowed: set[str]) -> None:
        self._tools: dict[str, Tool] = {}
        self._allowed = allowed

    @property
    def allowed(self) -> set[str]:
        return self._allowed

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("tool must have a non-empty name")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"unknown tool: {name!r}", code="unknown_tool", status=404)
        if "*" not in self._allowed and tool.name not in self._allowed:
            raise ToolNotAllowed(f"tool not in allowlist: {name!r}")
        return tool

    def visible_tools(self) -> list[Tool]:
        if "*" in self._allowed:
            return list(self._tools.values())
        return [t for t in self._tools.values() if t.name in self._allowed]

    def schemas(self) -> list[ToolSchema]:
        return [t.schema() for t in self.visible_tools()]

    def names(self) -> list[str]:
        return [t.name for t in self.visible_tools()]

    async def run(self, name: str, arguments: dict[str, Any], *, timeout: float = 120.0) -> ToolResult:
        started = time.time()
        try:
            tool = self.get(name)
            result = await asyncio.wait_for(tool.run(**arguments), timeout=timeout)
        except asyncio.TimeoutError:
            log.warning("tool.timeout", name=name, timeout=timeout)
            return ToolResult(ok=False, error=f"tool {name!r} timed out after {timeout}s")
        except ToolError as exc:
            log.warning("tool.error", name=name, error=str(exc))
            return ToolResult(ok=False, error=str(exc), meta={"code": exc.code})
        except Exception as exc:
            log.exception("tool.unexpected", name=name)
            return ToolResult(ok=False, error=f"{type(exc).__name__}: {exc}")
        finally:
            duration = time.time() - started
            log.info("tool.ran", name=name, duration=round(duration, 3))
        return result


async def run_tool_call(
    registry: ToolRegistry,
    tool_call: dict[str, Any],
    *,
    timeout: float = 120.0,
    on_event: Callable[[str, dict[str, Any]], Any] | None = None,
) -> tuple[str, ToolResult]:
    """Execute an LLM-produced tool call, returning ``(call_id, result)``.

    Accepts the OpenAI-style ``tool_call`` shape the orchestrator passes in.
    ``on_event`` is invoked with ``(event_type, payload)`` so callers can
    stream progress without the tool needing to know about the event bus.
    """
    call_id = tool_call.get("id") or "call_0"
    fn = tool_call.get("function") or {}
    name = fn.get("name") or ""
    args_raw = fn.get("arguments") or "{}"
    if isinstance(args_raw, dict):
        args = args_raw
    else:
        try:
            args = json.loads(args_raw)
        except json.JSONDecodeError as exc:
            return call_id, ToolResult(ok=False, error=f"invalid tool arguments JSON: {exc}")

    if on_event:
        await _maybe_await(on_event("tool_call_start", {"name": name, "arguments": args, "id": call_id}))
    result = await registry.run(name, args, timeout=timeout)
    if on_event:
        await _maybe_await(
            on_event(
                "tool_call_end",
                {
                    "name": name,
                    "id": call_id,
                    "ok": result.ok,
                    "error": result.error,
                    "output": _trim(result.output),
                },
            )
        )
    return call_id, result


async def _maybe_await(value: Any) -> None:
    if asyncio.iscoroutine(value):
        await value


def _trim(value: Any, limit: int = 4096) -> Any:
    """Truncate tool output used purely for UI display."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"... [truncated {len(value) - limit} chars]"
    if isinstance(value, (dict, list)):
        serialised = json.dumps(value, default=str)
        if len(serialised) <= limit:
            return value
        return serialised[:limit] + f"... [truncated {len(serialised) - limit} chars]"
    return value
