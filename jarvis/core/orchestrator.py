"""The Jarvis orchestrator.

This is the agent loop: given a user turn, the orchestrator renders the
persona into a system prompt, pulls recent conversation and profile notes
from the memory store, calls the LLM with the active tool schemas, executes
any tool calls (after clearing permission), feeds the results back, and
either returns a final answer or iterates up to a hard cap.

Streaming and interruption live here too. ``run_stream`` yields a sequence
of :class:`OrchestratorEvent` objects that callers can pipe into whatever
transport they want: WebSocket frames for the browser, stdout for the CLI,
TTS chunks for the voice loop.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from jarvis.config import Settings
from jarvis.core.permissions import PermissionBroker, assess
from jarvis.core.persona import Persona
from jarvis.core.profile import UserProfileStore
from jarvis.errors import JarvisError
from jarvis.events import Event, EventBus
from jarvis.llm.base import ChatMessage, LLMProvider, ToolSchema
from jarvis.logging import get_logger
from jarvis.memory.models import Message
from jarvis.memory.store import MemoryStore
from jarvis.security.audit import AuditLog, AuditRecord
from jarvis.tools.base import ToolRegistry, run_tool_call

log = get_logger(__name__)


MAX_TOOL_LOOPS = 8


class EventKind(str, Enum):
    TOKEN = "token"
    THINKING = "thinking"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESOLVED = "approval_resolved"
    MESSAGE = "message"
    USAGE = "usage"
    DONE = "done"
    ERROR = "error"


@dataclass
class OrchestratorEvent:
    kind: EventKind
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_json(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "ts": self.ts, "data": self.data}


@dataclass
class TurnResult:
    """What a completed non-streaming turn returns to the caller."""

    session_id: str
    assistant: Message
    tool_messages: list[Message] = field(default_factory=list)
    aborted: bool = False
    usage: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "assistant": self.assistant.to_chat_dict(),
            "tool_messages": [m.to_chat_dict() for m in self.tool_messages],
            "aborted": self.aborted,
            "usage": self.usage,
        }


class Orchestrator:
    """The agent loop. One instance per process."""

    def __init__(
        self,
        *,
        settings: Settings,
        llm: LLMProvider,
        registry: ToolRegistry,
        memory: MemoryStore,
        profile_store: UserProfileStore,
        persona: Persona,
        permissions: PermissionBroker,
        audit: AuditLog,
        bus: EventBus,
    ) -> None:
        self.settings = settings
        self.llm = llm
        self.registry = registry
        self.memory = memory
        self.profile_store = profile_store
        self.persona = persona
        self.permissions = permissions
        self.audit = audit
        self.bus = bus
        self._interrupts: dict[str, asyncio.Event] = {}

    # ----------------------------------------------------------- lifecycle
    async def close(self) -> None:
        await self.llm.close()

    def interrupt(self, session_id: str) -> None:
        evt = self._interrupts.get(session_id)
        if evt is not None:
            evt.set()

    # --------------------------------------------------------------- entry
    async def run(
        self,
        session_id: str,
        user_text: str,
        *,
        tool_filter: list[str] | None = None,
    ) -> TurnResult:
        """Non-streaming convenience wrapper around :meth:`run_stream`."""
        events: list[OrchestratorEvent] = []
        assistant_text = ""
        usage: dict[str, int] = {}
        tool_msgs: list[Message] = []
        aborted = False
        async for event in self.run_stream(session_id, user_text, tool_filter=tool_filter):
            events.append(event)
            if event.kind == EventKind.TOKEN:
                assistant_text += event.data.get("text", "")
            elif event.kind == EventKind.USAGE:
                usage = event.data
            elif event.kind == EventKind.DONE:
                aborted = event.data.get("aborted", False)
            elif event.kind == EventKind.MESSAGE:
                kind = event.data.get("role")
                if kind == "tool":
                    tool_msgs.append(
                        Message(
                            session_id=session_id,
                            role="tool",
                            content=event.data.get("content", ""),
                            tool_call_id=event.data.get("tool_call_id"),
                            name=event.data.get("name"),
                        )
                    )
        assistant = Message(session_id=session_id, role="assistant", content=assistant_text)
        return TurnResult(
            session_id=session_id,
            assistant=assistant,
            tool_messages=tool_msgs,
            aborted=aborted,
            usage=usage,
        )

    # --------------------------------------------------------------- stream
    async def run_stream(
        self,
        session_id: str,
        user_text: str,
        *,
        tool_filter: list[str] | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        """The streaming agent loop. Yields :class:`OrchestratorEvent`s."""
        interrupt_evt = self._interrupts.setdefault(session_id, asyncio.Event())
        interrupt_evt.clear()

        await self._ensure_session(session_id)
        user_msg = Message(session_id=session_id, role="user", content=user_text)
        await self.memory.add_message(user_msg)

        profile = await self.profile_store.load()
        tools = self._select_tools(tool_filter)
        tool_summary = _format_tool_summary(tools)
        system_prompt = self.persona.render_system(
            profile_notes=profile.render_notes(), tool_summary=tool_summary
        )

        history = await self.memory.recent_chat_dicts(session_id, limit=60)
        messages: list[ChatMessage] = [ChatMessage(role="system", content=system_prompt)]
        messages.extend(ChatMessage.from_dict(d) for d in history)

        final_text = ""
        usage_total: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
        assistant_records: list[Message] = []

        for loop in range(MAX_TOOL_LOOPS):
            if interrupt_evt.is_set():
                yield OrchestratorEvent(EventKind.DONE, {"aborted": True, "reason": "interrupted"})
                return

            yield OrchestratorEvent(EventKind.THINKING, {"loop": loop})
            try:
                result = await self.llm.chat(
                    messages,
                    tools=tools,
                    temperature=self.settings.llm_temperature,
                    max_tokens=self.settings.llm_max_tokens,
                )
            except JarvisError as exc:
                yield OrchestratorEvent(EventKind.ERROR, {"message": str(exc), "code": exc.code})
                yield OrchestratorEvent(EventKind.DONE, {"aborted": True})
                return
            except Exception as exc:  # pragma: no cover
                log.exception("orchestrator.llm_failed")
                yield OrchestratorEvent(EventKind.ERROR, {"message": f"LLM error: {exc}"})
                yield OrchestratorEvent(EventKind.DONE, {"aborted": True})
                return

            if result.usage:
                usage_total["prompt_tokens"] += int(result.usage.get("prompt_tokens", 0) or result.usage.get("input_tokens", 0) or 0)
                usage_total["completion_tokens"] += int(result.usage.get("completion_tokens", 0) or result.usage.get("output_tokens", 0) or 0)

            # --- assistant text
            if result.content:
                for piece in _chunk(result.content, 120):
                    if interrupt_evt.is_set():
                        yield OrchestratorEvent(EventKind.DONE, {"aborted": True, "reason": "interrupted"})
                        return
                    yield OrchestratorEvent(EventKind.TOKEN, {"text": piece})
                final_text += result.content

            assistant = Message(
                session_id=session_id,
                role="assistant",
                content=result.content,
                tool_calls=result.tool_calls or None,
            )
            await self.memory.add_message(assistant)
            assistant_records.append(assistant)
            messages.append(ChatMessage.from_dict(assistant.to_chat_dict()))

            # --- stop if no tool calls
            if not result.tool_calls:
                break

            # --- run tool calls sequentially so approvals are orderly
            for tool_call in result.tool_calls:
                if interrupt_evt.is_set():
                    yield OrchestratorEvent(EventKind.DONE, {"aborted": True, "reason": "interrupted"})
                    return

                args = _safe_args(tool_call)
                name = (tool_call.get("function") or {}).get("name") or ""
                assessment = assess(name, args)

                yield OrchestratorEvent(
                    EventKind.TOOL_CALL_START,
                    {
                        "id": tool_call.get("id"),
                        "name": name,
                        "arguments": args,
                        "risk": assessment.overall.value,
                    },
                )

                if assessment.overall.value != "none":
                    yield OrchestratorEvent(EventKind.APPROVAL_REQUEST, assessment.to_json())
                approved, reason = await self.permissions.authorize(assessment)
                yield OrchestratorEvent(
                    EventKind.APPROVAL_RESOLVED,
                    {"tool": name, "approved": approved, "reason": reason},
                )
                await self.audit.record(
                    AuditRecord(
                        kind="approval",
                        actor="user" if approved else "system",
                        subject=name,
                        action=json.dumps(args)[:500],
                        result="approved" if approved else "denied",
                        details={"risk": assessment.overall.value, "reason": reason},
                    )
                )

                if not approved:
                    result_text = json.dumps(
                        {
                            "ok": False,
                            "error": f"permission denied: {reason}",
                            "risk": assessment.overall.value,
                        }
                    )
                    tool_msg = Message(
                        session_id=session_id,
                        role="tool",
                        content=result_text,
                        tool_call_id=tool_call.get("id"),
                        name=name,
                    )
                    await self.memory.add_message(tool_msg)
                    messages.append(ChatMessage.from_dict(tool_msg.to_chat_dict()))
                    yield OrchestratorEvent(
                        EventKind.MESSAGE,
                        {
                            "role": "tool",
                            "name": name,
                            "tool_call_id": tool_call.get("id"),
                            "content": result_text,
                        },
                    )
                    continue

                call_id, tool_result = await run_tool_call(
                    self.registry, tool_call, timeout=120.0
                )
                yield OrchestratorEvent(
                    EventKind.TOOL_CALL_END,
                    {
                        "id": call_id,
                        "name": name,
                        "ok": tool_result.ok,
                        "error": tool_result.error,
                        "output": _trim(tool_result.output, 1200),
                    },
                )
                await self.audit.record(
                    AuditRecord(
                        kind="tool_call",
                        actor="llm",
                        subject=name,
                        action=json.dumps(args)[:500],
                        result="ok" if tool_result.ok else "failed",
                        details={"error": tool_result.error},
                    )
                )
                tool_text = tool_result.to_text()
                tool_msg = Message(
                    session_id=session_id,
                    role="tool",
                    content=tool_text,
                    tool_call_id=call_id,
                    name=name,
                )
                await self.memory.add_message(tool_msg)
                messages.append(ChatMessage.from_dict(tool_msg.to_chat_dict()))
                yield OrchestratorEvent(
                    EventKind.MESSAGE,
                    {"role": "tool", "name": name, "tool_call_id": call_id, "content": tool_text},
                )
        else:
            # Loop exit without break: tool-call loop cap reached.
            yield OrchestratorEvent(
                EventKind.ERROR,
                {"message": f"reached tool-loop cap ({MAX_TOOL_LOOPS})"},
            )

        # Learn from turn: small bookkeeping for the profile.
        await self._post_turn_profile_update(profile, user_text, final_text)

        yield OrchestratorEvent(EventKind.USAGE, usage_total)
        yield OrchestratorEvent(
            EventKind.DONE,
            {
                "aborted": False,
                "assistant_text": final_text,
                "turns": len(assistant_records),
            },
        )
        await self.bus.publish(
            Event(
                topic=f"session.{session_id}",
                type="turn_done",
                data={"session_id": session_id, "text": final_text[:1000]},
            )
        )

    # ---------------------------------------------------------------- helpers
    async def _ensure_session(self, session_id: str) -> None:
        if await self.memory.get_session(session_id) is None:
            await self.memory.create_session(title=f"Session {session_id[:6]}")

    def _select_tools(self, tool_filter: list[str] | None) -> list[ToolSchema]:
        visible = self.registry.schemas()
        if not tool_filter:
            return visible
        wanted = set(tool_filter)
        return [s for s in visible if s.name in wanted]

    async def _post_turn_profile_update(
        self, profile, user_text: str, assistant_text: str
    ) -> None:
        """Light-weight personality learning: pick up the user's preferred name."""
        text = user_text.strip()
        if not profile.name:
            for pattern in (
                r"^\s*my name is (\w[\w\s.'-]{1,40})",
                r"^\s*i'?m (\w[\w\s.'-]{1,40})",
                r"^\s*call me (\w[\w\s.'-]{1,40})",
            ):
                import re

                m = re.search(pattern, text, flags=re.IGNORECASE)
                if m:
                    name = m.group(1).strip().rstrip(".,!?")
                    await self.profile_store.update(name=name, preferred_address=name)
                    await self.profile_store.add_note(
                        f"User introduced themselves as {name}.", tag="profile"
                    )
                    return


# =============================================================== helpers
def _chunk(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def _safe_args(tool_call: dict[str, Any]) -> dict[str, Any]:
    fn = tool_call.get("function") or {}
    raw = fn.get("arguments")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def _trim(value: Any, limit: int = 1200) -> Any:
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"... [+{len(value) - limit}]"
    if isinstance(value, (dict, list)):
        s = json.dumps(value, default=str)
        if len(s) <= limit:
            return value
        return s[:limit] + f"... [+{len(s) - limit}]"
    return value


def _format_tool_summary(schemas: list[ToolSchema]) -> str:
    return "\n".join(f"- {s.name}: {s.description}" for s in schemas)
