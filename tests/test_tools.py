from pathlib import Path

import pytest

from jarvis.tools.base import ToolRegistry
from jarvis.tools.filesystem import FilesystemListTool, FilesystemReadTool, FilesystemWriteTool
from jarvis.tools.shell import ShellExecTool
from jarvis.tools.system import SystemInfoTool


@pytest.mark.asyncio
async def test_filesystem_roundtrip(tmp_path: Path):
    reg = ToolRegistry({"*"})
    reg.register(FilesystemWriteTool(tmp_path))
    reg.register(FilesystemReadTool(tmp_path))
    reg.register(FilesystemListTool(tmp_path))

    write = await reg.run("filesystem_write", {"path": "a/b.txt", "content": "hello"})
    assert write.ok

    read = await reg.run("filesystem_read", {"path": "a/b.txt"})
    assert read.ok
    assert read.output["content"] == "hello"

    listing = await reg.run("filesystem_list", {"path": ".", "depth": 2})
    assert listing.ok
    paths = {e["path"] for e in listing.output["entries"]}
    assert "a/b.txt" in paths


@pytest.mark.asyncio
async def test_filesystem_traversal_blocked(tmp_path: Path):
    reg = ToolRegistry({"*"})
    reg.register(FilesystemWriteTool(tmp_path))
    result = await reg.run("filesystem_write", {"path": "../escape.txt", "content": "x"})
    assert not result.ok
    assert "escape" in result.error.lower() or "path" in result.error.lower()


@pytest.mark.asyncio
async def test_allowlist_enforced(tmp_path: Path):
    reg = ToolRegistry({"filesystem_read"})
    reg.register(FilesystemWriteTool(tmp_path))
    reg.register(FilesystemReadTool(tmp_path))
    # write is registered but not allowed
    result = await reg.run("filesystem_write", {"path": "x.txt", "content": "x"})
    assert not result.ok
    assert "allowlist" in (result.error or "")


@pytest.mark.asyncio
async def test_shell_allowlist(tmp_path: Path):
    reg = ToolRegistry({"*"})
    reg.register(ShellExecTool({"echo"}, str(tmp_path), timeout=5))
    ok = await reg.run("shell_exec", {"command": "echo hi"})
    assert ok.ok
    assert "hi" in ok.output["stdout"]
    blocked = await reg.run("shell_exec", {"command": "rm -rf /"})
    assert not blocked.ok


@pytest.mark.asyncio
async def test_system_info():
    reg = ToolRegistry({"*"})
    reg.register(SystemInfoTool())
    r = await reg.run("system_info", {})
    assert r.ok
    assert "hostname" in r.output
    assert "memory" in r.output
