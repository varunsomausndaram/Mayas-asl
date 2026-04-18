"""Permission broker — risk assessment and human-in-the-loop approval.

Every tool invocation is classified into one of four risk levels. Low-risk
calls run without interruption. Anything above ``Risk.LOW`` goes through an
approval step: Jarvis asks the user, the user may approve once, approve for
the session, or deny. Denials carry a reason that the model can incorporate
into its next turn — "sir, I'm not comfortable with that yet, let me try
another way."

The broker also supports preauthorisation: the user can grant standing
consent for specific tools or ``(tool, arg-fingerprint)`` pairs via the CLI
or UI so their workflow isn't paused for every repeat action.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def at_least(self, other: RiskLevel) -> bool:
        order = [RiskLevel.NONE, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        return order.index(self) >= order.index(other)


@dataclass
class Risk:
    """A single risk dimension with a human explanation."""

    level: RiskLevel
    reason: str


@dataclass
class RiskAssessment:
    """Collected risks for a pending action plus the overall verdict."""

    tool: str
    arguments: dict[str, Any]
    risks: list[Risk] = field(default_factory=list)
    overall: RiskLevel = RiskLevel.NONE
    rationale: str = ""
    destructive: bool = False
    reversible: bool = True
    touches_network: bool = False
    touches_filesystem: bool = False
    touches_secrets: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "arguments": self.arguments,
            "risks": [{"level": r.level.value, "reason": r.reason} for r in self.risks],
            "overall": self.overall.value,
            "rationale": self.rationale,
            "destructive": self.destructive,
            "reversible": self.reversible,
            "touches_network": self.touches_network,
            "touches_filesystem": self.touches_filesystem,
            "touches_secrets": self.touches_secrets,
        }


class ApprovalDecision(str, Enum):
    APPROVED_ONCE = "approved_once"
    APPROVED_SESSION = "approved_session"
    APPROVED_ALWAYS = "approved_always"
    DENIED = "denied"


# --------------------------------------------------------------------- rules
# Static rules map each tool to a base risk level, a list of fingerprint
# generators (derive a stable key from arguments) and attribute flags.
_DEFAULT_RULES: dict[str, dict[str, Any]] = {
    "filesystem_read": {"base": RiskLevel.LOW, "fs": True},
    "filesystem_list": {"base": RiskLevel.LOW, "fs": True},
    "filesystem_write": {"base": RiskLevel.MEDIUM, "fs": True, "destructive": True},
    "web_search": {"base": RiskLevel.LOW, "network": True},
    "web_fetch": {"base": RiskLevel.LOW, "network": True},
    "github_list_repos": {"base": RiskLevel.LOW, "network": True},
    "github_get_file": {"base": RiskLevel.LOW, "network": True},
    "github_search": {"base": RiskLevel.LOW, "network": True},
    "github_create_issue": {"base": RiskLevel.MEDIUM, "network": True, "destructive": True},
    "system_info": {"base": RiskLevel.NONE},
    "notify": {"base": RiskLevel.NONE},
    "shell_exec": {
        "base": RiskLevel.HIGH,
        "fs": True,
        "destructive": True,
        "reversible": False,
    },
    "claude_code_dispatch": {
        "base": RiskLevel.HIGH,
        "fs": True,
        "network": True,
        "destructive": True,
        "reversible": False,
    },
}


def assess(tool: str, arguments: dict[str, Any]) -> RiskAssessment:
    """Produce a :class:`RiskAssessment` for ``tool(arguments)``."""
    rule = _DEFAULT_RULES.get(tool, {"base": RiskLevel.MEDIUM})
    base = rule["base"]
    risks: list[Risk] = []

    # ------------- generic content scan
    if rule.get("destructive"):
        risks.append(Risk(RiskLevel.MEDIUM, "action may create or modify state"))
    if not rule.get("reversible", True):
        risks.append(Risk(RiskLevel.HIGH, "operation is not easily reversible"))
    if rule.get("network"):
        risks.append(Risk(RiskLevel.LOW, "requires network egress"))

    # ------------- tool-specific heuristics
    if tool == "filesystem_write":
        path = str(arguments.get("path", ""))
        if path.startswith(("/etc", "/var", "/usr", "/System", "/Library")) or ".." in path:
            risks.append(Risk(RiskLevel.HIGH, f"writes outside workspace: {path}"))
            base = RiskLevel.HIGH

    if tool == "shell_exec":
        cmd = str(arguments.get("command", ""))
        lowered = cmd.lower()
        if any(pat in lowered for pat in [" rm -rf", "mkfs", "dd if=", ":(){", "sudo ", "curl | sh", "wget | sh"]):
            risks.append(Risk(RiskLevel.CRITICAL, "command contains a destructive or untrusted pattern"))
            base = RiskLevel.CRITICAL

    if tool == "claude_code_dispatch":
        prompt = str(arguments.get("prompt", ""))
        if any(w in prompt.lower() for w in ["delete", "drop database", "force push", "rm -rf"]):
            risks.append(Risk(RiskLevel.HIGH, "dispatch prompt suggests destructive intent"))
            base = RiskLevel.HIGH

    if tool == "github_create_issue":
        repo = str(arguments.get("repo", ""))
        if "/" not in repo:
            risks.append(Risk(RiskLevel.MEDIUM, f"ambiguous repo reference: {repo!r}"))

    # ------------- roll-up
    overall = base
    for r in risks:
        if r.level.at_least(overall):
            overall = r.level

    rationale = " | ".join(r.reason for r in risks) or f"baseline: {base.value}"
    return RiskAssessment(
        tool=tool,
        arguments=arguments,
        risks=risks,
        overall=overall,
        rationale=rationale,
        destructive=bool(rule.get("destructive")),
        reversible=bool(rule.get("reversible", True)),
        touches_network=bool(rule.get("network")),
        touches_filesystem=bool(rule.get("fs")),
        touches_secrets=tool.startswith("github_") or tool == "claude_code_dispatch",
    )


# -------------------------------------------------------------- broker type
ApprovalRequester = Callable[[RiskAssessment], Awaitable[ApprovalDecision]]


class PermissionBroker:
    """Gate tool calls behind a risk threshold and user approval.

    The broker is stateful: approvals granted ``APPROVED_SESSION`` last for
    the process lifetime; ``APPROVED_ALWAYS`` entries are persisted via the
    supplied ``persist_callback`` (typically the user profile store).
    """

    def __init__(
        self,
        *,
        auto_approve_below: RiskLevel = RiskLevel.MEDIUM,
        requester: ApprovalRequester | None = None,
        always_approved: set[str] | None = None,
        persist_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self.auto_approve_below = auto_approve_below
        self.requester = requester
        self._session_approvals: set[str] = set()
        self._always_approvals: set[str] = set(always_approved or set())
        self._persist = persist_callback
        self._lock = asyncio.Lock()
        self._audit: list[dict[str, Any]] = []

    # -------------------------------------------------- public gate API
    async def authorize(self, assessment: RiskAssessment) -> tuple[bool, str]:
        """Return ``(approved, reason)``."""
        fp = self._fingerprint(assessment.tool, assessment.arguments)

        if assessment.overall.at_least(RiskLevel.CRITICAL):
            # Critical always requires interactive approval — never auto.
            pass
        elif fp in self._always_approvals or assessment.tool in self._always_approvals:
            self._record(assessment, "always", approved=True)
            return True, "pre-authorised (always)"
        elif fp in self._session_approvals or assessment.tool in self._session_approvals:
            self._record(assessment, "session", approved=True)
            return True, "pre-authorised (session)"
        elif not assessment.overall.at_least(self.auto_approve_below):
            self._record(assessment, "auto", approved=True)
            return True, "below approval threshold"

        if self.requester is None:
            self._record(assessment, "no-requester", approved=False)
            return False, f"approval required (risk={assessment.overall.value}) but no approval handler available"

        async with self._lock:
            decision = await self.requester(assessment)

        if decision == ApprovalDecision.APPROVED_ONCE:
            self._record(assessment, "once", approved=True)
            return True, "approved once"
        if decision == ApprovalDecision.APPROVED_SESSION:
            self._session_approvals.add(fp)
            self._record(assessment, "session", approved=True)
            return True, "approved for session"
        if decision == ApprovalDecision.APPROVED_ALWAYS:
            self._always_approvals.add(fp)
            if self._persist is not None:
                await self._persist(fp)
            self._record(assessment, "always", approved=True)
            return True, "approved always"
        self._record(assessment, "denied", approved=False)
        return False, "user denied"

    # ------------------------------------------------- lifecycle helpers
    def revoke(self, fingerprint: str) -> None:
        self._always_approvals.discard(fingerprint)
        self._session_approvals.discard(fingerprint)

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit)

    @staticmethod
    def _fingerprint(tool: str, arguments: dict[str, Any]) -> str:
        blob = json.dumps({"t": tool, "a": _canonical(arguments)}, sort_keys=True).encode("utf-8")
        return f"{tool}:{hashlib.sha256(blob).hexdigest()[:16]}"

    def _record(self, a: RiskAssessment, source: str, *, approved: bool) -> None:
        self._audit.append(
            {
                "ts": time.time(),
                "tool": a.tool,
                "risk": a.overall.value,
                "source": source,
                "approved": approved,
            }
        )
        if len(self._audit) > 2000:
            self._audit = self._audit[-2000:]


def _canonical(v: Any) -> Any:
    """Deterministic JSON for fingerprints — ignore ordering, trim long strings."""
    if isinstance(v, dict):
        return {k: _canonical(v[k]) for k in sorted(v)}
    if isinstance(v, list):
        return [_canonical(x) for x in v]
    if isinstance(v, str) and len(v) > 200:
        return v[:200] + "..."
    return v
