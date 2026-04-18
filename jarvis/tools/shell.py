"""Constrained shell execution.

Shell access is *off* by default (``JARVIS_SHELL_ENABLED=false``). When
enabled, commands are matched against an allowlist of executables and run
with a timeout, bounded output, and no shell interpolation. This is still a
sharp edge: only enable on machines you control.
"""

from __future__ import annotations

import asyncio
import shlex
from typing import Any

from jarvis.tools.base import Tool, ToolResult

_OUTPUT_LIMIT = 64_000


class ShellExecTool(Tool):
    name = "shell_exec"
    description = (
        "Execute an allowlisted command. The first token must be in the allowlist. "
        "Arguments are parsed as shell tokens but not expanded by a shell."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Full command string."},
            "cwd": {"type": "string", "description": "Working directory."},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 600, "default": 60},
        },
        "required": ["command"],
    }

    def __init__(self, allowed: set[str], default_cwd: str, timeout: int = 60) -> None:
        self.allowed = allowed
        self.default_cwd = default_cwd
        self.default_timeout = timeout

    async def run(
        self,
        *,
        command: str,
        cwd: str | None = None,
        timeout: int | None = None,
        **_: Any,
    ) -> ToolResult:
        try:
            tokens = shlex.split(command)
        except ValueError as exc:
            return ToolResult(ok=False, error=f"unparseable command: {exc}")
        if not tokens:
            return ToolResult(ok=False, error="empty command")
        head = tokens[0]
        if head not in self.allowed:
            return ToolResult(
                ok=False,
                error=f"command {head!r} not in allowlist. Allowed: {sorted(self.allowed)}",
            )
        timeout_s = int(timeout) if timeout else self.default_timeout
        timeout_s = max(1, min(timeout_s, 600))
        proc = await asyncio.create_subprocess_exec(
            *tokens,
            cwd=cwd or self.default_cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(ok=False, error=f"command timed out after {timeout_s}s")

        out = _decode_bounded(stdout)
        err = _decode_bounded(stderr)
        return ToolResult(
            ok=proc.returncode == 0,
            output={"stdout": out, "stderr": err, "returncode": proc.returncode},
            error=None if proc.returncode == 0 else f"exit {proc.returncode}",
        )


def _decode_bounded(data: bytes) -> str:
    if len(data) > _OUTPUT_LIMIT:
        return data[:_OUTPUT_LIMIT].decode("utf-8", errors="replace") + f"\n... [truncated {len(data) - _OUTPUT_LIMIT} bytes]"
    return data.decode("utf-8", errors="replace")
