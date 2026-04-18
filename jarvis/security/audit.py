"""Persistent audit log for tool calls, approvals, and dispatches.

Every sensitive event writes a record here. The log is append-only by
convention, though nothing stops an operator from pruning it. It's the
first thing to check if Jarvis did something unexpected.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    actor TEXT NOT NULL,
    subject TEXT NOT NULL,
    action TEXT NOT NULL,
    result TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_kind_ts ON audit_log(kind, ts DESC);
"""


@dataclass
class AuditRecord:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    ts: float = field(default_factory=time.time)
    kind: str = ""      # tool_call | approval | dispatch | auth | config
    actor: str = ""     # "llm" | "user" | "system"
    subject: str = ""   # tool name, job id, endpoint
    action: str = ""    # what was attempted
    result: str = ""    # ok | denied | failed
    details: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts,
            "kind": self.kind,
            "actor": self.actor,
            "subject": self.subject,
            "action": self.action,
            "result": self.result,
            "details": self.details,
        }


class AuditLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialised = False

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()
        self._initialised = True

    async def record(self, record: AuditRecord) -> None:
        if not self._initialised:
            await self.init()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO audit_log(id, ts, kind, actor, subject, action, result, details) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    record.id,
                    record.ts,
                    record.kind,
                    record.actor,
                    record.subject,
                    record.action,
                    record.result,
                    json.dumps(record.details),
                ),
            )
            await db.commit()

    async def recent(self, *, kind: str | None = None, limit: int = 100) -> list[AuditRecord]:
        if not self._initialised:
            await self.init()
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            if kind:
                query = (
                    "SELECT * FROM audit_log WHERE kind = ? ORDER BY ts DESC LIMIT ?"
                )
                params: tuple[Any, ...] = (kind, limit)
            else:
                query = "SELECT * FROM audit_log ORDER BY ts DESC LIMIT ?"
                params = (limit,)
            async with db.execute(query, params) as cur:
                rows = await cur.fetchall()
        return [
            AuditRecord(
                id=r["id"],
                ts=r["ts"],
                kind=r["kind"],
                actor=r["actor"],
                subject=r["subject"],
                action=r["action"],
                result=r["result"],
                details=json.loads(r["details"] or "{}"),
            )
            for r in rows
        ]
