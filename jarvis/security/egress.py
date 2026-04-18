"""Outbound network allowlist.

Jarvis' tools talk to the outside world. We pass every outbound URL through
:meth:`EgressPolicy.check` so the operator can lock the assistant down to a
specific set of hosts if they want. The default policy allows the public
endpoints Jarvis' built-in tools need (news RSS, weather, DuckDuckGo,
GitHub, Anthropic, OpenAI, Ollama localhost) and blocks everything else.

This is a safety net, not a sandbox — if you need stronger guarantees, run
Jarvis inside a container with an egress firewall.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import urlparse

DEFAULT_HOSTS: set[str] = {
    "api.anthropic.com",
    "api.openai.com",
    "api.github.com",
    "api.open-meteo.com",
    "geocoding-api.open-meteo.com",
    "news.google.com",
    "duckduckgo.com",
    "html.duckduckgo.com",
    "raw.githubusercontent.com",
    "localhost",
    "127.0.0.1",
    "::1",
}


@dataclass
class EgressPolicy:
    """Allowlist policy. ``allow_any`` disables all checks (not recommended)."""

    allow_hosts: set[str] = field(default_factory=lambda: set(DEFAULT_HOSTS))
    allow_suffixes: set[str] = field(default_factory=set)
    allow_any: bool = False
    block_private: bool = True
    block_loopback: bool = False

    def add_host(self, host: str) -> None:
        self.allow_hosts.add(host.lower())

    def add_suffix(self, suffix: str) -> None:
        self.allow_suffixes.add(suffix.lower().lstrip("."))

    def check(self, url: str) -> tuple[bool, str]:
        """Return ``(allowed, reason)`` for ``url``."""
        if self.allow_any:
            return True, "allow_any"
        try:
            parsed = urlparse(url)
        except ValueError as exc:
            return False, f"unparseable URL: {exc}"
        if parsed.scheme not in ("http", "https"):
            return False, f"scheme not permitted: {parsed.scheme!r}"
        host = (parsed.hostname or "").lower()
        if not host:
            return False, "missing hostname"

        if self._is_blocked_ip(host):
            return False, f"blocked private / link-local address: {host}"

        if host in self.allow_hosts:
            return True, "host allowlisted"
        for suffix in self.allow_suffixes:
            if host == suffix or host.endswith("." + suffix):
                return True, f"suffix allowlisted: {suffix}"
        return False, f"host not in egress allowlist: {host}"

    def _is_blocked_ip(self, host: str) -> bool:
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            # Not an IP literal; let DNS-time firewalls handle it.
            return False
        if self.block_loopback and ip.is_loopback:
            return True
        return bool(self.block_private and (ip.is_private or ip.is_link_local or ip.is_reserved))


def assert_allowed(url: str, policy: EgressPolicy) -> None:
    """Raise :class:`PermissionError` if ``url`` is not allowed."""
    ok, reason = policy.check(url)
    if not ok:
        raise PermissionError(f"egress denied for {url!r}: {reason}")


def hostname_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def resolve_host(host: str) -> list[str]:
    """Best-effort DNS lookup. Returns an empty list on failure."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return []
    seen: list[str] = []
    for info in infos:
        addr = info[4][0]
        if addr not in seen:
            seen.append(addr)
    return seen
