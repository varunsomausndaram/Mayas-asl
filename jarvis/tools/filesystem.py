"""Filesystem tools — read and write text files under a configured root.

All paths are resolved against the configured data directory (or a caller-
supplied workspace) and then validated to ensure they do not escape it via
symlinks or ``..`` traversal. Binary files are refused; the tool is for
source code, config, notes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aiofiles

from jarvis.tools.base import Tool, ToolResult

_MAX_READ_BYTES = 512_000


def _safe_resolve(root: Path, rel: str) -> Path:
    """Resolve ``rel`` under ``root`` and reject traversal."""
    root = root.resolve()
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes root: {rel!r}") from exc
    return candidate


class FilesystemReadTool(Tool):
    name = "filesystem_read"
    description = "Read a UTF-8 text file from the workspace. Paths are sandboxed to the workspace root."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to workspace root."},
            "max_bytes": {
                "type": "integer",
                "minimum": 1,
                "maximum": _MAX_READ_BYTES,
                "default": _MAX_READ_BYTES,
            },
        },
        "required": ["path"],
    }

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def run(self, *, path: str, max_bytes: int = _MAX_READ_BYTES, **_: Any) -> ToolResult:
        try:
            resolved = _safe_resolve(self.root, path)
        except ValueError as exc:
            return ToolResult(ok=False, error=str(exc))
        if not resolved.exists():
            return ToolResult(ok=False, error=f"not found: {path}")
        if not resolved.is_file():
            return ToolResult(ok=False, error=f"not a file: {path}")
        max_bytes = max(1, min(int(max_bytes), _MAX_READ_BYTES))
        async with aiofiles.open(resolved, "rb") as f:
            data = await f.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        if truncated:
            data = data[:max_bytes]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return ToolResult(ok=False, error="file is not UTF-8 text")
        return ToolResult(
            ok=True,
            output={"path": path, "content": text, "truncated": truncated, "bytes": len(data)},
        )


class FilesystemWriteTool(Tool):
    name = "filesystem_write"
    description = "Create or overwrite a UTF-8 text file under the workspace root."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "append": {"type": "boolean", "default": False},
        },
        "required": ["path", "content"],
    }

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def run(self, *, path: str, content: str, append: bool = False, **_: Any) -> ToolResult:
        try:
            resolved = _safe_resolve(self.root, path)
        except ValueError as exc:
            return ToolResult(ok=False, error=str(exc))
        resolved.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        async with aiofiles.open(resolved, mode, encoding="utf-8") as f:
            await f.write(content)
        return ToolResult(
            ok=True,
            output={"path": path, "bytes_written": len(content.encode("utf-8")), "appended": append},
        )


class FilesystemListTool(Tool):
    name = "filesystem_list"
    description = "List files and directories under a workspace-relative path."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": "."},
            "depth": {"type": "integer", "minimum": 1, "maximum": 4, "default": 1},
        },
    }

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def run(self, *, path: str = ".", depth: int = 1, **_: Any) -> ToolResult:
        try:
            resolved = _safe_resolve(self.root, path)
        except ValueError as exc:
            return ToolResult(ok=False, error=str(exc))
        if not resolved.exists():
            return ToolResult(ok=False, error=f"not found: {path}")
        if not resolved.is_dir():
            return ToolResult(ok=False, error=f"not a directory: {path}")
        depth = max(1, min(int(depth), 4))
        entries: list[dict[str, Any]] = []

        def walk(p: Path, d: int) -> None:
            if d <= 0:
                return
            for child in sorted(p.iterdir()):
                rel = child.relative_to(self.root).as_posix()
                entry = {
                    "path": rel,
                    "type": "dir" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.is_file() else None,
                }
                entries.append(entry)
                if child.is_dir() and d > 1:
                    walk(child, d - 1)

        walk(resolved, depth)
        return ToolResult(ok=True, output={"root": path, "entries": entries})
