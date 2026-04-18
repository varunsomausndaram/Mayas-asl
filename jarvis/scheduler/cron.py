"""A compact, dependency-free cron parser.

Supports the standard 5-field syntax: ``minute hour day month weekday``.
Each field accepts:

* ``*`` — any value.
* a number — exact match.
* ``a-b`` — inclusive range.
* ``a-b/s`` — range with step.
* ``*/s`` — every ``s`` values.
* ``a,b,c`` — explicit list.

Weekday 0 is Sunday, matching cron. Day-of-month and day-of-week are
OR-ed: if either matches, the job fires (classic cron semantics).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


class CronField:
    """One field of a cron expression, expanded to a set of allowed values."""

    __slots__ = ("values", "raw")

    def __init__(self, raw: str, min_val: int, max_val: int) -> None:
        self.raw = raw
        self.values = self._expand(raw, min_val, max_val)

    @staticmethod
    def _expand(raw: str, min_val: int, max_val: int) -> set[int]:
        values: set[int] = set()
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            step = 1
            if "/" in part:
                base, step_str = part.split("/", 1)
                step = int(step_str)
                if step <= 0:
                    raise ValueError(f"invalid step: {step_str!r}")
            else:
                base = part
            if base == "*":
                lo, hi = min_val, max_val
            elif "-" in base:
                a, b = base.split("-", 1)
                lo, hi = int(a), int(b)
            else:
                lo = hi = int(base)
            if lo < min_val or hi > max_val or lo > hi:
                raise ValueError(f"range out of bounds in {raw!r}: {lo}-{hi}")
            values.update(range(lo, hi + 1, step))
        if not values:
            raise ValueError(f"empty cron field: {raw!r}")
        return values

    def matches(self, value: int) -> bool:
        return value in self.values


@dataclass
class CronTrigger:
    """A parsed 5-field cron expression with a :meth:`next_after` helper."""

    minute: CronField
    hour: CronField
    day: CronField
    month: CronField
    weekday: CronField
    raw: str

    @classmethod
    def parse(cls, expr: str) -> CronTrigger:
        parts = expr.split()
        if len(parts) != 5:
            raise ValueError(f"cron expression must have 5 fields, got {len(parts)}: {expr!r}")
        m, h, d, mo, w = parts
        return cls(
            minute=CronField(m, 0, 59),
            hour=CronField(h, 0, 23),
            day=CronField(d, 1, 31),
            month=CronField(mo, 1, 12),
            weekday=CronField(w, 0, 6),
            raw=expr,
        )

    def matches(self, dt: datetime) -> bool:
        weekday = (dt.weekday() + 1) % 7  # cron: Sunday = 0
        day_ok = self.day.matches(dt.day)
        wday_ok = self.weekday.matches(weekday)
        # The raw field comparison (neither wildcard) activates OR semantics.
        if self.day.raw != "*" and self.weekday.raw != "*":
            dom_wday = day_ok or wday_ok
        else:
            dom_wday = day_ok and wday_ok
        return (
            self.minute.matches(dt.minute)
            and self.hour.matches(dt.hour)
            and self.month.matches(dt.month)
            and dom_wday
        )

    def next_after(self, start: datetime, *, horizon_days: int = 366) -> datetime | None:
        """Return the first minute at or after ``start`` that the trigger matches.

        Returns ``None`` if no match is found within ``horizon_days`` (which
        would indicate an unsatisfiable expression such as ``0 0 31 2 *``).
        """
        cur = (start + timedelta(seconds=60 - start.second - 1)).replace(microsecond=0)
        if start.second == 0 and start.microsecond == 0:
            cur = start
        cur = cur + timedelta(seconds=60 - cur.second) if cur.second else cur
        horizon = start + timedelta(days=horizon_days)
        while cur <= horizon:
            if self.matches(cur):
                return cur
            cur = cur + timedelta(minutes=1)
        return None


def iter_next(trigger: CronTrigger, start: datetime, count: int) -> Iterable[datetime]:
    """Yield the next ``count`` firing times after ``start``."""
    cur = start
    for _ in range(count):
        nxt = trigger.next_after(cur + timedelta(seconds=1))
        if nxt is None:
            return
        yield nxt
        cur = nxt


def utcnow() -> datetime:
    """UTC-aware current time."""
    return datetime.now(timezone.utc)
