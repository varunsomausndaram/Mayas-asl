"""System inspection and desktop notification tools."""

from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import sys
from typing import Any

import psutil

from jarvis.tools.base import Tool, ToolResult


class SystemInfoTool(Tool):
    name = "system_info"
    description = "Return a read-only summary of the host: OS, CPU, memory, uptime, IPs."
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    async def run(self, **_: Any) -> ToolResult:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(os.getcwd())
        try:
            ips = socket.gethostbyname_ex(socket.gethostname())[2]
        except socket.gaierror:
            ips = []
        info = {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version,
            "cpu_count": psutil.cpu_count(logical=True),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory": {
                "total": mem.total,
                "available": mem.available,
                "percent": mem.percent,
            },
            "disk_cwd": {
                "total": disk.total,
                "free": disk.free,
                "percent": disk.percent,
            },
            "boot_time": psutil.boot_time(),
            "ips": ips,
            "cwd": os.getcwd(),
        }
        return ToolResult(ok=True, output=info)


class NotifyTool(Tool):
    name = "notify"
    description = "Post a desktop notification (best-effort across macOS, Linux, Windows)."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "message": {"type": "string"},
        },
        "required": ["title", "message"],
    }

    async def run(self, *, title: str, message: str, **_: Any) -> ToolResult:
        delivered = _deliver_notification(title, message)
        return ToolResult(ok=True, output={"delivered": delivered, "title": title, "message": message})


def _deliver_notification(title: str, message: str) -> bool:
    """Dispatch to the platform's notification system. Always returns cleanly."""
    system = platform.system()
    try:
        if system == "Darwin" and shutil.which("osascript"):
            safe_title = title.replace('"', '\\"')
            safe_msg = message.replace('"', '\\"')
            subprocess.run(
                ["osascript", "-e", f'display notification "{safe_msg}" with title "{safe_title}"'],
                check=False,
                timeout=5,
            )
            return True
        if system == "Linux" and shutil.which("notify-send"):
            subprocess.run(["notify-send", title, message], check=False, timeout=5)
            return True
        if system == "Windows":
            # PowerShell toast — best-effort, Windows 10+.
            if shutil.which("powershell"):
                ps = (
                    "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                    "ContentType = WindowsRuntime] > $null;"
                )
                subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False, timeout=5)
                return True
    except (subprocess.TimeoutExpired, OSError):
        return False
    return False
