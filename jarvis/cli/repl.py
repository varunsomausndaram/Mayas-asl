"""Interactive Jarvis REPL.

Input is handled by :mod:`prompt_toolkit` (async-aware readline with history
and multi-line editing), streaming output is rendered via :mod:`rich`.
Typing ``/help`` prints slash commands; ``Ctrl-C`` interrupts the current
turn without killing the session.
"""

from __future__ import annotations

import asyncio
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.panel import Panel

from jarvis.cli.client import JarvisClient

console = Console()


HELP = """/help           Show this help.
/new            Start a fresh session.
/session <id>   Switch to an existing session.
/sessions       List recent sessions.
/interrupt      Cancel the current turn.
/approvals      List pending approvals.
/approve <id>   Approve the pending approval (once).
/deny <id>      Deny the pending approval.
/info           Show runtime info.
/quit           Exit the REPL.
"""


async def run_repl(base_url: str, api_key: str, *, session: str | None, new: bool) -> None:
    async with JarvisClient(base_url, api_key) as client:
        session_id = session
        if new or session_id is None:
            s = await client.create_session(title="cli")
            session_id = s["id"]
            console.print(f"[dim]session {session_id[:8]} started[/]")

        prompt = PromptSession(message="you> ")
        console.print(Panel.fit("Jarvis is online. Type /help.", style="bold cyan"))

        while True:
            try:
                with patch_stdout():
                    text = await prompt.prompt_async()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]bye.[/]")
                return

            text = (text or "").strip()
            if not text:
                continue

            if text.startswith("/"):
                keep_going = await _handle_slash(client, text, session_state := {"id": session_id})
                session_id = session_state["id"]
                if not keep_going:
                    return
                continue

            await _run_turn(client, session_id, text)


async def _run_turn(client: JarvisClient, session_id: str, text: str) -> None:
    task: asyncio.Task | None = None

    async def driver() -> None:
        console.print("[bold green]jarvis>[/] ", end="")
        async for ev in client.chat_stream(text, session_id):
            kind = ev.get("kind")
            data = ev.get("data", {})
            if kind == "token":
                console.print(data.get("text", ""), end="")
            elif kind == "tool_call_start":
                console.print(f"\n[cyan]→ {data.get('name')}({_short_args(data.get('arguments'))})[/]")
            elif kind == "approval_request":
                console.print(
                    Panel.fit(
                        _format_assessment(data),
                        title="Approval requested",
                        style="yellow",
                    )
                )
                console.print("[yellow]use /approvals then /approve <id> or /deny <id>[/]")
            elif kind == "approval_resolved":
                console.print(
                    f"[dim]approval: {data.get('tool')} → {'approved' if data.get('approved') else 'denied'}[/]"
                )
            elif kind == "tool_call_end":
                mark = "[green]✓[/]" if data.get("ok") else "[red]✗[/]"
                console.print(f"{mark} {data.get('name')}")
            elif kind == "error":
                console.print(f"\n[red]{data.get('message')}[/]")
            elif kind == "done":
                console.print()
                return

    try:
        task = asyncio.create_task(driver())
        await task
    except KeyboardInterrupt:
        await client.interrupt(session_id)
        console.print("\n[yellow]interrupted[/]")
        if task is not None:
            task.cancel()


async def _handle_slash(client: JarvisClient, text: str, state: dict[str, Any]) -> bool:
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("/quit", "/exit", "/q"):
        return False
    if cmd == "/help":
        console.print(HELP)
        return True
    if cmd == "/new":
        s = await client.create_session(title="cli")
        state["id"] = s["id"]
        console.print(f"[dim]session {state['id'][:8]} started[/]")
        return True
    if cmd == "/session":
        if not arg:
            console.print("[red]usage: /session <id>[/]")
            return True
        state["id"] = arg.strip()
        console.print(f"[dim]switched to {state['id'][:8]}[/]")
        return True
    if cmd == "/sessions":
        sessions = await client.list_sessions()
        for s in sessions[:20]:
            console.print(f"{s['id'][:8]}  {s.get('title', '')}")
        return True
    if cmd == "/interrupt":
        await client.interrupt(state["id"])
        console.print("[yellow]interrupt sent[/]")
        return True
    if cmd == "/approvals":
        pending = await client.pending_approvals()
        if not pending:
            console.print("[dim](none)[/]")
            return True
        for p in pending:
            a = p.get("assessment", {})
            console.print(f"{p['id'][:8]}  {a.get('tool')}  risk={a.get('overall')}  — {a.get('rationale')}")
        return True
    if cmd in ("/approve", "/deny"):
        if not arg:
            console.print("[red]usage: /approve <id>|/deny <id>[/]")
            return True
        decision = "approved_once" if cmd == "/approve" else "denied"
        # Accept id prefix: resolve against the pending list if a prefix is given.
        target = arg.strip()
        pending = await client.pending_approvals()
        match = next((p for p in pending if p["id"].startswith(target)), None)
        if match is None:
            console.print(f"[red]no pending approval matches {target!r}[/]")
            return True
        await client.resolve_approval(match["id"], decision)
        console.print(f"[green]{decision}[/] for {match['assessment'].get('tool')}")
        return True
    if cmd == "/info":
        info = await client.runtime_info()
        console.print(info)
        return True
    console.print(f"[red]unknown command: {cmd}[/]")
    return True


def _format_assessment(a: dict[str, Any]) -> str:
    lines = [
        f"[bold]{a.get('tool')}[/]  (risk={a.get('overall')})",
        f"reason: {a.get('rationale')}",
    ]
    if a.get("destructive"):
        lines.append("⚠ destructive")
    if not a.get("reversible", True):
        lines.append("⚠ not easily reversible")
    if a.get("arguments"):
        lines.append(f"args: {a.get('arguments')}")
    return "\n".join(lines)


def _short_args(args: Any, limit: int = 120) -> str:
    if not args:
        return ""
    import json

    s = json.dumps(args, default=str)
    return s if len(s) <= limit else s[:limit] + "..."
