"""Token-bucket rate limiter used by the server and tool registry.

The implementation is intentionally in-process. For a single-user assistant
this is enough; if you later deploy Jarvis as a shared service, swap in
Redis via the same interface.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    capacity: float
    tokens: float
    refill_per_s: float
    last: float


class RateLimiter:
    """A simple per-key token bucket."""

    def __init__(self, rate_per_s: float = 2.0, burst: int = 10) -> None:
        self.rate = float(rate_per_s)
        self.burst = float(burst)
        self._buckets: dict[str, _Bucket] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str = "global", cost: float = 1.0) -> bool:
        """Return ``True`` if ``cost`` tokens were available for ``key``."""
        async with self._lock:
            now = time.monotonic()
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(self.burst, self.burst, self.rate, now)
                self._buckets[key] = bucket
            elapsed = now - bucket.last
            bucket.tokens = min(bucket.capacity, bucket.tokens + elapsed * bucket.refill_per_s)
            bucket.last = now
            if bucket.tokens >= cost:
                bucket.tokens -= cost
                return True
            return False

    async def wait(self, key: str = "global", cost: float = 1.0, *, max_wait: float = 30.0) -> bool:
        """Block up to ``max_wait`` seconds waiting for ``cost`` tokens."""
        deadline = time.monotonic() + max_wait
        while True:
            if await self.acquire(key, cost):
                return True
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(0.1)
