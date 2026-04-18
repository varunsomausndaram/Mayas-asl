"""Tool system.

Tools are the mechanism through which the model performs side effects —
running shell commands, reading files, talking to GitHub, and dispatching
Claude Code sessions. Use :func:`build_registry` to get a fully populated
registry wired against the current :class:`jarvis.config.Settings`.
"""

from jarvis.tools.base import Tool, ToolRegistry, ToolResult
from jarvis.tools.registry import build_registry

__all__ = ["Tool", "ToolRegistry", "ToolResult", "build_registry"]
