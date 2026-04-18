import asyncio

import pytest

from jarvis.security.egress import EgressPolicy, assert_allowed
from jarvis.security.ratelimit import RateLimiter


def test_default_policy_allows_known():
    policy = EgressPolicy()
    ok, _ = policy.check("https://api.anthropic.com/v1/messages")
    assert ok
    ok, _ = policy.check("https://api.github.com/user/repos")
    assert ok


def test_default_policy_blocks_unknown():
    policy = EgressPolicy()
    ok, reason = policy.check("https://evil.example.com/p")
    assert not ok
    assert "allowlist" in reason


def test_suffix_allowlist():
    policy = EgressPolicy()
    policy.add_suffix("ok-corp.com")
    assert policy.check("https://api.ok-corp.com/x")[0]
    assert policy.check("https://www.ok-corp.com/x")[0]
    assert not policy.check("https://evil.com/x")[0]


def test_ip_blocks():
    policy = EgressPolicy(block_loopback=True)
    assert not policy.check("http://127.0.0.1:8080")[0]
    assert not policy.check("http://192.168.0.1")[0]


def test_assert_allowed_raises():
    policy = EgressPolicy()
    with pytest.raises(PermissionError):
        assert_allowed("https://evil.example.com", policy)


@pytest.mark.asyncio
async def test_ratelimit():
    rl = RateLimiter(rate_per_s=5, burst=2)
    assert await rl.acquire("k") is True
    assert await rl.acquire("k") is True
    assert await rl.acquire("k") is False
    await asyncio.sleep(0.25)
    assert await rl.acquire("k") is True
