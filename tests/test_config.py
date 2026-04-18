from pathlib import Path

import pytest

from jarvis.config import Settings


def test_settings_defaults(tmp_path: Path):
    s = Settings(JARVIS_DATA_DIR=str(tmp_path))
    assert s.port == 8765
    assert s.log_level == "INFO"
    assert "*" not in s.allowed_tool_set() or s.allowed_tool_set() == {"*"}


def test_cors_parsing():
    assert Settings(JARVIS_CORS_ORIGINS="*").cors_list() == ["*"]
    assert Settings(JARVIS_CORS_ORIGINS="https://a.com,https://b.com").cors_list() == [
        "https://a.com",
        "https://b.com",
    ]


def test_allowed_tool_set():
    s = Settings(JARVIS_ALLOWED_TOOLS="a,b,c")
    assert s.allowed_tool_set() == {"a", "b", "c"}
    s = Settings(JARVIS_ALLOWED_TOOLS="*")
    assert s.allowed_tool_set() == {"*"}


def test_log_level_validation():
    with pytest.raises(ValueError):
        Settings(JARVIS_LOG_LEVEL="NOPE")


def test_llm_provider_validation():
    with pytest.raises(ValueError):
        Settings(JARVIS_LLM_PROVIDER="mystery")


def test_shell_allowed():
    s = Settings(JARVIS_SHELL_ALLOWLIST="git,ls, echo")
    assert s.shell_allowed() == {"git", "ls", "echo"}
