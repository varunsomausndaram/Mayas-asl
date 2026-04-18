"""Build the default tool registry from :class:`Settings`.

The registry returned here is a plain :class:`ToolRegistry` — gating by
permission happens one layer up in the orchestrator. That separation keeps
the tool layer unaware of approval state, which is easier to test and
easier to reason about.
"""

from __future__ import annotations

from pathlib import Path

from jarvis.config import Settings
from jarvis.dispatch.claude_code import ClaudeCodeDispatcher, ClaudeCodeDispatchTool
from jarvis.events import EventBus
from jarvis.scheduler.engine import Scheduler
from jarvis.tools.base import Tool, ToolRegistry
from jarvis.tools.filesystem import FilesystemListTool, FilesystemReadTool, FilesystemWriteTool
from jarvis.tools.github import (
    GitHubCreateIssueTool,
    GitHubGetFileTool,
    GitHubListReposTool,
    GitHubSearchTool,
)
from jarvis.tools.news import NewsHeadlinesTool, WeatherCurrentTool, WeatherForecastTool
from jarvis.tools.reminders import (
    CancelReminderTool,
    ListRemindersTool,
    ScheduleRecurringTool,
    SetReminderTool,
    SetTimerTool,
)
from jarvis.tools.shell import ShellExecTool
from jarvis.tools.system import NotifyTool, SystemInfoTool
from jarvis.tools.web import WebFetchTool, WebSearchTool


def build_registry(
    settings: Settings,
    *,
    scheduler: Scheduler | None = None,
    dispatcher: ClaudeCodeDispatcher | None = None,
    bus: EventBus | None = None,
    workspace: Path | None = None,
) -> tuple[ToolRegistry, ClaudeCodeDispatcher, Scheduler]:
    """Wire up every built-in tool.

    The scheduler is returned alongside the registry so the server can expose
    REST endpoints for jobs without re-reading settings.
    """
    registry = ToolRegistry(allowed=_expanded_allowlist(settings.allowed_tool_set()))

    ws = workspace or settings.data_dir / "workspace"
    ws.mkdir(parents=True, exist_ok=True)

    # ---- filesystem
    registry.register(FilesystemReadTool(ws))
    registry.register(FilesystemWriteTool(ws))
    registry.register(FilesystemListTool(ws))

    # ---- system
    registry.register(SystemInfoTool())
    registry.register(NotifyTool())

    # ---- web
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())

    # ---- smart-assistant
    registry.register(NewsHeadlinesTool())
    registry.register(WeatherCurrentTool())
    registry.register(WeatherForecastTool())

    # ---- github (only if a token is present)
    if settings.github_token:
        registry.register(GitHubListReposTool(settings.github_token, settings.github_default_owner))
        registry.register(GitHubGetFileTool(settings.github_token))
        registry.register(GitHubCreateIssueTool(settings.github_token))
        registry.register(GitHubSearchTool(settings.github_token))

    # ---- shell (guarded)
    if settings.shell_enabled:
        registry.register(
            ShellExecTool(
                allowed=settings.shell_allowed(),
                default_cwd=str(ws),
                timeout=settings.shell_timeout,
            )
        )

    # ---- scheduler
    sched = scheduler or Scheduler(settings.data_dir / "scheduler.sqlite3")
    registry.register(SetReminderTool(sched))
    registry.register(SetTimerTool(sched))
    registry.register(ScheduleRecurringTool(sched))
    registry.register(ListRemindersTool(sched))
    registry.register(CancelReminderTool(sched))

    # ---- claude code dispatcher
    disp = dispatcher or ClaudeCodeDispatcher(
        cli=settings.claude_code_cli,
        workspaces_root=settings.claude_code_workspaces,
        timeout=settings.claude_code_timeout,
        bus=bus,
    )
    registry.register(_ToolAdapter(ClaudeCodeDispatchTool(disp)))

    return registry, disp, sched


def _expanded_allowlist(allowed: set[str]) -> set[str]:
    """Add a sensible default set of smart-assistant tools to the allowlist.

    Users configuring ``JARVIS_ALLOWED_TOOLS`` explicitly still take
    precedence; this only kicks in when the default string is used so the
    new tools are usable out of the box.
    """
    if "*" in allowed:
        return allowed
    extras = {
        "news_headlines",
        "weather_current",
        "weather_forecast",
        "set_reminder",
        "set_timer",
        "schedule_recurring",
        "list_reminders",
        "cancel_reminder",
        "filesystem_list",
    }
    return allowed | extras


class _ToolAdapter(Tool):
    """Adapt a duck-typed tool (e.g. :class:`ClaudeCodeDispatchTool`) to :class:`Tool`."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.name = inner.name
        self.description = inner.description
        self.parameters = inner.parameters

    def schema(self):
        return self.inner.schema()

    async def run(self, **kwargs):
        return await self.inner.run(**kwargs)
