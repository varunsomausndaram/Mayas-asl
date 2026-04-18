import asyncio
import stat
from pathlib import Path
from textwrap import dedent

import pytest

from jarvis.dispatch.claude_code import ClaudeCodeDispatcher, JobState
from jarvis.events import EventBus


@pytest.fixture
def fake_claude(tmp_path: Path) -> str:
    """Create a fake claude CLI that prints its args and exits."""
    path = tmp_path / "fake-claude"
    path.write_text(
        dedent(
            """#!/usr/bin/env bash
            echo "args: $*"
            echo "running in $PWD"
            exit 0
            """
        ),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


@pytest.mark.asyncio
async def test_dispatcher_runs_fake_cli(tmp_path: Path, fake_claude: str):
    bus = EventBus()
    disp = ClaudeCodeDispatcher(
        cli=fake_claude,
        workspaces_root=tmp_path / "ws",
        timeout=15,
        bus=bus,
    )
    job = await disp.dispatch("hello world")
    # Wait for completion
    for _ in range(100):
        await asyncio.sleep(0.05)
        if job.state in {JobState.SUCCEEDED, JobState.FAILED}:
            break
    assert job.state == JobState.SUCCEEDED
    assert job.returncode == 0
    assert any("args:" in line for line in job.stdout)


@pytest.mark.asyncio
async def test_dispatcher_missing_cli(tmp_path: Path):
    disp = ClaudeCodeDispatcher(
        cli="/nope/definitely/not/a/binary",
        workspaces_root=tmp_path / "ws",
        timeout=5,
        bus=EventBus(),
    )
    job = await disp.dispatch("x")
    for _ in range(50):
        await asyncio.sleep(0.05)
        if job.state == JobState.FAILED:
            break
    assert job.state == JobState.FAILED
    assert any("not found" in line.lower() for line in job.stderr)
