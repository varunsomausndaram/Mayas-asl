"""Claude Code dispatcher.

Jarvis hands heavy-lifting coding work to Claude Code by invoking the
``claude`` CLI in headless mode. Each dispatched task runs inside its own
sandbox directory under ``CLAUDE_CODE_WORKSPACES`` and streams stdout back
to the caller through the event bus, so the UI can show progress live.

The dispatcher deliberately treats the CLI as an opaque executable: the
flags below are the documented stable surface of Claude Code's headless
mode, which makes this integration robust across upgrades.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from jarvis.errors import DispatchError
from jarvis.events import Event, EventBus
from jarvis.logging import get_logger

log = get_logger(__name__)


class JobState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class DispatchJob:
    """State tracked per dispatched Claude Code run."""

    id: str
    prompt: str
    workspace: Path
    repo_url: str | None = None
    state: JobState = JobState.PENDING
    started: float = 0.0
    finished: float | None = None
    returncode: int | None = None
    stdout: list[str] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def tail(self, lines: int = 50) -> list[str]:
        return self.stdout[-lines:]

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state.value,
            "started": self.started,
            "finished": self.finished,
            "returncode": self.returncode,
            "prompt": self.prompt[:500],
            "workspace": str(self.workspace),
            "repo_url": self.repo_url,
            "tail": self.tail(20),
        }


class ClaudeCodeDispatcher:
    """Runs Claude Code CLI sessions and tracks their state.

    Jobs are persisted in-memory; a restart loses history. That is
    intentional — Claude Code has its own conversation store under
    ``~/.claude``; Jarvis only needs to know *whether* a dispatch is still
    active so a client can watch or cancel it.
    """

    def __init__(
        self,
        cli: str,
        workspaces_root: Path,
        *,
        timeout: int = 1800,
        bus: EventBus | None = None,
    ) -> None:
        self.cli = cli
        self.workspaces_root = Path(workspaces_root)
        self.workspaces_root.mkdir(parents=True, exist_ok=True)
        self.timeout = int(timeout)
        self.bus = bus
        self._jobs: dict[str, DispatchJob] = {}
        self._procs: dict[str, asyncio.subprocess.Process] = {}
        self._lock = asyncio.Lock()

    # -------------------------------------------------------------- inventory
    def jobs(self) -> list[DispatchJob]:
        return sorted(self._jobs.values(), key=lambda j: -j.started)

    def get(self, job_id: str) -> DispatchJob | None:
        return self._jobs.get(job_id)

    # --------------------------------------------------------------- dispatch
    async def dispatch(
        self,
        prompt: str,
        *,
        repo_url: str | None = None,
        workspace: str | None = None,
        extra_flags: list[str] | None = None,
    ) -> DispatchJob:
        """Start a new Claude Code session and return the job descriptor."""
        if not prompt.strip():
            raise DispatchError("prompt is empty")

        job_id = uuid.uuid4().hex
        job_dir = self.workspaces_root / (workspace or job_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        if repo_url:
            await self._clone_repo(repo_url, job_dir)

        job = DispatchJob(
            id=job_id,
            prompt=prompt,
            workspace=job_dir,
            repo_url=repo_url,
            started=time.time(),
            state=JobState.PENDING,
        )
        self._jobs[job_id] = job
        await self._emit(job, "dispatch_started")
        asyncio.create_task(self._run(job, extra_flags or []))
        return job

    async def _clone_repo(self, url: str, into: Path) -> None:
        if any(into.iterdir()):
            log.info("dispatch.clone.skip", reason="workspace not empty", workspace=str(into))
            return
        cmd = ["git", "clone", "--depth", "1", url, str(into)]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise DispatchError(
                f"git clone failed ({proc.returncode}): {err.decode('utf-8', errors='replace')[:300]}"
            )
        log.info("dispatch.clone.ok", url=url, workspace=str(into))

    # ------------------------------------------------------------------- run
    async def _run(self, job: DispatchJob, extra_flags: list[str]) -> None:
        job.state = JobState.RUNNING
        await self._emit(job, "state")
        cmd = self._build_cmd(job.prompt, extra_flags)
        env = os.environ.copy()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(job.workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError:
            job.state = JobState.FAILED
            job.finished = time.time()
            job.stderr.append(f"Claude Code CLI not found: {self.cli!r}")
            await self._emit(job, "state")
            return

        self._procs[job.id] = proc
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    self._drain_stream(proc.stdout, job, "stdout"),
                    self._drain_stream(proc.stderr, job, "stderr"),
                ),
                timeout=self.timeout,
            )
            await proc.wait()
            job.returncode = proc.returncode
            job.state = JobState.SUCCEEDED if proc.returncode == 0 else JobState.FAILED
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            job.state = JobState.TIMED_OUT
            job.returncode = proc.returncode
            job.stderr.append(f"dispatch timed out after {self.timeout}s")
        finally:
            job.finished = time.time()
            self._procs.pop(job.id, None)
            await self._emit(job, "state")

    def _build_cmd(self, prompt: str, extra_flags: list[str]) -> list[str]:
        # ``claude -p`` is Claude Code's non-interactive "print" mode: it
        # consumes the prompt, runs tools, and exits. Output is streamed to
        # stdout — exactly what we need to relay to the UI.
        cmd = shlex.split(self.cli) + ["-p", prompt, "--output-format", "stream-json"]
        cmd.extend(extra_flags)
        return cmd

    async def _drain_stream(
        self,
        stream: asyncio.StreamReader | None,
        job: DispatchJob,
        kind: str,
    ) -> None:
        if stream is None:
            return
        bucket = job.stdout if kind == "stdout" else job.stderr
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip("\n")
            bucket.append(text)
            if len(bucket) > 5000:
                del bucket[: len(bucket) - 5000]
            await self._emit(job, kind, text)

    # ------------------------------------------------------------------- cancel
    async def cancel(self, job_id: str) -> bool:
        proc = self._procs.get(job_id)
        if proc is None:
            return False
        proc.kill()
        await proc.wait()
        job = self._jobs.get(job_id)
        if job is not None:
            job.state = JobState.CANCELLED
            job.finished = time.time()
            await self._emit(job, "state")
        return True

    # ------------------------------------------------------------------- stream
    async def stream(self, job_id: str) -> AsyncIterator[Event]:
        """Yield all events for a given job id. Finishes when job completes."""
        if self.bus is None:
            raise DispatchError("event bus not configured for streaming")
        async with await self.bus.subscribe(f"dispatch.{job_id}") as sub:
            async for event in sub:
                yield event
                if event.type == "state" and event.data.get("state") in {
                    JobState.SUCCEEDED.value,
                    JobState.FAILED.value,
                    JobState.CANCELLED.value,
                    JobState.TIMED_OUT.value,
                }:
                    return

    async def _emit(self, job: DispatchJob, kind: str, line: str | None = None) -> None:
        if self.bus is None:
            return
        payload: dict[str, Any] = {"job_id": job.id, "state": job.state.value}
        if line is not None:
            payload["line"] = line
        if kind == "state":
            payload["returncode"] = job.returncode
        await self.bus.publish(Event(topic=f"dispatch.{job.id}", type=kind, data=payload))


class ClaudeCodeDispatchTool:
    """Thin tool wrapper that exposes the dispatcher to the LLM.

    Declared here rather than in :mod:`jarvis.tools` so we can share the
    dispatcher instance with the HTTP layer.
    """

    name = "claude_code_dispatch"
    description = (
        "Dispatch a complex coding task to Claude Code. Use for multi-file refactors, "
        "repo-scale edits, or anything requiring tools beyond reading and writing one file. "
        "Returns a job id the caller can stream for progress."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "What Claude Code should do."},
            "repo_url": {"type": "string", "description": "Optional git clone URL."},
            "workspace": {"type": "string", "description": "Named workspace directory to reuse."},
        },
        "required": ["prompt"],
    }

    def __init__(self, dispatcher: ClaudeCodeDispatcher) -> None:
        self.dispatcher = dispatcher

    def schema(self):
        from jarvis.llm.base import ToolSchema

        return ToolSchema(name=self.name, description=self.description, parameters=self.parameters)

    async def run(
        self,
        *,
        prompt: str,
        repo_url: str | None = None,
        workspace: str | None = None,
        **_: Any,
    ):
        from jarvis.tools.base import ToolResult

        try:
            job = await self.dispatcher.dispatch(prompt, repo_url=repo_url, workspace=workspace)
        except DispatchError as exc:
            return ToolResult(ok=False, error=str(exc))
        return ToolResult(
            ok=True,
            output={
                "job_id": job.id,
                "state": job.state.value,
                "workspace": str(job.workspace),
                "stream_hint": f"Subscribe to dispatch.{job.id} to see progress.",
            },
        )
