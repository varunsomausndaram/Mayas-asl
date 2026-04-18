"""Top-level Typer app for the ``jarvis`` CLI.

Sub-commands:

* ``jarvis chat`` — interactive REPL.
* ``jarvis ask <text>`` — one-shot question, prints the reply.
* ``jarvis voice`` — push-to-talk / streaming voice mode.
* ``jarvis dispatch`` — hand a task to Claude Code and stream the log.
* ``jarvis schedule ...`` — scheduler CRUD.
* ``jarvis serve`` — run the server (same as ``jarvisd``).
* ``jarvis tray`` — run the system-tray applet.
* ``jarvis info`` / ``jarvis health`` — diagnostics.
"""

from __future__ import annotations

import asyncio
import os

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jarvis import __version__
from jarvis.cli.client import JarvisClient

app = typer.Typer(add_completion=False, help="Jarvis — your personal AI assistant.")
console = Console()


# --------------------------------------------------------------------- config
def _base_url() -> str:
    host = os.environ.get("JARVIS_HOST", "127.0.0.1")
    if host == "0.0.0.0":
        host = "127.0.0.1"
    port = os.environ.get("JARVIS_PORT", "8765")
    return os.environ.get("JARVIS_URL", f"http://{host}:{port}")


def _api_key() -> str:
    key = os.environ.get("JARVIS_API_KEY", "").strip()
    if not key or key == "change-me":
        typer.secho(
            "JARVIS_API_KEY is not set. Configure it in your .env before running the CLI.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    return key


def _client() -> JarvisClient:
    return JarvisClient(_base_url(), _api_key())


# ---------------------------------------------------------------- commands
@app.command("version")
def version_cmd() -> None:
    """Print the Jarvis version."""
    console.print(f"[bold]Jarvis[/] {__version__}")


@app.command("info")
def info_cmd() -> None:
    """Show runtime details from the server."""
    async def run() -> None:
        async with _client() as c:
            info = await c.runtime_info()
            profile = info.get("profile", {})
            persona = info.get("persona", {})
            tools = info.get("tools", [])
            t = Table(title="Runtime", show_lines=False, header_style="bold cyan")
            t.add_column("Key")
            t.add_column("Value")
            t.add_row("version", info.get("version", ""))
            t.add_row("llm", f"{info.get('llm', {}).get('provider')} / {info.get('llm', {}).get('model')}")
            t.add_row("persona address", persona.get("address", ""))
            t.add_row("humor level", str(persona.get("humor_level", "")))
            t.add_row("profile name", profile.get("name", "") or "(unset)")
            t.add_row("tools", ", ".join(tools))
            console.print(t)

    asyncio.run(run())


@app.command("health")
def health_cmd() -> None:
    """Hit ``/healthz``."""
    async def run() -> None:
        async with _client() as c:
            data = await c.health()
            console.print(data)

    asyncio.run(run())


@app.command("ask")
def ask_cmd(
    message: str = typer.Argument(..., help="Your question for Jarvis."),
    session: str = typer.Option(None, "--session", "-s", help="Existing session id."),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream the reply."),
) -> None:
    """Ask Jarvis something and print the reply."""

    async def run() -> None:
        async with _client() as c:
            if stream:
                session_id = session
                console.print("[dim]…[/]", end="")
                async for ev in c.chat_stream(message, session_id):
                    if ev.get("kind") == "token":
                        console.print(ev["data"].get("text", ""), end="")
                    elif ev.get("kind") == "tool_call_start":
                        console.print(f"\n[cyan]→ calling {ev['data'].get('name')}...[/]")
                    elif ev.get("kind") == "approval_request":
                        console.print(
                            Panel.fit(
                                f"[yellow]Approval requested[/] for {ev['data'].get('tool')} "
                                f"(risk={ev['data'].get('overall')})",
                                title="permission",
                            )
                        )
                    elif ev.get("kind") == "error":
                        console.print(f"\n[red]{ev['data'].get('message')}[/]")
                    elif ev.get("kind") == "done":
                        console.print()
                        return
            else:
                data = await c.chat(message, session_id=session)
                console.print(Panel(data.get("reply", ""), title="Jarvis"))

    asyncio.run(run())


@app.command("chat")
def chat_cmd(
    session: str = typer.Option(None, "--session", "-s"),
    new: bool = typer.Option(False, "--new", help="Start a fresh session."),
) -> None:
    """Interactive chat REPL. ``/help`` for commands."""
    from jarvis.cli.repl import run_repl

    asyncio.run(run_repl(_base_url(), _api_key(), session=session, new=new))


@app.command("voice")
def voice_cmd(
    session: str = typer.Option(None, "--session", "-s"),
    device: int = typer.Option(None, "--device", "-d", help="Input device index."),
    whisper_model: str = typer.Option("base", "--whisper-model"),
) -> None:
    """Push-to-talk voice mode (ENTER to start / stop recording)."""
    from jarvis.cli.voice_mode import run_voice

    asyncio.run(run_voice(_base_url(), _api_key(), session, device, whisper_model))


@app.command("dispatch")
def dispatch_cmd(
    prompt: str = typer.Argument(..., help="What Claude Code should do."),
    repo_url: str = typer.Option(None, "--repo", help="Optional git clone URL."),
    workspace: str = typer.Option(None, "--workspace", help="Named workspace directory."),
    follow: bool = typer.Option(True, "--follow/--no-follow"),
) -> None:
    """Hand a task off to Claude Code and stream the log."""

    async def run() -> None:
        async with _client() as c:
            job = await c._client.post(
                "/v1/dispatch",
                json={"prompt": prompt, "repo_url": repo_url, "workspace": workspace},
            )
            job.raise_for_status()
            job_data = job.json()
            console.print(f"[cyan]dispatched[/] job={job_data['id']} workspace={job_data['workspace']}")
            if not follow:
                return
            async for event in c.stream_dispatch(job_data["id"]):
                etype = event.get("type")
                data = event.get("data", {})
                if etype == "stdout":
                    console.print(f"[green]│[/] {data.get('line', '')}")
                elif etype == "stderr":
                    console.print(f"[red]│[/] {data.get('line', '')}")
                elif etype == "state":
                    console.print(f"[yellow]state[/] → {data.get('state')}")
                    if data.get("state") in {"succeeded", "failed", "cancelled", "timed_out"}:
                        return

    asyncio.run(run())


@app.command("serve")
def serve_cmd() -> None:
    """Run the Jarvis server (equivalent to ``jarvisd``)."""
    from jarvis.server.app import main

    main()


@app.command("tray")
def tray_cmd() -> None:
    """Launch the system-tray applet (requires [tray] extra)."""
    from jarvis.cli.tray import run_tray

    run_tray(_base_url(), _api_key())


# ---------------------------------------------------------- scheduler group
scheduler_app = typer.Typer(help="Manage scheduled jobs, cron, reminders.")
app.add_typer(scheduler_app, name="schedule")


@scheduler_app.command("list")
def sched_list() -> None:
    async def run() -> None:
        async with _client() as c:
            jobs = await c.list_jobs()
            if not jobs:
                console.print("[dim](no jobs scheduled)[/]")
                return
            t = Table(title="Scheduled jobs", header_style="bold cyan")
            for col in ("id", "title", "kind", "status", "next_run", "cron/every"):
                t.add_column(col)
            for j in jobs:
                when = j.get("cron") or (f"every {j['every_seconds']}s" if j.get("every_seconds") else "-")
                t.add_row(
                    j["id"][:8],
                    j["title"],
                    j["kind"],
                    j["status"],
                    str(j.get("next_run") or "-"),
                    when,
                )
            console.print(t)

    asyncio.run(run())


@scheduler_app.command("remind")
def sched_remind(
    message: str = typer.Argument(...),
    in_seconds: int = typer.Option(None, "--in-seconds"),
    at_iso: str = typer.Option(None, "--at"),
    title: str = typer.Option("Reminder", "--title"),
) -> None:
    async def run() -> None:
        async with _client() as c:
            if in_seconds is None and not at_iso:
                typer.secho("provide --in-seconds or --at", fg=typer.colors.RED)
                raise typer.Exit(2)
            payload = {
                "kind": "reminder",
                "title": title,
                "message": message,
            }
            if in_seconds is not None:
                import time

                payload["at_timestamp"] = time.time() + in_seconds
            elif at_iso:
                from datetime import datetime, timezone

                dt = datetime.fromisoformat(at_iso.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                payload["at_timestamp"] = dt.timestamp()
            job = await c.create_job(**payload)
            console.print(f"[green]scheduled[/] {job['id']}")

    asyncio.run(run())


@scheduler_app.command("cron")
def sched_cron(
    cron: str = typer.Argument(..., help="5-field cron expression."),
    title: str = typer.Argument(...),
    prompt: str = typer.Option(None, "--prompt", help="Fires a Jarvis prompt when due."),
    message: str = typer.Option(None, "--message", help="Reminder text (no prompt)."),
) -> None:
    async def run() -> None:
        async with _client() as c:
            kind = "prompt" if prompt else "reminder"
            payload = {"kind": kind, "title": title, "cron": cron}
            if prompt:
                payload["prompt"] = prompt
            if message:
                payload["message"] = message
            job = await c.create_job(**payload)
            console.print(f"[green]scheduled[/] {job['id']} @ {cron}")

    asyncio.run(run())


@scheduler_app.command("rm")
def sched_rm(job_id: str) -> None:
    async def run() -> None:
        async with _client() as c:
            await c.delete_job(job_id)
            console.print(f"[green]deleted[/] {job_id}")

    asyncio.run(run())


# ---------------------------------------------------------- profile group
profile_app = typer.Typer(help="Inspect / edit the user profile.")
app.add_typer(profile_app, name="profile")


@profile_app.command("show")
def profile_show() -> None:
    async def run() -> None:
        async with _client() as c:
            data = await c.get_profile()
            console.print(data)

    asyncio.run(run())


@profile_app.command("set")
def profile_set(
    name: str = typer.Option(None, "--name"),
    address: str = typer.Option(None, "--address"),
    humor: int = typer.Option(None, "--humor", min=0, max=3),
    verbosity: str = typer.Option(None, "--verbosity"),
    speech_rate: int = typer.Option(None, "--speech-rate", min=80, max=400),
    timezone: str = typer.Option(None, "--timezone"),
) -> None:
    patch = {
        "name": name,
        "preferred_address": address,
        "humor_level": humor,
        "verbosity": verbosity,
        "speech_rate": speech_rate,
        "timezone": timezone,
    }
    patch = {k: v for k, v in patch.items() if v is not None}
    if not patch:
        typer.secho("pass at least one --option", fg=typer.colors.YELLOW)
        raise typer.Exit(0)

    async def run() -> None:
        async with _client() as c:
            data = await c.patch_profile(**patch)
            console.print(data)

    asyncio.run(run())


if __name__ == "__main__":  # pragma: no cover
    app()
