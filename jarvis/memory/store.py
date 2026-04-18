"""SQLite-backed persistent memory for sessions and messages.

The store is intentionally small. Sessions and messages are the only
first-class entities; everything else (metadata, tool outputs, etc.) is
stored as JSON in the ``meta`` column so the schema never needs to migrate
when we add a new field to a model.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from pathlib import Path

import aiosqlite

from jarvis.memory.models import Message, Session

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created REAL NOT NULL,
    updated REAL NOT NULL,
    meta TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls TEXT,
    tool_call_id TEXT,
    name TEXT,
    ts REAL NOT NULL,
    meta TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_messages_session_ts
    ON messages(session_id, ts);

CREATE INDEX IF NOT EXISTS idx_sessions_updated
    ON sessions(updated DESC);
"""


class MemoryStore:
    """Async SQLite wrapper with a minimal, typed API."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialised = False

    async def init(self) -> None:
        """Create tables if they don't exist."""
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()
        self._initialised = True

    async def _ensure_init(self) -> None:
        if not self._initialised:
            await self.init()

    # ------------------------------------------------------------- sessions
    async def create_session(self, title: str = "New session", meta: dict | None = None) -> Session:
        session = Session(title=title, meta=meta or {})
        await self._ensure_init()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute(
                "INSERT INTO sessions(id, title, created, updated, meta) VALUES (?,?,?,?,?)",
                (session.id, session.title, session.created, session.updated, json.dumps(session.meta)),
            )
            await db.commit()
        return session

    async def get_session(self, session_id: str) -> Session | None:
        await self._ensure_init()
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, title, created, updated, meta FROM sessions WHERE id = ?",
                (session_id,),
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return None
        return Session(
            id=row["id"],
            title=row["title"],
            created=row["created"],
            updated=row["updated"],
            meta=json.loads(row["meta"] or "{}"),
        )

    async def list_sessions(self, limit: int = 50) -> list[Session]:
        await self._ensure_init()
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, title, created, updated, meta FROM sessions "
                "ORDER BY updated DESC LIMIT ?",
                (limit,),
            ) as cur:
                rows = await cur.fetchall()
        return [
            Session(
                id=r["id"],
                title=r["title"],
                created=r["created"],
                updated=r["updated"],
                meta=json.loads(r["meta"] or "{}"),
            )
            for r in rows
        ]

    async def delete_session(self, session_id: str) -> bool:
        await self._ensure_init()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            cur = await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            await db.commit()
            return cur.rowcount > 0

    async def rename_session(self, session_id: str, title: str) -> None:
        await self._ensure_init()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE sessions SET title = ?, updated = ? WHERE id = ?",
                (title, time.time(), session_id),
            )
            await db.commit()

    # ------------------------------------------------------------- messages
    async def add_message(self, message: Message) -> Message:
        await self._ensure_init()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute(
                "INSERT INTO messages(id, session_id, role, content, tool_calls, tool_call_id, name, ts, meta) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    message.id,
                    message.session_id,
                    message.role,
                    message.content,
                    json.dumps(message.tool_calls) if message.tool_calls else None,
                    message.tool_call_id,
                    message.name,
                    message.ts,
                    json.dumps(message.meta),
                ),
            )
            await db.execute(
                "UPDATE sessions SET updated = ? WHERE id = ?",
                (message.ts, message.session_id),
            )
            await db.commit()
        return message

    async def add_messages(self, messages: Iterable[Message]) -> None:
        msgs = list(messages)
        if not msgs:
            return
        await self._ensure_init()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.executemany(
                "INSERT INTO messages(id, session_id, role, content, tool_calls, tool_call_id, name, ts, meta) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    (
                        m.id,
                        m.session_id,
                        m.role,
                        m.content,
                        json.dumps(m.tool_calls) if m.tool_calls else None,
                        m.tool_call_id,
                        m.name,
                        m.ts,
                        json.dumps(m.meta),
                    )
                    for m in msgs
                ],
            )
            last_ts = max(m.ts for m in msgs)
            await db.execute(
                "UPDATE sessions SET updated = ? WHERE id = ?",
                (last_ts, msgs[0].session_id),
            )
            await db.commit()

    async def list_messages(self, session_id: str, limit: int = 200) -> list[Message]:
        await self._ensure_init()
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, session_id, role, content, tool_calls, tool_call_id, name, ts, meta "
                "FROM messages WHERE session_id = ? ORDER BY ts ASC LIMIT ?",
                (session_id, limit),
            ) as cur:
                rows = await cur.fetchall()
        return [
            Message(
                id=r["id"],
                session_id=r["session_id"],
                role=r["role"],
                content=r["content"],
                tool_calls=json.loads(r["tool_calls"]) if r["tool_calls"] else None,
                tool_call_id=r["tool_call_id"],
                name=r["name"],
                ts=r["ts"],
                meta=json.loads(r["meta"] or "{}"),
            )
            for r in rows
        ]

    async def recent_chat_dicts(self, session_id: str, limit: int = 40) -> list[dict]:
        msgs = await self.list_messages(session_id, limit=limit)
        return [m.to_chat_dict() for m in msgs]
