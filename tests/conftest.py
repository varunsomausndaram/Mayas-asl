"""Shared pytest fixtures.

Every test gets its own temporary data directory and an isolated
:class:`Settings`, so test runs never touch your real profile, audit log,
or scheduled jobs.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from jarvis.config import Settings
from jarvis.core.factory import build_runtime


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    """A Settings object rooted at a tmp dir and using the echo LLM."""
    os.environ["JARVIS_API_KEY"] = "test-key-123"
    return Settings(
        JARVIS_API_KEY="test-key-123",
        JARVIS_DATA_DIR=str(tmp_path / "var"),
        JARVIS_LLM_PROVIDER="echo",
        JARVIS_LLM_FALLBACK=None,
        JARVIS_VOICE_ENABLED=False,
        JARVIS_ALLOWED_TOOLS="*",
        CLAUDE_CODE_WORKSPACES=str(tmp_path / "workspaces"),
    )


@pytest.fixture
async def runtime(tmp_settings: Settings):
    rt = await build_runtime(tmp_settings)
    await rt.start()
    try:
        yield rt
    finally:
        await rt.stop()
